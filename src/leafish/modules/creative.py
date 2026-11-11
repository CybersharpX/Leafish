"""Creative-mode inventory helpers.

Only functional while the server has the bot in creative mode; the
server silently ignores ``set_creative_slot`` otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..exceptions import InventoryError
from ..inventory.item import Item

if TYPE_CHECKING:
    from ..bot import LeafishBot

__all__ = ["CreativeModule"]


class CreativeModule:
    """``bot.creative`` namespace for creative-only inventory ops."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot

    def _build_item(self, item: Any, count: int = 1) -> Item:
        if isinstance(item, Item):
            it = item
            it.count = count if count != 1 else it.count
            return it
        if isinstance(item, str):
            item_id = self.bot.world.gamedata.item_id_by_name(item)
            if item_id is None:
                raise InventoryError(f"Unknown item name: {item!r}")
            return Item(item_id=item_id, count=count, name=item)
        if isinstance(item, dict):
            return Item(
                item_id=item.get("itemId", item.get("item_id")),
                count=int(item.get("itemCount", item.get("count", count))),
                name=item.get("name"),
                components=item.get("components", []),
                remove_components=item.get("removeComponents", []),
            )
        raise InventoryError(f"Cannot build item from {item!r}")

    async def set_slot(self, slot: int, item: Any, count: int = 1) -> None:
        """Set player-inventory *slot* (window-0 indexing) to *item*.

        *item* may be an :class:`~leafish.inventory.item.Item`, an item
        name string, or a slot dict. Pass ``None``/empty to clear.
        """
        if not 0 <= slot <= 45:
            raise InventoryError(f"Creative slot {slot} out of range (0-45)")
        if item is None:
            slot_data: dict[str, Any] = {"itemCount": 0}
        else:
            built = self._build_item(item, count)
            if built.item_id is None:
                raise InventoryError("Item has no item_id")
            slot_data = built.to_slot()
        await self.bot._send_play(
            "set_creative_slot", {"slot": slot, "item": slot_data})
        # Keep local inventory consistent (server is authoritative, but
        # creative sets are applied immediately by the server).
        self.bot.inventory.update_slot(0, slot, slot_data)
        self.bot.emit("creative_slot_set", slot, item)

    async def give(self, name: str, count: int = 1,
                   slot: int | None = None) -> Item:
        """Give *count* of item *name*; returns the created Item.

        When *slot* is ``None`` the first empty inventory slot is used,
        falling back to slot 36 (first hotbar slot is 36 in window-0
        indexing... actually hotbar is 36-44, main inventory 9-35).
        """
        item = self._build_item(name, count)
        if slot is None:
            empty = self.bot.inventory.empty_slots()
            slot = empty[0] if empty else 36
        await self.set_slot(slot, item)
        return item

    async def clear(self, slot: int) -> None:
        """Clear player-inventory *slot*."""
        await self.set_slot(slot, None)

    async def set_held_item(self, name: str, count: int = 1) -> Item:
        """Give *name* and place it in the currently held hotbar slot."""
        slot = 36 + int(self.bot.inventory.held_slot or 0)
        item = self._build_item(name, count)
        await self.set_slot(slot, item)
        return item
