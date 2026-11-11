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
        """Drop *count* items from *slot* (or the whole stack).

        Uses window_click mode 4 (drop): button 0 drops one item,
        button 1 drops the whole stack.
        """
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
        if count is not None and 0 < count < item.count:
            for _ in range(count):
                await self.bot.containers.click(
                    0, slot_index, button=0, mode=4
                )
        else:
            await self.bot.containers.click(0, slot_index, button=1, mode=4)

    async def toss_stack(self, slot: int | Item) -> None:
        """Drop the entire stack in *slot*."""
        await self.toss(slot)

    async def drop_slot(self, slot: int) -> None:
        """Alias for :meth:`toss_stack`."""
        await self.toss_stack(slot)

    # -- lower-level window operations -------------------------------------------

    async def move_slot_item(self, source_slot: int, dest_slot: int) -> None:
        """Move the item in *source_slot* to *dest_slot* (window 0).

        Picks the item up, places it in the destination, and returns any
        remainder to the source.
        """
        win_id = self._window_id
        await self.bot.containers.click(win_id, source_slot)
        await self.bot.containers.click(win_id, dest_slot)
        await self.bot.containers.click(win_id, source_slot)

    async def put_away(self, slot: int) -> None:
        """Move the item in *slot* into the first empty inventory slot."""
        for empty in self.empty_slots():
            if HOTBAR_START <= empty <= HOTBAR_END or ARMOR_START <= empty <= ARMOR_END or empty == OFFHAND_SLOT:
                continue
            if empty == slot:
                continue
            await self.move_slot_item(slot, empty)
            return
        raise InventoryError("No empty inventory slot for put_away")

    async def transfer(self, options: dict | None = None) -> None:
        """Shift-click items between inventory sections.

        ``options`` may contain ``window`` (window id, default 0) and
        ``slots`` (iterable of slot indices); when omitted every slot in
        the player section is shift-clicked once.
        """
        options = options or {}
        win_id = options.get("window", self._window_id)
        slots = options.get("slots")
        if slots is None:
            slots = [s for s in self.slots if s is not None]
        for slot in slots:
            await self.bot.containers.shift_click(win_id, slot)

    async def put_selected_item_range(self, start: int, end: int,
                                      window_id: int | None = None,
                                      slot: int | None = None) -> None:
        """Move items from slots ``[start, end)`` into *slot* (merge).

        Picks each source stack up and places it onto the destination
        slot, letting the server merge stacks.
        """
        win_id = self._window_id if window_id is None else window_id
        dst = slot if slot is not None else HOTBAR_START + self.held_slot
        for src in range(start, end):
            item = self.slots.get(src)
            if item is None or item.empty:
                continue
            await self.bot.containers.click(win_id, src)
            await self.bot.containers.click(win_id, dst)
            # Return any remainder to the source slot.
            await self.bot.containers.click(win_id, src)

    # -- equipment helpers ----------------------------------------------------------

    async def unequip(self, destination: str = "hand") -> None:
        """Move the item in *destination* back into the inventory.

        ``destination`` is ``"hand"`` (held hotbar slot), ``"offhand"``
        or an armor destination like ``"armor"``/``"armor_5"``.
        """
        destination = destination.lower()
        if destination == "hand":
            src = HOTBAR_START + self.held_slot
        elif destination == "offhand":
            src = OFFHAND_SLOT
        elif destination == "armor":
            src = next(
                (s for s in range(ARMOR_START, ARMOR_END + 1)
                 if self.slots.get(s) is not None and not self.slots[s].empty),
                None,
            )
            if src is None:
                return
        elif destination.startswith("armor_"):
            try:
                src = int(destination.rsplit("_", 1)[1])
            except ValueError:
                raise InventoryError(f"Invalid destination '{destination}'") from None
            if not ARMOR_START <= src <= ARMOR_END:
                raise InventoryError(f"Invalid armor slot: {src}")
        else:
            raise InventoryError(f"Unknown destination '{destination}'")

        item = self.slots.get(src)
        if item is None or item.empty:
            return
        # Find an empty main-inventory slot (9-35) or hotbar slot.
        target = next(
            (s for s in list(range(9, 36)) + list(range(HOTBAR_START, HOTBAR_END + 1))
             if s != src and (self.slots.get(s) is None or self.slots[s].empty)),
            None,
        )
        if target is None:
            raise InventoryError("No inventory space to unequip into")
        await self.move_slot_item(src, target)
