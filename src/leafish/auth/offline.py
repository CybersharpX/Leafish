"""Offline-mode authentication (no Microsoft account required)."""

from __future__ import annotations

from .session import AuthSession, offline_uuid


class OfflineAuth:
    """Authentication for servers running in offline mode."""

    async def authenticate(self, username: str | None = None) -> AuthSession:
        if not username:
            raise ValueError("offline auth requires a username")
        return AuthSession(username=username, uuid=offline_uuid(username))
