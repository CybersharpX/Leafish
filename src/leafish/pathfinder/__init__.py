"""Pathfinder goals and helpers.

The A* implementation lives in :mod:`leafish.modules.pathfinder`; this
package provides the goal abstractions used with ``bot.pathfinder.goto``.
"""

from .goals import (
    Goal,
    GoalBlock,
    GoalComposite,
    GoalFollow,
    GoalFollowEntity,
    GoalGetToBlock,
    GoalInvert,
    GoalLookAtBlock,
    GoalNear,
    GoalNearXZ,
    GoalXZ,
    GoalY,
    coerce_goal,
)

__all__ = [
    "Goal", "GoalBlock", "GoalComposite", "GoalFollow", "GoalFollowEntity",
    "GoalGetToBlock", "GoalInvert", "GoalLookAtBlock", "GoalNear",
    "GoalNearXZ", "GoalXZ", "GoalY", "coerce_goal",
]
