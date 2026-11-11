"""Container window test: open a chest-like window, shift-click items."""

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


async def test_chest_window_shift_click(server):
    gd = get_gamedata("1.21.11")
    diamond = gd.item_by_name("diamond")
    assert diamond is not None

    bot = await Leafish.create_bot(
        host="127.0.0.1", port=server.port, username="ChestBot",
        auth="offline", version="1.21.11",
    )
    try:
        if not bot.spawned:
            await asyncio.wait_for(bot.wait_for("spawn", timeout=2), 2)
        conn = server.connections[0]

        # Open a 63-slot window (27 chest + 36 player).
        await conn.debug_open_window(1, 63, "Chest")
        for _ in range(50):
            if bot.containers.window(1) is not None:
                break
            await asyncio.sleep(0.05)
        win = bot.containers.window(1)
        assert win is not None
        assert win.player_offset == 27
        assert list(win.container_slots()) == list(range(27))
        assert list(win.player_slots()) == list(range(27, 63))

        # Put 5 diamonds in chest slot 0.
        await conn.debug_set_window_slot(1, 0, _slot(diamond["id"], 5))
        for _ in range(50):
            it = win.slots.get(0)
            if it is not None and it.count == 5:
                break
            await asyncio.sleep(0.05)
        assert win.slots[0].name == "diamond"

        # Shift-click withdraws to the player section (first empty >= 27).
        await bot.shift_click(1, 0)
        for _ in range(50):
            if 0 not in win.slots:
                break
            await asyncio.sleep(0.05)
        assert 0 not in win.slots
        player_items = [
            (s, i) for s, i in win.slots.items()
            if s >= 27 and i.name == "diamond"
        ]
        assert player_items and player_items[0][1].count == 5

        # Shift-click deposits back into the chest.
        await bot.shift_click(1, player_items[0][0])
        for _ in range(50):
            chest = win.slots.get(0)
            if chest is not None and chest.name == "diamond":
                break
            await asyncio.sleep(0.05)
        assert win.slots[0].name == "diamond"

        # Close the window.
        await bot.close_window(1)
        assert bot.containers.window(1) is None
    finally:
        await bot.quit()
