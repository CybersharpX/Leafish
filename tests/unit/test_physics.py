"""Physics collision tests against a stubbed world."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from leafish.modules.physics import PLAYER_HALF_WIDTH, PhysicsEngine
from leafish.utils.vectors import BlockPos, Vec3
from leafish.world.block import Block


def _solid_block(x: int, y: int, z: int) -> Block:
    return Block(
        state_id=1, block_id=1, name="stone",
        position=BlockPos(x, y, z), bounding_box="block",
    )


class _World:
    def __init__(self, blocks: dict[tuple[int, int, int], Block]) -> None:
        self._blocks = blocks

    def block_at(self, pos) -> Block | None:
        bp = pos.floor() if isinstance(pos, Vec3) else pos
        return self._blocks.get((bp.x, bp.y, bp.z))


class _Entity:
    def __init__(self, pos: Vec3) -> None:
        self.position = pos
        self.velocity = Vec3(0, 0, 0)
        self.yaw = 0.0
        self.pitch = 0.0
        self.on_ground = False
        self.eye_height = 1.62

    def set_position(self, x, y, z, *, absolute=True):
        self.position = Vec3(x, y, z)

    def floor(self):
        return self.position.floor()


class _Bot:
    def __init__(self, world: _World, pos: Vec3) -> None:
        self.world = world
        self.entity = _Entity(pos)
        self.control_states = {c: False for c in
                               ("forward", "backward", "left", "right",
                                "jump", "sneak", "sprint")}
        self.game_mode = "survival"
        self.sent: list[tuple[str, dict]] = []

    async def _send_play(self, name, params=None):
        self.sent.append((name, params or {}))

    def emit(self, *a, **k):
        pass


def _floor_world() -> _World:
    blocks = {}
    for x in range(-2, 4):
        for z in range(-2, 4):
            blocks[(x, 63, z)] = _solid_block(x, 63, z)
    return _World(blocks)


def test_player_stands_on_floor():
    world = _floor_world()
    bot = _Bot(world, Vec3(0.5, 64.0, 0.5))
    engine = PhysicsEngine(cast(Any, bot))

    # Not colliding while inside the floor? feet at y=64, box y 64..65.8.
    assert not engine._collides(Vec3(0.5, 64.0, 0.5))
    # Inside the floor block.
    assert engine._collides(Vec3(0.5, 63.5, 0.5))

    # Move down onto the floor: should collide and stop at y=64.
    new_pos, hit = engine._move_axis(Vec3(0.5, 64.0, 0.5), "y", -1.0)
    assert hit
    assert new_pos.y == 64.0


def test_horizontal_wall_stops_movement():
    blocks = {(x, 63, z): _solid_block(x, 63, z)
              for x in range(-2, 4) for z in range(-2, 4)}
    # Wall at x=1 spanning the player's height.
    for y in (64, 65):
        blocks[(1, y, 0)] = _solid_block(1, y, 0)
        blocks[(1, y, 1)] = _solid_block(1, y, 1)
    world = _World(blocks)
    bot = _Bot(world, Vec3(0.5, 64.0, 0.5))
    engine = PhysicsEngine(cast(Any, bot))

    new_pos, hit = engine._move_axis(Vec3(0.5, 64.0, 0.5), "x", 0.5)
    assert hit
    # Player half-width 0.3; wall starts at x=1 -> max center x = 0.7.
    assert new_pos.x <= 1.0 - PLAYER_HALF_WIDTH + 1e-6
    assert new_pos.x > 0.5


def test_tick_keeps_player_grounded():
    world = _floor_world()
    bot = _Bot(world, Vec3(0.5, 64.0, 0.5))
    engine = PhysicsEngine(cast(Any, bot))

    asyncio.run(engine.tick())
    assert bot.entity.position.y == 64.0
    assert engine.on_ground
    # A movement packet was emitted.
    assert any(name == "position_look" for name, _ in bot.sent)


def test_jump_leaves_ground():
    world = _floor_world()
    bot = _Bot(world, Vec3(0.5, 64.0, 0.5))
    engine = PhysicsEngine(cast(Any, bot))
    bot.control_states["jump"] = True
    asyncio.run(engine.tick())
    assert engine.velocity.y > 0 or bot.entity.position.y > 64.0
