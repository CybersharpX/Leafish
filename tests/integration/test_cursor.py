"""Cursor/line-of-sight queries against the fake server."""

import asyncio

import pytest

from leafish import Leafish
from tests.protocol.fake_server import FakeMinecraftServer


@pytest.fixture
async def server():
    srv = FakeMinecraftServer()
    await srv.start()
    yield srv
    await srv.stop()


async def test_entity_at_cursor(server):
    bot = await Leafish.create_bot(
        host="127.0.0.1", port=server.port, username="LookBot",
        auth="offline", version="1.21.11")
    try:
        if not bot.spawned:
            await asyncio.wait_for(bot.wait_for("spawn", timeout=2), 2)
        conn = server.connections[0]
        # Spawn a zombie 2 blocks along +z (bot faces +z at yaw 0).
        await conn.send("spawn_entity", {
            "entityId": 900, "objectUUID": "00000000-0000-0000-0000-0000000000dd",
            "type": 30, "x": 0.0, "y": 64.0, "z": 3.0,
            "velocity": {"x": 0, "y": 0, "z": 0},
            "pitch": 0, "yaw": 0, "headPitch": 0, "objectData": 0})
        await asyncio.sleep(0.2)
        ent = bot.entity_at_cursor(max_distance=6)
        assert ent is not None and ent.id == 900
        assert bot.can_see_entity(ent) is True
        # Out of range -> nothing under the crosshair.
        assert bot.entity_at_cursor(max_distance=1) is None
    finally:
        await bot.quit()
