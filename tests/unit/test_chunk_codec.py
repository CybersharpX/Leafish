"""Tests for the 1.21.5+ chunk section decoder."""

from __future__ import annotations

import pytest

from leafish.world.chunk_codec import (
    BIOME_SECTION_VOLUME,
    BLOCK_SECTION_VOLUME,
    ChunkDecodeError,
    decode_chunk_sections,
)
from tests.chunkdata import (
    container_direct,
    container_indirect,
    container_single,
)
from tests.chunkdata import (
    section as encode_section,
)


def _decode_one(data: bytes):
    (sec,) = decode_chunk_sections(data, section_count=1, min_section_y=0)
    return sec


class TestPalettedContainers:
    def test_single_value(self):
        sec = _decode_one(encode_section(container_single(42)))
        assert sec.block_states.get(0) == 42
        assert sec.block_states.get(4095) == 42
        assert sec.biomes.get(0) == 0

    def test_indirect_palette(self):
        # Palette [10, 20]; first 16 cells are index 1 (-> 20), rest index 0.
        indices = [1] * 16 + [0] * (4096 - 16)
        container = container_indirect([10, 20], indices, 4)
        sec = _decode_one(encode_section(container))
        assert sec.block_states.get(0) == 20
        assert sec.block_states.get(15) == 20
        assert sec.block_states.get(16) == 10
        assert sec.block_states.get(4095) == 10

    def test_direct_palette(self):
        values = [100 + (i % 7) for i in range(BLOCK_SECTION_VOLUME)]
        sec = _decode_one(encode_section(container_direct(values, 15)))
        for i in (0, 1, 100, 4095):
            assert sec.block_states.get(i) == values[i]

    def test_biome_indirect(self):
        container = container_indirect(
            [5, 9, 12], [i % 3 for i in range(BIOME_SECTION_VOLUME)], 2
        )
        sec = _decode_one(encode_section(container_single(0), container))
        assert sec.biomes.get(0) == 5
        assert sec.biomes.get(1) == 9
        assert sec.biomes.get(2) == 12
        assert sec.biomes.get(63) == 5

    def test_biome_direct(self):
        values = [i % 50 for i in range(BIOME_SECTION_VOLUME)]
        sec = _decode_one(
            encode_section(container_single(0), container_direct(values, 6))
        )
        assert sec.biomes.get(10) == values[10]

    def test_multi_section_ordering(self):
        data = encode_section(container_single(7)) + encode_section(
            container_single(9)
        )
        sections = decode_chunk_sections(data, section_count=2, min_section_y=-4)
        assert [s.y for s in sections] == [-4, -3]
        assert sections[0].block_states.get(0) == 7
        assert sections[1].block_states.get(0) == 9

    def test_truncated_data_raises(self):
        with pytest.raises(ChunkDecodeError):
            decode_chunk_sections(b"\x00\x00", section_count=24, min_section_y=-4)

    def test_bits_too_large_raises(self):
        with pytest.raises(ChunkDecodeError):
            _decode_one(encode_section(b"\x11"))  # bits=17, then nothing
