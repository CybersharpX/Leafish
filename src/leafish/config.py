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
#: Default path to cache Microsoft auth tokens.
DEFAULT_TOKEN_PATH = Path.home() / ".leafish" / "tokens.json"


@dataclass
class BotConfig:
    """Configuration for a single bot connection."""

    host: str = "localhost"
    port: int = DEFAULT_PORT
    username: str = "LeafishBot"
    auth: AuthMode = "offline"
    #: Minecraft version string (e.g. ``"1.21.1"``) or ``"latest"``.
    version: str = "latest"
    #: Client brand string sent during login/configuration.
    brand: str = "Leafish"
    #: View distance requested from the server (chunks).
    view_distance: int = 10
    #: Connection timeout in seconds.
    timeout: float = 30.0
    #: Whether the client should respond to keepalive packets automatically.
    auto_respond_keepalive: bool = True
    #: Directory used to cache Microsoft auth tokens.
    token_cache_path: Path = DEFAULT_TOKEN_PATH
    #: Extra protocol/custom options passed through to the client.
    options: dict[str, Any] = field(default_factory=dict)

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
