"""Player inventory: hotbar, main inventory, armor, offhand."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..exceptions import InventoryError
from .item import Item

if TYPE_CHECKING:
    from ..bot import LeafishBot

#: Window slot ranges in the player inventory window (windowId 0).
HOTBAR_START = 36
HOTBAR_END = 44  # inclusive
ARMOR_START = 5
ARMOR_END = 8  # inclusive
OFFHAND_SLOT = 45
CRAFTING_OUTPUT_SLOT = 0


class Inventory:
    """The player's own inventory (window id 0)."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self.slots: dict[int, Item] = {}
        self.held_slot: int = 0  # hotbar index 0-8
        self._window_id = 0

    # -- contents --------------------------------------------------------------

    def slot(self, index: int) -> Item | None:
        return self.slots.get(index)

    def items(self) -> list[Item]:
        return [i for i in self.slots.values() if i is not None and not i.empty]

    def items_by_name(self, name: str) -> list[Item]:
        return [i for i in self.items() if i.name == name]

    def count(self, name: str) -> int:
        """Total count of items named *name* across all slots."""
        return sum(i.count for i in self.items_by_name(name))

    def find_item(self, name: str, metadata: int | None = None, nbt=None) -> Item | None:
        """Find the first stack of *name* (optionally exact count match)."""
        matches = self.items_by_name(name)
        if metadata is not None:
            matches = [i for i in matches if getattr(i, "metadata", None) == metadata]
        return matches[0] if matches else None

    def find_items(self, name: str) -> list[Item]:
        return self.items_by_name(name)

    def empty_slots(self) -> list[int]:
        return [i for i in range(46) if i not in self.slots or self.slots[i].empty]

    @property
    def held_item(self) -> Item | None:
        return self.slots.get(HOTBAR_START + self.held_slot)

    # -- updates from server ----------------------------------------------------

    def _resolve(self, item: Item | None) -> Item | None:
        if item is not None and item.item_id is not None and item.name is None:
            item.name = self.bot.world.gamedata.item_name(item.item_id)
        return item

    def update_slot(self, window_id: int, slot: int, item_data: dict[str, Any]) -> None:
        if window_id != self._window_id:
            return
        item = self._resolve(Item.from_slot(item_data, slot))
        if item is None:
            self.slots.pop(slot, None)
        else:
            self.slots[slot] = item

    def update_contents(self, window_id: int, items_data: list[dict[str, Any]],
                        carried: dict[str, Any] | None = None) -> None:
        if window_id != self._window_id:
            return
        self.slots.clear()
        for idx, data in enumerate(items_data):
            item = self._resolve(Item.from_slot(data, idx))
            if item is not None:
                self.slots[idx] = item

    # -- actions -----------------------------------------------------------------

    async def set_held_slot(self, slot: int) -> None:
        """Select hotbar slot *slot* (0-8)."""
        if not 0 <= slot <= 8:
            raise InventoryError(f"Hotbar slot out of range: {slot}")
        await self.bot._send_play("held_item_slot", {"slotId": slot})
        self.held_slot = slot

    async def toss(self, slot: int | Item, count: int | None = None) -> None:
        """Drop *count* items from *slot* (or the held stack)."""
        if isinstance(slot, int):
            item = self.slots.get(slot)
            if item is None:
                raise InventoryError(f"Empty slot {slot}")
            slot_index = slot
        else:
            item = slot
            slot_index = item.slot if item.slot is not None else None
            if slot_index is None:
                raise InventoryError("Cannot determine slot for toss")
        # window_click: windowId=0, stateId, slot, mouseButton=1 (right/drop one)
        # Full click semantics arrive with the container module; for now use
        # the dedicated drop path via creative/inventory click.
        await self.bot._click_window_slot(0, slot_index, button=1)

    async def drop_stack(self, slot: int) -> None:
        await self.toss(slot)
