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

    metadata: int = 0
    """Legacy item damage/metadata (pre-1.13)."""

    nbt: Any = None
    """Raw NBT tag for pre-1.13 / 1.13-1.20 slots."""

    slot_format: str = "components"
    """Wire slot format this item was decoded from (see ``protocol.compat``)."""

    @classmethod
    def from_slot(cls, slot_data: dict[str, Any], slot_index: int | None = None) -> Item | None:
        """Build an Item from a decoded protocol ``Slot`` dict.

        Handles all slot wire eras: legacy ``blockId``/``itemDamage`` (1.8-1.12),
        ``itemId``+NBT (1.13), ``present``+``itemId`` (1.15-1.20) and the modern
        component format (1.21+).
        """
        if not slot_data:
            return None

        # 1.8-1.12: blockId i16 sentinel -1, itemCount i8, itemDamage i16, nbtData.
        if "blockId" in slot_data:
            block_id = slot_data.get("blockId")
            if block_id is None or block_id < 0:
                return None
            return cls(
                item_id=block_id,
                count=int(slot_data.get("itemCount", 1)),
                metadata=int(slot_data.get("itemDamage", 0)),
                nbt=slot_data.get("nbtData"),
                slot=slot_index,
                slot_format="legacy",
            )

        # 1.21+: itemCount varint + itemId/components (component markers
        # are always present on non-empty slots).
        if any(
            k in slot_data
            for k in ("components", "removeComponents", "addedComponentCount")
        ):
            count = int(slot_data.get("itemCount", 0))
            if count <= 0:
                return None
            return cls(
                item_id=slot_data.get("itemId"),
                count=count,
                components=slot_data.get("components", []),
                remove_components=slot_data.get("removeComponents", []),
                slot=slot_index,
                slot_format="components",
            )

        # 1.13: itemId i16 sentinel -1, itemCount i8, nbtData.
        if "itemId" in slot_data and "present" not in slot_data:
            item_id = slot_data.get("itemId")
            if item_id is None or item_id < 0:
                return None
            count = int(slot_data.get("itemCount", 1))
            if count <= 0:
                return None
            return cls(
                item_id=item_id,
                count=count,
                nbt=slot_data.get("nbtData"),
                slot=slot_index,
                slot_format="flat",
            )

        # 1.15-1.20: present bool + varint itemId/itemCount/nbtData.
        if "present" in slot_data:
            if not slot_data.get("present"):
                return None
            item_id = slot_data.get("itemId")
            if item_id is None:
                return None
            count = int(slot_data.get("itemCount", 1))
            if count <= 0:
                return None
            return cls(
                item_id=item_id,
                count=count,
                nbt=slot_data.get("nbtData"),
                slot=slot_index,
                slot_format="present",
            )

        # 1.21+: itemCount varint + optional item/components.
        count = int(slot_data.get("itemCount", 0))
        if count <= 0:
            return None
        return cls(
            item_id=slot_data.get("itemId"),
            count=count,
            components=slot_data.get("components", []),
            remove_components=slot_data.get("removeComponents", []),
            slot=slot_index,
            slot_format="components",
        )

    @property
    def empty(self) -> bool:
        return self.count <= 0 or self.item_id is None

    def to_slot(self, slot_format: str | None = None) -> dict[str, Any]:
        """Convert back to a protocol Slot dict for sending.

        *slot_format* selects the wire era; defaults to the format the
        item was decoded from (or ``"components"``).
        """
        fmt = slot_format or self.slot_format or "components"
        if self.empty:
            if fmt == "legacy":
                return {"blockId": -1}
            if fmt == "flat":
                return {"itemId": -1}
            if fmt == "present":
                return {"present": False}
            return {"itemCount": 0}
        if fmt == "legacy":
            return {
                "blockId": self.item_id or 0,
                "itemCount": self.count,
                "itemDamage": self.metadata,
                "nbtData": self.nbt,
            }
        if fmt == "flat":
            return {
                "itemId": self.item_id or 0,
                "itemCount": self.count,
                "nbtData": self.nbt,
            }
        if fmt == "present":
            return {
                "present": True,
                "itemId": self.item_id or 0,
                "itemCount": self.count,
                "nbtData": self.nbt,
            }
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
