"""Crafting: recipe lookup and 2x2 inventory-grid crafting via window clicks.

Recipes come from the vendored ``recipes.json`` (keyed by result item id,
variants for each ingredient combination). Crafting uses the player
inventory window (id 0): the 2x2 grid lives in slots 1-4 and the result in
slot 0. Ingredients are moved with mode-0 clicks; recipes that need the
3x3 crafting-table grid are recognized but rejected for now.

Click predictions (``changedSlots``/``cursorItem``) are sent empty; the
server remains authoritative and resyncs via ``window_items``/
``set_slot``. A state-id wait after every click keeps the client in sync.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..exceptions import CraftingError
from ..inventory.item import Item

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.crafting")

#: 2x2 crafting grid slots in the player inventory window (row-major).
GRID_SLOTS = (1, 2, 3, 4)
RESULT_SLOT = 0
#: Slots usable as ingredient sources / result deposit targets
#: (main inventory 9-35 + hotbar 36-44; avoids grid/armor/offhand).
STORAGE_SLOTS = range(9, 45)

_STATE_TIMEOUT = 1.0


@dataclass
class Recipe:
    """A single craftable recipe variant."""

    result_name: str
    result_count: int
    #: Normalized shape rows of item names (``None`` = empty cell), or
    #: empty for shapeless recipes.
    shape: tuple[tuple[str | None, ...], ...] = ()
    #: item name -> number of grid cells required per craft.
    needs: dict[str, int] = field(default_factory=dict)
    needs_table: bool = False


class CraftingModule:
    """Finds recipes and crafts them through inventory-window clicks."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self._index: dict[str, list[Recipe]] | None = None
        self._cursor: Item | None = None

    # -- recipe data -------------------------------------------------------------

    def _gamedata(self):
        return self.bot.world.gamedata

    def _ensure_index(self) -> dict[str, list[Recipe]]:
        if self._index is not None:
            return self._index
        idx: dict[str, list[Recipe]] = {}
        gd = self._gamedata()
        for _rid, variants in gd.recipes().items():
            for var in variants or []:
                if not isinstance(var, dict):
                    continue
                res = var.get("result") or {}
                rname = gd.item_name(res.get("id"))
                if not rname:
                    continue
                rec = self._variant_to_recipe(
                    rname, int(res.get("count") or 1), var
                )
                if rec is not None:
                    idx.setdefault(rname, []).append(rec)
        self._index = idx
        return idx

    def _variant_to_recipe(self, rname: str, rcount: int, var: dict) -> Recipe | None:
        gd = self._gamedata()
        if "inShape" in var:
            grid = var["inShape"] or []
            cells = [
                (r, c, gid)
                for r, row in enumerate(grid)
                for c, gid in enumerate(row)
                if gid is not None
            ]
            if not cells:
                return None
            r0 = min(r for r, _, _ in cells)
            r1 = max(r for r, _, _ in cells)
            c0 = min(c for _, c, _ in cells)
            c1 = max(c for _, c, _ in cells)
            h, w = r1 - r0 + 1, c1 - c0 + 1
            shape: list[tuple[str | None, ...]] = []
            needs: dict[str, int] = {}
            for r in range(r0, r1 + 1):
                row: list[str | None] = []
                for c in range(c0, c1 + 1):
                    gid = grid[r][c] if c < len(grid[r]) else None
                    nm = gd.item_name(gid) if gid is not None else None
                    row.append(nm)
                    if nm:
                        needs[nm] = needs.get(nm, 0) + 1
                shape.append(tuple(row))
            return Recipe(
                rname, rcount, tuple(shape), needs,
                needs_table=h > 2 or w > 2,
            )
        ings = var.get("ingredients") or []
        names = [gd.item_name(g) for g in ings]
        names = [n for n in names if n]
        if not names:
            return None
        needs: dict[str, int] = {}
        for nm in names:
            needs[nm] = needs.get(nm, 0) + 1
        return Recipe(
            rname, rcount, (), needs,
            needs_table=len(names) > len(GRID_SLOTS),
        )

    # -- queries --------------------------------------------------------------------

    def recipes_for(self, item_name: str) -> list[Recipe]:
        """All recipe variants producing *item_name*."""
        return list(self._ensure_index().get(item_name, ()))

    def can_craft(self, recipe: Recipe) -> bool:
        inv = self.bot.inventory
        return all(inv.count(n) >= c for n, c in recipe.needs.items())

    def find_recipe(self, item_name: str,
                    crafting_table: bool = False) -> Recipe | None:
        """First craftable non-table recipe for *item_name*."""
        for rec in self.recipes_for(item_name):
            if rec.needs_table:
                continue  # 3x3 grid not supported yet
            if crafting_table and rec.needs_table:
                continue
            if self.can_craft(rec):
                return rec
        return None

    # -- crafting ---------------------------------------------------------------------

    async def craft(self, item_name: str, count: int = 1,
                    crafting_table: bool = False) -> int:
        """Craft *count* of *item_name* via the 2x2 inventory grid.

        Returns the number of items actually added to the inventory.
        Raises :class:`CraftingError` when no usable recipe exists or
        ingredients run out mid-craft.
        """
        recipe = self.find_recipe(item_name, crafting_table)
        if recipe is None:
            if any(r.needs_table for r in self.recipes_for(item_name)):
                raise CraftingError(
                    f"'{item_name}' requires a crafting table (3x3 grid), "
                    "which is not supported yet"
                )
            raise CraftingError(
                f"No craftable recipe for '{item_name}' "
                "(missing ingredients or unknown item)"
            )
        inv = self.bot.inventory
        start = inv.count(item_name)
        made = 0
        attempts = 0
        max_attempts = (count + recipe.result_count - 1) // recipe.result_count + 3
        while made < count and attempts < max_attempts:
            attempts += 1
            await self._fill_grid(recipe)
            result = inv.slot(RESULT_SLOT)
            if result is None or result.empty:
                log.debug("craft(%s): result slot empty", item_name)
                continue
            self._cursor = result
            await self._click(RESULT_SLOT)
            await self._deposit_cursor()
            made = inv.count(item_name) - start
        if made < count:
            raise CraftingError(
                f"Crafting '{item_name}' produced {made}/{count} items"
            )
        self.bot.emit("crafted", item_name, made)
        return made

    # -- grid management ------------------------------------------------------------

    def _grid_expectation(self, recipe: Recipe) -> dict[int, str]:
        """Map grid slot -> required item name for this recipe."""
        exp: dict[int, str] = {}
        if recipe.shape:
            for r, row in enumerate(recipe.shape):
                for c, nm in enumerate(row):
                    if nm is not None:
                        exp[1 + r * 2 + c] = nm
            return exp
        # Shapeless: distribute required cells row-major.
        i = 0
        for nm, cnt in recipe.needs.items():
            for _ in range(cnt):
                if i >= len(GRID_SLOTS):
                    break
                exp[GRID_SLOTS[i]] = nm
                i += 1
        return exp

    async def _fill_grid(self, recipe: Recipe) -> None:
        inv = self.bot.inventory
        expected = self._grid_expectation(recipe)

        # Phase 1: clear cells holding the wrong item.
        for slot in GRID_SLOTS:
            item = inv.slot(slot)
            if item is None or item.empty:
                continue
            if item.name != expected.get(slot):
                await self._click(slot)
                await self._deposit_cursor()

        # Phase 2: fill each expected cell that lacks the right item.
        # Group by name so one pickup can serve several cells.
        by_name: dict[str, list[int]] = {}
        for slot, nm in expected.items():
            item = inv.slot(slot)
            if item is None or item.empty or item.name != nm:
                by_name.setdefault(nm, []).append(slot)
        for nm, slots in by_name.items():
            for dst in slots:
                src = self._find_storage(nm)
                if src is None:
                    raise CraftingError(f"Missing ingredient '{nm}'")
                stack = inv.slot(src)
                if stack is None:
                    raise CraftingError(f"Missing ingredient '{nm}'")
                await self._click(src)              # whole stack -> cursor
                self._cursor = stack
                await self._click(dst, button=1)    # place exactly one
                cur = self._cursor
                if cur is not None:
                    cur.count -= 1
                    if cur.count <= 0:
                        self._cursor = None
                if self._cursor is not None:
                    await self._click(src)          # return remainder
                    self._cursor = None

    def _find_storage(self, name: str) -> int | None:
        inv = self.bot.inventory
        for s in STORAGE_SLOTS:
            item = inv.slot(s)
            if item is not None and not item.empty and item.name == name:
                return s
        return None

    # -- clicks -----------------------------------------------------------------------

    async def _click(self, slot: int, button: int = 0) -> None:
        prev = self.bot.inventory_state_id
        await self.bot._click_window_slot(0, slot, button=button)
        await self._wait_state(prev)

    async def _wait_state(self, prev: int, timeout: float = _STATE_TIMEOUT) -> None:
        deadline = time.monotonic() + timeout
        while self.bot.inventory_state_id == prev:
            if time.monotonic() >= deadline:
                log.debug("window state did not change within %.1fs", timeout)
                return
            await asyncio.sleep(0.02)

    def _max_stack(self, item: Item) -> int:
        if item.item_id is None:
            return 64
        data = self._gamedata().item_by_id(item.item_id)
        return int((data or {}).get("stackSize") or 64)

    async def _deposit_cursor(self) -> None:
        """Place the cursor stack into storage (merge or empty slot)."""
        cur = self._cursor
        if cur is None or cur.empty:
            self._cursor = None
            return
        inv = self.bot.inventory
        while self._cursor is not None and not self._cursor.empty:
            cur = self._cursor
            target: int | None = None
            merge_room = 0
            # Prefer merging into a same-name stack with room.
            for s in STORAGE_SLOTS:
                it = inv.slot(s)
                if it is not None and not it.empty and it.name == cur.name:
                    room = self._max_stack(it) - it.count
                    if room > 0:
                        target, merge_room = s, room
                        break
            if target is None:
                for s in STORAGE_SLOTS:
                    it = inv.slot(s)
                    if it is None or it.empty:
                        target = s
                        break
            if target is None:
                raise CraftingError("No inventory space to deposit cursor item")
            await self._click(target)
            leftover = max(0, cur.count - merge_room) if merge_room else 0
            if merge_room and leftover > 0:
                self._cursor = Item(
                    item_id=cur.item_id, name=cur.name, count=leftover,
                    components=cur.components, slot=None,
                )
            else:
                self._cursor = None
