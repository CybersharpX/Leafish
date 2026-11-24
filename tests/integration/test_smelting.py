"""Furnace smelting end-to-end against the fake server."""

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


async def test_smelt_iron(server):
    gd = get_gamedata("1.21.11")
    bot = await Leafish.create_bot(
        host="127.0.0.1", port=server.port, username="Smelter",
        auth="offline", version="1.21.11")
    try:
        if not bot.spawned:
            await asyncio.wait_for(bot.wait_for("spawn", timeout=2), 2)
        conn = server.connections[0]
        await conn.debug_open_window(1, 39, "Furnace", kind="furnace")
        for _ in range(60):
            if bot.containers.window(1) is not None:
                break
            await asyncio.sleep(0.05)

        ore = gd.item_by_name("iron_ore")
        coal = gd.item_by_name("coal")
        assert ore is not None and coal is not None
        await conn.debug_set_window_slot(1, 10, _slot(ore["id"], 3))
        await conn.debug_set_window_slot(1, 11, _slot(coal["id"], 3))
        for _ in range(60):
            w = bot.containers.window(1)
            if w is not None and w.slots.get(10) and w.slots.get(11):
                break
            await asyncio.sleep(0.05)

        made = await asyncio.wait_for(bot.smelt("iron_ore", 2), 30)
        assert made == 2
        w = bot.containers.window(1)
        assert w is not None
        counts = {}
        for it in w.slots.values():
            counts[it.name] = counts.get(it.name, 0) + it.count
        assert counts.get("iron_ingot", 0) >= 2
        # One ore and one coal consumed per ingot.
        assert counts.get("iron_ore", 0) == 1
        assert counts.get("coal", 0) == 1
    finally:
        await bot.quit()
