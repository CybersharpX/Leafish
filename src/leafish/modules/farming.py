"""Farming: harvest mature crops and plant seeds on farmland.

Crop maturity is read from the block's ``age`` state property; the
maximum age per crop is fixed vanilla data (wheat/carrots/potatoes: 7,
beetroots: 3).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

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
