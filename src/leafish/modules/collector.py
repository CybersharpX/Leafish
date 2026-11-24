"""Item collection: walk to nearby dropped-item entities and pick them up.

The server picks items up automatically once the player is close enough;
this module just navigates to each :class:`ItemEntity` and waits for the
server to destroy it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ..entities.entity import Entity, ItemEntity

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.collector")


class CollectorModule:
    """Collects nearby item entities."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot

    def nearby_items(self, max_distance: float = 8.0) -> list[ItemEntity]:
        """Item entities within *max_distance* of the bot, nearest first."""
        entity = self.bot.entity
        if entity is None:
            return []
        items = [
            e for e in self.bot.entities.all()
            if isinstance(e, ItemEntity)
            and entity.position.distance_to(e.position) <= max_distance
        ]
        items.sort(key=lambda e: entity.position.distance_to(e.position))
        return items

    async def collect(self, max_distance: float = 8.0,
                      count: int | None = None,
                      goto_timeout: float = 10.0,
                      pickup_timeout: float = 5.0) -> int:
        """Collect nearby item entities; returns how many were picked up.

        For each item entity (nearest first) the bot paths to it and waits
        for the server to remove the entity (i.e. the pickup happened).
        """
        collected = 0
        skipped: set[int] = set()
        target = count if count is not None else 1_000_000
        while collected < target:
            items = [i for i in self.nearby_items(max_distance)
                     if i.id not in skipped]
            if not items:
                break
            item = items[0]
            entity = self.bot.entity
            if entity is None:
                break
            if entity.position.distance_to(item.position) > 1.5:
                arrived = await self.bot.goto(
                    item.position, timeout=goto_timeout
                )
                if not arrived:
                    log.debug("collect: could not reach %s", item.position)
                    skipped.add(item.id)
                    continue
            picked = await self._wait_gone_or_timeout(item, pickup_timeout)
            if picked:
                collected += 1
                self.bot.emit("item_collected", item)
            else:
                skipped.add(item.id)
        return collected

    async def _wait_gone_or_timeout(self, item: Entity,
                                    timeout: float) -> bool:
        """Wait until *item* leaves the entity registry or *timeout*."""
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if self.bot.entities.get(item.id) is not item:
                return True
            await asyncio.sleep(0.05)
        return self.bot.entities.get(item.id) is not item
