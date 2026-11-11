"""Creative module tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from leafish.data.registry import get_gamedata
from leafish.exceptions import InventoryError
from leafish.inventory.inventory import Inventory
from leafish.inventory.item import Item
from leafish.modules.creative import CreativeModule


class _Bot:
    def __init__(self) -> None:
        self.world = SimpleNamespace(gamedata=get_gamedata("1.21.11"))
        self.sent: list[tuple[str, dict]] = []
        self.events: list[tuple] = []
        self.inventory = Inventory(cast(Any, self))

    async def _send_play(self, name, params):
        self.sent.append((name, params))

    def emit(self, name, *args, **kwargs):
        self.events.append((name, args))


@pytest.mark.asyncio
async def test_set_slot_builds_untrusted_slot():
    bot = _Bot()
    cr = CreativeModule(cast(Any, bot))
    await cr.set_slot(36, "diamond", count=3)
    name, params = bot.sent[-1]
    assert name == "set_creative_slot"
    assert params["slot"] == 36
    assert params["item"]["itemCount"] == 3
    assert params["item"]["itemId"] is not None
    # local inventory updated
    assert bot.inventory.slots[36].name == "diamond"


@pytest.mark.asyncio
async def test_set_slot_clear():
    bot = _Bot()
    cr = CreativeModule(cast(Any, bot))
    await cr.set_slot(9, None)
    assert bot.sent[-1][1]["item"] == {"itemCount": 0}
    assert 9 not in bot.inventory.slots


@pytest.mark.asyncio
async def test_give_uses_empty_slot_and_set_held():
    bot = _Bot()
    bot.inventory.slots[9] = Item(item_id=1, count=1, name="dirt")
    cr = CreativeModule(cast(Any, bot))
    item = await cr.give("stone", count=2)
    assert item.name == "stone"
    slot_used = bot.sent[-1][1]["slot"]
    assert slot_used != 9
    await cr.set_held_item("iron_ingot")
    assert bot.sent[-1][1]["slot"] == 36 + bot.inventory.held_slot


@pytest.mark.asyncio
async def test_unknown_item_raises():
    bot = _Bot()
    cr = CreativeModule(cast(Any, bot))
    with pytest.raises(InventoryError):
        await cr.give("not_a_real_item_xyz")
    with pytest.raises(InventoryError):
        await cr.set_slot(99, "stone")
