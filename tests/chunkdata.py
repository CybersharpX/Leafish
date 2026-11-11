"""Test helpers for *encoding* Minecraft chunk-column data.

Mirrors ``leafish.world.chunk_codec`` (decode-only) so tests can build
synthetic ``map_chunk`` payloads.
"""

from __future__ import annotations

import struct


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def pack_longs(values: list[int], bits: int) -> list[int]:
    """Pack values into 64-bit longs, ``64 // bits`` entries per long."""
    per_long = 64 // bits
    longs = []
    for i in range(0, len(values), per_long):
        long_value = 0
        for k, v in enumerate(values[i : i + per_long]):
            long_value |= (v & ((1 << bits) - 1)) << (k * bits)
        longs.append(long_value)
    return longs


def container_single(value: int) -> bytes:
    return b"\x00" + varint(value)


def container_indirect(
    palette: list[int], indices: list[int], bits: int
) -> bytes:
    out = bytearray([bits])
    out += varint(len(palette))
    for p in palette:
        out += varint(p)
    for long_value in pack_longs(indices, bits):
        out += struct.pack(">Q", long_value)
    return bytes(out)


def container_direct(values: list[int], bits: int) -> bytes:
    out = bytearray([bits])
    for long_value in pack_longs(values, bits):
        out += struct.pack(">Q", long_value)
    return bytes(out)


def section(
    block_container: bytes,
    biome_container: bytes | None = None,
    *,
    non_air: int = 0,
    fluid: int = 0,
) -> bytes:
    if biome_container is None:
        biome_container = container_single(0)
    return struct.pack(">hh", non_air, fluid) + block_container + biome_container


def chunk_data(sections: list[bytes]) -> bytes:
    return b"".join(sections)


def air_chunk_data(
    section_count: int, air_state_id: int, *, fill_state: int | None = None,
    fill_section_index: int | None = None,
) -> bytes:
    """Build ``section_count`` all-air sections; optionally fill one section
    entirely with *fill_state* via an indirect palette."""
    sections = []
    for i in range(section_count):
        if fill_section_index == i and fill_state is not None:
            indices = [1] * 4096
            container = container_indirect([air_state_id, fill_state], indices, 4)
            sections.append(section(container, non_air=4096))
        else:
            sections.append(section(container_single(air_state_id)))
    return chunk_data(sections)
