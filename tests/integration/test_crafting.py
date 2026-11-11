"""End-to-end crafting test against the fake server's inventory model."""

import asyncio

import pytest

from leafish import Leafish
from leafish.data.registry import get_gamedata
from tests.protocol.fake_server import FakeMinecraftServer


@pytest.fixture
async def server():
    srv = FakeMinecraftServer()
    await srv.start()
    yield srv
    await srv.stop()


def _slot(item_id: int, count: int) -> dict:
    return {
        "itemCount": count, "itemId": item_id,
        "addedComponentCount": 0, "removedComponentCount": 0,
        "components": [], "removeComponents": [],
    }


async def _spawn_with_planks(server, count: int = 8):
    """Connect a bot and give it *count* oak_planks in slot 9."""
    gd = get_gamedata("1.21.11")
    planks = gd.item_by_name("oak_planks")
    assert planks is not None
    bot = await Leafish.create_bot(
        host="127.0.0.1", port=server.port, username="Crafter",
        auth="offline", version="1.21.11",
    )
    if not bot.spawned:
        await asyncio.wait_for(bot.wait_for("spawn", timeout=2), 2)
    conn = server.connections[0]
    await conn.debug_set_slot(9, _slot(planks["id"], count))
    for _ in range(50):
        if bot.inventory.count("oak_planks") >= count:
            break
        await asyncio.sleep(0.05)
    return bot


async def test_craft_crafting_table(server):
    bot = await _spawn_with_planks(server, 8)
    try:
        assert bot.inventory.count("oak_planks") == 8

        made = await asyncio.wait_for(bot.craft("crafting_table", 1), 15)
        assert made == 1
        assert bot.inventory.count("crafting_table") == 1
        # 4 planks consumed; 4 remain.
        assert bot.inventory.count("oak_planks") == 4
    finally:
        await bot.quit()


async def test_craft_stick_count(server):
    """Crafting 'stick' x8 from planks exercises the multi-craft loop."""
    bot = await _spawn_with_planks(server, 8)
    try:
        # stick recipe: 1 planks column -> 4 sticks. 8 planks -> 32 sticks max.
        made = await asyncio.wait_for(bot.craft("stick", 8), 30)
        assert made >= 8
        assert bot.inventory.count("stick") >= 8
    finally:
        await bot.quit()
