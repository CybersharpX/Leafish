"""Bot configuration."""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

AuthMode = Literal["offline", "microsoft"]

DEFAULT_PORT = 25565
#: Maximum allowed packet size (bytes) before the connection is dropped.
MAX_PACKET_SIZE = 2 * 1024 * 1024


def _default_token_path() -> Path:
    """Return the per-user default path for the Microsoft auth token cache.

    Using a factory instead of a module-level constant ensures that the path
    is evaluated at *instance creation* time, which avoids sharing a single
    mutable ``Path`` object across all ``BotConfig`` instances and allows
    the value to be overridden in tests via ``monkeypatch``.
    """
    return Path.home() / ".leafish" / "tokens.json"


#: Default path to cache Microsoft auth tokens (kept for backwards compat).
DEFAULT_TOKEN_PATH = _default_token_path()


@dataclass
class BotConfig:
    """Configuration for a single bot connection."""

    host: str = "localhost"
    port: int = DEFAULT_PORT
    username: str = "LeafishBot"
    auth: AuthMode = "offline"
    #: Minecraft version string (e.g. ``"1.21.1"``), ``"latest"`` or
    #: ``"auto"`` (detect the server version via a status ping).
    version: str = "auto"
    #: Client brand string sent during login/configuration.
    brand: str = "Leafish"
    #: View distance requested from the server (chunks).
    view_distance: int = 10
    #: Connection timeout in seconds.
    timeout: float = 30.0
    #: Whether the client should respond to keepalive packets automatically.
    auto_respond_keepalive: bool = True
    #: Whether to automatically reconnect after a disconnect.
    auto_reconnect: bool = False
    #: Base delay (seconds) between reconnect attempts; doubles on each failure.
    reconnect_delay: float = 5.0
    #: File path used to cache Microsoft auth tokens.
    token_cache_path: Path = field(default_factory=_default_token_path)
    #: Extra protocol/custom options passed through to the client.
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("host must be a non-empty string")
        if not isinstance(self.port, int) or isinstance(self.port, bool) or not (1 <= self.port <= 65535):
            raise ValueError(f"port must be an integer between 1 and 65535, got {self.port!r}")
        if self.auth not in ("offline", "microsoft"):
            raise ValueError(f"auth must be 'offline' or 'microsoft', got {self.auth!r}")
        if not isinstance(self.view_distance, int) or not (1 <= self.view_distance <= 32):
            raise ValueError(f"view_distance must be between 1 and 32, got {self.view_distance!r}")
        if self.timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {self.timeout!r}")
        if self.reconnect_delay < 0:
            raise ValueError(f"reconnect_delay must be >= 0, got {self.reconnect_delay!r}")
        if isinstance(self.token_cache_path, str):
            self.token_cache_path = Path(self.token_cache_path)

    @property
    def address(self) -> tuple[str, int]:
        """Return ``(host, port)`` with hostname resolution left to the OS."""
        return self.host, self.port


def resolve_host(host: str) -> str:
    """Resolve *host* to an IP address string.

    Falls back to the original hostname when resolution fails; the OS will
    retry resolution when the socket connects.
    """
    try:
        return socket.gethostbyname(host)
    except OSError:
        return host
