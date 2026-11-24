"""Named Binary Tag (NBT) parsing and serialization.

Supports the full Minecraft NBT tag set: end, byte, short, int, long, float,
double, byte array, string, list, compound, int array, long array.
Also provides SNBT (stringified NBT) parsing and formatting.
"""

from __future__ import annotations

import io
import struct
from typing import Any

# Tag type ids
TAG_End = 0
TAG_Byte = 1
TAG_Short = 2
TAG_Int = 3
TAG_Long = 4
TAG_Float = 5
TAG_Double = 6
TAG_ByteArray = 7
TAG_String = 8
TAG_List = 9
TAG_Compound = 10
TAG_IntArray = 11
TAG_LongArray = 12

#: Maximum nesting depth allowed by the Minecraft NBT specification.
MAX_NBT_DEPTH = 512
#: Maximum array/list length permitted during untrusted NBT parsing.
MAX_NBT_ARRAY_LENGTH = 16 * 1024 * 1024

_FORMATS = {
    TAG_Byte: ">b",
    TAG_Short: ">h",
    TAG_Int: ">i",
    TAG_Long: ">q",
    TAG_Float: ">f",
    TAG_Double: ">d",
}
_FORMAT_SIZES = {fmt: struct.calcsize(fmt) for fmt in _FORMATS.values()}
_FORMAT_SIZES[">H"] = 2


def _read(fmt: str, buf: io.BytesIO) -> Any:
    size = _FORMAT_SIZES[fmt]
    data = buf.read(size)
    if len(data) != size:
        raise ValueError("Unexpected end of NBT data")
    return struct.unpack(fmt, data)[0]


def _read_exact(buf: io.BytesIO, n: int) -> bytes:
    if n < 0 or n > MAX_NBT_ARRAY_LENGTH:
        raise ValueError(f"Invalid NBT length: {n}")
    data = buf.read(n)
    if len(data) != n:
        raise ValueError("Unexpected end of NBT data")
    return data


def _read_u8(buf: io.BytesIO) -> int:
    b = buf.read(1)
    if not b:
        raise ValueError("Unexpected end of NBT data")
    return b[0]


def _write(fmt: str, value: Any, buf: io.BytesIO) -> None:
    buf.write(struct.pack(fmt, value))


def read_tag(buf: io.BytesIO) -> tuple[int, Any]:
    """Read one unnamed tag. Returns ``(tag_type, value)``."""
    tag_type = _read_u8(buf)
    if tag_type == TAG_End:
        return tag_type, None
    return tag_type, _read_payload(tag_type, buf, depth=0)


def _read_payload(tag_type: int, buf: io.BytesIO, *, depth: int = 0) -> Any:
    if depth > MAX_NBT_DEPTH:
        raise ValueError(f"NBT nesting depth exceeds limit ({MAX_NBT_DEPTH})")
    if tag_type == TAG_Byte:
        return _read(">b", buf)
    if tag_type == TAG_Short:
        return _read(">h", buf)
    if tag_type == TAG_Int:
        return _read(">i", buf)
    if tag_type == TAG_Long:
        return _read(">q", buf)
    if tag_type == TAG_Float:
        return _read(">f", buf)
    if tag_type == TAG_Double:
        return _read(">d", buf)
    if tag_type == TAG_ByteArray:
        length = _read(">i", buf)
        return list(_read_exact(buf, length))
    if tag_type == TAG_String:
        length = _read(">H", buf)
        return _read_exact(buf, length).decode("utf-8")
    if tag_type == TAG_List:
        elem_type = _read_u8(buf)
        length = _read(">i", buf)
        if length < 0 or length > MAX_NBT_ARRAY_LENGTH:
            raise ValueError(f"Invalid NBT list length: {length}")
        return (
            [_read_payload(elem_type, buf, depth=depth + 1) for _ in range(length)]
            if length
            else []
        )
    if tag_type == TAG_Compound:
        return read_compound(buf, _depth=depth + 1)
    if tag_type == TAG_IntArray:
        length = _read(">i", buf)
        if length < 0 or length > MAX_NBT_ARRAY_LENGTH // 4:
            raise ValueError(f"Invalid NBT int array length: {length}")
        raw = _read_exact(buf, 4 * length)
        return list(struct.unpack(f">{length}i", raw)) if length else []
    if tag_type == TAG_LongArray:
        length = _read(">i", buf)
        if length < 0 or length > MAX_NBT_ARRAY_LENGTH // 8:
            raise ValueError(f"Invalid NBT long array length: {length}")
        raw = _read_exact(buf, 8 * length)
        return list(struct.unpack(f">{length}q", raw)) if length else []
    raise ValueError(f"Unknown NBT tag type {tag_type}")


