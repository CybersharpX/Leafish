"""A minimal fake Minecraft server for protocol integration tests.

Speaks enough of the Java protocol (handshaking -> login -> configuration ->
play) to exercise Leafish's client end-to-end: handshake, login_start,
login success, finish_configuration, login/spawn packets, keepalive,
position sync, chat and movement.

Usage::

    server = FakeMinecraftServer()
    await server.start()   # picks a free port
    bot = await Leafish.create_bot(host="127.0.0.1", port=server.port,
                                   username="TestBot", auth="offline")
    ...
    await server.stop()
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from leafish.protocol.compression import CompressionHandler
from leafish.protocol.framing import BufferReader, encode_varint
from leafish.protocol.protodef import ProtocolCodec

log = logging.getLogger("leafish.test.fake_server")

MAX_PACKET = 2 * 1024 * 1024


class _FakeConn:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 codec: ProtocolCodec) -> None:
        self.reader = reader
        self.writer = writer
        self.codec = codec
        self.state = "handshaking"
        self.compression = CompressionHandler()
        self.buf = bytearray()
        self.username: str | None = None
        self.entity_id = 1

    async def send(self, name: str, params: dict[str, Any] | None = None) -> None:
        payload = self.codec.encode(self.state, "toClient", name, params or {})
        data = self.compression.compress_payload(payload)
        frame = encode_varint(len(data)) + data
        self.writer.write(frame)
        await self.writer.drain()

    async def read_packet(self) -> dict[str, Any] | None:
        """Read one packet; returns {'name','params'} or None on EOF."""
        while True:
            reader = BufferReader(bytes(self.buf))
            try:
                length = reader.read_varint()
            except Exception:
                length = None
            if length is not None and 0 <= length <= MAX_PACKET:
                header = reader.pos
                if len(self.buf) - header >= length:
                    frame = bytes(self.buf[header:header + length])
                    del self.buf[:header + length]
                    data = self.compression.decompress_payload(frame)
                    return self.codec.decode(self.state, "toServer", data)
            chunk = await self.reader.read(65536)
            if not chunk:
                return None
            self.buf.extend(chunk)

    def set_state(self, state: str) -> None:
        self.state = state


class FakeMinecraftServer:
    """Async fake server implementing the login/config/play handshake."""

    def __init__(self, version: str = "1.21.11") -> None:
        self.codec = ProtocolCodec.for_version(version)
        self.version = version
        self.port: int = 0
        self._server: asyncio.AbstractServer | None = None
        self.connections: list[_FakeConn] = []
        self._tasks: list[asyncio.Task] = []
        #: Called with (conn, name, params) for every clientbound->server
        #: packet after 'login_start'. Tests can override to inject behavior.
        self.on_client_packet = None
        #: Extra packets the server sends after spawn (e.g. chunks).
        self.spawn_packets: list[tuple[str, dict]] = []

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> int:
        self._server = await asyncio.start_server(
            self._handle, host, port
        )
        sock = self._server.sockets[0]
        self.port = sock.getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        for t in self._tasks:
            t.cancel()
        for conn in self.connections:
            with contextlib.suppress(Exception):
                conn.writer.close()

    async def _handle(self, reader: asyncio.StreamReader,
                      writer: asyncio.StreamWriter) -> None:
        conn = _FakeConn(reader, writer, self.codec)
        self.connections.append(conn)
        try:
            await self._session(conn)
        except (ConnectionError, asyncio.CancelledError):
            pass
        except Exception:
            log.exception("Fake server session error")
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    async def _session(self, conn: _FakeConn) -> None:
        # -- handshaking ---------------------------------------------------
        pkt = await conn.read_packet()
        if pkt is None or pkt["name"] != "set_protocol":
            return
        conn.set_state("login")

        # -- login -----------------------------------------------------------
        pkt = await conn.read_packet()
        if pkt is None or pkt["name"] != "login_start":
            return
        conn.username = pkt["params"].get("username")

        # login success (online-mode-lite: no encryption, no compression)
        await conn.send("success", {
            "uuid": "00000000-0000-0000-0000-000000000001",
            "username": conn.username or "fake",
            "properties": [],
        })

        pkt = await conn.read_packet()
        if pkt is None or pkt["name"] != "login_acknowledged":
            return

        # -- configuration ------------------------------------------------------
        conn.set_state("configuration")
        # Tell the client configuration is done immediately.
        await conn.send("finish_configuration", {})

        pkt = await conn.read_packet()
        if pkt is None or pkt["name"] != "finish_configuration":
            return

        # -- play -----------------------------------------------------------------
        conn.set_state("play")
        await self._send_spawn(conn)

        # Packet loop: respond to keepalive, record everything else.
        while True:
            pkt = await conn.read_packet()
            if pkt is None:
                return
            name = pkt["name"]
            params = pkt["params"]
            if self.on_client_packet is not None:
                result = self.on_client_packet(conn, name, params)
                if asyncio.iscoroutine(result):
                    await result
            if name == "keep_alive":
                await conn.send("keep_alive", {"keepAliveId": params.get("keepAliveId")})

    async def _send_spawn(self, conn: _FakeConn) -> None:
        await conn.send("login", {
            "entityId": conn.entity_id,
            "isHardcore": False,
            "worldNames": ["minecraft:overworld"],
            "maxPlayers": 20,
            "viewDistance": 10,
            "simulationDistance": 10,
            "reducedDebugInfo": False,
            "enableRespawnScreen": True,
            "doLimitedCrafting": False,
            "worldState": {
                "dimension": 0,
                "name": "minecraft:overworld",
                "hashedSeed": 0,
                "gamemode": "survival",
                "previousGamemode": 255,
                "isDebug": False,
                "isFlat": False,
                "death": None,
                "portalCooldown": 0,
                "seaLevel": 63,
            },
            "enforcesSecureChat": False,
        })
        await conn.send("position", {
            "teleportId": 1,
            "x": 0.0, "y": 64.0, "z": 0.0,
            "dx": 0.0, "dy": 0.0, "dz": 0.0,
            "yaw": 0.0, "pitch": 0.0,
            "flags": {},
        })
        for name, params in self.spawn_packets:
            await conn.send(name, params)
