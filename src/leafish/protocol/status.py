"""Server status (ping) probe for protocol version autodetection.

The status-state packets (``ping_start``/``server_info``/``ping``) are
identical on every supported Minecraft version, so a raw probe can learn
the server's protocol version without knowing it up front. Servers
answer status pings regardless of the protocol version announced in the
handshake — the same reason incompatible servers still appear in the
multiplayer server list.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import struct
from typing import Any

from ..exceptions import BotConnectionError
from ..version import list_versions, load_version_json
from .framing import MAX_PACKET_SIZE, encode_varint

log = logging.getLogger("leafish.protocol.status")


def _string(value: str) -> bytes:
    data = value.encode("utf-8")
    return encode_varint(len(data)) + data


def _frame(payload: bytes) -> bytes:
    return encode_varint(len(payload)) + payload


async def _read_varint(reader: asyncio.StreamReader) -> int:
    result = 0
    shift = 0
    while True:
        byte = await reader.readexactly(1)
        result |= (byte[0] & 0x7F) << shift
        if not (byte[0] & 0x80):
            if result & 0x80000000:
                result -= 1 << 32
            return result
        shift += 7
        if shift >= 35:
            raise BotConnectionError("VarInt too long in status response")


async def _read_frame(reader: asyncio.StreamReader) -> bytes:
    length = await _read_varint(reader)
    if length < 0 or length > MAX_PACKET_SIZE:
        raise BotConnectionError(f"Invalid status packet length {length}")
    return await reader.readexactly(length)


def _latest_protocol_version() -> int:
    """Highest vendored protocol version (sent in the probe handshake)."""
    return max(
        int(load_version_json(v, "version")["version"])
        for v in list_versions()
    )


async def ping_status(
    host: str, port: int, *, timeout: float = 10.0
) -> dict[str, Any] | None:
    """Query the server list status and return the parsed JSON, or None.

    Returns ``None`` when the server does not answer a status ping.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
    except (OSError, TimeoutError):
        return None
    try:
        # handshaking -> status (nextState 1)
        handshake = (
            b"\x00"
            + encode_varint(_latest_protocol_version())
            + _string(host)
            + struct.pack(">H", port)
            + encode_varint(1)
        )
        # ping_start (empty packet, id 0x00)
        writer.write(_frame(handshake) + _frame(b"\x00"))
        await writer.drain()

        async def _probe() -> dict[str, Any] | None:
            while True:
                payload = await _read_frame(reader)
                buf = payload
                pos = 0
                packet_id = 0
                shift = 0
                while pos < len(buf):
                    b = buf[pos]
                    pos += 1
                    packet_id |= (b & 0x7F) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                    if shift >= 35:
                        raise BotConnectionError("VarInt too long in status packet id")
                if packet_id == 0:  # server_info
                    length = 0
                    shift = 0
                    while pos < len(buf):
                        b = buf[pos]
                        pos += 1
                        length |= (b & 0x7F) << shift
                        if not (b & 0x80):
                            break
                        shift += 7
                        if shift >= 35:
                            raise BotConnectionError("VarInt too long in status string length")
                    if length < 0 or pos + length > len(buf):
                        raise BotConnectionError("Truncated status response string")
                    text = buf[pos : pos + length].decode("utf-8")
                    parsed = json.loads(text)
                    return parsed if isinstance(parsed, dict) else None
                # ping (0x01): echo the i64 time back and keep reading
                if packet_id == 1 and len(buf) - pos >= 8:
                    writer.write(_frame(b"\x01" + buf[pos : pos + 8]))
                    await writer.drain()

        return await asyncio.wait_for(_probe(), timeout=timeout)
    except (OSError, TimeoutError, BotConnectionError, ValueError) as exc:
        log.debug("Status probe failed for %s:%d: %r", host, port, exc)
        return None
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


async def detect_server_protocol(
    host: str, port: int, *, timeout: float = 10.0
) -> int | None:
    """Return the server's protocol version via a status ping."""
    info = await ping_status(host, port, timeout=timeout)
    if info is None:
        return None
    try:
        return int(info["version"]["protocol"])
    except (KeyError, TypeError, ValueError):
        return None
