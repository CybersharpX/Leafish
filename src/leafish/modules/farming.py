"""Farming: harvest mature crops and plant seeds on farmland.

Crop maturity is read from the block's ``age`` state property; the
maximum age per crop is fixed vanilla data (wheat/carrots/potatoes: 7,
beetroots: 3).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.farming")

#: crop block name -> (seed item name, max age)
CROPS: dict[str, tuple[str, int]] = {
    "wheat": ("wheat_seeds", 7),
    "carrots": ("carrot", 7),
    "potatoes": ("potato", 7),
    "beetroots": ("beetroot_seeds", 3),
}


class FarmingModule:
    """Crop harvesting and planting helpers."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot

    # -- queries -----------------------------------------------------------------

    def _crop_names(self, names: list[str] | None) -> list[str]:
        if names:
            return [n for n in names if n in CROPS]
        return list(CROPS)

    @staticmethod
    def _age(block) -> int | None:
        props = getattr(block, "state_properties", None) or {}
        raw = props.get("age")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def mature_crops(self, names: list[str] | None = None,
                     max_distance: int = 32) -> list:
        """Mature crop blocks near the bot."""
        crops = []
        for name in self._crop_names(names):
            _, max_age = CROPS[name]
            for pos in self.bot.find_blocks(name, max_distance=max_distance,
                                            count=0):
                block = self.bot.block_at(pos)
                if block is None:
                    continue
                age = self._age(block)
                if age is not None and age >= max_age:
                    crops.append(block)
        return crops

    # -- actions ---------------------------------------------------------------------

    async def harvest(self, names: list[str] | None = None,
                      max_distance: int = 32) -> int:
        """Dig all mature crops in range; returns blocks harvested."""
        crops = self.mature_crops(names, max_distance)
        dug = 0
        for block in crops:
            try:
                await self.bot.dig(block)
                dug += 1
            except Exception as exc:
                log.debug("harvest: failed at %s: %s", block.position, exc)
        self.bot.emit("harvested", dug)
        return dug

    async def plant(self, seed_name: str | None = None,
                    max_distance: int = 16) -> int:
        """Plant *seed_name* on every empty farmland block in range.

        When *seed_name* is omitted, the first crop seed found in the
        inventory is used. Returns the number of seeds planted.
        """
        if seed_name is None:
            seed_name = self._find_seed()
            if seed_name is None:
                raise ValueError("No crop seeds in inventory")

        farmland = self.bot.find_blocks("farmland",
                                        max_distance=max_distance, count=0)
        planted = 0
        for pos in farmland:
            above = pos.offset(0, 1, 0)
            block = self.bot.block_at(above)
            if block is not None and not block.is_air:
                continue  # already occupied
            # Equip the seed, then place it on the farmland's top face.
            await self.bot.actions.equip(seed_name, "hand")
            try:
                await self.bot.actions.place_block(pos, face="up",
                                                   swing=False)
                planted += 1
            except Exception as exc:
                log.debug("plant: failed at %s: %s", pos, exc)
        self.bot.emit("planted", planted, seed_name)
        return planted

    def _find_seed(self) -> str | None:
        inv = self.bot.inventory
        for _crop, (seed, _) in CROPS.items():
            if inv.find_item(seed) is not None:
                return seed
        return None

    def _find_hoe(self) -> Any:
        inv = self.bot.inventory
        if inv is None:
            return None
        if callable(getattr(inv, "items", None)):
            for item in inv.items():
                if "hoe" in (getattr(item, "name", "") or ""):
                    return item
        slots = getattr(inv, "slots", None)
        if isinstance(slots, dict):
            for item in slots.values():
                if item and "hoe" in (getattr(item, "name", "") or ""):
                    return item
        elif isinstance(slots, (list, tuple)):
            for slot in slots:
                it = getattr(slot, "item", slot)
                if it and "hoe" in (getattr(it, "name", "") or ""):
                    return it
        return None

    async def till(self, block_or_pos) -> bool:
        """Till dirt or grass block into farmland using an inventory hoe."""
        pos = self.bot.actions._resolve_pos(block_or_pos)
        block = self.bot.world.block_at(pos)
        if block is None or block.name not in (
            "dirt", "grass_block", "dirt_path", "coarse_dirt", "rooted_dirt",
        ):
            return False
        # Block above must be air
        above = pos.offset(0, 1, 0)
        above_block = self.bot.world.block_at(above)
        if above_block is not None and not above_block.is_air:
            return False

        hoe = self._find_hoe()
        if hoe is None:
            raise ValueError("No hoe found in inventory for tilling")
        await self.bot.equip(hoe, "hand")
        await self.bot.actions.interact_block(pos, face="up")
        self.bot.emit("tilled", pos)
        return True

    async def till_area(self, start_pos, end_pos) -> int:
        """Till all dirt/grass blocks in a bounding box."""
        start = self.bot.actions._resolve_pos(start_pos)
        end = self.bot.actions._resolve_pos(end_pos)
        min_x, max_x = min(start.x, end.x), max(start.x, end.x)
        min_y, max_y = min(start.y, end.y), max(start.y, end.y)
        min_z, max_z = min(start.z, end.z), max(start.z, end.z)
        from ..utils.vectors import BlockPos

        tilled = 0
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                for z in range(min_z, max_z + 1):
                    p = BlockPos(x, y, z)
                    if await self.till(p):
                        tilled += 1
        return tilled

    # -- convenience -----------------------------------------------------------------

    async def tend(self, names: list[str] | None = None,
                   max_distance: int = 32) -> dict[str, int]:
        """Harvest mature crops, then replant with available seeds."""
        harvested = await self.harvest(names, max_distance)
        planted = 0
        seed = self._find_seed()
        if seed is not None:
            planted = await self.plant(seed, max_distance=max_distance)
        return {"harvested": harvested, "planted": planted}
