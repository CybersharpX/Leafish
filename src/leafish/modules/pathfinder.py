"""A* pathfinding over the loaded world's collision grid.

Walkability rule (v2):
  - **Walking** (dry land): feet and head blocks are non-solid, block below is solid.
  - **Swimming**: feet block is a fluid (water/lava); player can swim to any
    adjacent fluid or surface cell with higher cost.
  - **Climbing** (ladders/vines): feet block is a climbable block; player may
    move straight up or down with an extra cost penalty.
  - Diagonal movement is supported when both adjacent cardinal cells are
    passable at feet level (corner-cutting prevention).
  - One-block step-ups are allowed when there is headroom.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import heapq
import logging
import math
from collections.abc import Iterable
from functools import partial
from typing import TYPE_CHECKING

from ..utils.vectors import BlockPos, Vec3

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.pathfinder")

# 4-connected cardinal + 4 diagonal neighbors (8-directional movement).
_CARDINALS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1))

# Shared thread-pool executor used for off-loading A* from the event loop.
_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None


def _get_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="leafish-pathfinder"
        )
    return _EXECUTOR


def _solid(world, pos: BlockPos) -> bool:
    block = world.block_at(pos)
    if block is None:
        return False  # unloaded: don't path through unknown as solid
    return block.bounding_box == "block"


def _passable(world, pos: BlockPos) -> bool:
    """Whether the feet+head blocks at *pos* are both non-solid."""
    return not _solid(world, pos) and not _solid(world, pos.offset(0, 1, 0))


# Block names that allow climbing without ground support.
_CLIMBABLE = frozenset({
    "ladder", "vine", "twisting_vines", "weeping_vines",
    "twisting_vines_plant", "weeping_vines_plant",
    "cave_vines", "cave_vines_plant",
    "scaffolding",
})

# Block names considered fluid (swimable).
_FLUID = frozenset({"water", "lava"})


def _is_fluid(world, pos: BlockPos) -> bool:
    block = world.block_at(pos)
    if block is None:
        return False
    return block.name in _FLUID or block.is_fluid


def _is_climbable(world, pos: BlockPos) -> bool:
    block = world.block_at(pos)
    if block is None:
        return False
    return block.name in _CLIMBABLE


class Pathfinder:
    """Computes and follows paths through the loaded world."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self.max_nodes = 100_000
        self.max_distance = 64.0
        self.allow_jump = True
        self.allow_diagonal = True
        """Allow 8-directional movement (default: True)."""
        self._goto_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    # -- walkability ---------------------------------------------------------------

    def is_walkable(self, pos: BlockPos) -> bool:
        """Whether a player AABB can stand at *pos* (feet position).

        Returns ``True`` for:
        - Normal land: space for feet+head, solid block below.
        - Fluid (water/lava): block at feet is a fluid.
        - Climbable: ladder/vine at feet position.
        """
        world = self.bot.world
        # Cannot be inside a solid block.
        if _solid(world, pos) or _solid(world, pos.offset(0, 1, 0)):
            return False
        below = pos.offset(0, -1, 0)
        # Normal ground.
        if _solid(world, below):
            return True
        # Swimming in fluid.
        if _is_fluid(world, pos):
            return True
        # Climbing (ladder/vine) — climbable at feet or head.
        return bool(_is_climbable(world, pos) or _is_climbable(world, pos.offset(0, 1, 0)))

    def _neighbors(self, pos: BlockPos) -> Iterable[tuple[BlockPos, float]]:
        """Yield (neighbor, cost) pairs, including step-ups, diagonals,
        swimming (up/down in fluid) and ladder climbing."""
        world = self.bot.world

        # --- Vertical movement in fluid or on a climbable block ---
        in_fluid = _is_fluid(world, pos)
        on_ladder = _is_climbable(world, pos) or _is_climbable(world, pos.offset(0, 1, 0))

        if in_fluid or on_ladder:
            cost_mult = 1.5 if in_fluid else 2.0  # swimming/climbing is slower
            # Swim/climb up.
            up = pos.offset(0, 1, 0)
            if self.is_walkable(up):
                yield up, cost_mult
            # Swim/climb down.
            down = pos.offset(0, -1, 0)
            if self.is_walkable(down):
                yield down, cost_mult

        # --- Horizontal movement (cardinals + optional diagonals) ---
        for dx, dz in _CARDINALS:
            for dy in (0, 1):
                if dy == 1 and not self.allow_jump:
                    continue
                nxt = pos.offset(dx, dy, dz)
                if not self.is_walkable(nxt):
                    continue
                # Extra cost for step-ups.
                yield nxt, 1.0 + (0.5 if dy else 0.0) + (0.5 if _is_fluid(world, nxt) else 0.0)

        if self.allow_diagonal:
            for dx, dz in _DIAGONALS:
                # Corner-cutting prevention: both adjacent cardinal cells must
                # be passable at feet level before we allow the diagonal.
                if not _passable(world, pos.offset(dx, 0, 0)):
                    continue
                if not _passable(world, pos.offset(0, 0, dz)):
                    continue
                for dy in (0, 1):
                    if dy == 1 and not self.allow_jump:
                        continue
                    nxt = pos.offset(dx, dy, dz)
                    if not self.is_walkable(nxt):
                        continue
                    yield nxt, 1.414 + (0.5 if dy else 0.0) + (0.5 if _is_fluid(world, nxt) else 0.0)

    # -- A* -------------------------------------------------------------------------

    def find_path(
        self,
        start: BlockPos | Vec3,
        goal: BlockPos | Vec3,
        *,
        max_nodes: int | None = None,
    ) -> list[BlockPos] | None:
        """Return a list of BlockPos from *start* to *goal*, or ``None``.

        The path includes both endpoints. ``None`` means no path was found
        within the node budget.
        """
        start = _to_block_pos(start)
        goal = _to_block_pos(goal)
        if start == goal:
            return [start]
        if not self.is_walkable(start):
            # Try to find a nearby walkable start.
            start = self._nearest_walkable(start) or start
        if not self.is_walkable(goal):
            goal = self._nearest_walkable(goal) or goal

        limit = max_nodes or self.max_nodes
        open_heap: list[tuple[float, int, BlockPos]] = []
        counter = 0
        g_score: dict[BlockPos, float] = {start: 0.0}
        came_from: dict[BlockPos, BlockPos] = {}
        heapq.heappush(open_heap, (self._heuristic(start, goal), counter, start))
        closed: set[BlockPos] = set()
        expanded = 0

        while open_heap and expanded < limit:
            _, _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            closed.add(current)
            expanded += 1
            if current == goal:
                return self._reconstruct(came_from, current)
            for nxt, cost in self._neighbors(current):
                if nxt in closed:
                    continue
                tentative = g_score[current] + cost
                if tentative < g_score.get(nxt, float("inf")):
                    g_score[nxt] = tentative
                    came_from[nxt] = current
                    counter += 1
                    heapq.heappush(
                        open_heap,
                        (tentative + self._heuristic(nxt, goal), counter, nxt),
                    )
        return None

    @staticmethod
    def _heuristic(a: BlockPos, b: BlockPos) -> float:
        return math.sqrt(
            (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2
        )

    @staticmethod
    def _reconstruct(came_from: dict[BlockPos, BlockPos], goal: BlockPos) -> list[BlockPos]:
        path = [goal]
        while path[-1] in came_from:
            path.append(came_from[path[-1]])
        path.reverse()
        return path

    def _nearest_walkable(self, pos: BlockPos, radius: int = 3) -> BlockPos | None:
        if self.is_walkable(pos):
            return pos
        for r in range(1, radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    for dz in range(-r, r + 1):
                        cand = pos.offset(dx, dy, dz)
                        if self.is_walkable(cand):
                            return cand
        return None

    # -- execution ---------------------------------------------------------------------

    async def goto(self, goal, timeout: float | None = None) -> bool:
        """Pathfind to *goal* and walk there. Returns True on arrival.

        *goal* may be a position (``BlockPos``/``Vec3``/tuple) or any
        :class:`~leafish.pathfinder.goals.Goal` — including dynamic goals
        like ``GoalFollow``, which are re-evaluated and replanned as the
        target moves.

        A previous ``goto`` is cancelled cleanly before the new one starts.
        """
        from ..pathfinder.goals import coerce_goal

        # Cancel any previous goto task before starting a new one.
        await self.stop()

        entity = self.bot.entity
        if entity is None:
            return False
        g = coerce_goal(goal)
        self._stop_event.clear()

        async def _run() -> bool:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + (timeout or 30.0)
            ent = self.bot.entity
            if ent is None:
                return False
            while not g.is_end(ent.position):
                if self._stop_event.is_set():
                    await self.bot.stop_moving()
                    return False
                remaining = deadline - loop.time()
                if remaining <= 0:
                    await self.bot.stop_moving()
                    return False
                target = _to_block_pos(g.target_at(ent.position))
                # Run A* in the thread pool to avoid blocking the event loop.
                path = await loop.run_in_executor(
                    _get_executor(),
                    partial(self.find_path, ent.position.floor(), target),
                )
                if path is None:
                    self.bot.emit("pathfinding_failed", target)
                    await self.bot.stop_moving()
                    return False
                self.bot.emit("path_update", path)
                if not await self._follow(path, timeout=remaining):
                    return False
                # Refresh entity reference in case of respawn.
                ent = self.bot.entity
                if ent is None:
                    return False
            await self.bot.stop_moving()
            return True

        self._goto_task = asyncio.ensure_future(_run())
        try:
            return await self._goto_task
        except asyncio.CancelledError:
            return False
        finally:
            self._goto_task = None

    async def _follow(self, path: list[BlockPos], timeout: float | None = None) -> bool:
        entity = self.bot.entity
        assert entity is not None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (timeout or 30.0)
        idx = 1  # skip start node
        last_pos = entity.position
        stuck_ticks = 0

        while idx < len(path):
            if self._stop_event.is_set():
                await self.bot.stop_moving()
                return False
            if loop.time() > deadline:
                await self.bot.stop_moving()
                return False
            node = path[idx]
            # Waypoint: center of the node's feet block.
            target = Vec3(node.x + 0.5, node.y + 0.1, node.z + 0.5)
            if entity.position.distance_to(target) < 0.35:
                idx += 1
                continue
            # Face the waypoint horizontally (look toward the XZ target).
            dx, dz = target.x - entity.position.x, target.z - entity.position.z
            if abs(dx) > 1e-3 or abs(dz) > 1e-3:
                yaw = math.degrees(math.atan2(-dx, dz))
                await self.bot.look(yaw % 360.0, 0.0)

            world = self.bot.world
            feet_bp = entity.position.floor()
            in_fluid = _is_fluid(world, feet_bp)
            on_ladder = _is_climbable(world, feet_bp)

            # Vertical movement handling.
            node_y = node.y
            current_y = entity.position.floor().y
            if node_y > current_y:
                # Climbing up: jump on land, hold jump in fluid (swim up), use
                # ladder sneak-release (just hold forward on a ladder).
                if in_fluid:
                    await self.bot.set_control_state("jump", True)
                elif on_ladder:
                    # On a ladder moving forward climbs up naturally.
                    await self.bot.set_control_state("jump", False)
                else:
                    await self.bot.set_control_state("jump", True)
            elif node_y < current_y:
                # Descending: in fluid hold sneak to sink; on ladder hold sneak.
                if in_fluid or on_ladder:
                    await self.bot.set_control_state("sneak", True)
                await self.bot.set_control_state("jump", False)
            else:
                await self.bot.set_control_state("jump", False)
                await self.bot.set_control_state("sneak", False)

            await self.bot.set_control_state("forward", True)
            await asyncio.sleep(0.05)

            # Stuck detection: no meaningful progress for ~5 s.
            if entity.position.distance_squared_to(last_pos) < 1e-4:
                stuck_ticks += 1
            else:
                stuck_ticks = 0
                last_pos = entity.position
            if stuck_ticks > 100:
                await self.bot.stop_moving()
                # One replan attempt from current position.
                goal_pos = path[-1]
                new_path = await loop.run_in_executor(
                    _get_executor(),
                    partial(self.find_path, entity.position.floor(), goal_pos),
                )
                if new_path is None:
                    return False
                path = new_path
                idx = 1
                stuck_ticks = 0

        await self.bot.stop_moving()
        return True

    async def stop(self) -> None:
        """Cancel any running goto and stop movement."""
        self._stop_event.set()
        task = self._goto_task
        if task is not None and not task.done():
            task.cancel()
            import contextlib
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._goto_task = None
        await self.bot.stop_moving()


def _to_block_pos(pos) -> BlockPos:
    if isinstance(pos, BlockPos):
        return pos
    if isinstance(pos, Vec3):
        return pos.floor()
    if isinstance(pos, tuple):
        return BlockPos(*pos)
    raise TypeError(f"Cannot convert {pos!r} to BlockPos")
