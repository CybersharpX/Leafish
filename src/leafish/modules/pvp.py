"""Combat module (``bot.pvp``): target selection and attack loop.

``pvp.start()`` continuously engages a target — or the nearest matching
entity — walking into reach with the pathfinder, aiming and attacking on a
cooldown. ``pvp.stop()`` cancels the loop and any in-progress path.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from ..entities.entity import Entity, ItemEntity, Mob, Player, Projectile

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.pvp")

#: Common hostile mob type names for ``hostile_only`` filtering.
HOSTILE_TYPES = {
    "zombie", "zombie_villager", "husk", "drowned", "skeleton", "stray",
    "bogged", "wither_skeleton", "creeper", "spider", "cave_spider",
    "enderman", "witch", "slime", "magma_cube", "ghast", "blaze",
    "piglin", "piglin_brute", "hoglin", "zoglin", "pillager", "vindicator",
    "evoker", "ravager", "vex", "illusioner", "phantom", "silverfish",
    "endermite", "guardian", "elder_guardian", "shulker", "wither",
    "warden", "breeze",
}


class PVPModule:
    """Target acquisition and melee combat."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self.target: Entity | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    # -- single attack ---------------------------------------------------------

    async def attack(self, target: Entity, swing: bool = True) -> None:
        """Attack *target* once (delegates to the actions module)."""
        await self.bot.actions.attack(target, swing=swing)

    # -- target selection --------------------------------------------------------

    def _default_predicate(self) -> Any:
        def pred(e: Entity) -> bool:
            if self.bot.entity is not None and e.id == self.bot.entity.id:
                return False
            if isinstance(e, (ItemEntity, Projectile)):
                return False
            if e.health is not None and e.health <= 0:
                return False
            return isinstance(e, (Mob, Player))
        return pred

    def _make_predicate(self, opts: dict[str, Any]) -> Any:
        names = opts.get("entities")
        hostile_only = opts.get("hostile_only", False)
        custom = opts.get("filter")
        base = self._default_predicate()

        def pred(e: Entity) -> bool:
            if not base(e):
                return False
            if custom is not None and not custom(e):
                return False
            if hostile_only and not self._is_hostile(e):
                return False
            if names:
                t = e.type
                tname = t if isinstance(t, str) else ""
                wanted = {n.lower() for n in names}
                return tname.lower() in wanted or any(
                    w in tname.lower() for w in wanted
                )
            return True
        return pred

    @staticmethod
    def _is_hostile(e: Entity) -> bool:
        t = e.type
        if not isinstance(t, str):
            return False
        tl = t.lower()
        return tl in HOSTILE_TYPES or any(h in tl for h in ("zombie", "skeleton", "creeper"))

    def nearest_target(self, max_distance: float | None = None,
                       **opts: Any) -> Entity | None:
        """Nearest entity matching the given filters."""
        entity = self.bot.entity
        if entity is None:
            return None
        pred = self._make_predicate(opts)
        return self.bot.entities.nearest(
            entity.position, pred, max_distance or opts.get("maxDistance")
        )

    # -- combat loop ----------------------------------------------------------------

    async def start(self, target: Entity | None = None,
                    **opts: Any) -> None:
        """Continuously attack *target* (or nearest match) until stopped.

        Options:
            reach: attack distance in blocks (default 3.0)
            cooldown: seconds between attacks (default 0.5)
            maxDistance: target acquisition radius (default 32)
            goto_timeout: per-approach pathfind timeout (default 5)
            swing: swing arm on attack (default True)
            entities: iterable of entity type names to match
            hostile_only: only target hostile mobs
            filter: custom predicate ``(entity) -> bool``
        """
        if self._running:
            await self.stop()
        self._running = True
        reach = float(opts.get("reach", 3.0))
        cooldown = float(opts.get("cooldown", 0.5))
        max_dist = float(opts.get("maxDistance", 32.0))
        goto_timeout = float(opts.get("goto_timeout", 5.0))
        swing = bool(opts.get("swing", True))

        async def run() -> None:
            while self._running:
                t = target if target is not None else self.nearest_target(
                    max_dist, **opts
                )
                if t is None:
                    await asyncio.sleep(0.25)
                    continue
                self.target = t
                self.bot.emit("target", t)
                while self._running and self._is_valid(t, max_dist):
                    entity = self.bot.entity
                    if entity is None:
                        break
                    dist = entity.position.distance_to(t.position)
                    if dist > reach:
                        arrived = await self.bot.goto(
                            t.position, timeout=goto_timeout
                        )
                        if not arrived:
                            break  # unreachable; reacquire
                        continue
                    await self.bot.actions.attack(t, swing=swing)
                    await asyncio.sleep(cooldown)
                self.target = None
                if target is not None:
                    break  # explicit single target: one engagement
            self.bot.emit("stopped")

        self._task = asyncio.ensure_future(run())
        try:
            await self._task
        except asyncio.CancelledError:
            if self._running:
                raise
        finally:
            self._running = False
            self._task = None

    def _is_valid(self, t: Entity, max_dist: float) -> bool:
        if not self._running:
            return False
        if self.bot.entities.get(t.id) is not t:
            return False
        if t.health is not None and t.health <= 0:
            return False
        entity = self.bot.entity
        return not (
            entity is not None
            and entity.position.distance_to(t.position) > max_dist * 2
        )

    async def stop(self) -> None:
        """Stop the combat loop and any in-progress approach."""
        self._running = False
        with contextlib.suppress(Exception):
            await self.bot.pathfinder.stop()
        task = self._task
        if task is not None and not task.done():
            # The loop exits on its own once _running is False and any
            # in-progress goto is interrupted by pathfinder.stop().
            with contextlib.suppress(Exception):
                await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        self.target = None
