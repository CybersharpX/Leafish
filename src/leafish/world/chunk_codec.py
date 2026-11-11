"""Decoder for Minecraft chunk-column section data (1.21.5+ wire format).

The ``chunkData`` byte array of the chunk packet is *not* length-prefixed per
section: it contains exactly ``world_height / 16`` chunk sections, ordered
bottom-to-top from ``min_section_y``. Each section stores a block-state count,
a fluid count, a paletted container of 4096 block states and a paletted
container of 64 biome cells.

Paletted containers come in three forms (see the "Paletted Container"
structure in the Java Edition protocol chunk-format documentation):

* ``bits == 0``: single-valued — one VarInt global palette id, no data array.
* ``bits <= max_indirect_bits``: indirect — a VarInt-length-prefixed palette of
  global ids followed by a packed index array.
* otherwise: direct — the packed array holds global palette ids directly and
  no palette is present on the wire.

Packed arrays store ``bits``-wide unsigned integers, ``values_per_long =
64 // bits`` per 64-bit big-endian long; entries never span longs. Since
1.21.5 the long count is *not* sent — it is computed from the capacity.
"""

from __future__ import annotations

import math
import struct
from collections.abc import Iterator

BLOCK_SECTION_VOLUME = 16 * 16 * 16  # 4096
BIOME_SECTION_VOLUME = 4 * 4 * 4  # 64

MAX_INDIRECT_BITS_BLOCKS = 8
MAX_INDIRECT_BITS_BIOMES = 3


class ChunkDecodeError(ValueError):
    """Raised when chunk section data cannot be decoded."""


class _Reader:
    """Cursor over the chunkData byte array (big-endian primitives)."""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def read_u8(self) -> int:
        if self.pos + 1 > len(self.data):
            raise ChunkDecodeError("unexpected end of chunk data")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def read_i16(self) -> int:
        if self.pos + 2 > len(self.data):
            raise ChunkDecodeError("unexpected end of chunk data")
        (value,) = struct.unpack_from(">h", self.data, self.pos)
        self.pos += 2
        return value

    def read_u64(self) -> int:
        if self.pos + 8 > len(self.data):
            raise ChunkDecodeError("unexpected end of chunk data")
        (value,) = struct.unpack_from(">Q", self.data, self.pos)
        self.pos += 8
        return value

    def read_varint(self) -> int:
        result = 0
        shift = 0
        while True:
            if self.pos >= len(self.data):
                raise ChunkDecodeError("unexpected end of chunk data")
            byte = self.data[self.pos]
            self.pos += 1
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                return result
            shift += 7
            if shift > 35:
                raise ChunkDecodeError("VarInt too long")


def _unpack_long_values(
    longs: list[int], bits: int, capacity: int
) -> Iterator[int]:
    """Yield packed values; each 64-bit long holds ``64 // bits`` entries."""
    if bits <= 0:
        raise ChunkDecodeError("bits per entry must be > 0")
    values_per_long = 64 // bits
    mask = (1 << bits) - 1
    produced = 0
    for long_value in longs:
        for k in range(values_per_long):
            if produced >= capacity:
                return
            yield (long_value >> (k * bits)) & mask
            produced += 1


class PalettedContainer:
    """Decoded paletted container (blocks or biomes) for one chunk section."""

    __slots__ = ("bits", "capacity", "longs", "palette")

    def __init__(
        self,
        capacity: int,
        bits: int,
        palette: list[int] | None,
        longs: list[int],
    ) -> None:
        self.capacity = capacity
        self.bits = bits
        # ``palette is None`` means the direct (global) format.
        self.palette = palette
        self.longs = longs

    @property
    def is_single(self) -> bool:
        return self.bits == 0

    def get(self, index: int) -> int:
        """Return the global palette id at *index*."""
        if self.bits == 0:
            return self.palette[0] if self.palette else 0
        values_per_long = 64 // self.bits
        long_index = index // values_per_long
        if long_index >= len(self.longs):
            return 0
        shift = (index % values_per_long) * self.bits
        value = (self.longs[long_index] >> shift) & ((1 << self.bits) - 1)
        if self.palette is not None:
            if value >= len(self.palette):
                return 0
            return self.palette[value]
        return value

    def values(self) -> Iterator[int]:
        for i in range(self.capacity):
            yield self.get(i)

    def to_list(self) -> list[int]:
        return [self.get(i) for i in range(self.capacity)]


def _decode_container(
    reader: _Reader, capacity: int, max_indirect_bits: int
) -> PalettedContainer:
    bits = reader.read_u8()
    if bits == 0:
        # Single-valued palette; no data array on the wire.
        value = reader.read_varint()
        return PalettedContainer(capacity, 0, [value], [])
    if bits > 16:
        raise ChunkDecodeError(f"bits per entry too large: {bits}")

    if bits > max_indirect_bits:
        # Direct format: packed global palette ids, no palette on the wire.
        values_per_long = 64 // bits
        long_count = math.ceil(capacity / values_per_long)
        longs = [reader.read_u64() for _ in range(long_count)]
        return PalettedContainer(capacity, bits, None, longs)

    # Indirect format: VarInt-length-prefixed palette then packed indices.
    palette_length = reader.read_varint()
    palette = [reader.read_varint() for _ in range(palette_length)]
    values_per_long = 64 // bits
    long_count = math.ceil(capacity / values_per_long)
    longs = [reader.read_u64() for _ in range(long_count)]
    return PalettedContainer(capacity, bits, palette, longs)


class ChunkSectionData:
    """Decoded contents of one 16x16x16 chunk section."""

    __slots__ = ("biomes", "block_states", "fluid_count", "non_air_count", "y")

    def __init__(
        self,
        y: int,
        non_air_count: int,
        fluid_count: int,
        block_states: PalettedContainer,
        biomes: PalettedContainer,
    ) -> None:
        self.y = y
        self.non_air_count = non_air_count
        self.fluid_count = fluid_count
        self.block_states = block_states
        self.biomes = biomes


def decode_chunk_sections(
    data: bytes,
    *,
    section_count: int,
    min_section_y: int,
    has_fluid_count: bool = True,
) -> list[ChunkSectionData]:
    """Decode the ``chunkData`` buffer into per-section containers.

    ``section_count`` is ``world_height // 16`` and ``min_section_y`` is
    ``min_y // 16`` for the current dimension. Sections are ordered
    bottom-to-top.
    """
    reader = _Reader(data)
    sections: list[ChunkSectionData] = []
    for i in range(section_count):
        if reader.remaining() < 4:
            raise ChunkDecodeError(
                f"chunk data ended after {i} of {section_count} sections"
            )
        section_y = min_section_y + i
        non_air_count = reader.read_i16()
        fluid_count = reader.read_i16() if has_fluid_count else 0
        blocks = _decode_container(
            reader, BLOCK_SECTION_VOLUME, MAX_INDIRECT_BITS_BLOCKS
        )
        biomes = _decode_container(
            reader, BIOME_SECTION_VOLUME, MAX_INDIRECT_BITS_BIOMES
        )
        sections.append(
            ChunkSectionData(section_y, non_air_count, fluid_count, blocks, biomes)
        )
    return sections
