"""Anvil interactions: repair and combining via the anvil window.

An anvil window has three container slots — tool (0), material (1),
result (2) — followed by the 36 player-inventory slots. The server is
authoritative for whether a repair is possible and what it costs in
levels; this module only moves items and takes the result.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from ..exceptions import InventoryError

if TYPE_CHECKING:
    from ..bot import LeafishBot
    from ..modules.containers import WindowState

_RESULT_TIMEOUT = 5.0


class AnvilModule:
    """Drives item repair/rename through an open anvil window."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot

    # -- queries -----------------------------------------------------------------

    def find_window(self, window_id: int | None = None) -> WindowState | None:
        """Locate an open anvil window.

        Anvils have 3 container slots (player inventory offset 3, 39
        total slots); the window title distinguishes them from furnaces
        and other 3-slot containers.
        """
        windows = self.bot.containers.windows
        if window_id is not None:
            return windows.get(window_id)
        for win in windows.values():
            if win.player_offset == 3 and win.size == 39 and \
                    (win.title or "").lower().find("anvil") >= 0:
                return win
        return None

    # -- actions -----------------------------------------------------------------

    async def repair(self, item_name: str,
                     material_name: str | None = None,
                     window_id: int | None = None) -> int:
        """Place *item_name* (+ optional *material_name*) in an anvil and
        take the result. Returns the number of result items taken (0 or 1).

        Raises :class:`InventoryError` when no anvil window is open or the
        ingredients are missing.
        """
        win = self.find_window(window_id)
        if win is None:
            raise InventoryError(
                "No anvil window is open; right-click an anvil first"
            )
        wid = win.window_id
        await self._ensure_slot(wid, win, 0, item_name)
        if material_name is not None:
            await self._ensure_slot(wid, win, 1, material_name)
        # Wait for the server to populate the result slot.
        deadline = time.monotonic() + _RESULT_TIMEOUT
        result_name = None
        while True:
            result = win.slots.get(2)
            if result is not None and not result.empty:
                result_name = result.name
                break
            if time.monotonic() >= deadline:
                raise InventoryError(
                    "Anvil produced no result (invalid repair or"
                    " insufficient materials)"
                )
            await asyncio.sleep(0.05)
        await self.bot.containers.click(wid, 2)
        await self._deposit_cursor(win, result_name)
        return 1

    # -- helpers -------------------------------------------------------------------

    async def _ensure_slot(self, wid: int, win: WindowState, dst: int,
                           name: str) -> None:
        """Ensure container slot *dst* holds one of *name*, moving a
        single item from the player section if needed."""
        item = win.slots.get(dst)
        if item is not None and not item.empty:
            if item.name == name:
                return
            await self._clear_slot(wid, win, dst)
        src = self._find_player_item(win, name)
        if src is None:
            raise InventoryError(f"Missing '{name}' for anvil repair")
        # Pick up the stack, place exactly one, return the remainder.
        await self.bot.containers.click(wid, src)
        await self.bot.containers.click(wid, dst, button=1)
        await self.bot.containers.click(wid, src)

    def _find_player_item(self, win: WindowState, name: str) -> int | None:
        for slot in win.player_slots():
            item = win.slots.get(slot)
            if item is not None and not item.empty and item.name == name:
                return slot
        return None

    async def _clear_slot(self, wid: int, win: WindowState, slot: int) -> None:
        """Move whatever is in container *slot* back to the player section."""
        await self.bot.containers.click(wid, slot)  # pickup to cursor
        for p in win.player_slots():
            it = win.slots.get(p)
            if it is None or it.empty:
                await self.bot.containers.click(wid, p)
                return
        raise InventoryError("No player-inventory space to clear anvil slot")

    async def _deposit_cursor(self, win: WindowState,
                              name: str | None = None) -> None:
        """Place the carried item into the player section, preferring a
        same-name stack with room, then any empty slot."""
        wid = win.window_id
        if name is not None:
            for slot in win.player_slots():
                it = win.slots.get(slot)
                if it is not None and not it.empty and it.name == name:
                    await self.bot.containers.click(wid, slot)
                    return
        for slot in win.player_slots():
            it = win.slots.get(slot)
            if it is None or it.empty:
                await self.bot.containers.click(wid, slot)
                return
