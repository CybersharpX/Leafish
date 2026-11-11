"""Entity manager classification and update tests (no server needed)."""

from leafish.entities.entity import ItemEntity, Mob, Player, Projectile, Vehicle
from leafish.entities.manager import EntityManager, _class_for_type
from leafish.utils.vectors import Vec3


def test_classification():
    assert _class_for_type("player") is Player
    assert _class_for_type("zombie") is Mob
    assert _class_for_type("item") is ItemEntity
    assert _class_for_type("arrow") is Projectile
    assert _class_for_type("minecart") is Vehicle
    assert _class_for_type("oak_boat") is Vehicle
    assert _class_for_type(None) is not Player


def test_spawn_classifies_by_type_name():
    mgr = EntityManager({1: "player", 2: "item", 3: "creeper"})
    p = mgr.spawn({"entityId": 1, "type": 1, "x": 0, "y": 64, "z": 0})
    i = mgr.spawn({"entityId": 2, "type": 2, "x": 1, "y": 64, "z": 0})
    m = mgr.spawn({"entityId": 3, "type": 3, "x": 2, "y": 64, "z": 0})
    assert isinstance(p, Player) and isinstance(i, ItemEntity)
    assert isinstance(m, Mob) and not isinstance(m, Player)
    assert p.uuid is None or isinstance(p.uuid, str)


def test_move_relative_fixed_point():
    mgr = EntityManager({})
    e = mgr.spawn({"entityId": 5, "type": "zombie",
                   "x": 0.0, "y": 0.0, "z": 0.0})
    mgr.move_relative(5, 4096, 0, -4096)
    assert e.position.x == 1.0
    assert e.position.z == -1.0


def test_metadata_health_and_destroy():
    mgr = EntityManager({})
    e = mgr.spawn({"entityId": 7, "type": "zombie",
                   "x": 0.0, "y": 0.0, "z": 0.0})
    e.update_metadata([{"key": 9, "value": 12.5}])
    assert e.health == 12.5
    removed = mgr.destroy([7])
    assert removed == [e]
    assert mgr.get(7) is None


def test_nearest():
    mgr = EntityManager({})
    mgr.spawn({"entityId": 1, "type": "zombie", "x": 0, "y": 0, "z": 0})
    mgr.spawn({"entityId": 2, "type": "zombie", "x": 10, "y": 0, "z": 0})
    near = mgr.nearest(Vec3(9, 0, 0))
    assert near is not None and near.id == 2
