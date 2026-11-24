"""Version-matrix tests: codec compile, era formats and packet adaptation."""

from __future__ import annotations

import struct

import pytest

from leafish.inventory.item import Item
from leafish.protocol.compat import adapt_send, slot_format
from leafish.protocol.protodef import ProtocolCodec, supported_versions
from leafish.world.chunk_codec import (
    ChunkFormat,
    chunk_format,
    decode_chunk_column,
)

VERSIONS = supported_versions()


def _block_at(section, index: int) -> int:
    states = section.block_states
    assert states is not None
    if isinstance(states, list):
        return states[index]
    return states.get(index)


def _biome_at(section, index: int) -> int:
    biomes = section.biomes
    assert biomes is not None
    return biomes.get(index)


class TestCodecCompile:
    @pytest.mark.parametrize("version", VERSIONS)
    def test_codec_compiles(self, version: str):
        codec = ProtocolCodec.for_version(version)
        assert codec.protocol_version > 0

    @pytest.mark.parametrize("version", VERSIONS)
    def test_keepalive_roundtrip(self, version: str):
        codec = ProtocolCodec.for_version(version)
        data = codec.encode(
            "play", "toServer", "keep_alive", {"keepAliveId": 12345}
        )
        packet = codec.decode("play", "toServer", data)
        assert packet["name"] == "keep_alive"
        assert packet["params"]["keepAliveId"] == 12345

    @pytest.mark.parametrize("version", VERSIONS)
    def test_login_start_encodes(self, version: str):
        codec = ProtocolCodec.for_version(version)
        fields = codec.packet_fields("login", "toServer", "login_start") or []
        params: dict = {"username": "Test"}
        if "playerUUID" in fields:
            params["playerUUID"] = "00000000-0000-0000-0000-000000000000"
        codec.encode("login", "toServer", "login_start", params)


class TestChunkFormat:
    @pytest.mark.parametrize(
        "version,era",
        [
            ("1.8", "legacy_2d"),
            ("1.9", "sections_v1"),
            ("1.12", "sections_v1"),
            ("1.13", "sections_v1"),
            ("1.14", "sections_v2"),
            ("1.16", "sections_v2"),
            ("1.17", "sections_v2"),
            ("1.18", "sections_v3"),
            ("1.20", "sections_v3"),
            ("1.21", "sections_v3"),
            ("1.21.4", "sections_v3"),
            ("1.21.9", "sections_v4"),
            ("1.21.11", "sections_v4"),
            ("26.1", "sections_v5"),
        ],
    )
    def test_era(self, version: str, era: str):
        codec = ProtocolCodec.for_version(version)
        assert chunk_format(codec.protocol_version).era == era


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _pack(values: list[int], bits: int) -> bytes:
    per_long = 64 // bits
    out = bytearray()
    for i in range(0, len(values), per_long):
        v = 0
        for k, x in enumerate(values[i : i + per_long]):
            v |= (x & ((1 << bits) - 1)) << (k * bits)
        out += struct.pack(">Q", v)
    return bytes(out)


