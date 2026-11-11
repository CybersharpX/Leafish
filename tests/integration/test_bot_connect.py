"""End-to-end test: bot connects to the fake server, spawns, chats, moves."""

import asyncio

import pytest

from leafish import Leafish
from leafish.exceptions import LeafishError
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