def read_compound(buf: io.BytesIO, *, _depth: int = 0) -> dict[str, Any]:
    """Read a TAG_Compound (named tags until TAG_End)."""
    if _depth > MAX_NBT_DEPTH:
        raise ValueError(f"NBT nesting depth exceeds limit ({MAX_NBT_DEPTH})")
    compound: dict[str, Any] = {}
    while True:
        tag_type = buf.read(1)
        if not tag_type:
            raise ValueError("Unexpected end of NBT compound")
        t = tag_type[0]
        if t == TAG_End:
            return compound
        name_len = _read(">H", buf)
        name = _read_exact(buf, name_len).decode("utf-8")
        compound[name] = _read_payload(t, buf, depth=_depth + 1)


def read_named_tag(buf: io.BytesIO) -> tuple[int, str, Any]:
    """Read a named root tag: ``(type, name, value)``."""
    tag_type = _read_u8(buf)
    if tag_type == TAG_End:
        return TAG_End, "", None
    name_len = _read(">H", buf)
    name = _read_exact(buf, name_len).decode("utf-8")
    return tag_type, name, _read_payload(tag_type, buf, depth=0)


def write_compound(compound: dict[str, Any], buf: io.BytesIO | None = None) -> bytes:
    """Serialize a compound to binary NBT (without a root tag header)."""
    buf = buf or io.BytesIO()
    for name, value in compound.items():
        tag_type = _infer_type(value)
        buf.write(bytes([tag_type]))
        encoded = name.encode("utf-8")
        _write(">H", len(encoded), buf)
        buf.write(encoded)
        _write_payload(tag_type, value, buf)
    buf.write(bytes([TAG_End]))
    return buf.getvalue()


def write_named_tag(tag_type: int, name: str, value: Any) -> bytes:
    """Serialize a single named tag (e.g. for NBT packet fields)."""
    buf = io.BytesIO()
    buf.write(bytes([tag_type]))
    encoded = name.encode("utf-8")
    _write(">H", len(encoded), buf)
    buf.write(encoded)
    _write_payload(tag_type, value, buf)
    return buf.getvalue()


def _infer_type(value: Any) -> int:
    if isinstance(value, bool):
        return TAG_Byte
    if isinstance(value, int):
        return TAG_Int
    if isinstance(value, float):
        return TAG_Double
    if isinstance(value, str):
        return TAG_String
    if isinstance(value, (bytes, bytearray)):
        return TAG_ByteArray
    if isinstance(value, list):
        return TAG_List
    if isinstance(value, dict):
        return TAG_Compound
    raise TypeError(f"Cannot infer NBT type for {type(value)!r}")


_PY_TO_TAG = {
    bool: TAG_Byte,
    int: TAG_Int,
    float: TAG_Double,
    str: TAG_String,
    dict: TAG_Compound,
    (bytes, bytearray): TAG_ByteArray,
    (list, tuple): TAG_List,
}


def _py_to_tag(value: Any) -> int:
    if isinstance(value, NBTByte):
        return TAG_Byte
    if isinstance(value, NBTShort):
        return TAG_Short
    if isinstance(value, NBTLong):
        return TAG_Long
    if isinstance(value, NBTFloat):
        return TAG_Float
    for py_type, tag in _PY_TO_TAG.items():
        if isinstance(value, py_type):
            return tag
    raise TypeError(f"Cannot infer NBT type for {type(value)!r}")


def _list_element_type(values: list[Any]) -> int:
    if not values:
        return TAG_End
    first = _py_to_tag(values[0])
    if all(_py_to_tag(v) == first or (
        first == TAG_Byte and isinstance(v, int) and not isinstance(v, bool)
    ) for v in values):
        return first
    raise TypeError("NBT lists must be homogeneous")


