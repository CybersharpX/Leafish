"""Minecraft packet compression (zlib with a configurable threshold)."""

from __future__ import annotations

import zlib

from ..exceptions import ProtocolError
from .framing import BufferReader, encode_varint

#: Maximum allowed uncompressed packet size (8 MiB, matching modern Notchian client).
MAX_DECOMPRESSED_PACKET_SIZE = 8 * 1024 * 1024


class CompressionHandler:
    """Applies Minecraft's packet compression scheme.

    Once enabled, every packet payload is prefixed with a VarInt "data
    length": ``0`` means the following bytes are uncompressed, otherwise it
    is the length of the zlib-compressed data that follows.
    """

    def __init__(self, threshold: int = 256, *, max_decompressed_size: int = MAX_DECOMPRESSED_PACKET_SIZE) -> None:
        self.threshold = threshold
        self.enabled = False
        self.max_decompressed_size = max_decompressed_size

    def enable(self, threshold: int) -> None:
        """Enable compression at *threshold*, or disable if ``threshold < 0``."""
        if threshold < 0:
            self.threshold = threshold
            self.enabled = False
            return
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
            return encode_varint(len(data)) + compressed
        return encode_varint(0) + data

    def decompress_payload(self, data: bytes) -> bytes:
        """Reverse :meth:`compress_payload`; returns raw packet bytes.

        Enforces ``max_decompressed_size`` and verifies the decompressed byte
        count matches the declared ``data_length`` to defend against zlib
        decompression bombs.
        """
        if not self.enabled:
            return data
        reader = BufferReader(data)
        data_length = reader.read_varint()
        rest = reader.read_rest()
        if data_length == 0:
            return rest
        if data_length < 0 or data_length > self.max_decompressed_size:
            raise ProtocolError(
                f"Invalid decompressed length {data_length} "
                f"(max {self.max_decompressed_size})"
            )
        decompressor = zlib.decompressobj()
        try:
            # Cap decompression to data_length + 1 so a bomb cannot allocate
            # unbounded memory even if it lies about data_length.
            decompressed = decompressor.decompress(rest, data_length + 1)
            if decompressor.unconsumed_tail:
                raise ProtocolError(
                    f"Decompressed payload exceeds declared length {data_length}"
                )
            tail = decompressor.flush()
            if tail:
                decompressed += tail
        except zlib.error as exc:
            raise ProtocolError(f"Packet decompression failed: {exc}") from exc
        if len(decompressed) != data_length:
            raise ProtocolError(
                f"Decompressed length mismatch: expected {data_length}, "
                f"got {len(decompressed)}"
            )
        return decompressed
