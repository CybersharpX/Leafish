"""Leafish — a pure Python, asynchronous Minecraft bot framework.

Quick start (high-level ``Bot`` API)::

    import asyncio
    from leafish import Bot

    async def main():
        bot = Bot(host="localhost", username="LeafishBot")

        @bot.on("spawn")
        async def on_spawn():
            await bot.chat("Hello!")

        await bot.start()
        await bot.wait_until_disconnected()

    asyncio.run(main())

Classic API::

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

from .bot import Bot, Leafish, LeafishBot
from .config import BotConfig
from .entities.entity import Entity, Mob, Player
from .events import events
from .events.emitter import EventEmitter
from .exceptions import (
    AuthenticationError,
    BotConnectionError,
    ConnectionError,
    CraftingError,
    DiggingError,
    DisconnectError,
    FishingError,
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
from .modules.builder import BlockPlacement, ConstructionPlan
from .utils.vectors import BlockPos, Vec3
from .version import list_versions
from .world.block import Block

__version__ = "0.1.0"

__all__ = [
    "AuthenticationError",
    "Block",
    "BlockPlacement",
    "BlockPos",
    "Bot",
    "BotConfig",
    "BotConnectionError",
    "ConnectionError",
    "ConstructionPlan",
    "CraftingError",
    "DiggingError",
    "DisconnectError",
    "Entity",
    "EventEmitter",
    "FishingError",
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
    "events",
    "list_versions",
]
