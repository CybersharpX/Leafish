"""Entity model: players, mobs, items, projectiles, etc."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utils.geometry import BoundingBox
from ..utils.vectors import Vec3


@dataclass
class Entity:
    """A tracked Minecraft entity."""

    id: int
    """Server-assigned entity id."""

    uuid: str | None = None
    """Entity UUID when known."""

    type: int | str | None = None
    """Entity type: numeric type id or resolved name."""

    name: str | None = None
    """Display name when known (players, named entities)."""

    position: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))
    velocity: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))
    yaw: float = 0.0
    pitch: float = 0.0
    head_yaw: float = 0.0
    on_ground: bool = False
    eye_height: float = 1.62
    """Height of the entity's eyes above its position (for raycasts)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Entity metadata entries keyed by metadata index."""

    equipment: dict[int, Any] = field(default_factory=dict)
    """Equipment slot -> item stack."""

    health: float | None = None
    """Health when exposed via metadata; ``None`` if unknown."""

    bounding_box: BoundingBox | None = None

    _last_position: Vec3 | None = field(default=None, repr=False)
    _position_changed: bool = field(default=False, repr=False)

    # -- queries ---------------------------------------------------------

    @property
    def is_player(self) -> bool:
        return isinstance(self, Player)

    def distance_to(self, other: Entity) -> float:
        return self.position.distance_to(other.position)

    def distance_to_point(self, point: Vec3) -> float:
        return self.position.distance_to(point)

    # -- updates -----------------------------------------------------------

    def set_position(self, x: float, y: float, z: float, *, absolute: bool = True) -> None:
        if absolute:
            self._last_position = self.position
            self.position = Vec3(x, y, z)
        else:
            self._last_position = self.position
            self.position = self.position + Vec3(x, y, z)
        self._position_changed = True

    def set_rotation(self, yaw: float, pitch: float, *, head_yaw: float | None = None) -> None:
        self.yaw = yaw
        self.pitch = pitch
        if head_yaw is not None:
            self.head_yaw = head_yaw

    def update_metadata(self, entries: list[dict[str, Any]]) -> None:
        """Apply entity metadata entries ``[{key,type,value}]``."""
        for entry in entries:
            key = entry.get("key", entry.get("_index"))
            value = entry.get("value")
            self.metadata[key] = value
            # Living entity health is metadata index 9 ("health" float) in
            # modern versions; keep it best-effort.
            if key == 9 and isinstance(value, (int, float)):
                self.health = float(value)

    def consume_position_changed(self) -> bool:
        changed = self._position_changed
        self._position_changed = False
        return changed


class Player(Entity):
    """A player entity (remote or the bot itself)."""

    game_mode: int | None = None
    latency: int | None = None
    listed: bool = True


class Mob(Entity):
    """A non-player living entity."""


class ItemEntity(Entity):
    """A dropped item entity."""

    item: Any = None


class Projectile(Entity):
    """A projectile (arrow, fireball, ...)."""


class Vehicle(Entity):
    """A vehicle the bot or another entity can ride."""
