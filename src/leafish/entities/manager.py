"""Entity registry: tracks all entities seen by the client."""

from __future__ import annotations

import logging
from typing import Any

from ..utils.vectors import Vec3
from .entity import Entity, ItemEntity, Mob, Player, Projectile, Vehicle

log = logging.getLogger("leafish.entities")

#: Rough classification of entity type ids -> Python class.
#: Filled from entities.json data where possible; numeric ids are
#: version-dependent so classification is best-effort.
_PLAYER_TYPES = {"player"}
_VEHICLE_TYPES = {
    "boat", "chest_boat", "minecart", "spawner_minecart", "tnt_minecart",
    "hopper_minecart", "furnace_minecart", "command_block_minecart",
}
_PROJECTILE_TYPES = {
    "arrow", "spectral_arrow", "trident", "fireball", "small_fireball",
    "dragon_fireball", "wither_skull", "shulker_bullet", "llama_spit",
    "snowball", "egg", "ender_pearl", "experience_bottle", "potion",
    "fishing_bobber",
}
_ITEM_TYPES = {"item", "item_display", "item_frame", "glow_item_frame"}


def _class_for_type(type_name: str | None) -> type[Entity]:
    if type_name is None:
        return Entity
    t = type_name.lower()
    if "player" in t:
        return Player
    if t in _VEHICLE_TYPES or "minecart" in t or "boat" in t:
        return Vehicle
    if t in _PROJECTILE_TYPES:
        return Projectile
    if t in _ITEM_TYPES:
        return ItemEntity
    return Mob


class EntityManager:
    """Tracks entities by id; resolves type names via game data."""

    def __init__(self, entity_type_names: dict[int, str] | None = None) -> None:
        self.entities: dict[int, Entity] = {}
        self.players: dict[str, Player] = {}  # by uuid
        self._type_names = entity_type_names or {}

    # -- lookups -------------------------------------------------------------

    def get(self, entity_id: int) -> Entity | None:
        return self.entities.get(entity_id)

    def by_uuid(self, uuid_str: str) -> Entity | None:
        for e in self.entities.values():
            if e.uuid == uuid_str:
                return e
        return None

    def all(self) -> list[Entity]:
        return list(self.entities.values())

    def nearest(
        self,
        position: Vec3,
        predicate=None,
        max_distance: float | None = None,
    ) -> Entity | None:
        best = None
        best_dist = float("inf")
        for e in self.entities.values():
            if predicate is not None and not predicate(e):
                continue
            d = position.distance_to(e.position)
            if max_distance is not None and d > max_distance:
                continue
            if d < best_dist:
                best_dist = d
                best = e
        return best

    # -- packet-driven updates -------------------------------------------------

    def spawn(self, params: dict[str, Any]) -> Entity:
        entity_id = params["entityId"]
        if entity_id in self.entities:
            return self.entities[entity_id]

        type_id = params.get("type")
        type_name = self._type_names.get(type_id) if isinstance(type_id, int) else type_id
        cls = _class_for_type(type_name)

        entity = cls(id=entity_id)
        entity.uuid = params.get("objectUUID") or params.get("uuid")
        entity.type = type_name if type_name is not None else type_id
        pos = params.get("position") or {}
        entity.set_position(
            float(params.get("x", pos.get("x", 0))),
            float(params.get("y", pos.get("y", 0))),
            float(params.get("z", pos.get("z", 0))),
        )
        vel = params.get("velocity") or {}
        entity.velocity = Vec3(
            float(vel.get("x", 0)), float(vel.get("y", 0)), float(vel.get("z", 0))
        )
        if "yaw" in params or "pitch" in params:
            entity.set_rotation(
                _byte_rot_to_degrees(params.get("yaw", 0)),
                _byte_rot_to_degrees(params.get("pitch", 0)),
                head_yaw=_byte_rot_to_degrees(params.get("headPitch", params.get("yaw", 0))),
            )
        entity.on_ground = bool(params.get("onGround", False))

        self.entities[entity_id] = entity
        if isinstance(entity, Player) and entity.uuid:
            self.players[entity.uuid] = entity
        return entity

    def move_relative(self, entity_id: int, dx: float, dy: float, dz: float,
                      yaw: float | None = None, pitch: float | None = None,
                      on_ground: bool | None = None) -> Entity | None:
        e = self.entities.get(entity_id)
        if e is None:
            return None
        # Relative moves are in fixed-point 1/4096 blocks.
        e.set_position(dx / 4096.0, dy / 4096.0, dz / 4096.0, absolute=False)
        if yaw is not None:
            e.yaw = _byte_rot_to_degrees(yaw)
        if pitch is not None:
            e.pitch = _byte_rot_to_degrees(pitch)
        if on_ground is not None:
            e.on_ground = on_ground
        return e

    def teleport(self, entity_id: int, params: dict[str, Any]) -> Entity | None:
        e = self.entities.get(entity_id)
        if e is None:
            return None
        e.set_position(
            float(params.get("x", 0)),
            float(params.get("y", 0)),
            float(params.get("z", 0)),
        )
        e.velocity = Vec3(
            float(params.get("dx", 0)),
            float(params.get("dy", 0)),
            float(params.get("dz", 0)),
        )
        if "yaw" in params:
            e.set_rotation(float(params["yaw"]), float(params["pitch"]))
        e.on_ground = bool(params.get("onGround", False))
        return e

    def update_metadata(self, entity_id: int, entries: list[dict[str, Any]]) -> Entity | None:
        e = self.entities.get(entity_id)
        if e is not None:
            e.update_metadata(entries)
        return e

    def update_equipment(self, entity_id: int, equipments: list[dict[str, Any]]) -> Entity | None:
        e = self.entities.get(entity_id)
        if e is not None:
            for eq in equipments:
                slot = eq.get("slot")
                if slot is not None:
                    e.equipment[int(slot)] = eq.get("item")
        return e

    def destroy(self, entity_ids: list[int]) -> list[Entity]:
        removed = []
        for eid in entity_ids:
            e = self.entities.pop(eid, None)
            if e is not None:
                if isinstance(e, Player) and e.uuid:
                    self.players.pop(e.uuid, None)
                removed.append(e)
        return removed

    def clear(self) -> None:
        self.entities.clear()
        self.players.clear()


def _rot_to_degrees(value: Any) -> float:
    """Convert a rotation value to degrees (byte rotations * 360/256)."""
    try:
        return float(value) * 360.0 / 256.0
    except (TypeError, ValueError):
        return 0.0


def _byte_rot_to_degrees(value: Any) -> float:
    return float(value) * 360.0 / 256.0