def _container_v1(bits: int, palette: list[int] | None, values: list[int],
                  *, zero_varint: bool) -> bytes:
    """1.9-1.13 block container (VarInt long count present)."""
    out = bytearray([bits])
    if palette is not None:
        out += _varint(len(palette))
        for p in palette:
            out += _varint(p)
    elif zero_varint:
        out += _varint(0)
    longs = _pack(values, bits) if bits else b""
    out += _varint(len(longs) // 8)
    out += longs
    return bytes(out)


def _container_modern(bits: int, palette: list[int] | None, values: list[int],
                      capacity: int, *, size_prefix: bool) -> bytes:
    """1.14+ paletted container."""
    out = bytearray([bits])
    if bits == 0:
        out += _varint(values[0] if values else 0)
        if size_prefix:
            out += _varint(0)
        return bytes(out)
    if palette is not None:
        out += _varint(len(palette))
        for p in palette:
            out += _varint(p)
    longs = _pack(values, bits)
    if size_prefix:
        out += _varint(len(longs) // 8)
    out += longs
    return bytes(out)


class TestLegacy2DChunk:
    def test_1_8_chunk(self):
        fmt = chunk_format(47)
        # Two sections present (bits 0 and 3 of the u16 bitMap).
        mask = 0b1001
        data = bytearray()
        for _ in range(2):
            # 4096 u16 LE state ids: (blockId<<4)|meta. id=1 meta=0 -> 16.
            data += struct.pack("<4096H", *([16] * 4096))
        # Light + biome trailer (ignored by the decoder).
        data += b"\x00" * (2048 * 2 * 2 + 256)
        sections = decode_chunk_column(bytes(data), fmt, section_mask=mask)
        assert [s.y for s in sections] == [0, 3]
        assert _block_at(sections[0],0) == 16
        assert _block_at(sections[0],4095) == 16


class TestMaskedChunkFormats:
    def test_1_13_section(self):
        fmt = chunk_format(393)
        # mask bit 0 set; indirect palette [7, 9], all indices 1.
        container = _container_v1(4, [7, 9], [1] * 4096, zero_varint=False)
        data = container + b"\x00" * 4096  # block+sky light nibbles
        sections = decode_chunk_column(data, fmt, section_mask=1)
        assert len(sections) == 1
        sec = sections[0]
        assert _block_at(sec,0) == 9
        assert _block_at(sec,4095) == 9

    def test_1_12_direct_palette(self):
        fmt = chunk_format(335)
        # Direct format: bits=13 > 8, palette absent but a varint 0 marker.
        container = _container_v1(13, None, [100] * 4096, zero_varint=True)
        data = container + b"\x00" * 4096
        sections = decode_chunk_column(data, fmt, section_mask=1)
        assert _block_at(sections[0],5) == 100

    def test_1_16_block_count(self):
        fmt = chunk_format(735)
        container = _container_modern(4, [3, 4], [1] * 4096, 4096, size_prefix=True)
        data = struct.pack(">h", 4096) + container
        sections = decode_chunk_column(data, fmt, section_mask=1)
        assert sections[0].non_air_count == 4096
        assert _block_at(sections[0],2) == 4

    def test_1_17_mask_long_array(self):
        fmt = chunk_format(755)
        # Mask as i64 array: bit 0 set -> [1].
        container = _container_modern(0, None, [42], 4096, size_prefix=True)
        data = struct.pack(">h", 4096) + container
        sections = decode_chunk_column(data, fmt, section_mask=[1])
        assert len(sections) == 1
        assert _block_at(sections[0],0) == 42


class TestSequentialChunkFormats:
    def _sequential_data(self, fmt: ChunkFormat, *, fluid: bool = False) -> bytes:
        out = bytearray()
        for _ in range(fmt.section_count):
            out += struct.pack(">h", 0)
            if fluid:
                out += struct.pack(">h", 0)
            out += _container_modern(
                0, None, [1], 4096, size_prefix=fmt.has_size_prefix
            )
            out += _container_modern(
                0, None, [2], 64, size_prefix=fmt.has_size_prefix
            )
        return bytes(out)

    def test_1_18_sequential(self):
        fmt = chunk_format(757)
        data = self._sequential_data(fmt)
        sections = decode_chunk_column(data, fmt)
        assert len(sections) == fmt.section_count
        assert sections[0].y == fmt.min_section_y
        assert sections[-1].y == fmt.min_section_y + fmt.section_count - 1
        assert _block_at(sections[0],0) == 1
        assert _biome_at(sections[0],0) == 2

    def test_1_21_11_no_size_prefix(self):
        fmt = chunk_format(774)
        data = self._sequential_data(fmt)
        sections = decode_chunk_column(data, fmt)
        assert len(sections) == fmt.section_count
        assert _block_at(sections[0],0) == 1

    def test_26_1_fluid_count(self):
        fmt = chunk_format(775)
        out = bytearray()
        for i in range(fmt.section_count):
            out += struct.pack(">hh", 100 if i == 5 else 0, 7 if i == 5 else 0)
            out += _container_modern(0, None, [1], 4096, size_prefix=False)
            out += _container_modern(0, None, [2], 64, size_prefix=False)
        sections = decode_chunk_column(bytes(out), fmt)
        assert sections[5].fluid_count == 7
        assert sections[5].non_air_count == 100


class TestSlotFormats:
    def test_slot_format_per_version(self):
        assert slot_format(ProtocolCodec.for_version("1.8")) == "legacy"
        assert slot_format(ProtocolCodec.for_version("1.12")) == "legacy"
        assert slot_format(ProtocolCodec.for_version("1.13")) == "flat"
        assert slot_format(ProtocolCodec.for_version("1.15")) == "present"
        assert slot_format(ProtocolCodec.for_version("1.20")) == "present"
        assert slot_format(ProtocolCodec.for_version("1.21")) == "components"
        assert slot_format(ProtocolCodec.for_version("1.21.11")) == "components"
        assert slot_format(ProtocolCodec.for_version("26.1")) == "components"

    def test_from_slot_legacy(self):
        item = Item.from_slot({"blockId": 5, "itemCount": 3, "itemDamage": 2})
        assert item is not None
        assert item.item_id == 5 and item.count == 3 and item.metadata == 2
        assert item.to_slot("legacy")["itemDamage"] == 2
        assert Item.from_slot({"blockId": -1}) is None

    def test_from_slot_flat(self):
        item = Item.from_slot({"itemId": 300, "itemCount": 2, "nbtData": None})
        assert item is not None and item.item_id == 300 and item.slot_format == "flat"
        assert Item.from_slot({"itemId": -1}) is None

    def test_from_slot_present(self):
        item = Item.from_slot({"present": True, "itemId": 7, "itemCount": 4})
        assert item is not None and item.count == 4
        assert Item.from_slot({"present": False}) is None

    def test_from_slot_components(self):
        item = Item.from_slot({"itemCount": 1, "itemId": 9, "components": []})
        assert item is not None and item.slot_format == "components"
        assert Item.from_slot({"itemCount": 0}) is None

    def test_to_slot_roundtrip(self):
        for fmt in ("legacy", "flat", "present", "components"):
            item = Item(item_id=5, count=2, slot_format=fmt)
            slot = item.to_slot(fmt)
            back = Item.from_slot(slot)
            assert back is not None and back.item_id == 5 and back.count == 2


class TestPacketAdaptation:
    def _codec(self, version: str) -> ProtocolCodec:
        return ProtocolCodec.for_version(version)

    def test_chat_legacy(self):
        adapted = adapt_send(self._codec("1.13"), "chat_message", {"message": "hi"})
        assert adapted is not None and adapted[0] == "chat"
        assert adapted[1] == {"message": "hi"}

    def test_chat_command_legacy(self):
        adapted = adapt_send(self._codec("1.13"), "chat_command", {"command": "give"})
        assert adapted is not None and adapted[0] == "chat"
        assert adapted[1]["message"] == "/give"

    def test_chat_message_modern(self):
        adapted = adapt_send(
            self._codec("1.20"), "chat_message", {"message": "hi"}
        )
        assert adapted is not None and adapted[0] == "chat_message"
        fields = adapted[1]
        assert fields["message"] == "hi"
        assert "offset" in fields and "acknowledged" in fields
        assert "checksum" not in fields  # added in 1.21.5+

    def test_chat_command_1_21(self):
        adapted = adapt_send(
            self._codec("1.21"), "chat_command", {"command": "help"}
        )
        assert adapted is not None and adapted[0] == "chat_command"
        assert adapted[1] == {"command": "help"}

    def test_window_click_eras(self):
        params = {
            "windowId": 0, "stateId": 3, "slot": 5, "mouseButton": 0,
            "mode": 0, "changedSlots": [], "cursorItem": None,
        }
        # <=1.16: action + item, no stateId/changedSlots/cursorItem.
        adapted = adapt_send(self._codec("1.13"), "window_click", params)
        assert adapted is not None
        assert set(adapted[1]) == {"windowId", "slot", "mouseButton", "action", "mode", "item"}
        # 1.17: changedSlots/cursorItem but no stateId.
        adapted = adapt_send(self._codec("1.17"), "window_click", params)
        assert adapted is not None
        assert "changedSlots" in adapted[1] and "stateId" not in adapted[1]
        # 1.18+: stateId present.
        adapted = adapt_send(self._codec("1.20"), "window_click", params)
        assert adapted is not None and adapted[1]["stateId"] == 3

    def test_missing_packet_skipped(self):
        # teleport_confirm does not exist in 1.8.
        assert adapt_send(self._codec("1.8"), "teleport_confirm", {"teleportId": 1}) is None
        assert adapt_send(self._codec("1.9"), "teleport_confirm", {"teleportId": 1}) is not None

    def test_block_place_eras(self):
        params = {
            "hand": 0,
            "location": {"x": 1, "y": 2, "z": 3},
            "direction": 1,
            "cursorX": 0.5, "cursorY": 0.5, "cursorZ": 0.5,
        }
        adapted = adapt_send(self._codec("1.8"), "block_place", params)
        assert adapted is not None
        assert "heldItem" in adapted[1] and "hand" not in adapted[1]
        adapted = adapt_send(self._codec("1.21.11"), "block_place", params)
        assert adapted is not None
        assert "worldBorderHit" in adapted[1] and "sequence" in adapted[1]
