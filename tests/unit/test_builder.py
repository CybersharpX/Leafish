"""Unit tests for the ConstructionPlan and BuilderModule."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from leafish import BlockPlacement, BlockPos, ConstructionPlan
from leafish.inventory.item import Item
from leafish.modules.builder import BuilderModule
from leafish.utils.vectors import Vec3


def test_construction_plan_column():
    plan = ConstructionPlan.column((0, 64, 0), height=3, block_name="stone")
    assert len(plan) == 3
    assert plan.placements[0] == BlockPlacement(BlockPos(0, 64, 0), "stone")
    assert plan.placements[1] == BlockPlacement(BlockPos(0, 65, 0), "stone")
    assert plan.placements[2] == BlockPlacement(BlockPos(0, 66, 0), "stone")


def test_construction_plan_platform():
    plan = ConstructionPlan.platform((0, 64, 0), (2, 64, 1), "oak_planks")
    # (3 in X) * (2 in Z) = 6 blocks
    assert len(plan) == 6
    req = plan.required_materials()
    assert req == {"oak_planks": 6}


def test_construction_plan_box_solid_and_hollow():
    solid = ConstructionPlan.box((0, 60, 0), (2, 62, 2), "stone", hollow=False)
    assert len(solid) == 3 * 3 * 3  # 27 blocks

    hollow = ConstructionPlan.box((0, 60, 0), (2, 62, 2), "stone", hollow=True)
    # Center block (1, 61, 1) is omitted in hollow box -> 27 - 1 = 26
    assert len(hollow) == 26


def test_construction_plan_wall():
    plan = ConstructionPlan.wall((0, 64, 0), (3, 64, 0), height=2, block_name="cobblestone")
    # 4 blocks wide * 2 blocks high = 8 blocks
    assert len(plan) == 8
    req = plan.required_materials()
    assert req == {"cobblestone": 8}


def test_construction_plan_ordering():
    plan = ConstructionPlan()
    plan.add((0, 70, 0), "stone")
    plan.add((0, 64, 0), "stone")
    plan.add((1, 65, 0), "stone")

    ordered = plan.order_for_construction()
    assert ordered[0].position.y == 64
    assert ordered[1].position.y == 65
    assert ordered[2].position.y == 70


def test_construction_plan_inventory_validation():
    bot = MagicMock()
    # Inventory has 10 cobblestone
    slot = MagicMock()
    slot.item = Item(item_id=4, count=10, name="cobblestone")
    bot.inventory.slots = [slot]

    plan_ok = ConstructionPlan.wall(
        (0, 64, 0), (1, 64, 0), height=2, block_name="cobblestone"
    )  # 4 blocks
    has_all, missing = plan_ok.validate_inventory(bot)
    assert has_all is True
    assert missing == {}

    plan_insufficient = ConstructionPlan.column(
        (0, 64, 0), height=15, block_name="cobblestone"
    )  # 15 blocks
    has_all, missing = plan_insufficient.validate_inventory(bot)
    assert has_all is False
    assert missing == {"cobblestone": 5}


@pytest.mark.asyncio
async def test_builder_module_execution():
    bot = MagicMock()
    bot.game_mode = "creative"
    bot.creative.set_slot = AsyncMock()
    bot.equip = AsyncMock()
    bot.entity = MagicMock()
    bot.entity.position = Vec3(0, 64, 0)
    bot.world.block_at.return_value = None
    bot.actions.place_block = AsyncMock()
    bot.emit = MagicMock()

    builder = BuilderModule(bot)
    plan = builder.plan_column((0, 64, 0), height=3, block_name="stone")

    success = await builder.build(plan, reach=5.0, navigate=False, check_materials=False)
    assert success is True
    assert bot.actions.place_block.call_count == 3
    bot.emit.assert_any_call("build_started", plan)
    bot.emit.assert_any_call("build_complete", plan)
