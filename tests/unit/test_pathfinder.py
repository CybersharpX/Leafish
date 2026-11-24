"""Pathfinder A* tests on synthetic worlds."""

from __future__ import annotations

from typing import Any, cast

from leafish.modules.pathfinder import Pathfinder
from leafish.utils.vectors import BlockPos, Vec3
from leafish.world.block import Block


def _block(x: int, y: int, z: int, solid: bool = True) -> Block:
    return Block(
        state_id=1 if solid else 0, block_id=1 if solid else 0,
        name="stone" if solid else "air",
        position=BlockPos(x, y, z),
        bounding_box="block" if solid else "empty",
    )


class _World:
    """Dict-backed world; missing blocks are air (non-solid)."""

    def __init__(self, solids: set[tuple[int, int, int]]) -> None:
        self.solids = solids

    def block_at(self, pos) -> Block | None:
        bp = pos.floor() if isinstance(pos, Vec3) else pos
        return _block(bp.x, bp.y, bp.z, (bp.x, bp.y, bp.z) in self.solids)


class _Bot:
    def __init__(self, world: _World) -> None:
        self.world = world
        self.entity = None


def _flat_world(x_range=range(-5, 10), z_range=range(-5, 10), floor_y=63):
    solids = {(x, floor_y, z) for x in x_range for z in z_range}
    return _World(solids)


def test_straight_line_path():
    world = _flat_world()
    pf = Pathfinder(cast(Any, _Bot(world)))
    path = pf.find_path(BlockPos(0, 64, 0), BlockPos(5, 64, 0))
    assert path is not None
    assert path[0] == BlockPos(0, 64, 0)
    assert path[-1] == BlockPos(5, 64, 0)
    assert len(path) == 6


def test_wall_requires_detour():
    solids = {(x, 63, z) for x in range(-5, 10) for z in range(-5, 10)}
    # Wall at x=2 for z in -2..2, two blocks high.
    for z in range(-2, 3):
        for y in (64, 65):
            solids.add((2, y, z))
    world = _World(solids)
    pf = Pathfinder(cast(Any, _Bot(world)))
    path = pf.find_path(BlockPos(0, 64, 0), BlockPos(4, 64, 0))
    assert path is not None
    # Path must go around the wall (z beyond ±2).
    assert any(abs(p.z) > 2 for p in path)
    assert all(p.x != 2 or abs(p.z) > 2 or p.y != 64 for p in path)


def test_unreachable_goal_returns_none():
    solids = {(x, 63, z) for x in range(-5, 10) for z in range(-5, 10)}
    # Seal the goal in a wall box (feet + head level around it).
    gx, gy, gz = 4, 64, 0
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx == 0 and dz == 0:
                continue
            for dy in (0, 1):
                solids.add((gx + dx, gy + dy, gz + dz))
    solids.add((gx, gy + 2, gz))  # cap above the head
    world = _World(solids)
    pf = Pathfinder(cast(Any, _Bot(world)))
    pf.max_nodes = 5000
    assert pf.find_path(BlockPos(0, 64, 0), BlockPos(gx, gy, gz)) is None


def test_step_up_one_block():
    solids = {(x, 63, z) for x in range(-5, 10) for z in range(-5, 10)}
    # Raised platform: top surface at y=65 for x in 2..4.
    for x in range(2, 5):
        for z in range(-1, 2):
            solids.add((x, 64, z))
    world = _World(solids)
    pf = Pathfinder(cast(Any, _Bot(world)))
    path = pf.find_path(BlockPos(0, 64, 0), BlockPos(4, 65, 0))
    assert path is not None
    assert path[-1] == BlockPos(4, 65, 0)
    # Path should climb onto the platform (y=65).
    assert any(p.y == 65 for p in path)
