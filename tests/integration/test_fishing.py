"""End-to-end fishing test: cast, bobber spawn, bite, reel."""

import asyncio

import pytest

from leafish import Leafish
from leafish.data.registry import get_gamedata
from tests.chunkdata import air_chunk_data
from tests.protocol.fake_server import FakeMinecraftServer


@pytest.fixture
async def server():
    srv = FakeMinecraftServer()
    await srv.start()
    yield srv
    await srv.stop()


async def test_fish(server):
    gd = get_gamedata("1.21.11")
    air_id = gd.block_state_id("air")
    water_id = gd.block_state_id("water")
    rod = gd.item_by_name("fishing_rod")
    bobber_type = gd.entity_by_name("fishing_bobber")
    assert air_id is not None and water_id is not None
    assert rod is not None and bobber_type is not None

    # Fill the y=64 section (index 8) with water.
    chunk_bytes = air_chunk_data(
        24, air_id, fill_state=water_id, fill_section_index=8
    )
    server.spawn_packets.append((
        "map_chunk", {
            "x": 0, "z": 0, "heightmaps": [], "chunkData": chunk_bytes,
            "blockEntities": [], "skyLightMask": [], "blockLightMask": [],
            "emptySkyLightMask": [], "emptyBlockLightMask": [],
            "skyLight": [], "blockLight": [],
        },
    ))

    uses = {"count": 0}
    bobber_id = 100

    async def on_packet(conn, name, params):
        if name != "use_item":
            return
        uses["count"] += 1
        if uses["count"] == 1:
            # Cast: spawn the bobber, then signal a bite.
            await conn.send("spawn_entity", {
                "entityId": bobber_id,
                "objectUUID": "00000000-0000-0000-0000-0000000000bb",
                "type": bobber_type["id"],
                "x": 2.0, "y": 64.5, "z": 2.0,
                "velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
                "pitch": 0, "yaw": 0, "headPitch": 0,
                "objectData": 0,
            })
            await asyncio.sleep(0.3)
            await conn.send("entity_status", {
                "entityId": bobber_id, "entityStatus": 31,
            })
        elif uses["count"] == 2:
            # Reel: bobber despawns.
            await conn.send("entity_destroy", {"entityIds": [bobber_id]})

    server.on_client_packet = on_packet

    bot = await Leafish.create_bot(
        host="127.0.0.1", port=server.port, username="Angler",
        auth="offline", version="1.21.11",
    )
    try:
        if not bot.spawned:
            await asyncio.wait_for(bot.wait_for("spawn", timeout=2), 2)
        conn = server.connections[0]
        _slot = {
            "itemCount": 1, "itemId": rod["id"],
            "addedComponentCount": 0, "removedComponentCount": 0,
            "components": [], "removeComponents": [],
        }
        await conn.debug_set_slot(36, _slot)
        for _ in range(50):
            if bot.inventory.held_item and bot.inventory.held_item.name == "fishing_rod":
                break
            await asyncio.sleep(0.05)
        assert bot.inventory.held_item is not None

        ok = await asyncio.wait_for(
            bot.fish(timeout=20, loot_timeout=0.3), 25
        )
        assert ok is True
        assert uses["count"] == 2
    finally:
        await bot.quit()
