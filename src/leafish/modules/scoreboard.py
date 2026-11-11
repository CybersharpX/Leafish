"""Scoreboard, team, boss-bar and particle state objects.

These mirror the clientbound ``scoreboard_*``, ``teams`` and ``boss_bar``
packets, exposing the same concepts Mineflayer surfaces as
``bot.scoreboards`` / ``bot.teams`` / boss-bar events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utils.text import component_to_text, nbt_to_python
from ..utils.vectors import Vec3


def _text(value: Any) -> str:
    """Best-effort text extraction from a decoded chat component/NBT."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return component_to_text(nbt_to_python(value)) or ""


@dataclass
class ScoreItem:
    """One scoreboard entry (a score line)."""

    name: str
    """The entity/player name this score belongs to."""

    score_name: str
    """The objective this score belongs to."""

    value: int = 0
    display_name: str | None = None
    number_format: Any = None
    styling: Any = None


@dataclass
class ScoreBoard:
    """A scoreboard objective plus its displayed scores."""

    name: str
    """Objective name (id used on the wire)."""

    title: str = ""
    """Human-readable objective title."""

    type: str | None = None
    """Criterion type (e.g. ``"integer"``, ``"hearts"``)."""

    items_map: dict[str, ScoreItem] = field(default_factory=dict)
    """``score_name -> ScoreItem`` entries."""

    @property
    def items(self) -> list[ScoreItem]:
        return list(self.items_map.values())

    def update(self, params: dict[str, Any]) -> ScoreItem:
        """Apply a ``scoreboard_score`` packet's fields."""
        item = ScoreItem(
            name=params.get("itemName", ""),
            score_name=params.get("scoreName", ""),
            value=int(params.get("value", 0)),
            display_name=_text(params.get("display_name")) or None,
            number_format=params.get("number_format"),
            styling=params.get("styling"),
        )
        self.items_map[item.score_name] = item
        return item

    def remove(self, score_name: str) -> ScoreItem | None:
        return self.items_map.pop(score_name, None)


@dataclass
class Team:
    """A scoreboard team."""

    name: str
    display_name: str = ""
    prefix: str = ""
    suffix: str = ""
    friendly_fire: int = 0
    name_tag_visibility: str | None = None
    color: str | None = None
    collision_rule: str | None = None
    members: set[str] = field(default_factory=set)


@dataclass
class BossBar:
    """A boss-bar entry (withers, ender dragon, event bosses)."""

    uuid: str
    title: str = ""
    health: float = 0.0
    division: int = 0
    color: str | None = None
    flags: int = 0
    darkened_sky: bool = False
    dragon_bar: bool = False
    create_fog: bool = False


@dataclass
class Particle:
    """A world particle spawned by the server."""

    particle_id: int | str | None = None
    name: str | None = None
    position: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))
    offset: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))
    max_speed: float = 0.0
    count: int = 0
    long_distance_render: bool = False
    always_show: bool = False
    data: Any = None