def _write_payload(tag_type: int, value: Any, buf: io.BytesIO) -> None:
    if tag_type == TAG_Byte:
        _write(">b", int(value), buf)
    elif tag_type == TAG_Short:
        _write(">h", int(value), buf)
    elif tag_type == TAG_Int:
        _write(">i", int(value), buf)
    elif tag_type == TAG_Long:
        _write(">q", int(value), buf)
    elif tag_type == TAG_Float:
        _write(">f", float(value), buf)
    elif tag_type == TAG_Double:
        _write(">d", float(value), buf)
    elif tag_type == TAG_ByteArray:
        data = bytes(value)
        _write(">i", len(data), buf)
        buf.write(data)
    elif tag_type == TAG_String:
        encoded = str(value).encode("utf-8")
        _write(">H", len(encoded), buf)
        buf.write(encoded)
    elif tag_type == TAG_List:
        elem_type = _list_element_type(value)
        buf.write(bytes([elem_type]))
        _write(">i", len(value), buf)
        for item in value:
            _write_payload(elem_type, item, buf)
    elif tag_type == TAG_Compound:
        buf.write(write_compound(value))
    elif tag_type == TAG_IntArray:
        _write(">i", len(value), buf)
        buf.write(struct.pack(f">{len(value)}i", *value))
    elif tag_type == TAG_LongArray:
        _write(">i", len(value), buf)
        buf.write(struct.pack(f">{len(value)}q", *value))
    else:
        raise ValueError(f"Cannot write NBT tag type {tag_type}")


# ---------------------------------------------------------------------------
# Typed wrappers so callers can force narrow integer types
# ---------------------------------------------------------------------------


class NBTByte(int):
    """A byte-typed NBT value."""


class NBTShort(int):
    """A short-typed NBT value."""


class NBTLong(int):
    """A long-typed NBT value."""


class NBTFloat(float):
    """A float-typed NBT value."""


def nbt_type_of(value: Any) -> int:
    """Return the NBT tag type that would be used for *value*."""
    if isinstance(value, NBTByte):
        return TAG_Byte
    if isinstance(value, NBTShort):
        return TAG_Short
    if isinstance(value, NBTLong):
        return TAG_Long
    if isinstance(value, NBTFloat):
        return TAG_Float
    return _infer_type(value)


def write_compound_typed(compound: dict[str, Any], buf: io.BytesIO | None = None) -> bytes:
    """Serialize a compound honoring NBTByte/Short/Long/Float wrappers."""
    buf = buf or io.BytesIO()
    for name, value in compound.items():
        tag_type = nbt_type_of(value)
        buf.write(bytes([tag_type]))
        encoded = name.encode("utf-8")
        _write(">H", len(encoded), buf)
        buf.write(encoded)
        _write_payload(tag_type, value, buf)
    buf.write(bytes([TAG_End]))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# SNBT
# ---------------------------------------------------------------------------


