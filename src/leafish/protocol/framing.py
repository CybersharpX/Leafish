"""Minecraft protocol primitives: VarInt, VarLong, and packet framing."""

from __future__ import annotations

import io
import struct
from typing import BinaryIO

from ..exceptions import PacketDecodeError, PacketEncodeError

MAX_VARINT_BYTES = 5
MAX_VARLONG_BYTES = 10
MAX_PACKET_SIZE = 2 * 1024 * 1024  # 2 MiB hard cap on a single packet


class BufferReader:
    """Cursor-based reader over a bytes-like object."""

    __slots__ = ("_buf", "pos")

    def __init__(self, data: bytes | bytearray | memoryview) -> None:
        self._buf = memoryview(data)
        self.pos = 0

    @property
    def remaining(self) -> int:
        return len(self._buf) - self.pos

    def read(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self._buf):
            raise PacketDecodeError(
                f"Buffer underflow: need {n} bytes, have {self.remaining}"
            )
        out = bytes(self._buf[self.pos : self.pos + n])
        self.pos += n
        return out

    def read_u8(self) -> int:
        return self.read(1)[0]

    def read_bool(self) -> bool:
        return self.read_u8() != 0

    def read_i8(self) -> int:
        return struct.unpack(">b", self.read(1))[0]

    def read_u16(self) -> int:
        return struct.unpack(">H", self.read(2))[0]

    def read_i16(self) -> int:
        return struct.unpack(">h", self.read(2))[0]

    def read_u24(self) -> int:
        b = self.read(3)
        return (b[0] << 16) | (b[1] << 8) | b[2]

    def read_i24(self) -> int:
        v = self.read_u24()
        return v - (1 << 24) if v & 0x800000 else v

    def read_i32(self) -> int:
        return struct.unpack(">i", self.read(4))[0]

    def read_u32(self) -> int:
        return struct.unpack(">I", self.read(4))[0]

    def read_i64(self) -> int:
        return struct.unpack(">q", self.read(8))[0]

    def read_u64(self) -> int:
        return struct.unpack(">Q", self.read(8))[0]

    def read_f32(self) -> float:
        return struct.unpack(">f", self.read(4))[0]

    def read_f64(self) -> float:
        return struct.unpack(">d", self.read(8))[0]

    def read_varint(self) -> int:
        value = 0
        for i in range(MAX_VARINT_BYTES):
            byte = self.read_u8()
            value |= (byte & 0x7F) << (7 * i)
            if not (byte & 0x80):
                # Sign-extend 32-bit
                if value & 0x80000000:
                    value -= 1 << 32
                return value
        raise PacketDecodeError("VarInt is too long (max 5 bytes)")

    def read_varlong(self) -> int:
        value = 0
        for i in range(MAX_VARLONG_BYTES):
            byte = self.read_u8()
            value |= (byte & 0x7F) << (7 * i)
            if not (byte & 0x80):
                if value & (1 << 63):
                    value -= 1 << 64
                return value
        raise PacketDecodeError("VarLong is too long (max 10 bytes)")

    def read_string(self, max_length: int = 32767) -> str:
        length = self.read_varint()
        if length < 0 or length > max_length:
            raise PacketDecodeError(f"Invalid string length {length}")
        return self.read(length).decode("utf-8", errors="replace")

    def read_bytes(self, n: int) -> bytes:
        return self.read(n)

    def read_uuid(self) -> str:
        import uuid as _uuid

        return str(_uuid.UUID(bytes=self.read(16)))

    def read_rest(self) -> bytes:
        out = bytes(self._buf[self.pos :])
        self.pos = len(self._buf)
        return out


