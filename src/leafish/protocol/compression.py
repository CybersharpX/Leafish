"""Minecraft packet compression (zlib with a configurable threshold)."""

from __future__ import annotations

import zlib

from ..exceptions import ProtocolError


class CompressionHandler:
    """Applies Minecraft's packet compression scheme.

    Once enabled, every packet payload is prefixed with a VarInt "data
    length": ``0`` means the following bytes are uncompressed, otherwise it
    is the length of the zlib-compressed data that follows.
    """

    def __init__(self, threshold: int = 256) -> None:
        self.threshold = threshold
        self.enabled = False

    def enable(self, threshold: int) -> None:
        self.threshold = threshold
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    def compress_payload(self, data: bytes) -> bytes:
        """Return the on-wire *data* section for uncompressed packet *data*."""
        if not self.enabled:
            return data
        if len(data) >= self.threshold:
            compressed = zlib.compress(data)
            from .framing import encode_varint

            return encode_varint(len(data)) + compressed
        from .framing import encode_varint

        return encode_varint(0) + data

    def decompress_payload(self, data: bytes) -> bytes:
        """Reverse :meth:`compress_payload`; returns raw packet bytes."""
        if not self.enabled:
            return data
        from .framing import BufferReader

        reader = BufferReader(data)
        data_length = reader.read_varint()
        rest = reader.read_rest()
        if data_length == 0:
            return rest
        if data_length < 0 or data_length > 0x7FFFFFFF:
            raise ProtocolError(f"Invalid decompressed length {data_length}")
        try:
            return zlib.decompress(rest)
        except zlib.error as exc:
            raise ProtocolError(f"Packet decompression failed: {exc}") from exc
