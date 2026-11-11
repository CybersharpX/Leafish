"""Leafish exception hierarchy.

All Leafish-specific exceptions derive from :class:`LeafishError` so callers
can catch a single base type or narrow to a subsystem.
"""

from __future__ import annotations


class LeafishError(Exception):
    """Base class for all Leafish errors."""


# -- Connection / protocol -------------------------------------------------


class ConnectionError(LeafishError):
    """The connection to the server failed or was lost."""


class AuthenticationError(LeafishError):
    """Authentication with Minecraft services or the server failed."""


class ProtocolError(LeafishError):
    """A protocol-level error occurred."""


class UnsupportedVersionError(ProtocolError):
    """The requested Minecraft version is not supported."""


class PacketDecodeError(ProtocolError):
    """A packet could not be decoded."""


class PacketEncodeError(ProtocolError):
    """A packet could not be encoded."""


class DisconnectError(ConnectionError):
    """The server disconnected the client.

    Attributes:
        reason: The server-provided disconnect reason, if any.
    """

    def __init__(self, message: str = "Disconnected", reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


# -- Gameplay ---------------------------------------------------------------


class MovementError(LeafishError):
    """A movement operation failed."""


class PathfindingError(LeafishError):
    """Pathfinding failed or was cancelled."""


class InventoryError(LeafishError):
    """An inventory operation failed."""


class DiggingError(LeafishError):
    """A digging operation failed."""


class CraftingError(LeafishError):
    """A crafting operation failed."""


class PluginError(LeafishError):
    """A plugin failed to load or execute."""
