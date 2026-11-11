"""Fishing: equip a rod, cast, wait for a bite, reel in.

Bite detection is best-effort: the vanilla server signals a bite through
the bobber's movement and splash effects rather than a dedicated packet,
so any of ``entity_move``/``entity_update`` on the bobber, an
``entity_status`` for it, or a splash/fishing sound/particle event counts
as a bite.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ..entities.entity import Entity
from ..exceptions import FishingError
from ..utils.vectors import Vec3

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.fishing")


class FishingModule:
    """Simple fishing-rod automation."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self.bobber: Entity | None = None
        self._sequence = 0

    # -- public API -----------------------------------------------------------------

    async def fish(self, timeout: float = 60.0, **opts: Any) -> bool:
        """Cast the rod and catch one fish.

        Returns ``True`` when a catch was reeled in, ``False`` on timeout
        or when no bobber/bite was observed. Raises
        :class:`FishingError` when prerequisites (water, rod) are missing.
        """
        bobber_timeout = float(opts.get("bobber_timeout", 15.0))
        bite_timeout = float(opts.get("bite_timeout", timeout))

        positions = self._find_water(opts)
        pos = positions[0] if positions else None
        if pos is None:
            raise FishingError("No water found within range")

        await self.bot.actions.equip(opts.get("rod", "fishing_rod"), "hand")

        # Face the water and cast.
        await self.bot.look_at(Vec3(pos.x + 0.5, pos.y + 1.0, pos.z + 0.5))
        await self._use_item()

        bobber = await self._wait_bobber(bobber_timeout)
        if bobber is None:
            await self._use_item()  # reel in the empty cast
            return False
        self.bobber = bobber
        try:
            bit = await self._wait_bite(bite_timeout)
            if not bit:
                log.debug("fish: no bite within %.1fs", bite_timeout)
                await self._reel_in()
                return False
            self.bot.emit("fish_bite", bobber)
            await self._use_item()  # reel in
            await self._wait_loot(float(opts.get("loot_timeout", 5.0)))
            return True
        finally:
            self.bobber = None

    async def reel_in(self) -> None:
        """Reel in an active cast without waiting for a bite."""
        await self._reel_in()

    # -- internals ---------------------------------------------------------------------

    def _find_water(self, opts: dict[str, Any]):
        max_dist = int(opts.get("max_distance", 16))
        count = int(opts.get("count", 1))
        return self.bot.find_blocks("water", max_distance=max_dist, count=count)

    async def _use_item(self) -> None:
        entity = self.bot.entity
        yaw = entity.yaw if entity is not None else 0.0
        pitch = entity.pitch if entity is not None else 0.0
        self._sequence = (self._sequence + 1) & 0x7FFFFFFF
        await self.bot._send_play(
            "use_item",
            {
                "hand": 0,
                "sequence": self._sequence,
                "rotation": {"x": yaw, "y": pitch},
            },
        )

    async def _wait_bobber(self, timeout: float) -> Entity | None:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            for e in self.bot.entities.all():
                t = e.type
                if isinstance(t, str) and "fishing_bobber" in t:
                    return e
            # Also catch a bobber that spawned before we started waiting.
            await asyncio.sleep(0.05)
        return None

    async def _wait_bite(self, timeout: float) -> bool:
        bobber = self.bobber
        if bobber is None:
            return False
        ev = asyncio.Event()
        grace = asyncio.get_running_loop().time() + 0.5

        def on_move(e: Entity) -> None:
            if e.id == bobber.id and \
                    asyncio.get_running_loop().time() >= grace:
                ev.set()

        def on_bobber_status(entity_id: int, _status: int) -> None:
            if entity_id == bobber.id:
                ev.set()

        def on_splash(*args: Any) -> None:
            text = " ".join(str(a) for a in args).lower()
            if "splash" in text or "fishing" in text:
                ev.set()

        subs = [
            ("entity_move", on_move),
            ("entity_update", on_move),
            ("entity_status", on_bobber_status),
            ("sound_effect", on_splash),
            ("entity_sound_effect", on_splash),
            ("world_particles", on_splash),
        ]
        for event, handler in subs:
            self.bot.on(event, handler)
        try:
            await asyncio.wait_for(ev.wait(), timeout)
            return True
        except TimeoutError:
            return False
        finally:
            for event, handler in subs:
                self.bot.off(event, handler)

    async def _reel_in(self) -> None:
        await self._use_item()

    async def _wait_loot(self, timeout: float) -> None:
        """Brief wait for the catch to arrive as an item entity."""
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            for e in self.bot.entities.all():
                if type(e).__name__ == "ItemEntity":
                    return
            await asyncio.sleep(0.1)
