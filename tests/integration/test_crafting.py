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


async def test_craft_in_crafting_table(server):
    """A 3x3-only recipe (diamond_pickaxe) crafts inside a table window."""
    gd = get_gamedata("1.21.11")
    bot = await _spawn_with_planks(server, 0)
    try:
        conn = server.connections[0]
        # Open a 46-slot workbench window (result + 3x3 grid + 36 player).
        await conn.debug_open_window(
            1, 46, "Crafting Table", kind="crafting_table")
        for _ in range(60):
            if bot.containers.window(1) is not None:
                break
            await asyncio.sleep(0.05)
        win = bot.containers.window(1)
        assert win is not None
        assert win.player_offset == 10

        # Seed 3 diamonds + 2 sticks into the window's player section.
        diamond = gd.item_by_name("diamond")
        stick = gd.item_by_name("stick")
        assert diamond is not None and stick is not None
        for i in range(3):
            await conn.debug_set_window_slot(
                1, 10 + i, _slot(diamond["id"], 1))
        for i in range(2):
            await conn.debug_set_window_slot(
                1, 13 + i, _slot(stick["id"], 1))
        for _ in range(60):
            if win.slots.get(10) is not None and \
                    win.slots.get(14) is not None:
                break
            await asyncio.sleep(0.05)

        made = await asyncio.wait_for(
            bot.craft("diamond_pickaxe", 1, crafting_table=True), 30)
        assert made == 1
        names = [it.name for it in win.slots.values()]
        assert "diamond_pickaxe" in names
        # Ingredients consumed: 3 diamonds, 2 sticks.
        assert "diamond" not in names
        assert "stick" not in names
    finally:
        await bot.quit()
