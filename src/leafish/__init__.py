"""Leafish — a pure Python, asynchronous Minecraft bot framework.

Quick start::

    import asyncio
    from leafish import Leafish

    async def main():
        bot = await Leafish.create_bot(
            host="localhost", username="Leafish", auth="offline",
        )

        @bot.on("spawn")
        async def on_spawn():
            print("Leafish joined the world!")

        await bot.wait_until_disconnected()

    asyncio.run(main())
"""

from .bot import Leafish, LeafishBot
from .config import BotConfig
from .entities.entity import Entity, Mob, Player
from .events.emitter import EventEmitter
from .exceptions import (
    AuthenticationError,
    ConnectionError,
    CraftingError,
    DiggingError,
    DisconnectError,
    InventoryError,
    LeafishError,
    MovementError,
    PacketDecodeError,
    PacketEncodeError,
    PathfindingError,
    PluginError,
    ProtocolError,
    UnsupportedVersionError,
)
from .inventory.item import Item
from .utils.vectors import BlockPos, Vec3
from .version import list_versions
from .world.block import Block

__version__ = "0.1.0"

__all__ = [
    "AuthenticationError",
    "Block",
    "BlockPos",
    "BotConfig",
    "ConnectionError",
    "CraftingError",
    "DiggingError",
    "DisconnectError",
    "Entity",
    "EventEmitter",
    "InventoryError",
    "Item",
    "Leafish",
    "LeafishBot",
    "LeafishError",
    "Mob",
    "MovementError",
    "PacketDecodeError",
    "PacketEncodeError",
    "PathfindingError",
    "Player",
    "PluginError",
    "ProtocolError",
    "UnsupportedVersionError",
    "Vec3",
    "__version__",
    "list_versions",
]
