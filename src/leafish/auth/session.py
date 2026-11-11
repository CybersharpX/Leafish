"""Authentication session and provider abstractions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class AuthSession:
    """The result of a successful authentication."""

    username: str
    uuid: str
    """Undashed or dashed UUID string accepted by ``uuid.UUID``."""

    access_token: str | None = None
    """Minecraft services access token (online mode only)."""

    profile: dict = field(default_factory=dict)
    """Extra profile data (skins, cape, etc.) when available."""

    @property
    def online(self) -> bool:
        return self.access_token is not None


class AuthProvider(Protocol):
    """Pluggable authentication provider interface."""

    async def authenticate(self, username: str | None = None) -> AuthSession: ...


def offline_uuid(username: str) -> str:
    """Compute the offline-mode UUID for *username*.

    Minecraft derives it as ``UUID.nameUUIDFromBytes("OfflinePlayer:"+name)``
    (MD5-based, version 3).
    """
    import hashlib

    digest = hashlib.md5(f"OfflinePlayer:{username}".encode()).digest()
    # Set version 3 and variant bits per RFC 4122.
    b = bytearray(digest)
    b[6] = (b[6] & 0x0F) | 0x30
    b[8] = (b[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(b)))