class BufferWriter:
    """Append-only writer producing big-endian Minecraft protocol bytes."""

    __slots__ = ("_buf",)

    def __init__(self) -> None:
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> None:
        self._buf.write(data)

    def write_u8(self, v: int) -> None:
        self._buf.write(struct.pack(">B", v & 0xFF))

    def write_bool(self, v: bool) -> None:
        self.write_u8(1 if v else 0)

    def write_i8(self, v: int) -> None:
        self._buf.write(struct.pack(">b", v))

    def write_u16(self, v: int) -> None:
        self._buf.write(struct.pack(">H", v & 0xFFFF))

    def write_i16(self, v: int) -> None:
        self._buf.write(struct.pack(">h", v))

    def write_i32(self, v: int) -> None:
        self._buf.write(struct.pack(">i", v))

    def write_u32(self, v: int) -> None:
        self._buf.write(struct.pack(">I", v & 0xFFFFFFFF))

    def write_i64(self, v: int) -> None:
        self._buf.write(struct.pack(">q", v))

    def write_u64(self, v: int) -> None:
        self._buf.write(struct.pack(">Q", v & 0xFFFFFFFFFFFFFFFF))

    def write_f32(self, v: float) -> None:
        self._buf.write(struct.pack(">f", v))

    def write_f64(self, v: float) -> None:
        self._buf.write(struct.pack(">d", v))

    def write_varint(self, value: int) -> None:
        value &= 0xFFFFFFFF
        if value & 0x80000000:
            value -= 1 << 32
        value &= 0xFFFFFFFF
        while True:
            byte = value & 0x7F
            value >>= 7
            if value:
                self.write_u8(byte | 0x80)
            else:
                self.write_u8(byte)
                return

    def write_varlong(self, value: int) -> None:
        value &= 0xFFFFFFFFFFFFFFFF
        if value & (1 << 63):
            value -= 1 << 64
        value &= 0xFFFFFFFFFFFFFFFF
        while True:
            byte = value & 0x7F
            value >>= 7
            if value:
                self.write_u8(byte | 0x80)
            else:
                self.write_u8(byte)
                return

    def write_string(self, s: str, max_length: int = 32767) -> None:
        data = s.encode("utf-8")
        self.write_varint(len(data))
        self._buf.write(data)

    def write_bytes(self, data: bytes) -> None:
        self._buf.write(data)

    def write_uuid(self, u: str) -> None:
        import uuid as _uuid

        self.write_bytes(_uuid.UUID(u).bytes)

    def to_bytes(self) -> bytes:
        return self._buf.getvalue()

    def __len__(self) -> int:
        return self._buf.tell()


# ---------------------------------------------------------------------------
# Raw encode/decode helpers used by tests and low-level code
# ---------------------------------------------------------------------------


def encode_varint(value: int) -> bytes:
    w = BufferWriter()
    w.write_varint(value)
    return w.to_bytes()


def decode_varint(data: bytes | BinaryIO) -> tuple[int, int]:
    """Decode a VarInt from *data*; returns ``(value, bytes_consumed)``."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        reader = BufferReader(data)
        value = reader.read_varint()
        return value, reader.pos
    # file-like
    value = 0
    for i in range(MAX_VARINT_BYTES):
        byte = data.read(1)
        if not byte:
            raise PacketDecodeError("Unexpected EOF reading VarInt")
        b = byte[0]
        value |= (b & 0x7F) << (7 * i)
        if not (b & 0x80):
            if value & 0x80000000:
                value -= 1 << 32
            return value, i + 1
    raise PacketDecodeError("VarInt is too long")


def encode_packet_frame(packet_id_payload: bytes) -> bytes:
    """Wrap *packet_id_payload* (id varint + fields) in a length prefix."""
    length = len(packet_id_payload)
    if length > MAX_PACKET_SIZE:
        raise PacketEncodeError(f"Packet too large: {length} bytes")
    return encode_varint(length) + packet_id_payload


def read_packet_frame(reader: BufferReader) -> bytes:
    """Read one length-prefixed packet payload (id + fields)."""
    length = reader.read_varint()
    if length < 0 or length > MAX_PACKET_SIZE:
        raise PacketDecodeError(f"Invalid packet length {length}")
    return reader.read(length)
