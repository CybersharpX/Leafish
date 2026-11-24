"""Unit tests for hoe tilling."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from leafish.inventory.item import Item
from leafish.modules.farming import FarmingModule
from leafish.utils.vectors import BlockPos


@pytest.mark.asyncio
async def test_farming_till_dirt():
    bot = MagicMock()
    hoe_item = Item(item_id=10, count=1, name="iron_hoe", slot=36)
    slot = MagicMock()
    slot.item = hoe_item
    bot.inventory.slots = [slot]

    dirt_block = MagicMock()
    dirt_block.name = "dirt"
    air_block = MagicMock()
    air_block.is_air = True

    def block_at_mock(pos):
        if pos == BlockPos(0, 64, 0):
            return dirt_block
        if pos == BlockPos(0, 65, 0):
            return air_block
        return None

    bot.world.block_at.side_effect = block_at_mock
    bot.actions._resolve_pos = lambda p: p if isinstance(p, BlockPos) else BlockPos(*p)
    bot.actions.interact_block = AsyncMock()
    bot.equip = AsyncMock()
    bot.emit = MagicMock()

    farming = FarmingModule(bot)
    success = await farming.till(BlockPos(0, 64, 0))

    assert success is True
    bot.equip.assert_awaited_once_with(hoe_item, "hand")
    bot.actions.interact_block.assert_awaited_once_with(BlockPos(0, 64, 0), face="up")
    bot.emit.assert_called_with("tilled", BlockPos(0, 64, 0))


@pytest.mark.asyncio
async def test_farming_till_non_dirt():
    bot = MagicMock()
    stone_block = MagicMock()
    stone_block.name = "stone"
    bot.world.block_at.return_value = stone_block
    bot.actions._resolve_pos = lambda p: p if isinstance(p, BlockPos) else BlockPos(*p)

    farming = FarmingModule(bot)
    success = await farming.till(BlockPos(0, 64, 0))
    assert success is False
