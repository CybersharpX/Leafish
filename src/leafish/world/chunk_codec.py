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
            if shift >= 35:
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
        if self.bits == 0:
            val = self.palette[0] if self.palette else 0
            for _ in range(self.capacity):
                yield val
            return
        pal = self.palette
        if pal is not None:
            pal_len = len(pal)
            for idx in _unpack_long_values(self.longs, self.bits, self.capacity):
                yield pal[idx] if idx < pal_len else 0
        else:
            yield from _unpack_long_values(self.longs, self.bits, self.capacity)

    def to_list(self) -> list[int]:
        if self.bits == 0:
            val = self.palette[0] if self.palette else 0
            return [val] * self.capacity
        return list(self.values())


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
        block_states: PalettedContainer | list[int] | None,
        biomes: PalettedContainer | None,
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
    has_fluid_count: bool = False,
    has_size_prefix: bool = False,
) -> list[ChunkSectionData]:
    """Decode the ``chunkData`` buffer into per-section containers.

    ``section_count`` is ``world_height // 16`` and ``min_section_y`` is
    ``min_y // 16`` for the current dimension. Sections are ordered
    bottom-to-top.

    ``has_size_prefix`` selects the pre-1.21.5 format where each
    paletted container's long-array length is sent as a VarInt; modern
    versions (1.21.5+) omit it and it is computed from the bit width.
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
        blocks = _decode_container_v2(
            reader, BLOCK_SECTION_VOLUME, MAX_INDIRECT_BITS_BLOCKS,
            has_size_prefix=has_size_prefix,
        )
        biomes = _decode_container_v2(
            reader, BIOME_SECTION_VOLUME, MAX_INDIRECT_BITS_BIOMES,
            has_size_prefix=has_size_prefix,
        )
        sections.append(
            ChunkSectionData(section_y, non_air_count, fluid_count, blocks, biomes)
        )
    return sections


def _decode_container_v2(
    reader: _Reader,
    capacity: int,
    max_indirect_bits: int,
    *,
    has_size_prefix: bool,
) -> PalettedContainer:
    """Decode a 1.14+ paletted container (block count already consumed).

    Layout: ``bits u8``; ``bits == 0`` -> single VarInt value; indirect ->
    VarInt palette length + VarInt entries; direct -> nothing. When
    ``has_size_prefix`` is set a VarInt long count precedes the longs
    (pre-1.21.5); otherwise the count is computed.
    """
    bits = reader.read_u8()
    if bits > 16:
        raise ChunkDecodeError(f"bits per entry too large: {bits}")
    palette: list[int] | None
    if bits == 0:
        value = reader.read_varint()
        if has_size_prefix:
            _read_long_array(reader, has_size_prefix=True)
        return PalettedContainer(capacity, 0, [value], [])
    if bits <= max_indirect_bits:
        palette_length = reader.read_varint()
        if palette_length < 0 or palette_length > 65536:
            raise ChunkDecodeError(f"palette length out of range: {palette_length}")
        palette = [reader.read_varint() for _ in range(palette_length)]
    else:
        palette = None
    longs = _read_long_array(reader, has_size_prefix=has_size_prefix, bits=bits, capacity=capacity)
    return PalettedContainer(capacity, bits, palette, longs)


def _read_long_array(
    reader: _Reader,
    *,
    has_size_prefix: bool,
    bits: int = 0,
    capacity: int = 0,
) -> list[int]:
    """Read the packed long array; count is prefixed or computed."""
    if has_size_prefix:
        count = reader.read_varint()
    else:
        if bits <= 0:
            return []
        values_per_long = 64 // bits
        count = math.ceil(capacity / values_per_long)
    if count < 0 or count > (1 << 22):
        raise ChunkDecodeError(f"long array length out of range: {count}")
    return [reader.read_u64() for _ in range(count)]


# -- older chunk column formats -----------------------------------------------------


class ChunkFormat:
    """Wire-format description of ``chunkData`` for one protocol era."""

    __slots__ = (
        "direct_palette_zero_varint",
        "era",
        "has_block_count",
        "has_fluid_count",
        "has_lights",
        "has_mask",
        "has_size_prefix",
        "height",
        "mask_long_array",
        "min_y",
        "sequential",
    )

    def __init__(
        self,
        era: str,
        *,
        min_y: int,
        height: int,
        has_mask: bool,
        mask_long_array: bool = False,
        has_block_count: bool = False,
        has_lights: bool = False,
        direct_palette_zero_varint: bool = False,
        has_size_prefix: bool = True,
        has_fluid_count: bool = False,
        sequential: bool = False,
    ) -> None:
        self.era = era
        self.min_y = min_y
        self.height = height
        self.has_mask = has_mask
        self.mask_long_array = mask_long_array
        self.has_block_count = has_block_count
        self.has_lights = has_lights
        self.direct_palette_zero_varint = direct_palette_zero_varint
        self.has_size_prefix = has_size_prefix
        self.has_fluid_count = has_fluid_count
        self.sequential = sequential

    @property
    def section_count(self) -> int:
        return self.height // 16

    @property
    def min_section_y(self) -> int:
        return self.min_y >> 4


def chunk_format(protocol_version: int) -> ChunkFormat:
    """Return the chunk-column wire format for a protocol version.

    Era boundaries (verified against minecraft-data/protocol history and
    reference implementations):

    * ``legacy_2d``      — 1.8 (protocol 47): fixed 8192-byte sections of
      little-endian u16 block states + separate light/biome trailer.
    * ``sections_v1``    — 1.9-1.13: varint section mask, paletted block
      containers *without* block counts, light nibble arrays inside
      ``chunkData``.
    * ``sections_v2``    — 1.14-1.17.1: adds the non-air block count,
      removes in-section lights; 1.17 sends the mask as an i64 array.
    * ``sections_v3``    — 1.18-1.21.4: no mask (all sections sequential),
      per-section biome container, VarInt long counts.
    * ``sections_v4``    — 1.21.5-1.21.11: long counts computed, not sent.
    * ``sections_v5``    — 26.1 (protocol 775): adds the fluid count.
    """
    if protocol_version <= 47:  # 1.8.x
        return ChunkFormat(
            "legacy_2d", min_y=0, height=256, has_mask=True,
            has_lights=False, has_size_prefix=False, sequential=False,
        )
    if protocol_version <= 393:  # 1.9 - 1.13
        return ChunkFormat(
            "sections_v1", min_y=0, height=256, has_mask=True,
            has_lights=True, has_size_prefix=True,
            direct_palette_zero_varint=protocol_version < 393,
        )
    if protocol_version < 757:  # 1.14 - 1.17.1
        return ChunkFormat(
            "sections_v2",
            min_y=-64 if protocol_version >= 755 else 0,
            height=384 if protocol_version >= 755 else 256,
            has_mask=True,
            mask_long_array=protocol_version >= 755,
            has_block_count=True,
            has_lights=False,
            has_size_prefix=True,
        )
    if protocol_version < 770:  # 1.18 - 1.21.4
        return ChunkFormat(
            "sections_v3", min_y=-64, height=384,
            has_mask=False, has_block_count=True,
            has_lights=False, has_size_prefix=True, sequential=True,
        )
    if protocol_version < 775:  # 1.21.5 - 1.21.11
        return ChunkFormat(
            "sections_v4", min_y=-64, height=384,
            has_mask=False, has_block_count=True,
            has_lights=False, has_size_prefix=False, sequential=True,
        )
    # 26.1+
    return ChunkFormat(
        "sections_v5", min_y=-64, height=384,
        has_mask=False, has_block_count=True,
        has_lights=False, has_size_prefix=False, has_fluid_count=True,
        sequential=True,
    )


def _decode_container_v1(
    reader: _Reader, *, direct_palette_zero_varint: bool
) -> PalettedContainer:
    """Decode a 1.9-1.13 block container.

    ``bits u8``; indirect -> VarInt palette length + entries; direct ->
    (1.9-1.12 only) a VarInt 0 palette-length marker. Always followed by
    a VarInt long count and the packed longs.
    """
    bits = reader.read_u8()
    if bits > 16:
        raise ChunkDecodeError(f"bits per entry too large: {bits}")
    palette: list[int] | None
    if bits <= MAX_INDIRECT_BITS_BLOCKS:
        palette_length = reader.read_varint()
        if palette_length < 0 or palette_length > 65536:
            raise ChunkDecodeError(f"palette length out of range: {palette_length}")
        palette = [reader.read_varint() for _ in range(palette_length)]
    else:
        if direct_palette_zero_varint:
            reader.read_varint()
        palette = None
    longs = _read_long_array(reader, has_size_prefix=True, bits=bits, capacity=BLOCK_SECTION_VOLUME)
    return PalettedContainer(BLOCK_SECTION_VOLUME, bits, palette, longs)


def decode_chunk_column(
    data: bytes,
    fmt: ChunkFormat,
    *,
    section_mask: int | list[int] | None = None,
) -> list[ChunkSectionData]:
    """Decode a ``chunkData`` buffer for any supported protocol era.

    *section_mask* is the packet's ``bitMap`` field for masked formats
    (``int`` for <=1.16, ``list[int]`` of i64 words for 1.17) and is
    ignored for sequential formats.
    """
    if fmt.era == "legacy_2d":
        return _decode_legacy_2d(data, fmt, section_mask)
    if fmt.era == "sections_v1":
        return _decode_masked_v1(data, fmt, section_mask)
    if fmt.era in ("sections_v2",):
        return _decode_masked_v2(data, fmt, section_mask)
    return _decode_sequential(data, fmt)


def _mask_bits(mask: int | list[int] | None) -> int:
    """Combine a section mask into a single int."""
    if mask is None:
        return 0
    if isinstance(mask, int):
        return mask
    value = 0
    for i, word in enumerate(mask):
        value |= (int(word) & 0xFFFFFFFFFFFFFFFF) << (64 * i)
    return value


def _decode_masked_v1(
    data: bytes, fmt: ChunkFormat, mask: int | list[int] | None
) -> list[ChunkSectionData]:
    """1.9-1.13: mask + per-section container + 2048B block/sky light."""
    reader = _Reader(data)
    bits_mask = _mask_bits(mask)
    sections: list[ChunkSectionData] = []
    for i in range(fmt.section_count):
        if not (bits_mask >> i) & 1:
            continue
        if reader.remaining() < 1:
            raise ChunkDecodeError("chunk data ended inside section mask")
        blocks = _decode_container_v1(
            reader, direct_palette_zero_varint=fmt.direct_palette_zero_varint
        )
        # In-section light nibble arrays: 2048 bytes each, skipped.
        if fmt.has_lights:
            if reader.remaining() < 4096:
                raise ChunkDecodeError("chunk data ended inside section light data")
            reader.pos += 4096
        sections.append(
            ChunkSectionData(fmt.min_section_y + i, 0, 0, blocks, None)
        )
    return sections


def _decode_masked_v2(
    data: bytes, fmt: ChunkFormat, mask: int | list[int] | None
) -> list[ChunkSectionData]:
    """1.14-1.17: mask + blockCount + modern container per section."""
    reader = _Reader(data)
    bits_mask = _mask_bits(mask)
    sections: list[ChunkSectionData] = []
    for i in range(fmt.section_count):
        if not (bits_mask >> i) & 1:
            continue
        if reader.remaining() < 3:
            raise ChunkDecodeError("chunk data ended inside section mask")
        non_air = reader.read_i16()
        blocks = _decode_container_v2(
            reader, BLOCK_SECTION_VOLUME, MAX_INDIRECT_BITS_BLOCKS,
            has_size_prefix=fmt.has_size_prefix,
        )
        sections.append(
            ChunkSectionData(fmt.min_section_y + i, non_air, 0, blocks, None)
        )
    return sections


def _decode_sequential(data: bytes, fmt: ChunkFormat) -> list[ChunkSectionData]:
    """1.18+: every section in the world height range is serialized."""
    reader = _Reader(data)
    sections: list[ChunkSectionData] = []
    for i in range(fmt.section_count):
        if reader.remaining() < 2:
            raise ChunkDecodeError(
                f"chunk data ended after {i} of {fmt.section_count} sections"
            )
        non_air = reader.read_i16()
        fluid = reader.read_i16() if fmt.has_fluid_count else 0
        blocks = _decode_container_v2(
            reader, BLOCK_SECTION_VOLUME, MAX_INDIRECT_BITS_BLOCKS,
            has_size_prefix=fmt.has_size_prefix,
        )
        biomes = _decode_container_v2(
            reader, BIOME_SECTION_VOLUME, MAX_INDIRECT_BITS_BIOMES,
            has_size_prefix=fmt.has_size_prefix,
        )
        sections.append(
            ChunkSectionData(fmt.min_section_y + i, non_air, fluid, blocks, biomes)
        )
    return sections


def _decode_legacy_2d(
    data: bytes, fmt: ChunkFormat, mask: int | list[int] | None
) -> list[ChunkSectionData]:
    """1.8: fixed-layout sections of u16 LE block states + light + biomes.

    Layout: for each of the 16 sections (bottom-to-top), if set in the
    bitMap, 4096 little-endian u16 ``(blockId << 4) | metadata`` values
    (8192 bytes). Then block-light nibbles (2048B per included section),
    sky-light nibbles, and finally 256 biome bytes. We decode only the
    block states; light is skipped.
    """
    bits_mask = _mask_bits(mask)
    reader = _Reader(data)
    included = [i for i in range(fmt.section_count) if (bits_mask >> i) & 1]
    section_values: dict[int, list[int]] = {}
    for i in included:
        if reader.remaining() < 8192:
            raise ChunkDecodeError("chunk data ended inside legacy section")
        values = list(struct.unpack_from(f"<{BLOCK_SECTION_VOLUME}H", reader.data, reader.pos))
        reader.pos += 8192
        section_values[i] = values
    sections: list[ChunkSectionData] = []
    for i in included:
        values = section_values[i]
        # Store as a direct paletted container: 16 bits per entry is not
        # packable into 64-bit longs cleanly, so keep a plain list.
        sections.append(
            ChunkSectionData(
                fmt.min_section_y + i, 0, 0, values, None  # type: ignore[arg-type]
            )
        )
    return sections
