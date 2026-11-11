"""Bot state objects exposed as properties (game info, time, XP, ...)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameInfo:
    """Server/game information from login, respawn and related packets."""

    level_type: str | None = None
    """World type name (e.g. ``"minecraft:overworld"``)."""

    dimension: str | None = None
    """Current dimension name."""

    difficulty: str | None = None
    """Server difficulty (peaceful/easy/normal/hard)."""

    game_mode: str | None = None
    """Current game mode (survival/creative/adventure/spectator)."""

    hardcore: bool = False
    max_players: int | None = None
    server_brand: str | None = None
    min_y: int = -64
    height: int = 384
    view_distance: int | None = None
    simulation_distance: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimeInfo:
    """World clock state from ``update_time`` packets."""

    do_daylight_cycle: bool = True
    big_time: int = 0
    """Total world age in ticks (never wraps)."""

    time: int = 0
    """Time of day in ticks (wraps every 24000)."""

    tick_day_time: bool = False
    """Whether the server ticks the day cycle."""

    @property
    def time_of_day(self) -> int:
        return self.time % 24000

    @property
    def day(self) -> int:
        return self.big_time // 24000

    @property
    def is_day(self) -> bool:
        return 0 <= self.time_of_day < 12000 or self.time_of_day >= 23000

    @property
    def moon_phase(self) -> int:
        return (self.big_time // 24000) % 8

    @property
    def age(self) -> int:
        return self.big_time


@dataclass
class ExperienceInfo:
    """Player experience state."""

    level: int = 0
    points: int = 0
    """Total experience points collected."""

    progress: float = 0.0
    """Progress through the current level (0.0-1.0)."""

    total: int = 0


@dataclass
class AbilitiesInfo:
    """Player abilities from the ``abilities`` packet."""

    invulnerable: bool = False
    flying: bool = False
    may_fly: bool = False
    instabuild: bool = False
    may_build: bool = True
    flying_speed: float = 0.05
    walking_speed: float = 0.1


@dataclass
class WeatherInfo:
    """Weather state derived from ``game_state_change`` packets."""

    raining: bool = False
    thundering: bool = False
    rain_level: float = 0.0
    thunder_level: float = 0.0


@dataclass
class SettingsInfo:
    """Client settings reported/configured for the bot."""

    chat_colors: bool = True
    view_distance: int | None = None
    difficulty: int | None = None
    skin_parts: dict[str, bool] = field(default_factory=dict)
    enable_text_filtering: bool = False
    enable_server_listing: bool = True
    particle_status: str = "all"
    main_hand: str = "right"
