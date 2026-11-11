"""Farming module tests with a stubbed world."""

from typing import Any, cast

from leafish.modules.farming import CROPS, FarmingModule
from leafish.utils.vectors import BlockPos
from leafish.world.block import Block


def _crop(name: str, x: int, age: int) -> Block:
    return Block(
        state_id=1, block_id=1, name=name,
        position=BlockPos(x, 64, 0),
        state_properties={"age": str(age)},
    )


def _air(x: int) -> Block:
    return Block(
        state_id=0, block_id=0, name="air",
        position=BlockPos(x, 64, 0), bounding_box="empty",
    )


class _World:
    def __init__(self, blocks: dict[tuple[int, int, int], Block]) -> None:
        self._blocks = blocks

    def block_at(self, pos) -> Block | None:
        bp = pos if isinstance(pos, BlockPos) else pos.floor()
        return self._blocks.get((bp.x, bp.y, bp.z))


class _Bot:
    def __init__(self, blocks: dict[tuple[int, int, int], Block],
                 find: dict[str, list[BlockPos]]) -> None:
        self.world = _World(blocks)
        self._find = find
        self.entity = None

    def find_blocks(self, names, **kwargs):
        if isinstance(names, str):
            names = [names]
        out = []
        for n in names:
            out.extend(self._find.get(n, []))
        return out

    def block_at(self, pos):
        return self.world.block_at(pos)


def _module(blocks, find) -> FarmingModule:
    return FarmingModule(cast(Any, _Bot(blocks, find)))


def test_mature_crops_filters_by_age():
    blocks = {
        (0, 64, 0): _crop("wheat", 0, 7),   # mature
        (1, 64, 0): _crop("wheat", 1, 3),   # growing
        (2, 64, 0): _crop("beetroots", 2, 3),  # mature (max 3)
        (3, 64, 0): _crop("beetroots", 3, 2),  # growing
    }
    find = {
        "wheat": [BlockPos(0, 64, 0), BlockPos(1, 64, 0)],
        "beetroots": [BlockPos(2, 64, 0), BlockPos(3, 64, 0)],
    }
    fm = _module(blocks, find)
    crops = fm.mature_crops()
    xs = sorted(b.position.x for b in crops)
    assert xs == [0, 2]


def test_mature_crops_names_filter():
    blocks = {
        (0, 64, 0): _crop("wheat", 0, 7),
        (1, 64, 0): _crop("carrots", 1, 7),
    }
    find = {
        "wheat": [BlockPos(0, 64, 0)],
        "carrots": [BlockPos(1, 64, 0)],
    }
    fm = _module(blocks, find)
    crops = fm.mature_crops(names=["carrots"])
    assert [b.name for b in crops] == ["carrots"]


def test_crop_table_covers_vanilla_crops():
    assert set(CROPS) == {"wheat", "carrots", "potatoes", "beetroots"}
    assert CROPS["beetroots"][1] == 3
