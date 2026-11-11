"""A* pathfinding over the loaded world's collision grid.

Walkability rule (v1): a node is walkable when the feet and head blocks are
non-solid and the block below is solid (or the node is the goal). One-block
steps up are allowed when there is headroom. Swimming/flying and diagonal
corner-cutting are not yet supported.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import math
from collections.abc import Iterable
from typing import TYPE_CHECKING

from ..utils.vectors import BlockPos, Vec3

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.pathfinder")

# 4-connected neighbors plus optional +1 step-ups handled in neighbors().
_CARDINALS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _solid(world, pos: BlockPos) -> bool:
    block = world.block_at(pos)
    if block is None:
        return False  # unloaded: don't path through unknown as solid
    return block.bounding_box == "block"


class Pathfinder:
    """Computes and follows paths through the loaded world."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self.max_nodes = 100_000
        self.max_distance = 64.0
        self.allow_jump = True
        self._goto_task = None
        self._stop_event = asyncio.Event()

    # -- walkability ---------------------------------------------------------------

    def is_walkable(self, pos: BlockPos) -> bool:
        """Whether a player AABB can stand at *pos* (feet position)."""
        if _solid(self.bot.world, pos):
            return False
        if _solid(self.bot.world, pos.offset(0, 1, 0)):
            return False
        below = pos.offset(0, -1, 0)
        return _solid(self.bot.world, below)

    def _neighbors(self, pos: BlockPos) -> Iterable[tuple[BlockPos, float]]:
        """Yield (neighbor, cost) pairs, including 1-block step-ups."""
        for dx, dz in _CARDINALS:
            for dy in (0, 1):
                if dy == 1 and not self.allow_jump:
                    continue
                nxt = pos.offset(dx, dy, dz)
                if not self.is_walkable(nxt):
                    continue
                # Prevent corner cutting: both orthogonal neighbors must be
                # passable (feet level) for diagonal-free cardinal moves this
                # only matters for jumps; keep it simple.
                yield nxt, 1.0 + (0.5 if dy else 0.0)

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
        """
        from ..pathfinder.goals import coerce_goal

        entity = self.bot.entity
        if entity is None:
            return False
        g = coerce_goal(goal)
        self._stop_event.clear()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (timeout or 30.0)
        while not g.is_end(entity.position):
            remaining = deadline - loop.time()
            if remaining <= 0:
                await self.bot.stop_moving()
                return False
            target = _to_block_pos(g.target_at(entity.position))
            path = self.find_path(entity.position.floor(), target)
            if path is None:
                self.bot.emit("pathfinding_failed", target)
                await self.bot.stop_moving()
                return False
            self.bot.emit("path_update", path)
            if not await self._follow(path, timeout=remaining):
                return False
        await self.bot.stop_moving()
        return True

    async def _follow(self, path: list[BlockPos], timeout: float | None = None) -> bool:
        import asyncio

        entity = self.bot.entity
        assert entity is not None
        deadline = asyncio.get_running_loop().time() + (timeout or 30.0)
        idx = 1  # skip start node
        last_pos = entity.position
        stuck_ticks = 0

        while idx < len(path):
            if self._stop_event.is_set():
                await self.bot.stop_moving()
                return False
            if asyncio.get_running_loop().time() > deadline:
                await self.bot.stop_moving()
                return False
            node = path[idx]
            # Waypoint: center of the node's feet block, slightly ahead.
            target = Vec3(node.x + 0.5, node.y + 0.1, node.z + 0.5)
            if entity.position.distance_to(target) < 0.35:
                idx += 1
                continue
            # Face the waypoint and walk.
            dx, dz = target.x - entity.position.x, target.z - entity.position.z
            if abs(dx) > 1e-3 or abs(dz) > 1e-3:
                yaw = math.degrees(math.atan2(-dx, dz))
                await self.bot.look(yaw % 360.0, 0.0)
            # Jump if the next node is above us.
            if node.y > entity.position.floor().y:
                await self.bot.set_control_state("jump", True)
            else:
                await self.bot.set_control_state("jump", False)
            await self.bot.set_control_state("forward", True)
            await asyncio.sleep(0.05)

            # Stuck detection.
            if entity.position.distance_squared_to(last_pos) < 1e-4:
                stuck_ticks += 1
            else:
                stuck_ticks = 0
                last_pos = entity.position
            if stuck_ticks > 100:  # ~5s without progress
                await self.bot.stop_moving()
                # One replan attempt.
                goal = path[-1]
                new_path = self.find_path(entity.position.floor(), goal)
                if new_path is None:
                    return False
                path = new_path
                idx = 1
                stuck_ticks = 0

        await self.bot.stop_moving()
        return True

    async def stop(self) -> None:
        self._stop_event.set()
        await self.bot.stop_moving()


def _to_block_pos(pos) -> BlockPos:
    if isinstance(pos, BlockPos):
        return pos
    if isinstance(pos, Vec3):
        return pos.floor()
    if isinstance(pos, tuple):
        return BlockPos(*pos)
    raise TypeError(f"Cannot convert {pos!r} to BlockPos")
