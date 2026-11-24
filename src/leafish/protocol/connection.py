"""Asynchronous TCP transport for the Minecraft protocol.

Handles connection lifecycle, packet framing (VarInt length prefix),
optional zlib compression and AES/CFB8 encryption, keepalive plumbing and
graceful shutdown. Protocol semantics (packet names/fields) are delegated
to :class:`~leafish.protocol.protodef.ProtocolCodec`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from typing import Any

from ..config import MAX_PACKET_SIZE
from ..exceptions import BotConnectionError, PacketEncodeError, ProtocolError
from .compression import CompressionHandler
from .encryption import EncryptionHandler
from .framing import decode_varint_from_buffer, encode_varint
from .protodef import ProtocolCodec

log = logging.getLogger("leafish.protocol")

PacketCallback = Callable[[str, str, str, dict[str, Any]], Any]
"""``(state, direction, name, params)`` — direction is from the server's
perspective: ``toClient`` for packets we received, ``toServer`` for packets
we sent (used for local echo/testing)."""


class Connection:
    """One TCP connection to a Minecraft server."""

    def __init__(
        self,
        codec: ProtocolCodec,
        host: str,
        port: int,
        *,
        state: str = "handshaking",
        on_packet: PacketCallback | None = None,
        on_disconnect: Callable[[str], Any] | None = None,
    ) -> None:
        self.codec = codec
        self.host = host
        self.port = port
        self.state = state
        self._on_packet = on_packet
        self._on_disconnect = on_disconnect

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._read_task: asyncio.Task | None = None
        self._write_lock = asyncio.Lock()
        self._closing = False
        self._disconnect_reason: str | None = None

        self.compression = CompressionHandler()
        self.encryption = EncryptionHandler()
        self._framer_buffer = bytearray()

        # Connection diagnostics
        self.bytes_sent: int = 0
        self.bytes_received: int = 0
        self.packets_sent: int = 0
        self.packets_received: int = 0
        self.connected_at: float | None = None
        self.latency_ms: float | None = None

    # -- lifecycle ----------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._closing

    @property
    def disconnect_reason(self) -> str | None:
        return self._disconnect_reason

    def diagnostics(self) -> dict[str, Any]:
        """Return networking statistics and connection status."""
        uptime = (time.time() - self.connected_at) if self.connected_at else 0.0
        return {
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "state": self.state,
            "uptime_seconds": round(uptime, 2),
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "latency_ms": self.latency_ms,
            "compression_enabled": self.compression.enabled,
            "encryption_enabled": self.encryption.enabled,
        }

    async def connect(self, timeout: float = 30.0) -> None:
        """Open the TCP connection and start the reader loop."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=timeout
            )
        except (TimeoutError, OSError) as exc:
            raise BotConnectionError(
                f"Could not connect to {self.host}:{self.port}: {exc}"
            ) from exc
        self._read_task = asyncio.create_task(self._read_loop(), name="leafish-reader")
        self.connected_at = time.time()
        log.debug("Connected to %s:%d", self.host, self.port)

    async def close(self, reason: str = "client closing") -> None:
        """Gracefully close the connection."""
        if self._closing:
            return
        self._closing = True
        self._disconnect_reason = reason
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except (OSError, RuntimeError):
                pass
        if (
            self._read_task is not None
            and not self._read_task.done()
            and asyncio.current_task() is not self._read_task
        ):
            self._read_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._read_task
        if self._on_disconnect is not None:
            result = self._on_disconnect(reason)
            if asyncio.iscoroutine(result):
                await result

    # -- sending --------------------------------------------------------------

    async def send(
        self,
        state: str,
        direction: str,
        name: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Encode and send a packet.

        ``direction`` must be ``"toServer"`` for client->server packets or
        ``"toClient"`` for server->client (used by the status ping reply
        path and tests).
        """
        if self._writer is None or self._closing:
            raise BotConnectionError("Not connected")
        payload = self.codec.encode(state, direction, name, params)
        # Frame + encrypt MUST happen inside _write_lock so AES/CFB8 stream
        # cipher state stays strictly ordered with wire transmission.
        async with self._write_lock:
            if self._writer is None or self._closing:
                raise BotConnectionError("Not connected")
            frame = self._frame_outgoing(payload)
            self._writer.write(frame)
            await self._writer.drain()
            self.packets_sent += 1
            self.bytes_sent += len(frame)

    def _frame_outgoing(self, packet_payload: bytes) -> bytes:
        """Apply compression + length prefix + encryption to *packet_payload*.

        ``packet_payload`` is the raw ``packet_id + fields`` bytes.
        """
        data_section = self.compression.compress_payload(packet_payload)
        if len(data_section) > MAX_PACKET_SIZE:
            raise PacketEncodeError(
                f"Encoded packet too large: {len(data_section)} bytes "
                f"(max {MAX_PACKET_SIZE})"
            )
        frame_body = encode_varint(len(data_section)) + data_section
        if self.encryption.enabled:
            # AES/CFB8 is a stream cipher applied to the whole frame.
            return self.encryption.encrypt_outgoing(frame_body)
        return frame_body

    # -- receiving ------------------------------------------------------------

    async def _read_loop(self) -> None:
        assert self._reader is not None
        try:
            while not self._closing:
                chunk = await self._reader.read(65536)
                if not chunk:
                    raise BotConnectionError("Connection closed by remote host")
                self.bytes_received += len(chunk)
                if self.encryption.enabled:
                    chunk = self.encryption.decrypt_incoming(chunk)
                self._framer_buffer.extend(chunk)
                await self._drain_frames()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._closing:
                self._closing = True
                self._disconnect_reason = str(exc)
                log.debug("Reader loop ended: %r", exc)
                if self._writer is not None:
                    with contextlib.suppress(OSError, RuntimeError):
                        self._writer.close()
                if self._on_disconnect is not None:
                    result = self._on_disconnect(str(exc))
                    if asyncio.iscoroutine(result):
                        with contextlib.suppress(Exception):
                            await result

    async def _drain_frames(self) -> None:
        """Extract complete frames and dispatch them.

        Frames are decoded and dispatched one at a time, awaiting each
        handler, so protocol state transitions (e.g. login -> play)
        take effect before the next frame is decoded. Servers may send
        the state-transition packet and the first next-state packets in
        a single TCP segment.
        """
        while not self._closing:
            res = decode_varint_from_buffer(self._framer_buffer)
            if res is None:
                return  # incomplete frame header; wait for more data
            length, header = res
            if length < 0 or length > MAX_PACKET_SIZE:
                raise ProtocolError(f"Invalid packet length {length}")
            if len(self._framer_buffer) - header < length:
                return  # incomplete frame; wait for more data
            payload = bytes(self._framer_buffer[header : header + length])
            del self._framer_buffer[: header + length]
            await self._handle_frame(payload)

    async def _handle_frame(self, frame: bytes) -> None:
        """Decompress (if needed) and decode one frame, then dispatch."""
        self.packets_received += 1
        data = self.compression.decompress_payload(frame)
        packet = self.codec.decode(self.state, "toClient", data)
        if self._on_packet is not None:
            try:
                result = self._on_packet(self.state, "toClient", packet["name"], packet["params"])
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                log.exception("Packet callback failed")

    # -- state helpers ---------------------------------------------------------

    def set_state(self, state: str) -> None:
        self.state = state

    def enable_compression(self, threshold: int) -> None:
        self.compression.enable(threshold)

    def enable_encryption(self, shared_secret: bytes) -> None:
        self.encryption.enable(shared_secret)
