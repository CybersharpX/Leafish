"""Pathfinder goal abstractions.

A ``Goal`` describes *when* navigation is complete and provides a
heuristic target for A*. Goals may be static (a block) or dynamic
(following an entity whose position changes).
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from ..utils.vectors import BlockPos, Vec3


class Goal(ABC):
    """Base class for pathfinder goals."""

    @abstractmethod
    def is_end(self, pos: Vec3) -> bool:
        """Whether the bot has arrived (position is entity feet pos)."""

    @abstractmethod
    def heuristic(self, pos: Vec3) -> float:
        """Estimated cost-to-go from *pos* (used by A* when supported)."""

    @property
    @abstractmethod
    def target(self) -> Vec3 | BlockPos:
        """Static point to path toward (see :meth:`target_at`)."""

    def target_at(self, pos: Vec3) -> Vec3 | BlockPos:
        """Point to path toward from *pos* (dynamic goals override)."""
        return self.target


def _dist(pos: Vec3, x: float, y: float, z: float) -> float:
    return math.sqrt((pos.x - x) ** 2 + (pos.y - y) ** 2 + (pos.z - z) ** 2)


class GoalBlock(Goal):
    """Arrive at an exact block position."""

    def __init__(self, x: int, y: int, z: int) -> None:
        self.x, self.y, self.z = x, y, z

    def is_end(self, pos: Vec3) -> bool:
        return (pos.x - self.x) ** 2 + (pos.y - self.y) ** 2 + \
            (pos.z - self.z) ** 2 <= 0.25

    def heuristic(self, pos: Vec3) -> float:
        return _dist(pos, self.x + 0.5, self.y, self.z + 0.5)

    @property
    def target(self) -> Vec3:
        return Vec3(self.x + 0.5, self.y, self.z + 0.5)


class GoalNear(Goal):
    """Get within *range* blocks of a point."""

    def __init__(self, x: float, y: float, z: float, range: float = 1.0) -> None:
        self.x, self.y, self.z = x, y, z
        self.range = range

    def is_end(self, pos: Vec3) -> bool:
        return _dist(pos, self.x, self.y, self.z) <= self.range

    def heuristic(self, pos: Vec3) -> float:
        return max(0.0, _dist(pos, self.x, self.y, self.z) - self.range)

    @property
    def target(self) -> Vec3:
        return Vec3(self.x, self.y, self.z)


class GoalXZ(Goal):
    """Get within *range* blocks horizontally of (x, z), any height."""

    def __init__(self, x: float, z: float, range: float = 0.0) -> None:
        self.x, self.z = x, z
        self.range = range

    def is_end(self, pos: Vec3) -> bool:
        return math.hypot(pos.x - self.x, pos.z - self.z) <= self.range

    def heuristic(self, pos: Vec3) -> float:
        return max(0.0, math.hypot(pos.x - self.x, pos.z - self.z) - self.range)

    @property
    def target(self) -> Vec3:
        return Vec3(self.x, 0, self.z)

    def target_at(self, pos: Vec3) -> Vec3:
        return Vec3(self.x, pos.y, self.z)


class GoalY(Goal):
    """Reach a specific Y level (any X/Z)."""

    def __init__(self, y: float, range: float = 0.0) -> None:
        self.y = y
        self.range = range

    def is_end(self, pos: Vec3) -> bool:
        return abs(pos.y - self.y) <= self.range

    def heuristic(self, pos: Vec3) -> float:
        return max(0.0, abs(pos.y - self.y) - self.range)

    @property
    def target(self) -> Vec3:
        return Vec3(0, self.y, 0)

    def target_at(self, pos: Vec3) -> Vec3:
        return Vec3(pos.x, self.y, pos.z)


class _EntityTarget:
    """Mixin for goals that track a moving point."""

    def __init__(self, target: Any) -> None:
        if callable(target):
            self._target_fn = target
        else:
            if getattr(target, "position", None) is None:
                raise TypeError(
                    "target must be an entity or a callable returning Vec3")
            self._target_fn = lambda: target.position

    @property
    def point(self) -> Vec3:
        return self._target_fn()


class GoalFollow(_EntityTarget, Goal):
    """Follow an entity (or callable position) within *range*."""

    def __init__(self, target: Any, range: float = 2.0) -> None:
        _EntityTarget.__init__(self, target)
        self.range = range

    def is_end(self, pos: Vec3) -> bool:
        return pos.distance_to(self.point) <= self.range

    def heuristic(self, pos: Vec3) -> float:
        return max(0.0, pos.distance_to(self.point) - self.range)

    @property
    def target(self) -> Vec3:
        return self.point


class GoalGetToBlock(Goal):
    """Get to any position inside the bounds of block (x, y, z)."""

    def __init__(self, x: int, y: int, z: int) -> None:
        self.x, self.y, self.z = x, y, z

    def is_end(self, pos: Vec3) -> bool:
        return (self.x <= pos.x < self.x + 1 and
                self.y <= pos.y < self.y + 1 and
                self.z <= pos.z < self.z + 1)

    def heuristic(self, pos: Vec3) -> float:
        return _dist(pos, self.x + 0.5, self.y + 0.5, self.z + 0.5)

    @property
    def target(self) -> Vec3:
        return Vec3(self.x + 0.5, self.y, self.z + 0.5)


class GoalLookAtBlock(Goal):
    """Get within *range* of a block and face it (approximation).

    Completion requires being within range horizontally; the caller is
    responsible for looking at the block afterwards.
    """

    def __init__(self, x: int, y: int, z: int, range: float = 4.0) -> None:
        self.x, self.y, self.z = x, y, z
        self.range = range

    def is_end(self, pos: Vec3) -> bool:
        center = Vec3(self.x + 0.5, self.y + 0.5, self.z + 0.5)
        return pos.distance_to(center) <= self.range

    def heuristic(self, pos: Vec3) -> float:
        return max(
            0.0,
            pos.distance_to(Vec3(self.x + 0.5, self.y + 0.5, self.z + 0.5))
            - self.range,
        )

    @property
    def target(self) -> Vec3:
        return Vec3(self.x + 0.5, self.y, self.z + 0.5)


class GoalComposite(Goal):
    """Combine goals with AND (``all_goals=True``) or OR semantics."""

    @property
    def target(self) -> Vec3 | BlockPos:
        return self.goals[0].target

    def __init__(self, goals: Iterable[Goal], all_goals: bool = True) -> None:
        self.goals = list(goals)
        if not self.goals:
            raise ValueError("GoalComposite requires at least one goal")
        self.all_goals = all_goals

    def is_end(self, pos: Vec3) -> bool:
        results = [g.is_end(pos) for g in self.goals]
        return all(results) if self.all_goals else any(results)

    def heuristic(self, pos: Vec3) -> float:
        vals = [g.heuristic(pos) for g in self.goals]
        return max(vals) if self.all_goals else min(vals)

    def target_at(self, pos: Vec3) -> Vec3 | BlockPos:
        # Path toward the goal with the largest remaining heuristic.
        key = (lambda g: g.heuristic(pos)) if self.all_goals else \
            (lambda g: -g.heuristic(pos))
        return max(self.goals, key=key).target_at(pos)


class GoalInvert(Goal):
    """Inverted goal: satisfied when the wrapped goal is *not*.

    Useful for "get away from" semantics; pair with a timeout since the
    bot may wander indefinitely.
    """

    def __init__(self, goal: Goal) -> None:
        self.goal = goal

    def is_end(self, pos: Vec3) -> bool:
        return not self.goal.is_end(pos)

    def heuristic(self, pos: Vec3) -> float:
        # Once outside the wrapped goal's range we are done; inside, push
        # away by treating distance-from-goal as cost.
        return -self.goal.heuristic(pos)

    @property
    def target(self) -> Vec3 | BlockPos:
        return self.goal.target


# Convenience aliases matching Mineflayer naming.
GoalFollowEntity = GoalFollow
GoalNearXZ = GoalXZ


def coerce_goal(goal: Any) -> Goal:
    """Wrap a position-like value in a Goal if needed."""
    if isinstance(goal, Goal):
        return goal
    if isinstance(goal, BlockPos):
        return GoalBlock(goal.x, goal.y, goal.z)
    if isinstance(goal, Vec3):
        return GoalBlock(int(goal.x), int(goal.y), int(goal.z))
    if isinstance(goal, tuple) and len(goal) == 3:
        return GoalBlock(int(goal[0]), int(goal[1]), int(goal[2]))
    raise TypeError(f"Cannot use {goal!r} as a pathfinder goal")
