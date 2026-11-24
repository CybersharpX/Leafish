"""Unit tests for world biome lookups and multi-state find_blocks."""

from unittest.mock import MagicMock

from leafish.data.registry import get_gamedata
from leafish.utils.vectors import BlockPos
from leafish.world.world import Chunk, ChunkSection, World


def test_gamedata_block_state_ids():
    gd = get_gamedata("1.21.11")
    # oak_log has multiple orientations (axis=y, axis=x, axis=z)
    state_ids = gd.block_state_ids("oak_log")
    assert len(state_ids) >= 3


def test_world_biome_at():
    bot = MagicMock()
    world = World(bot, "1.21.11")

    chunk = Chunk(0, 0)
    section = ChunkSection(4)
    # Mock biomes palette
    section.biomes = MagicMock()
    section.biomes.get.return_value = 1  # e.g. plains
    chunk.sections[4] = section
    world.chunks[(0, 0)] = chunk

    # Block position at (5, 64, 5) -> chunk (0, 0), section 4
    biome_info = world.biome_at(BlockPos(5, 64, 5))
    assert biome_info is not None
    assert "name" in biome_info
