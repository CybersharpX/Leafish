"""Crafting recipe-index tests (no server needed)."""

from typing import Any, cast

from leafish.data.registry import get_gamedata
from leafish.modules.crafting import CraftingModule


class _World:
    def __init__(self) -> None:
        self.gamedata = get_gamedata("1.21.11")


class _Inv:
    def __init__(self, counts: dict[str, int] | None = None) -> None:
        self._counts = counts or {}

    def count(self, name: str) -> int:
        return self._counts.get(name, 0)

    def slot(self, index: int):
        return None


class _Bot:
    def __init__(self, counts: dict[str, int] | None = None) -> None:
        self.world = _World()
        self.inventory = _Inv(counts)
        self.inventory_state_id = 0


def _module(counts: dict[str, int] | None = None) -> CraftingModule:
    return CraftingModule(cast(Any, _Bot(counts)))


def test_recipes_index_has_entries():
    cm = _module()
    recipes = cm.recipes_for("crafting_table")
    assert recipes, "expected crafting_table recipes in 1.21.11 data"
    # Every variant is a 2x2 (or smaller) planks recipe.
    assert all(not r.needs_table for r in recipes)
    assert all(r.needs for r in recipes)


def test_stick_recipe_shape():
    cm = _module()
    sticks = cm.recipes_for("stick")
    assert sticks
    rec = sticks[0]
    # Vertical 1x2 shape of some planks type.
    assert len(rec.shape) == 2
    assert all(len(row) == 1 for row in rec.shape)
    assert all(row[0] is not None for row in rec.shape)


def test_find_recipe_requires_ingredients():
    cm = _module()  # empty inventory
    assert cm.find_recipe("crafting_table") is None


def test_find_recipe_with_ingredients():
    # All wood variants exist; give enough of one type.
    cm = _module({"oak_planks": 8})
    rec = cm.find_recipe("crafting_table")
    assert rec is not None
    assert rec.result_name == "crafting_table"
    assert rec.needs == {"oak_planks": 4}


def test_table_only_recipes_flagged():
    cm = _module({"diamond": 3, "stick": 2})
    # diamond_pickaxe needs a 3x3 grid -> needs_table, never returned.
    recipes = cm.recipes_for("diamond_pickaxe")
    assert recipes
    assert all(r.needs_table for r in recipes)
    assert cm.find_recipe("diamond_pickaxe") is None
