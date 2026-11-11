"""Scoreboard/team/boss-bar/particle handler tests."""

from __future__ import annotations

from types import SimpleNamespace

from leafish.bot import LeafishBot
from leafish.entities.manager import EntityManager
from leafish.modules.scoreboard import BossBar, Particle, ScoreBoard, Team


def _nbt(text: str) -> dict:
    return {"type": "compound",
            "value": {"text": {"type": "string", "value": text}}}


class _FakeBot:
    """Minimal stand-in exposing only what these handlers touch."""

    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.entities = EntityManager({})
        self.boss_bars: dict[str, BossBar] = {}
        self.teams: dict[str, Team] = {}
        self.scoreboards: dict[str, ScoreBoard] = {}
        self._title_state: dict = {}
        self._scoreboard_slots: dict[int, str] = {}
        self.settings = SimpleNamespace(view_distance=12)
        self._game = SimpleNamespace(view_distance=12)
        self.entity_id = None
        self.entity = None
        # Bind the helper methods these handlers delegate to.
        import types
        for name in ("_apply_boss_bar", "_apply_team_fields",
                     "_entity_or_self"):
            setattr(self, name,
                    types.MethodType(getattr(LeafishBot, name), self))

    def emit(self, name, *args, **kwargs) -> None:
        self.events.append((name, args, kwargs))


def _call(method: str, bot: _FakeBot, params: dict) -> None:
    getattr(LeafishBot, method)(bot, params)  # type: ignore[arg-type]


def test_boss_bar_lifecycle():
    bot = _FakeBot()
    uuid = "00000000-0000-0000-0000-0000000000aa"
    _call("_packet_boss_bar", bot,
          {"entityUUID": uuid, "action": 0, "title": _nbt("Wither"),
           "health": 1.0, "color": 1, "dividers": 0, "flags": 2})
    bar = bot.boss_bars[uuid]
    assert bar.title == "Wither"
    assert bar.health == 1.0
    assert bar.dragon_bar is True
    assert tuple(e[0] for e in bot.events[:1]) == ("boss_bar_created",)

    _call("_packet_boss_bar", bot,
          {"entityUUID": uuid, "action": 2, "health": 0.5})
    assert bot.boss_bars[uuid].health == 0.5
    assert bot.events[-1][0] == "boss_bar_updated"

    _call("_packet_boss_bar", bot, {"entityUUID": uuid, "action": 1})
    assert uuid not in bot.boss_bars
    assert bot.events[-1][0] == "boss_bar_deleted"


def test_teams_lifecycle():
    bot = _FakeBot()
    _call("_packet_teams", bot, {
        "team": "red", "mode": "add", "name": _nbt("Red Team"),
        "flags": {"friendly_fire": True, "see_friendly_invisible": False},
        "nameTagVisibility": "always", "collisionRule": "never",
        "formatting": 4, "prefix": _nbt("[R] "), "suffix": _nbt(""),
        "players": []})
    team = bot.teams["red"]
    assert team.display_name == "Red Team"
    assert team.friendly_fire == 1
    assert team.prefix == "[R] "

    _call("_packet_teams", bot,
          {"team": "red", "mode": "join", "players": ["Alice", "Bob"]})
    assert team.members == {"Alice", "Bob"}

    _call("_packet_teams", bot,
          {"team": "red", "mode": "leave", "players": ["Alice"]})
    assert team.members == {"Bob"}

    _call("_packet_teams", bot, {"team": "red", "mode": "remove"})
    assert "red" not in bot.teams


def test_scoreboard_lifecycle():
    bot = _FakeBot()
    _call("_packet_scoreboard_objective", bot,
          {"name": "kills", "action": 0, "displayText": _nbt("Kills"),
           "type": 0})
    board = bot.scoreboards["kills"]
    assert board.title == "Kills"

    _call("_packet_scoreboard_display_objective", bot,
          {"position": 1, "name": "kills"})
    assert bot.scoreboards[bot._scoreboard_slots[1]] is board

    _call("_packet_scoreboard_score", bot, {
        "itemName": "Alice", "scoreName": "kills", "value": 5,
        "display_name": None, "number_format": None})
    assert board.items_map["kills"].value == 5

    _call("_packet_reset_score", bot,
          {"entity_name": "Alice", "objective_name": "kills"})
    assert board.items_map == {}

    _call("_packet_scoreboard_objective", bot,
          {"name": "kills", "action": 1})
    assert "kills" not in bot.scoreboards


def test_titles_and_particles():
    bot = _FakeBot()
    _call("_packet_set_title_text", bot, {"text": _nbt("Level Up!")})
    assert bot.events[-1][0] == "title"
    _call("_packet_set_title_time", bot,
          {"fadeIn": 10, "stay": 70, "fadeOut": 20})
    assert bot.events[-1][0] == "title_times"
    _call("_packet_clear_titles", bot, {"reset": True})
    assert bot.events[-1][0] == "title_clear"
    assert bot._title_state == {}

    _call("_packet_world_particles", bot, {
        "longDistance": False, "alwaysShow": False,
        "x": 1.0, "y": 64.0, "z": 2.0,
        "offsetX": 0.1, "offsetY": 0.1, "offsetZ": 0.1,
        "velocityOffset": 0.0, "amount": 10,
        "particle": {"type": "flame", "data": None}})
    particle_events = [e for e in bot.events if e[0] == "particle"]
    assert particle_events
    p: Particle = particle_events[0][1][0]
    assert p.name == "flame"
    assert p.count == 10
    assert p.position.x == 1.0


def test_collect_destroys_item_entity():
    bot = _FakeBot()
    from leafish.entities.entity import ItemEntity
    item_ent = ItemEntity(id=99, uuid="u")
    bot.entities.entities[99] = item_ent
    _call("_packet_collect", bot, {
        "collectedEntityId": 99, "collectorEntityId": 1,
        "pickupItemCount": 3})
    assert bot.entities.get(99) is None
    names = [e[0] for e in bot.events]
    assert "player_collect" in names
    assert "entity_destroy" in names
