"""End-to-end smoke tests across all vendored protocol versions.

For every supported Minecraft version a :class:`FakeMinecraftServer`
drives the era-appropriate login flow (with or without the
configuration state) and the bot must reach the play state, receive the
spawn position and be able to send packets without encode errors.
"""

from __future__ import annotations

import asyncio

import pytest

from leafish import Leafish
from leafish.exceptions import DisconnectError
from leafish.protocol.protodef import supported_versions
from tests.protocol.fake_server import FakeMinecraftServer

VERSIONS = supported_versions()


@pytest.mark.parametrize("version", VERSIONS)
async def test_connect_spawn_and_chat(version: str):
    server = FakeMinecraftServer(version=version)
    await server.start()
    bot = None
    try:
        bot = await Leafish.create_bot(
            host="127.0.0.1", port=server.port, username="SmokeBot",
            auth="offline", version=version,
        )
        assert bot.spawned or bot.session is not None
        if not bot.spawned:
            await asyncio.wait_for(bot.wait_for("spawn", timeout=5), 5)
        assert bot.entity is not None
        assert bot.entity.position.y == pytest.approx(64.0)

        # Chat must adapt to the era's packet (chat / chat_message / ...).
        await bot.chat("hello")
        await asyncio.sleep(0.1)

        # Movement packet must encode for this version.
        await bot.set_control_state("forward", True)
        await asyncio.sleep(0.2)
        await bot.set_control_state("forward", False)
    finally:
        if bot is not None:
            await bot.quit()
        await server.stop()


@pytest.mark.parametrize("version", ["1.8", "1.13", "1.18", "1.21.11", "26.1"])
async def test_version_autodetect(version: str):
    """version="auto" pings the server and picks the matching codec."""
    server = FakeMinecraftServer(version=version)
    await server.start()
    bot = None
    try:
        bot = await Leafish.create_bot(
            host="127.0.0.1", port=server.port, username="AutoBot",
            auth="offline", version="auto",
        )
        assert bot.config.version == version
        assert bot.codec.protocol_version == server.codec.protocol_version
    finally:
        if bot is not None:
            await bot.quit()
        await server.stop()


async def test_login_disconnect_surfaces_error():
    """A server-side disconnect during login must raise DisconnectError,
    not hang until the login timeout."""
    server = FakeMinecraftServer(version="1.21.11")
    server.reject_login = "go away"
    await server.start()
    try:
        with pytest.raises(DisconnectError, match="go away"):
            await Leafish.create_bot(
                host="127.0.0.1", port=server.port, username="B",
                auth="offline", version="1.21.11", timeout=30,
            )
    finally:
        await server.stop()
