"""Pathfinder goal tests."""

from __future__ import annotations

import pytest

from leafish.pathfinder.goals import (
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
from leafish.utils.vectors import BlockPos, Vec3


class _Entity:
    def __init__(self, pos: Vec3) -> None:
        self.position = pos


def test_goal_block_end_and_target():
    g = GoalBlock(10, 64, -3)
    assert not g.is_end(Vec3(10.4, 64.0, -3.4))
    # within 0.5 of block corner counts as arrived
    assert g.is_end(Vec3(10.1, 64.0, -3.1))
    assert g.target == Vec3(10.5, 64, -2.5)


def test_goal_near_range():
    g = GoalNear(0, 64, 0, range=3.0)
    assert g.is_end(Vec3(2.0, 64.0, 2.0))
    assert not g.is_end(Vec3(5.0, 64.0, 0.0))
    assert g.heuristic(Vec3(5, 64, 0)) == pytest.approx(2.0)


def test_goal_xz_ignores_y():
    g = GoalXZ(4, 4, range=1.0)
    assert g.is_end(Vec3(4.5, 200.0, 4.5))
    assert not g.is_end(Vec3(10.0, 64.0, 4.0))
    # target keeps the caller's Y so pathing stays at a sane level
    assert g.target_at(Vec3(0, 70, 0)) == Vec3(4, 70, 4)


def test_goal_y_range():
    g = GoalY(80, range=2.0)
    assert g.is_end(Vec3(0, 81.0, 0))
    assert not g.is_end(Vec3(0, 70.0, 0))
    assert g.target_at(Vec3(5, 0, 5)) == Vec3(5, 80, 5)


def test_goal_get_to_block_bounds():
    g = GoalGetToBlock(3, 64, 3)
    assert g.is_end(Vec3(3.2, 64.5, 3.9))
    assert not g.is_end(Vec3(4.0, 64.5, 3.5))
    assert not g.is_end(Vec3(3.5, 65.0, 3.5))


def test_goal_look_at_block():
    g = GoalLookAtBlock(0, 64, 0, range=4.0)
    assert g.is_end(Vec3(0.5, 64.0, 3.5))
    assert not g.is_end(Vec3(20.0, 64.0, 20.0))


def test_goal_follow_entity_and_callable():
    e = _Entity(Vec3(10, 64, 10))
    g = GoalFollow(e, range=2.0)
    assert g.is_end(Vec3(10.5, 64.0, 9.0))
    assert not g.is_end(Vec3(0, 64, 0))
    # dynamic target follows the entity
    e.position = Vec3(20, 64, 20)
    assert g.target == Vec3(20, 64, 20)

    g2 = GoalFollow(lambda: Vec3(1, 2, 3), range=0.5)
    assert g2.is_end(Vec3(1.1, 2.0, 3.1))
    assert GoalFollowEntity is GoalFollow
    assert GoalNearXZ is GoalXZ


def test_goal_composite_and_invert():
    both = GoalComposite([GoalXZ(0, 0, range=1), GoalY(64, range=1)])
    assert not both.is_end(Vec3(0.5, 70, 0.5))
    assert both.is_end(Vec3(0.5, 64.5, 0.5))

    either = GoalComposite([GoalXZ(0, 0, range=1), GoalXZ(50, 50, range=1)],
                           all_goals=False)
    assert either.is_end(Vec3(50.5, 64, 50.5))

    inv = GoalInvert(GoalBlock(0, 64, 0))
    assert inv.is_end(Vec3(5, 64, 5))
    assert not inv.is_end(Vec3(0.2, 64, 0.2))


def test_coerce_goal():
    assert isinstance(coerce_goal(BlockPos(1, 2, 3)), GoalBlock)
    assert isinstance(coerce_goal(Vec3(1.5, 2.5, 3.5)), GoalBlock)
    assert isinstance(coerce_goal((1, 2, 3)), GoalBlock)
    g = GoalNear(0, 0, 0)
    assert coerce_goal(g) is g
    with pytest.raises(TypeError):
        coerce_goal("nowhere")
