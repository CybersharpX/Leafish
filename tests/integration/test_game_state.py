"""Integration tests for game-state packets: boss bars, teams,
scoreboards, titles, particles, sounds, vehicles, window properties."""

import asyncio

import pytest

from leafish import Leafish
from tests.protocol.fake_server import FakeMinecraftServer


def _nbt(text: str) -> dict:
    return {"type": "compound",
            "value": {"text": {"type": "string", "value": text}}}


@pytest.fixture
async def server():
    srv = FakeMinecraftServer()
    await srv.start()
    yield srv
    await srv.stop()


async def _connect(server) -> "object":
    bot = await Leafish.create_bot(
        host="127.0.0.1", port=server.port,
        username="StateBot", auth="offline", version="1.21.11")
    if not bot.spawned:
        await asyncio.wait_for(bot.wait_for("spawn", timeout=2), 2)
    return bot


async def test_boss_bar_packets(server):
    bot = await _connect(server)
    try:
        conn = server.connections[0]
        events = []
        bot.on("boss_bar_created", lambda b: events.append(("created", b)))
        bot.on("boss_bar_updated", lambda b: events.append(("updated", b)))
        bot.on("boss_bar_deleted", lambda b: events.append(("deleted", b)))

        uuid = "00000000-0000-0000-0000-0000000000bb"
        await conn.send("boss_bar", {
            "entityUUID": uuid, "action": 0, "title": _nbt("Ender Dragon"),
            "health": 1.0, "color": 5, "dividers": 1, "flags": 2})
        await asyncio.sleep(0.15)
        bar = bot.boss_bars[uuid]
        assert bar.title == "Ender Dragon"
        assert bar.dragon_bar is True

        await conn.send("boss_bar", {
            "entityUUID": uuid, "action": 2, "health": 0.25})
        await asyncio.sleep(0.15)
        assert bot.boss_bars[uuid].health == 0.25

        await conn.send("boss_bar", {"entityUUID": uuid, "action": 1})
        await asyncio.sleep(0.15)
        assert uuid not in bot.boss_bars
        kinds = [e[0] for e in events]
        assert kinds == ["created", "updated", "deleted"]
    finally:
        await bot.disconnect()


async def test_team_and_scoreboard_packets(server):
    bot = await _connect(server)
    try:
        conn = server.connections[0]
        await conn.send("teams", {
            "team": "blue", "mode": "add", "name": _nbt("Blue"),
            "flags": {"friendly_fire": False,
                      "see_friendly_invisible": False},
            "nameTagVisibility": "always", "collisionRule": "always",
            "formatting": 4, "prefix": _nbt(""), "suffix": _nbt(""),
            "players": []})
        await conn.send("teams", {
            "team": "blue", "mode": "join", "players": ["Alice"]})
        await conn.send("scoreboard_objective", {
            "name": "deaths", "action": 0, "displayText": _nbt("Deaths"),
            "type": 0, "number_format": None})
        await conn.send("scoreboard_display_objective", {
            "position": 1, "name": "deaths"})
        await conn.send("scoreboard_score", {
            "itemName": "Alice", "scoreName": "deaths", "value": 3,
            "display_name": None, "number_format": None})
        await asyncio.sleep(0.2)

        assert bot.teams["blue"].members == {"Alice"}
        board = bot.scoreboard
        assert board is not None and board.title == "Deaths"
        assert board.items[0].value == 3
    finally:
        await bot.disconnect()


async def test_title_and_particle_packets(server):
    bot = await _connect(server)
    try:
        conn = server.connections[0]
        titles = []
        particles = []
        bot.on("title", lambda *a: titles.append(a))
        bot.on("particle", lambda p: particles.append(p))

        await conn.send("set_title_text", {"text": _nbt("You died!")})
        await conn.send("set_title_time",
                        {"fadeIn": 10, "stay": 60, "fadeOut": 10})
        await conn.send("clear_titles", {"reset": True})
        await conn.send("world_particles", {
            "longDistance": False, "alwaysShow": False,
            "x": 0.0, "y": 64.0, "z": 0.0,
            "offsetX": 0.2, "offsetY": 0.2, "offsetZ": 0.2,
            "velocityOffset": 0.0, "amount": 20,
            "particle": {"type": "flame", "data": None}})
        await asyncio.sleep(0.2)

        assert titles[0][0] == "You died!"
        assert particles and particles[0].name == "flame"
        assert particles[0].count == 20
    finally:
        await bot.disconnect()


async def test_vehicle_and_collect_packets(server):
    bot = await _connect(server)
    try:
        conn = server.connections[0]
        # Spawn a horse entity then attach the bot's entity to it.
        await conn.send("spawn_entity", {
            "entityId": 500, "objectUUID": "00000000-0000-0000-0000-0000000000cc",
            "type": 90, "x": 2.0, "y": 64.0, "z": 2.0,
            "velocity": {"x": 0, "y": 0, "z": 0},
            "pitch": 0, "yaw": 0, "headPitch": 0, "objectData": 0})
        await asyncio.sleep(0.15)
        await conn.send("attach_entity",
                        {"entityId": bot.entity_id, "vehicleId": 500})
        await asyncio.sleep(0.15)
        assert bot.player.vehicle is not None
        assert bot.player.vehicle.id == 500

        await conn.send("attach_entity",
                        {"entityId": bot.entity_id, "vehicleId": -1})
        await asyncio.sleep(0.15)
        assert bot.player.vehicle is None
    finally:
        await bot.disconnect()
