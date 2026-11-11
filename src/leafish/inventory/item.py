"""Item stack model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Item:
    """An item stack as understood by the client."""

    item_id: int | None = None
    """Registry id of the item (version-dependent)."""

    name: str | None = None
    """Resolved item name (e.g. ``"diamond"``) when registry data is loaded."""

    count: int = 1
    """Stack size."""

    components: list[dict[str, Any]] = field(default_factory=list)
    """Raw data components (enchantments, damage, custom_data, ...)."""

    remove_components: list[dict[str, Any]] = field(default_factory=list)

    slot: int | None = None
    """Window slot this item occupies, if known."""

    @classmethod
    def from_slot(cls, slot_data: dict[str, Any], slot_index: int | None = None) -> Item | None:
        """Build an Item from a decoded protocol ``Slot`` dict."""
        if not slot_data or slot_data.get("itemCount", 0) <= 0:
            return None
        return cls(
            item_id=slot_data.get("itemId"),
            count=int(slot_data.get("itemCount", 1)),
            components=slot_data.get("components", []),
            remove_components=slot_data.get("removeComponents", []),
            slot=slot_index,
        )

    @property
    def empty(self) -> bool:
        return self.count <= 0 or self.item_id is None

    def to_slot(self) -> dict[str, Any]:
        """Convert back to protocol Slot dict for sending."""
        if self.empty:
            return {"itemCount": 0}
        return {
            "itemCount": self.count,
            "itemId": self.item_id or 0,
            "addedComponentCount": len(self.components),
            "removedComponentCount": len(self.remove_components),
            "components": self.components,
            "removeComponents": self.remove_components,
        }

    def __repr__(self) -> str:
        name = self.name or f"#{self.item_id}"
        return f"Item({name} x{self.count})"
