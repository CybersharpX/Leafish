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
        self.connection.set_state("login")
        self._set_connection_state("login")

        # 2. Login start
        await self.connection.send(
            "login",
            "toServer",
            "login_start",
            {"username": username, "playerUUID": player_uuid},
        )

        # Wait until configuration is finished (play state reached).
        await asyncio.wait_for(self._config_done.wait(), timeout=self.config.timeout)
        self.state.spawned = True  # login packet may arrive slightly later
        return self.state

    async def wait_for_spawn(self, timeout: float | None = None) -> None:
        await asyncio.wait_for(self._spawn_done.wait(), timeout=timeout)

    async def wait_until_disconnected(self) -> None:
        await self._disconnect_event.wait()

    async def disconnect(self, reason: str = "client disconnect") -> None:
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
                asyncio.get_running_loop().create_task(_maybe_await(result))

    async def _dispatch(
        self, state: str, direction: str, name: str, params: dict[str, Any]
    ) -> None:
        # Protocol-level handling first.
        if state == "login" and direction == "toClient":
            if await self._handle_login_packet(name, params):
                return
        elif state == "configuration" and direction == "toClient":
            if await self._handle_config_packet(name, params):
                return
        elif state == "play" and direction == "toClient" and await self._handle_play_packet(name, params):
            return
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
            self.state.compression_enabled = True
            return False
        if name == "encryption_begin":
            await self._handle_encryption_begin(params)
            return False
        if name == "success":
            self.state.login_success = params
            await self.connection.send("login", "toServer", "login_acknowledged", {})
            self.connection.set_state("configuration")
            self._set_connection_state("configuration")
            self._login_done.set()
            return False
        return False

    async def _handle_encryption_begin(self, params: dict) -> None:
        """Perform the RSA/AES encryption handshake.

        The server sends its RSA public key; we generate a random shared
        secret, derive the AES key via SHA-1, encrypt the secret and verify
        token with AES/CFB8 (key=IV=secret), send them in ``encryption_begin``
        (serverbound), then enable stream encryption on the connection.
        """
        import hashlib
        import hmac
        import secrets

        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        public_key_bytes = params.get("publicKey")
        server_id = params.get("serverId", "")
        if not public_key_bytes:
            raise AuthenticationError("encryption_begin missing publicKey")

        secret = secrets.token_bytes(16)

        # sharedSecret = SHA1(pubkey || secret || pubkey)[0:16]
        digest = hashlib.sha1()
        digest.update(public_key_bytes)
        digest.update(secret)
        digest.update(public_key_bytes)
        shared_secret = digest.digest()[:16]

        # verifyToken = HMAC-SHA256(key=secret, msg=serverId) || serverId
        verify_token = (
            hmac.new(secret, server_id.encode("utf-8"), hashlib.sha256).digest()
            + server_id.encode("utf-8")
        )

        # Encrypt secret and verifyToken with AES/CFB8, key = IV = secret.
        def _cfb8_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
            enc = Cipher(algorithms.AES(key), modes.CFB8(iv)).encryptor()
            return enc.update(data) + enc.finalize()

        enc_secret = _cfb8_encrypt(secret, secret, secret)
        enc_verify = _cfb8_encrypt(secret, secret, verify_token)

        await self.connection.send(
            "login",
            "toServer",
            "encryption_begin",
            {"sharedSecret": enc_secret, "verifyToken": enc_verify},
        )

        # From here on the stream is encrypted with the shared secret.
        self.connection.enable_encryption(shared_secret)
        self.state.encryption_enabled = True

    async def _handle_config_packet(self, name: str, params: dict) -> bool:
        if name == "disconnect":
            reason = params.get("reason", "Disconnected during configuration")
            raise DisconnectError(str(reason), reason=str(reason))
        if name == "finish_configuration":
            await self.connection.send("configuration", "toServer", "finish_configuration", {})
            self.connection.set_state("play")
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
            await self.connection.close(str(reason))
            self._disconnect_event.set()
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
        self._disconnect_event.set()


async def _maybe_await(coro: Awaitable) -> None:
    try:
        await coro
    except Exception:
        log.exception("State-change callback failed")
