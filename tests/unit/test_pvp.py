"""PVP module tests with stubbed bot/actions/pathfinder."""

import asyncio
from typing import Any, cast

from leafish.entities.entity import ItemEntity, Mob, Player
from leafish.entities.manager import EntityManager
from leafish.modules.pvp import PVPModule


class _World:
    pass


class _Inv:
    pass


class _Actions:
    def __init__(self) -> None:
        self.attacks: list[int] = []

    async def attack(self, entity, swing: bool = True) -> None:
        self.attacks.append(entity.id)


class _Pathfinder:
    async def stop(self) -> None:
        pass

    async def goto(self, goal, timeout=None) -> bool:
        return True


class _Bot:
    def __init__(self) -> None:
        self.entity = Player(id=1, uuid="me")
        self.entity.set_position(0, 64, 0)
        self.entities = EntityManager({})
        self.entities.entities[1] = self.entity
        self.actions = _Actions()
        self.pathfinder = _Pathfinder()
        self.world = _World()
        self.inventory = _Inv()
        self.emitted: list[tuple] = []

    def emit(self, event, *args, **kwargs) -> None:
        self.emitted.append((event, args))


def _mob(eid: int, x: float, health: float | None = 20.0,
         type_name: str = "zombie") -> Mob:
    m = Mob(id=eid)
    m.type = type_name
    m.set_position(x, 64, 0)
    m.health = health
    return m


def _module() -> tuple[PVPModule, _Bot]:
    bot = _Bot()
    return PVPModule(cast(Any, bot)), bot


def test_nearest_target_skips_self_and_dead():
    pvp, bot = _module()
    dead = _mob(2, 1.0, health=0.0)
    alive = _mob(3, 5.0)
    bot.entities.entities[2] = dead
    bot.entities.entities[3] = alive
    t = pvp.nearest_target(max_distance=32)
    assert t is alive


def test_nearest_target_hostile_only():
    pvp, bot = _module()
    cow = _mob(2, 1.0, type_name="cow")
    zombie = _mob(3, 5.0, type_name="zombie")
    bot.entities.entities[2] = cow
    bot.entities.entities[3] = zombie
    t = pvp.nearest_target(max_distance=32, hostile_only=True)
    assert t is zombie


def test_nearest_target_entities_filter():
    pvp, bot = _module()
    zombie = _mob(2, 1.0, type_name="zombie")
    cow = _mob(3, 2.0, type_name="cow")
    bot.entities.entities[2] = zombie
    bot.entities.entities[3] = cow
    t = pvp.nearest_target(max_distance=32, entities=["cow"])
    assert t is cow


def test_nearest_target_ignores_items():
    pvp, bot = _module()
    item = ItemEntity(id=2)
    item.set_position(1, 64, 0)
    bot.entities.entities[2] = item
    assert pvp.nearest_target(max_distance=32) is None


async def test_start_attacks_until_target_dies():
    pvp, bot = _module()
    zombie = _mob(2, 2.0, health=20.0)
    bot.entities.entities[2] = zombie

    async def engage():
        await pvp.start(zombie, cooldown=0.01, reach=3.0)

    task = asyncio.ensure_future(engage())
    # Let a few attacks land, then kill the zombie.
    for _ in range(100):
        await asyncio.sleep(0.01)
        if bot.actions.attacks:
            break
    assert bot.actions.attacks
    zombie.health = 0.0
    await asyncio.wait_for(task, 5)
    assert pvp.target is None
    assert bot.actions.attacks == [2] * len(bot.actions.attacks)


async def test_stop_cancels_loop():
    pvp, bot = _module()
    zombie = _mob(2, 2.0)
    bot.entities.entities[2] = zombie
    task = asyncio.ensure_future(pvp.start(None, cooldown=0.01,
                                         entities=["zombie"]))
    await asyncio.sleep(0.1)
    assert pvp._running
    await pvp.stop()
    await asyncio.wait_for(task, 5)
    assert not pvp._running
