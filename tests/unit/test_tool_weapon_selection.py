"""Unit tests for tool and weapon selection."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from leafish.inventory.item import Item
from leafish.modules.actions import ActionsModule, _best_tool_class_for_block
from leafish.modules.pvp import PVPModule


def test_tool_class_identification():
    assert _best_tool_class_for_block("stone") == "pickaxe"
    assert _best_tool_class_for_block("diamond_ore") == "pickaxe"
    assert _best_tool_class_for_block("dirt") == "shovel"
    assert _best_tool_class_for_block("sand") == "shovel"
    assert _best_tool_class_for_block("oak_log") == "axe"
    assert _best_tool_class_for_block("spruce_planks") == "axe"
    assert _best_tool_class_for_block("sponge") == "hoe"
    assert _best_tool_class_for_block("white_wool") == "shears"


def test_best_tool_selection():
    bot = MagicMock()
    # Create inventory with wood pickaxe, iron pickaxe, diamond pickaxe, and iron shovel
    slots = []
    items = [
        Item(item_id=1, count=1, name="wooden_pickaxe", slot=36),
        Item(item_id=2, count=1, name="iron_pickaxe", slot=37),
        Item(item_id=3, count=1, name="diamond_pickaxe", slot=38),
        Item(item_id=4, count=1, name="iron_shovel", slot=39),
    ]
    for it in items:
        s = MagicMock()
        s.item = it
        slots.append(s)

    bot.inventory.slots = slots
    actions = ActionsModule(bot)

    # For stone, diamond pickaxe should be selected (highest tier)
    tool = actions.best_tool_for("stone")
    assert tool is not None
    assert tool.name == "diamond_pickaxe"

    # For dirt, iron shovel should be selected
    tool_shovel = actions.best_tool_for("dirt")
    assert tool_shovel is not None
    assert tool_shovel.name == "iron_shovel"


@pytest.mark.asyncio
async def test_equip_for_block():
    bot = MagicMock()
    held_slot = MagicMock()
    held_slot.item = Item(item_id=1, count=1, name="wooden_pickaxe", slot=36)
    bot.inventory.held_item = held_slot.item

    diamond_pick = Item(item_id=2, count=1, name="diamond_pickaxe", slot=37)
    s2 = MagicMock()
    s2.item = diamond_pick

    bot.inventory.slots = [held_slot, s2]
    bot.equip = AsyncMock()

    actions = ActionsModule(bot)
    actions.equip = bot.equip

    best = await actions.equip_for_block("iron_ore")
    assert best is not None
    assert best.name == "diamond_pickaxe"
    bot.equip.assert_awaited_once_with(diamond_pick, "hand")


def test_best_weapon_selection():
    bot = MagicMock()
    items = [
        Item(item_id=1, count=1, name="wooden_sword", slot=36),
        Item(item_id=2, count=1, name="iron_sword", slot=37),
        Item(item_id=3, count=1, name="diamond_sword", slot=38),
        Item(item_id=4, count=1, name="iron_axe", slot=39),
    ]
    slots = []
    for it in items:
        s = MagicMock()
        s.item = it
        slots.append(s)
    bot.inventory.slots = slots

    pvp = PVPModule(bot)
    weapon = pvp.best_weapon()
    assert weapon is not None
    assert weapon.name == "diamond_sword"


@pytest.mark.asyncio
async def test_equip_best_weapon():
    bot = MagicMock()
    diamond_sword = Item(item_id=3, count=1, name="diamond_sword", slot=38)
    s = MagicMock()
    s.item = diamond_sword
    bot.inventory.slots = [s]
    bot.inventory.held_item = None
    bot.equip = AsyncMock()

    pvp = PVPModule(bot)
    equipped = await pvp.equip_best_weapon()
    assert equipped is not None
    assert equipped.name == "diamond_sword"
    bot.equip.assert_awaited_once_with(diamond_sword, "hand")
