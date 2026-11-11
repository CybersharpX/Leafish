"""End-to-end test: bot connects to the fake server, spawns, chats, moves."""

import asyncio

import pytest

from leafish import Leafish
from leafish.data.registry import get_gamedata
from leafish.exceptions import LeafishError
from leafish.utils.vectors import BlockPos
from tests.chunkdata import air_chunk_data
from tests.protocol.fake_server import FakeMinecraftServer


@pytest.fixture
async def server():
    srv = FakeMinecraftServer()
    await srv.start()
    yield srv
    await srv.stop()


async def test_connect_spawn_chat(server):
    received = []

    def on_packet(conn, name, params):
        received.append((name, params))

    server.on_client_packet = on_packet

    bot = await Leafish.create_bot(
        host="127.0.0.1",
        port=server.port,
        username="TestBot",
        auth="offline",
        version="1.21.11",
    )
    try:
        # 'spawn' is emitted on first position packet — may already have fired.
        if not bot.spawned:
            await asyncio.wait_for(bot.wait_for("spawn", timeout=2), 2)
        assert bot.spawned
        assert bot.entity is not None
        assert bot.entity.position.y == pytest.approx(64.0)

        await bot.chat("Hello, server!")
        await asyncio.sleep(0.2)

        names = [n for n, _ in received]
        assert "chat_message" in names
        assert "teleport_confirm" in names

        # Movement: set controls, let physics tick, then stop.
        await bot.set_control_state("forward", True)
        await asyncio.sleep(0.3)
        await bot.stop_moving()
        assert not bot.control_states["forward"]

        # look()
        await bot.look(90.0, 0.0)
        assert bot.entity.yaw == pytest.approx(90.0)
    finally:
        await bot.quit()


async def test_chunk_column_load(server):
    """Server sends a map_chunk; the bot decodes sections and reads blocks."""
    gd = get_gamedata("1.21.11")
    air_id = gd.block_state_id("air")
    stone_id = gd.block_state_id("stone")
    assert air_id is not None and stone_id is not None

    # Bot spawns at y=64 -> section_y=4; min_section_y=-4 -> data index 8.
    chunk_bytes = air_chunk_data(
        24, air_id, fill_state=stone_id, fill_section_index=8
    )
    server.spawn_packets.append((
        "map_chunk",
        {
            "x": 0,
            "z": 0,
            "heightmaps": [],
            "chunkData": chunk_bytes,
            "blockEntities": [],
            "skyLightMask": [],
            "blockLightMask": [],
            "emptySkyLightMask": [],
            "emptyBlockLightMask": [],
            "skyLight": [],
            "blockLight": [],
        },
    ))

    bot = await Leafish.create_bot(
        host="127.0.0.1", port=server.port, username="ChunkBot",
        auth="offline", version="1.21.11",
    )
    try:
        if not bot.spawned:
            await asyncio.wait_for(bot.wait_for("spawn", timeout=2), 2)
        # Give the chunk packet a moment to be processed.
        for _ in range(50):
            if bot.world.chunk_at(0, 0) is not None:
                break
            await asyncio.sleep(0.05)

        chunk = bot.world.chunk_at(0, 0)
        assert chunk is not None
        assert 4 in chunk.sections  # section_y for y=64

        stone = bot.block_at(BlockPos(0, 64, 0))
        assert stone is not None and stone.name == "stone"

        air = bot.block_at(BlockPos(0, 63, 0))
        assert air is not None and air.name == "air"

        # find_blocks should locate the stone section.
        found = bot.find_blocks("stone", max_distance=64)
        assert found
    finally:
        await bot.quit()


async def test_disconnect(server):
    bot = await Leafish.create_bot(
        host="127.0.0.1", port=server.port, username="B", auth="offline",
        version="1.21.11",
    )
    await bot.quit()
    assert bot.session is not None


async def test_unimplemented_methods_raise(server):
    bot = await Leafish.create_bot(
        host="127.0.0.1", port=server.port, username="B", auth="offline",
        version="1.21.11",
    )
    try:
        with pytest.raises(LeafishError):
            await bot.dig(None)
    finally:
        await bot.quit()
