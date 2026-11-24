"""Furnace smelting: move items into a furnace window and collect output.

Furnaces are container windows with three slots — input (0), fuel (1),
output (2) — followed by the 36 player-inventory slots. The server is
authoritative for *what* smelts into *what* and how long it takes, so
this module only moves items and waits for the output slot.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from ..exceptions import InventoryError

if TYPE_CHECKING:
    from ..bot import LeafishBot
    from .windows import FurnaceWindow

#: Items that burn as furnace fuel, best-first.
_FUEL_NAMES = (
    "coal", "charcoal", "coal_block", "blaze_rod", "lava_bucket",
    "dried_kelp_block", "bamboo", "stick",
)

_OUTPUT_TIMEOUT = 120.0


class SmeltingModule:
    """Drives furnace/blast-furnace/smoker windows."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot

    # -- queries -----------------------------------------------------------------

    def open_furnace_window(self, window_id: int | None = None) -> FurnaceWindow | None:
        """Return the typed view of an open furnace-type window."""
        from .windows import FurnaceWindow

        windows = self.bot.containers.windows
        if window_id is not None:
            win = windows.get(window_id)
            if win is None:
                return None
            view = self.bot.containers.window_view(window_id)
            return view if isinstance(view, FurnaceWindow) else None
        for wid in windows:
            view = self.bot.containers.window_view(wid)
            if isinstance(view, FurnaceWindow):
                return view
        return None

    # -- actions -----------------------------------------------------------------

    async def smelt(self, item_name: str, count: int = 1, *,
                    fuel: str | None = None,
                    block=None,
                    window_id: int | None = None,
                    timeout: float = _OUTPUT_TIMEOUT) -> int:
        """Smelt *count* of *item_name* in an open (or *block*-opened)
        furnace window. Returns the number of output items collected.

        *fuel* names the fuel item; when omitted the first available
        fuel from :data:`_FUEL_NAMES` is used.
        """
        win = await self._ensure_window(block, window_id)
        if win is None:
            raise InventoryError(
                "No furnace window is open; right-click a furnace first"
            )
        made = 0
        deadline = time.monotonic() + timeout
        while made < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await self._ensure_slot(win, win.input_slot, item_name)
            fuel_name = fuel or self._find_fuel(win)
            if fuel_name is None:
                raise InventoryError("No furnace fuel in inventory")
            await self._ensure_slot(win, win.fuel_slot, fuel_name)
            # Wait for the server to produce output.
            out_deadline = time.monotonic() + remaining
            while True:
                out = win.output_item
                if out is not None and not out.empty:
                    break
                if time.monotonic() >= out_deadline:
                    raise InventoryError(
                        "Furnace produced no output in time"
                    )
                await asyncio.sleep(0.1)
            await self._take_output(win)
            made += 1
        return made

    # -- helpers -------------------------------------------------------------------

    async def _ensure_window(self, block, window_id) -> FurnaceWindow | None:
        if block is not None:
            view = await self.bot.open_furnace(block)
            if view is None:
                return None
            return view
        return self.open_furnace_window(window_id)

    def _find_fuel(self, win: FurnaceWindow) -> str | None:
        for name in _FUEL_NAMES:
            for slot in win.player_slots:
                item = win.item(slot)
                if item is not None and not item.empty and item.name == name:
                    return name
        return None

    async def _ensure_slot(self, win: FurnaceWindow, dst: int, name: str) -> None:
        """Ensure container slot *dst* holds one of *name*."""
        item = win.item(dst)
        if item is not None and not item.empty:
            if item.name == name:
                return
            await self._clear_slot(win, dst)
        src = self._find_player_item(win, name)
        if src is None:
            raise InventoryError(f"Missing '{name}' for smelting")
        await win.click(src)                 # whole stack -> cursor
        await win.click(dst, button=1)       # place exactly one
        await win.click(src)                 # return remainder

    def _find_player_item(self, win: FurnaceWindow, name: str) -> int | None:
        for slot in win.player_slots:
            item = win.item(slot)
            if item is not None and not item.empty and item.name == name:
                return slot
        return None

    async def _clear_slot(self, win: FurnaceWindow, slot: int) -> None:
        await win.click(slot)
        for p in win.player_slots:
            it = win.item(p)
            if it is None or it.empty:
                await win.click(p)
                return
        raise InventoryError("No player-inventory space to clear furnace slot")

    async def _take_output(self, win: FurnaceWindow) -> None:
        """Take the output stack and stash it in the player section."""
        out = win.output_item
        out_name = out.name if out is not None else None
        await win.click(win.output_slot)      # output -> cursor
        # Prefer merging into a same-name player stack, else an empty slot.
        for slot in win.player_slots:
            it = win.item(slot)
            if out_name is not None and it is not None and not it.empty \
                    and it.name == out_name:
                await win.click(slot)
                return
        for slot in win.player_slots:
            it = win.item(slot)
            if it is None or it.empty:
                await win.click(slot)
                return
