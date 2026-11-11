"""Container windows: chests, furnaces, crafting tables, etc.

Tracks every open window's slots and state id, and sends ``window_click``
transactions. For container-type windows the player inventory always
occupies the **last 36 slots** of the window's slot array (27 main +
9 hotbar), so the container section is everything before that.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..exceptions import InventoryError
from ..inventory.item import Item

if TYPE_CHECKING:
    from ..bot import LeafishBot

__all__ = ["ContainerModule", "SimpleClick", "WindowState"]

_STATE_TIMEOUT = 1.0


@dataclass
class WindowState:
    """Server-authoritative snapshot of one open window."""

    window_id: int
    title: str | None = None
    inventory_type: int | None = None
    slots: dict[int, Item] = field(default_factory=dict)
    state_id: int = 0
    player_offset: int | None = None
    """Index of the first player-inventory slot (len(items) - 36)."""

    @property
    def size(self) -> int:
        if self.player_offset is not None:
            return self.player_offset + 36
        return max(self.slots, default=-1) + 1

    def container_slots(self) -> range:
        end = self.player_offset if self.player_offset is not None else self.size
        return range(0, max(0, end))

    def player_slots(self) -> range:
        start = self.player_offset if self.player_offset is not None else self.size - 36
        return range(max(0, start), self.size)


class SimpleClick:
    """Convenience left/right mouse clicks in the player inventory window."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot

    async def left_mouse(self, slot: int) -> None:
        """Left-click (pick up / place) *slot* in window 0."""
        await self.bot.containers.click(0, slot, button=0, mode=0)

    async def right_mouse(self, slot: int) -> None:
        """Right-click (place one / pick half) *slot* in window 0."""
        await self.bot.containers.click(0, slot, button=1, mode=0)


class ContainerModule:
    """Manages open windows other than the player inventory (window 0)."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self.windows: dict[int, WindowState] = {}

    # -- queries -----------------------------------------------------------------

    def window(self, window_id: int) -> WindowState | None:
        return self.windows.get(window_id)

    def state_id(self, window_id: int) -> int:
        if window_id == 0:
            return self.bot.inventory_state_id
        win = self.windows.get(window_id)
        return win.state_id if win is not None else 0

    def open_windows(self) -> list[int]:
        return list(self.windows)

    # -- server-driven updates ------------------------------------------------------

    def open_window(self, window_id: int, title: str | None,
                    inventory_type: int | None) -> WindowState:
        win = WindowState(window_id, title=title, inventory_type=inventory_type)
        self.windows[window_id] = win
        return win

    def close_window(self, window_id: int) -> None:
        self.windows.pop(window_id, None)

    def set_state(self, window_id: int, state_id: int) -> None:
        win = self.windows.get(window_id)
        if win is not None:
            win.state_id = state_id

    def _resolve(self, item: Item | None) -> Item | None:
        if item is not None and item.item_id is not None and item.name is None:
            item.name = self.bot.world.gamedata.item_name(item.item_id)
        return item

    def update_slot(self, window_id: int, slot: int,
                    item_data: dict[str, Any]) -> None:
        win = self.windows.get(window_id)
        if win is None:
            return
        item = self._resolve(Item.from_slot(item_data, slot))
        if item is None:
            win.slots.pop(slot, None)
        else:
            win.slots[slot] = item

    def update_contents(self, window_id: int,
                        items_data: list[dict[str, Any]]) -> None:
        win = self.windows.get(window_id)
        if win is None:
            return
        win.slots.clear()
        for idx, data in enumerate(items_data):
            item = self._resolve(Item.from_slot(data, idx))
            if item is not None:
                win.slots[idx] = item
        win.player_offset = max(0, len(items_data) - 36)

    # -- actions ---------------------------------------------------------------------

    async def click(self, window_id: int, slot: int, button: int = 0,
                    mode: int = 0) -> None:
        """Send a ``window_click`` for *window_id*.

        ``mode`` 0 = normal click (button 0 pickup/place, 1 place-one/
        pick-half), 1 = shift-click, 2 = hotbar swap.
        """
        win = self.windows.get(window_id)
        if win is None and window_id != 0:
            raise InventoryError(f"Window {window_id} is not open")
        prev = self.state_id(window_id)
        await self.bot._send_play(
            "window_click",
            {
                "windowId": window_id,
                "stateId": prev,
                "slot": slot,
                "mouseButton": button,
                "mode": mode,
                "changedSlots": [],
                "cursorItem": None,
            },
        )
        await self._wait_state(window_id, prev)

    async def shift_click(self, window_id: int, slot: int) -> None:
        """Shift-click *slot* (quick-move between container and inventory)."""
        await self.click(window_id, slot, button=0, mode=1)

    async def close(self, window_id: int | None = None) -> None:
        """Close *window_id* (or the currently open window if omitted)."""
        wid = self.bot.current_window_id if window_id is None else window_id
        if wid is None:
            return
        await self.bot._send_play("close_window", {"windowId": wid})
        self.windows.pop(wid, None)

    async def open_container(self, reference_block,
                             timeout: float = 5.0) -> int | None:
        """Right-click *reference_block* and wait for the server to open
        a window. Returns the new window id, or ``None`` on timeout."""
        before = set(self.windows)
        await self.bot.interact_block(reference_block)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            new = [w for w in self.windows if w not in before]
            if new:
                return new[0]
            await asyncio.sleep(0.05)
        return None

    # -- bulk transfers ---------------------------------------------------------

    async def deposit_all(self, window_id: int,
                          name: str | None = None) -> int:
        """Shift-click every matching player-section slot into the
        container. Returns the number of slots moved."""
        win = self.windows.get(window_id)
        if win is None:
            raise InventoryError(f"Window {window_id} is not open")
        moved = 0
        for slot in list(win.player_slots()):
            item = win.slots.get(slot)
            if item is None or item.empty:
                continue
            if name is not None and item.name != name:
                continue
            await self.shift_click(window_id, slot)
            moved += 1
        return moved

    async def withdraw(self, window_id: int, name: str,
                       count: int | None = None) -> int:
        """Shift-click container slots holding *name* into the player
        section until *count* items (or all, when ``None``) moved.
        Returns items moved."""
        win = self.windows.get(window_id)
        if win is None:
            raise InventoryError(f"Window {window_id} is not open")
        moved = 0
        for slot in list(win.container_slots()):
            if count is not None and moved >= count:
                break
            item = win.slots.get(slot)
            if item is None or item.empty or item.name != name:
                continue
            want = item.count if count is None else min(
                item.count, count - moved)
            await self.shift_click(window_id, slot)
            moved += want
        return moved

    async def _wait_state(self, window_id: int, prev: int,
                          timeout: float = _STATE_TIMEOUT) -> None:
        deadline = time.monotonic() + timeout
        while self.state_id(window_id) == prev:
            if time.monotonic() >= deadline:
                return
            await asyncio.sleep(0.02)