class _SNBTParser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\n\r":
            self.pos += 1

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _expect(self, ch: str) -> None:
        self._skip_ws()
        if self._peek() != ch:
            raise ValueError(f"Expected '{ch}' at position {self.pos} in SNBT")
        self.pos += 1

    def parse_compound(self, depth: int = 0) -> dict[str, Any]:
        if depth > MAX_NBT_DEPTH:
            raise ValueError(f"SNBT nesting depth exceeds limit ({MAX_NBT_DEPTH})")
        self._expect("{")
        result: dict[str, Any] = {}
        self._skip_ws()
        while self._peek() != "}":
            if not self._peek():
                raise ValueError("Unterminated SNBT compound")
            key = self._parse_key()
            self._expect(":")
            result[key] = self._parse_value(depth + 1)
            self._skip_ws()
            if self._peek() == ",":
                self.pos += 1
                self._skip_ws()
        self._expect("}")
        return result

    def _parse_key(self) -> str:
        self._skip_ws()
        ch = self._peek()
        if ch in "\"'":
            quote = ch
            self.pos += 1
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] != quote:
                self.pos += 1
            if self.pos >= len(self.text):
                raise ValueError("Unterminated quoted SNBT key")
            key = self.text[start:self.pos]
            self.pos += 1
            return key
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in ":,}":
            self.pos += 1
        key = self.text[start:self.pos].strip()
        if not key:
            raise ValueError(f"Empty key at position {self.pos} in SNBT")
        return key

    def _parse_value(self, depth: int = 0) -> Any:
        self._skip_ws()
        ch = self._peek()
        if not ch:
            raise ValueError("Unexpected end of SNBT value")
        if ch == "{":
            return self.parse_compound(depth)
        if ch == "[":
            return self._parse_list(depth)
        if ch in "\"'":
            quote = ch
            self.pos += 1
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] != quote:
                if self.text[self.pos] == "\\":
                    self.pos += 1
                self.pos += 1
            if self.pos >= len(self.text):
                raise ValueError("Unterminated quoted SNBT string")
            value = self.text[start:self.pos]
            self.pos += 1
            return value
        # scalar token
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in ",}] \t\n\r":
            self.pos += 1
        token = self.text[start:self.pos]
        return _snbt_scalar(token)

    def _parse_list(self, depth: int = 0) -> list[Any]:
        if depth > MAX_NBT_DEPTH:
            raise ValueError(f"SNBT nesting depth exceeds limit ({MAX_NBT_DEPTH})")
        self._expect("[")
        result: list[Any] = []
        self._skip_ws()
        # Optional element type prefix like [I;...] or [B;...] or [L;...]
        if self._peek() in "BIJSL":
            marker = self._peek()
            self.pos += 1
            if self._peek() == ";":
                self.pos += 1
                self._skip_ws()
                while self._peek() != "]":
                    if not self._peek():
                        raise ValueError("Unterminated SNBT typed array")
                    self._skip_ws()
                    if self._peek() == ",":
                        self.pos += 1
                        continue
                    start = self.pos
                    while self._peek() not in ",]" and self._peek() != "":
                        self.pos += 1
                    token = self.text[start:self.pos].strip()
                    if token:
                        result.append(_typed_array_scalar(marker, token))
                self._expect("]")
                return result
            # not a typed array; rewind
            self.pos -= 1
        while self._peek() != "]":
            if not self._peek():
                raise ValueError("Unterminated SNBT list")
            self._skip_ws()
            if self._peek() == ",":
                self.pos += 1
                continue
            result.append(self._parse_value(depth + 1))
            self._skip_ws()
        self._expect("]")
        return result


def _typed_array_scalar(marker: str, token: str) -> Any:
    if marker == "B":
        return NBTByte(int(token.rstrip("bB")))
    if marker == "I":
        return int(token)
    if marker in ("J", "L"):
        return NBTLong(int(token.rstrip("lL")))
    if marker == "S":
        return NBTShort(int(token.rstrip("sS")))
    return token


def _snbt_scalar(token: str) -> Any:
    if not token:
        return ""
    low = token.lower()
    if low == "true":
        return NBTByte(1)
    if low == "false":
        return NBTByte(0)
    if low.endswith("b"):
        return NBTByte(int(token[:-1]))
    if low.endswith("s"):
        return NBTShort(int(token[:-1]))
    if low.endswith("l"):
        return NBTLong(int(token[:-1]))
    if low.endswith("f"):
        return NBTFloat(float(token[:-1]))
    if low.endswith("d"):
        return float(token[:-1])
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def parse_snbt(text: str) -> dict[str, Any]:
    """Parse an SNBT compound string into a Python dict."""
    parser = _SNBTParser(text.strip())
    return parser.parse_compound()


def _to_snbt(value: Any) -> str:
    if isinstance(value, dict):
        inner = ",".join(f"{k}:{_to_snbt(v)}" for k, v in value.items())
        return "{" + inner + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_to_snbt(v) for v in value) + "]"
    if isinstance(value, NBTByte):
        return f"{int(value)}b"
    if isinstance(value, NBTShort):
        return f"{int(value)}s"
    if isinstance(value, NBTLong):
        return f"{int(value)}l"
    if isinstance(value, NBTFloat):
        return f"{float(value)}f"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def to_snbt(compound: dict[str, Any]) -> str:
    """Format a compound dict as an SNBT string."""
    return _to_snbt(compound)
