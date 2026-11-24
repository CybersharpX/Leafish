"""Typed window tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from leafish.exceptions import InventoryError
from leafish.inventory.item import Item
from leafish.modules.containers import WindowState
from leafish.modules.windows import (
    AnvilWindow,
    EnchantmentTableWindow,
    FurnaceWindow,
    HorseWindow,
    VillagerWindow,
    Window,
    typed_window,
)


class _Bot:
    def __init__(self) -> None:
        self.world = SimpleNamespace(
            gamedata=SimpleNamespace(item_name=lambda i: f"item{i}"))
        self.sent: list[tuple[str, dict]] = []
        self.containers = SimpleNamespace(
            click=self._click, shift_click=self._shift_click,
            close=self._close)

    async def _send_play(self, name, params):
        self.sent.append((name, params))

    async def _click(self, wid, slot, button=0, mode=0):
        pass

    async def _shift_click(self, wid, slot):
        pass

    async def _close(self, wid):
        pass


def _win(title: str, player_offset: int = 3,
         slots: dict[int, Item] | None = None,
         properties: dict[int, int] | None = None,
         extras: dict | None = None) -> WindowState:
    w = WindowState(window_id=1, title=title, player_offset=player_offset)
    w.slots.update(slots or {})
    w.properties.update(properties or {})
    w.extras.update(extras or {})
    return w


def _item(slot: int, item_id: int = 5, count: int = 1) -> Item:
    return Item(item_id=item_id, count=count, name=f"item{item_id}",
                slot=slot)


def test_typed_window_detection():
    bot = cast(Any, _Bot())
    assert isinstance(typed_window(bot, _win("Furnace")), FurnaceWindow)
    assert isinstance(typed_window(bot, _win("Blast Furnace")), FurnaceWindow)
    assert isinstance(typed_window(bot, _win("Smoker")), FurnaceWindow)
    assert isinstance(typed_window(bot, _win("Enchanting Table")),
                      EnchantmentTableWindow)
    assert isinstance(typed_window(bot, _win("Anvil")), AnvilWindow)
    assert isinstance(typed_window(bot, _win("Villager")), VillagerWindow)
    assert isinstance(typed_window(bot, _win("Chest")), Window)


def test_typed_window_trades_extras():
    bot = cast(Any, _Bot())
    w = _win("Villager", extras={"trades": [{"a": 1}], "villagerLevel": 3,
                                 "experience": 10, "canRestock": True})
    vw = typed_window(bot, w)
    assert isinstance(vw, VillagerWindow)
    assert vw.trades == [{"a": 1}]
    assert vw.villager_level == 3
    assert vw.experience == 10
    assert vw.can_restock is True


def test_furnace_window_progress():
    bot = cast(Any, _Bot())
    w = _win("Furnace", properties={0: 800, 1: 1600, 2: 100, 3: 200},
             slots={0: _item(0), 2: _item(2, 7, 3)})
    fw = FurnaceWindow(bot, w)
    assert fw.burn_time == 800
    assert fw.burn_time_total == 1600
    assert fw.cook_time == 100
    assert fw.cook_time_total == 200
    assert fw.progress == pytest.approx(0.5)
    assert fw.input_item is w.slots[0]
    assert fw.output_item is not None and fw.output_item.count == 3


def test_enchantment_table_window():
    bot = cast(Any, _Bot())
    w = _win("Enchanting Table", player_offset=3,
             slots={0: _item(0, 9), 1: _item(1, 4, 3), 2: _item(2, 10)})
    ew = EnchantmentTableWindow(bot, w)
    assert ew.item_slot is not None and ew.item_slot.item_id == 9
    assert ew.lapis_slot is not None and ew.lapis_slot.count == 3
    assert ew.result_slot is not None and ew.result_slot.item_id == 10


@pytest.mark.asyncio
async def test_enchant_sends_packet():
    bot = cast(Any, _Bot())
    ew = EnchantmentTableWindow(bot, _win("Enchanting Table"))
    await ew.enchant(1)
    assert bot.sent == [("enchant_item",
                         {"windowId": 1, "enchantment": 1})]
    with pytest.raises(InventoryError):
        await ew.enchant(3)


def test_anvil_window_cost_and_rename():
    bot = cast(Any, _Bot())
    aw = AnvilWindow(bot, _win("Anvil", properties={0: 7}))
    assert aw.repair_cost == 7


@pytest.mark.asyncio
async def test_anvil_rename_sends_packet():
    bot = cast(Any, _Bot())
    aw = AnvilWindow(bot, _win("Anvil"))
    await aw.rename("Excalibur")
    assert bot.sent == [("name_item", {"name": "Excalibur"})]


def test_horse_window_extras():
    bot = cast(Any, _Bot())
    hw = HorseWindow(bot, _win("Horse", player_offset=2,
                               extras={"entityId": 42, "slotCount": 2}))
    assert hw.entity_id == 42
    assert hw.slot_count == 2


@pytest.mark.asyncio
async def test_villager_select_trade():
    bot = cast(Any, _Bot())
    vw = VillagerWindow(bot, _win("Villager",
                                  extras={"trades": [{"a": 1}, {"b": 2}]}))
    await vw.select_trade(1)
    assert bot.sent == [("select_trade", {"slot": 1})]
    with pytest.raises(InventoryError):
        await vw.select_trade(5)
