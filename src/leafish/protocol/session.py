"""Client session: drives the Minecraft connection state machine.

handshaking -> status (ping only) -> login -> configuration -> play

The session owns a :class:`Connection`, performs the handshake/login
negotiation (including compression and encryption when the server requires
them), answers keepalives/pings, and dispatches decoded packets to a
handler callback. Gameplay logic lives above this layer (see
``leafish.client`` / ``leafish.bot``).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ..config import BotConfig
from ..exceptions import AuthenticationError, DisconnectError
from .connection import Connection
from .protodef import ProtocolCodec

log = logging.getLogger("leafish.protocol.session")

PacketHandler = Callable[[str, str, str, dict[str, Any]], Awaitable[None] | None]
"""``(state, direction, name, params)`` async-or-sync packet handler."""


@dataclass
class SessionState:
    """Mutable negotiation state for one connection attempt."""

    connected: bool = False
    spawned: bool = False
    compression_enabled: bool = False
    encryption_enabled: bool = False
    login_success: dict[str, Any] = field(default_factory=dict)
    server_brand: str | None = None
    disconnect_reason: str | None = None


class ClientSession:
    """Runs the login handshake for one bot."""

    def __init__(
        self,
        config: BotConfig,
        codec: ProtocolCodec,
        *,
        on_packet: PacketHandler,
        on_state_change: Callable[[str], Any] | None = None,
    ) -> None:
        self.config = config
        self.codec = codec
        self._on_packet = on_packet
        self._on_state_change = on_state_change
        self.state = SessionState()
        self._handshake_done = asyncio.Event()
        self._login_done = asyncio.Event()
        self._config_done = asyncio.Event()
        self._spawn_done = asyncio.Event()
        self._disconnect_event = asyncio.Event()
        self._fatal_event = asyncio.Event()
        self.fatal_error: BaseException | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()

        self.connection = Connection(
            codec,
            config.host,
            config.port,
            state="handshaking",
            on_packet=self._dispatch,
            on_disconnect=self._handle_disconnect,
        )

    # -- public API ------------------------------------------------------------

    async def connect_and_login(
        self,
        username: str,
        player_uuid: str,
        *,
        access_token: str | None = None,
        on_device_code=None,
    ) -> SessionState:
        """Connect and drive the session through to the play state."""
        # Store credentials so the encryption handler can use them.
        self._access_token = access_token or ""
        self._player_uuid = player_uuid or ""
        await self.connection.connect(timeout=self.config.timeout)
        self.state.connected = True

        # 1. Handshake -> login
        await self.connection.send(
            "handshaking",
            "toServer",
            "set_protocol",
            {
                "protocolVersion": self.codec.protocol_version,
                "serverHost": self.config.host,
                "serverPort": self.config.port,
                "nextState": 2,
            },
        )
        self._set_connection_state("login")

        # 2. Login start — field layout varies by version (playerUUID was
        # added in 1.19.3 / made required in 1.20.2+).
        fields = self.codec.packet_fields("login", "toServer", "login_start") or []
        login_params: dict[str, Any] = {"username": username}
        if "playerUUID" in fields:
            login_params["playerUUID"] = player_uuid
        await self.connection.send("login", "toServer", "login_start", login_params)

        # Wait until the play state is reached (via configuration on
        # 1.20.2+, or directly after login success on older versions) —
        # or until a fatal error/disconnect ends the attempt early.
        waiters = {
            asyncio.create_task(self._config_done.wait()),
            asyncio.create_task(self._fatal_event.wait()),
        }
        try:
            done, pending = await asyncio.wait(
                waiters,
                timeout=self.config.timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        except asyncio.CancelledError:
            for task in waiters:
                task.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)
            await self.connection.close("login cancelled")
            raise
        if self.fatal_error is not None:
            await self.connection.close(str(self.fatal_error))
            raise self.fatal_error
        if not done:
            await self.connection.close("login timeout")
            raise TimeoutError(
                f"Timed out waiting for login/configuration after "
                f"{self.config.timeout}s"
            )
        self.state.spawned = True  # login packet may arrive slightly later
        return self.state

    async def wait_for_spawn(self, timeout: float | None = None) -> None:
        await asyncio.wait_for(self._spawn_done.wait(), timeout=timeout)

    async def wait_until_disconnected(self) -> None:
        await self._disconnect_event.wait()

    async def disconnect(self, reason: str = "client disconnect") -> None:
        for task in list(self._background_tasks):
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*list(self._background_tasks), return_exceptions=True)
            self._background_tasks.clear()
        await self.connection.close(reason)

    async def send(
        self,
        state: str,
        direction: str,
        name: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        await self.connection.send(state, direction, name, params)

    # -- internal ---------------------------------------------------------------

    def _set_connection_state(self, state: str) -> None:
        self.connection.set_state(state)
        if self._on_state_change is not None:
            result = self._on_state_change(state)
            if asyncio.iscoroutine(result):
                task = asyncio.get_running_loop().create_task(_maybe_await(result))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

    async def _dispatch(
        self, state: str, direction: str, name: str, params: dict[str, Any]
    ) -> None:
        # Protocol-level handling first. Fatal negotiation errors are
        # recorded so connect_and_login can re-raise them instead of
        # timing out (the connection layer logs and swallows handler
        # exceptions to keep the reader alive).
        try:
            if state == "login" and direction == "toClient":
                if await self._handle_login_packet(name, params):
                    return
            elif state == "configuration" and direction == "toClient":
                if await self._handle_config_packet(name, params):
                    return
            elif state == "play" and direction == "toClient" and await self._handle_play_packet(name, params):
                return
        except (DisconnectError, AuthenticationError) as exc:
            self._set_fatal(exc)
            raise
        # Then forward to the bot-level handler.
        if self._on_packet is not None:
            result = self._on_packet(state, direction, name, params)
            if asyncio.iscoroutine(result):
                await result

    async def _handle_login_packet(self, name: str, params: dict) -> bool:
        if name == "disconnect":
            reason = params.get("reason", "Disconnected during login")
            raise DisconnectError(str(reason), reason=str(reason))
        if name == "compress":
            threshold = int(params.get("threshold", 256))
            self.connection.enable_compression(threshold)
            self.state.compression_enabled = self.connection.compression.enabled
            return False
        if name == "encryption_begin":
            await self._handle_encryption_begin(params)
            return False
        if name == "success":
            self.state.login_success = params
            if self.codec.has_packet("login", "toServer", "login_acknowledged"):
                await self.connection.send("login", "toServer", "login_acknowledged", {})
                if self.codec.has_state("configuration"):
                    self._set_connection_state("configuration")
                else:
                    self._set_connection_state("play")
                    self._config_done.set()
            else:
                # Pre-1.20.2: success transitions straight to play.
                self._set_connection_state("play")
                self._config_done.set()
            self._login_done.set()
            return False
        return False

    async def _handle_encryption_begin(self, params: dict) -> None:
        """Perform the RSA/AES encryption handshake.

        The server sends its RSA public key (DER) and a random verify token.
        We generate a 16-byte shared secret, RSA-encrypt both the secret and
        the verify token with the server's public key, then send them back.
        Stream encryption is then enabled on the connection.

        Server-hash computation follows Notch's signed hexadecimal SHA-1:
        sha1(server_id + secret + pubkey) interpreted as a signed big-endian
        160-bit integer formatted in base 16 (with leading ``-`` if negative).
        That hash is sent to the Mojang session server when in online mode.
        In offline mode no session join call is needed.
        """
        import secrets

        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import load_der_public_key

        public_key_bytes = params.get("publicKey")
        verify_token_bytes = params.get("verifyToken")
        server_id = params.get("serverId", "")
        should_authenticate = bool(params.get("shouldAuthenticate", True))
        if not public_key_bytes:
            raise AuthenticationError("encryption_begin missing publicKey")
        if not verify_token_bytes:
            raise AuthenticationError("encryption_begin missing verifyToken")

        # Generate a fresh 16-byte shared secret.
        secret = secrets.token_bytes(16)

        # Load the server's RSA public key and encrypt both values.
        try:
            rsa_key = load_der_public_key(public_key_bytes)
            enc_secret = rsa_key.encrypt(secret, padding.PKCS1v15())
            enc_verify = rsa_key.encrypt(verify_token_bytes, padding.PKCS1v15())
        except Exception as exc:
            raise AuthenticationError(
                f"Failed to encrypt with server's RSA key: {exc}"
            ) from exc

        # Compute the server-auth hash for Mojang session join (online mode).
        server_hash = _compute_server_hash(server_id, secret, public_key_bytes)

        # If we have a Mojang/Minecraft access token and the server requests
        # authentication, join the session now.
        access_token = getattr(self, "_access_token", None)
        player_uuid = getattr(self, "_player_uuid", None)
        if should_authenticate and access_token and player_uuid:
            await _join_server(access_token, player_uuid, server_hash)

        await self.connection.send(
            "login",
            "toServer",
            "encryption_begin",
            {"sharedSecret": enc_secret, "verifyToken": enc_verify},
        )

        # From here on the entire stream is AES/CFB8 encrypted with the
        # shared secret (key = secret, IV = secret for both directions).
        self.connection.enable_encryption(secret)
        self.state.encryption_enabled = True

    async def _handle_config_packet(self, name: str, params: dict) -> bool:
        if name == "disconnect":
            reason = params.get("reason", "Disconnected during configuration")
            raise DisconnectError(str(reason), reason=str(reason))
        if name == "select_known_packs":
            if self.codec.has_packet("configuration", "toServer", "select_known_packs"):
                await self.connection.send(
                    "configuration", "toServer", "select_known_packs", {"packs": []}
                )
            return False
        if name == "finish_configuration":
            await self.connection.send("configuration", "toServer", "finish_configuration", {})
            self._set_connection_state("play")
            self._config_done.set()
            return True
        if name == "keep_alive":
            if self.config.auto_respond_keepalive:
                await self.connection.send(
                    "configuration", "toServer", "keep_alive",
                    {"keepAliveId": params.get("keepAliveId")},
                )
            return False
        if name == "ping":
            await self.connection.send(
                "configuration", "toServer", "pong",
                {"id": params.get("id")},
            )
            return False
        return False

    async def _handle_play_packet(self, name: str, params: dict) -> bool:
        if name == "disconnect":
            reason = params.get("reason", "Disconnected")
            self.state.disconnect_reason = str(reason)
            self._disconnect_event.set()
            await self.connection.close(str(reason))
            return True
        if name == "keep_alive":
            if self.config.auto_respond_keepalive:
                await self.connection.send(
                    "play", "toServer", "keep_alive",
                    {"keepAliveId": params.get("keepAliveId")},
                )
            return False
        if name == "login":
            # Clientbound login = we spawned into the world.
            self._spawn_done.set()
            return False
        return False

    async def _handle_disconnect(self, reason: str) -> None:
        self.state.disconnect_reason = reason
        if self.fatal_error is None and not self._config_done.is_set():
            self._set_fatal(
                DisconnectError(f"Connection lost during login: {reason}")
            )
        self._disconnect_event.set()

    def _set_fatal(self, exc: BaseException) -> None:
        if self.fatal_error is None:
            self.fatal_error = exc
        self._fatal_event.set()


async def _maybe_await(coro: Awaitable[Any]) -> None:
    try:
        await coro
    except Exception:
        log.exception("State-change callback failed")


def _compute_server_hash(server_id: str, shared_secret: bytes, public_key: bytes) -> str:
    """Compute the Notch-style server auth hash sent to Mojang's session server.

    Algorithm: SHA-1(server_id_ascii + shared_secret + public_key_der).
    The 20-byte digest is interpreted as a signed big-endian 160-bit integer
    and formatted in lowercase hexadecimal (``BigInteger(digest).toString(16)``
    in Java). Negative digests are prefixed with ``-``.
    """
    import hashlib

    digest = hashlib.sha1(
        server_id.encode("ascii") + shared_secret + public_key
    ).digest()
    value = int.from_bytes(digest, byteorder="big", signed=True)
    return format(value, "x")


async def _join_server(access_token: str, player_uuid: str, server_hash: str) -> None:
    """Call the Mojang session join API (online-mode auth).

    Skipped automatically when ``access_token`` is empty (offline mode).
    Raises :class:`AuthenticationError` if the server responds with an error.
    """
    try:
        import httpx
    except ImportError:
        log.warning("httpx not available; skipping session join call")
        return

    url = "https://sessionserver.mojang.com/session/minecraft/join"
    payload = {
        "accessToken": access_token,
        "selectedProfile": player_uuid.replace("-", ""),
        "serverId": server_hash,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code not in (200, 204):
            body_preview = resp.text[:256]
            raise AuthenticationError(
                f"Session join failed: HTTP {resp.status_code} — {body_preview}"
            )
    except httpx.HTTPError as exc:
        raise AuthenticationError(
            f"Session join request failed: {exc}"
        ) from exc
