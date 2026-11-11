"""Microsoft account authentication via the device-code OAuth flow.

Implements the full chain used by the official Minecraft launcher:

    Microsoft OAuth2 (device code) -> Xbox Live -> XSTS -> Minecraft Services

Tokens are cached to disk so subsequent logins don't require re-auth.
No credentials or tokens are ever logged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from ..exceptions import AuthenticationError
from .session import AuthSession

log = logging.getLogger("leafish.auth")

#: Public client ID used by Minecraft Java Edition (device-code capable).
MINECRAFT_CLIENT_ID = "00000000402b5328c11ce0d2bccecc09"
#: Alternate widely-used client id for the consumers tenant device flow.
MINECRAFT_CLIENT_ID_CONSUMERS = "00000000441cc96b"

DEVICE_CODE_URL = (
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
)
TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
SCOPE = "XboxLive.signin offline_access"

XBL_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
MC_LOGIN_URL = "https://api.minecraftservices.com/authentication/login_with_xbox"
MC_PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"
MC_ENTITLEMENTS_URL = "https://api.minecraftservices.com/entitlements/mcstore"
MC_OWNERSHIP_URL = "https://api.minecraftservices.com/entitlements/license"

XBL_RP = "http://auth.xboxlive.com"
XSTS_RP = "rp://api.minecraftservices.com/"


class MicrosoftAuth:
    """Authenticate a Microsoft account and obtain a Minecraft session."""

    def __init__(
        self,
        *,
        client_id: str = MINECRAFT_CLIENT_ID,
        cache_path: Path | None = None,
        http_client: httpx.AsyncClient | None = None,
        on_device_code: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.client_id = client_id
        self.cache_path = cache_path
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._on_device_code = on_device_code
        self._tokens: dict[str, Any] = {}
        if cache_path is not None and cache_path.exists():
            try:
                self._tokens = json.loads(cache_path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                self._tokens = {}

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # -- public API ---------------------------------------------------------

    async def authenticate(self, username: str | None = None) -> AuthSession:
        """Run the full auth flow (cached when possible)."""
        msa_token = await self._msa_access_token()
        xbl_token = await self._xbox_live_token(msa_token)
        xsts_token = await self._xsts_token(xbl_token)
        mc_token = await self._minecraft_token(xsts_token)
        profile = await self._minecraft_profile(mc_token)

        self._tokens["mc_access_token"] = mc_token
        self._tokens["mc_token_expires"] = time.time() + 86400
        self._save_cache()

        name = profile.get("name", "Steve")
        uuid_str = profile.get("id", "")
        return AuthSession(
            username=name,
            uuid=_format_minecraft_uuid(uuid_str),
            access_token=mc_token,
            profile=profile,
        )

    async def refresh(self) -> AuthSession:
        """Force a fresh authentication, ignoring cached tokens."""
        self._tokens.pop("mc_access_token", None)
        return await self.authenticate()

    # -- Microsoft OAuth ------------------------------------------------------

    async def _msa_access_token(self) -> str:
        cached = self._tokens.get("msa_access_token")
        expires = self._tokens.get("msa_expires_at", 0)
        if cached and time.time() < expires - 60:
            return cached
        if self._tokens.get("msa_refresh_token"):
            token = await self._refresh_msa_token(self._tokens["msa_refresh_token"])
            if token:
                return token
        return await self._device_code_flow()

    async def _device_code_flow(self) -> str:
        """Interactive device-code login; prints the code for the user."""
        try:
            resp = await self._client.post(
                DEVICE_CODE_URL,
                data={"client_id": self.client_id, "scope": SCOPE},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AuthenticationError(f"Device code request failed: {exc}") from exc
        if "device_code" not in data:
            raise AuthenticationError(
                f"Device code flow rejected: {data.get('error_description', data)}"
            )

        if self._on_device_code is not None:
            self._on_device_code(data)
        else:
            print("\n" + "=" * 60)
            print("Microsoft authentication required.")
            print(f"Go to: {data.get('verification_uri', data.get('verification_url'))}")
            print(f"Enter code: {data.get('user_code')}")
            print("=" * 60 + "\n")

        interval = int(data.get("interval", 5))
        deadline = time.time() + int(data.get("expires_in", 900))
        device_code = data["device_code"]

        while time.time() < deadline:
            await asyncio.sleep(interval)
            try:
                resp = await self._client.post(
                    TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "device_code": device_code,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                result = resp.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                raise AuthenticationError(f"Token poll failed: {exc}") from exc

            if "access_token" in result:
                self._store_msa_tokens(result)
                return result["access_token"]
            error = result.get("error")
            if error in ("authorization_pending", "slow_down"):
                continue
            raise AuthenticationError(
                f"Microsoft auth failed: {result.get('error_description', error)}"
            )
        raise AuthenticationError("Device code flow timed out")

    async def _refresh_msa_token(self, refresh_token: str) -> str | None:
        try:
            resp = await self._client.post(
                TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "scope": SCOPE,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            result = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None
        if "access_token" not in result:
            return None
        self._store_msa_tokens(result)
        return result["access_token"]

    def _store_msa_tokens(self, result: dict[str, Any]) -> None:
        self._tokens["msa_access_token"] = result["access_token"]
        self._tokens["msa_expires_at"] = time.time() + int(result.get("expires_in", 3600))
        if result.get("refresh_token"):
            self._tokens["msa_refresh_token"] = result["refresh_token"]
        self._save_cache()

    # -- Xbox Live -------------------------------------------------------------

    async def _xbox_live_token(self, msa_token: str) -> dict[str, str]:
        """Returns ``{"Token": ..., "uhs": ...}``."""
        try:
            resp = await self._client.post(
                XBL_AUTH_URL,
                json={
                    "Properties": {
                        "AuthMethod": "RPS",
                        "SiteName": "user.auth.xboxlive.com",
                        "RpsTicket": f"d={msa_token}",
                    },
                    "RelyingParty": XBL_RP,
                    "TokenType": "JWT",
                },
            )
            data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AuthenticationError(f"Xbox Live auth failed: {exc}") from exc
        if "Token" not in data:
            raise AuthenticationError(
                f"Xbox Live auth failed: {data.get('XErr', data)}"
            )
        uhs = data.get("DisplayClaims", {}).get("xui", [{}])[0].get("uhs", "")
        return {"Token": data["Token"], "uhs": uhs}

    async def _xsts_token(self, xbl: dict[str, str]) -> str:
        try:
            resp = await self._client.post(
                XSTS_AUTH_URL,
                json={
                    "Properties": {
                        "SandboxId": "RETAIL",
                        "UserTokens": [xbl["Token"]],
                    },
                    "RelyingParty": XSTS_RP,
                    "TokenType": "JWT",
                },
                headers={"x-xbl-contract-version": "1"},
            )
            data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AuthenticationError(f"XSTS auth failed: {exc}") from exc
        if "Token" not in data:
            raise AuthenticationError(
                f"XSTS auth failed: {data.get('XErr', data)}"
            )
        return data["Token"]

    # -- Minecraft Services -----------------------------------------------------

    async def _minecraft_token(self, xsts_token: str) -> str:
        try:
            resp = await self._client.post(
                MC_LOGIN_URL,
                json={"identityToken": f"XBL3.0 x={xsts_token}"},
            )
            data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise AuthenticationError(f"Minecraft login failed: {exc}") from exc
        token = data.get("access_token")
        if not token:
            raise AuthenticationError(
                "Minecraft login failed: no access_token in response"
            )
        return token

    async def _minecraft_profile(self, mc_token: str) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {mc_token}"}
        try:
            resp = await self._client.get(MC_PROFILE_URL, headers=headers)
            profile = resp.json()
            if resp.status_code == 404 or "id" not in profile:
                raise AuthenticationError(
                    "This Microsoft account does not own Minecraft Java Edition"
                )
            return profile
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"Profile fetch failed: {exc}") from exc

    # -- cache ------------------------------------------------------------------

    def _save_cache(self) -> None:
        if self.cache_path is None:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._tokens, indent=2), "utf-8")
        except OSError as exc:
            log.debug("Could not write token cache: %s", exc)


def _format_minecraft_uuid(minecraft_uuid: str) -> str:
    """Minecraft profile UUIDs lack dashes; reinsert them."""
    u = minecraft_uuid.replace("-", "")
    if len(u) != 32:
        return minecraft_uuid
    return f"{u[0:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:32]}"
