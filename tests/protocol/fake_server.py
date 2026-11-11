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
from typing import Any, ClassVar

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
        # Player-inventory (window 0) model for click handling.
        self.inv: dict[int, dict[str, Any]] = {}
        self.cursor: dict[str, Any] = {"itemCount": 0}
        self.state_id = 0
        self._craft_index: list | None = None
        # Extra open windows: wid -> {"slots": {}, "size": int, "state_id": int}
        self.windows: dict[int, dict[str, Any]] = {}

    _EMPTY_SLOT: ClassVar[dict[str, Any]] = {"itemCount": 0}

    @staticmethod
    def _store_get(store: dict[int, dict[str, Any]], slot: int) -> dict[str, Any]:
        return store.get(slot, _FakeConn._EMPTY_SLOT)

    @staticmethod
    def _store_set(store: dict[int, dict[str, Any]], slot: int,
                   data: dict[str, Any]) -> None:
        if data.get("itemCount", 0) <= 0:
            store.pop(slot, None)
        else:
            store[slot] = data

    def _slot_get(self, slot: int) -> dict[str, Any]:
        return self._store_get(self.inv, slot)

    def _slot_set(self, slot: int, data: dict[str, Any]) -> None:
        self._store_set(self.inv, slot, data)

    async def sync_inventory(self) -> None:
        """Send a full window_items snapshot for window 0."""
        await self.send("window_items", {
            "windowId": 0,
            "stateId": self.state_id,
            "items": [self._slot_get(i) for i in range(46)],
            "carriedItem": self.cursor,
        })

    async def debug_open_window(self, window_id: int, size: int,
                                title: str = "Chest") -> None:
        """Test helper: open a container window of *size* slots."""
        self.windows[window_id] = {
            "slots": {}, "size": size, "state_id": 0,
        }
        await self.send("open_window", {
            "windowId": window_id,
            "inventoryType": 1,
            "windowTitle": {"type": "string", "value": title},
        })
        await self.sync_window(window_id)

    async def debug_set_window_slot(self, window_id: int, slot: int,
                                    item: dict[str, Any]) -> None:
        """Test helper: set a slot in an open container window."""
        win = self.windows.get(window_id)
        if win is None:
            return
        self._store_set(win["slots"], slot, item)
        win["state_id"] += 1
        await self.sync_window(window_id)

    async def sync_window(self, window_id: int) -> None:
        win = self.windows.get(window_id)
        if win is None:
            return
        await self.send("window_items", {
            "windowId": window_id,
            "stateId": win["state_id"],
            "items": [self._store_get(win["slots"], i)
                      for i in range(win["size"])],
            "carriedItem": self.cursor,
        })

    async def debug_set_slot(self, slot: int, item: dict[str, Any]) -> None:
        """Test helper: set a window-0 slot and resync."""
        self._slot_set(slot, item)
        self.state_id += 1
        await self.sync_inventory()

    @staticmethod
    def _item_dict(item_id: int, count: int) -> dict[str, Any]:
        if count <= 0:
            return {"itemCount": 0}
        return {
            "itemCount": count,
            "itemId": item_id,
            "addedComponentCount": 0,
            "removedComponentCount": 0,
            "components": [],
            "removeComponents": [],
        }

    def _apply_click(self, store: dict[int, dict[str, Any]], slot: int,
                     button: int, mode: int) -> bool:
        """Apply a window_click to *store* (slot -> item dict).

        ``self.cursor`` is the shared carried item. Returns True if the
        click was understood.
        """
        # Determine the valid slot range from the store's owner window.
        max_slot = 45
        for win in self.windows.values():
            if win["slots"] is store:
                max_slot = win["size"] - 1
                break
        if not (0 <= slot <= max_slot):
            return False
        if mode == 2:
            # Hotbar swap: mouseButton is the hotbar index 0-8.
            if not (0 <= button <= 8):
                return False
            target = 36 + button if store is self.inv else None
            if target is None or target > max_slot:
                return False
            a = dict(self._store_get(store, slot))
            b = dict(self._store_get(store, target))
            self._store_set(store, slot, b)
            self._store_set(store, target, a)
            return True
        if mode == 1:
            return self._shift_click(store, slot, max_slot)
        if mode != 0:
            return False  # other modes not implemented
        was_result_take = store is self.inv and slot == 0 and \
            self._store_get(store, 0).get("itemCount", 0) > 0
        cur = dict(self.cursor)
        it = dict(self._store_get(store, slot))
        cur_empty = cur.get("itemCount", 0) <= 0
        it_empty = it.get("itemCount", 0) <= 0
        if button == 0:
            if cur_empty and not it_empty:
                self.cursor = it
                self._store_set(store, slot, dict(self._EMPTY_SLOT))
            elif not cur_empty and it_empty:
                self._store_set(store, slot, cur)
                self.cursor = dict(self._EMPTY_SLOT)
            elif not cur_empty and not it_empty:
                if cur.get("itemId") == it.get("itemId") and \
                        cur.get("itemCount", 0) < 64:
                    room = 64 - cur["itemCount"]
                    mv = min(room, it["itemCount"])
                    cur["itemCount"] += mv
                    it["itemCount"] -= mv
                    self.cursor = cur if cur["itemCount"] < 64 else \
                        dict(self._EMPTY_SLOT)
                    self._store_set(store, slot, it if it["itemCount"] > 0 else
                                   dict(self._EMPTY_SLOT))
                else:
                    self.cursor = it
                    self._store_set(store, slot, cur)
        elif button == 1:
            if cur_empty and not it_empty:
                take = (it["itemCount"] + 1) // 2
                self.cursor = {**it, "itemCount": take}
                it["itemCount"] -= take
                self._store_set(store, slot, it if it["itemCount"] > 0 else
                               dict(self._EMPTY_SLOT))
            elif not cur_empty and it_empty:
                if cur.get("itemCount", 0) > 1:
                    cur["itemCount"] -= 1
                    self.cursor = cur
                    placed = dict(cur)
                    placed["itemCount"] = 1
                    self._store_set(store, slot, placed)
                else:
                    self._store_set(store, slot, cur)
                    self.cursor = dict(self._EMPTY_SLOT)
            elif not cur_empty and not it_empty and \
                    cur.get("itemId") == it.get("itemId") and \
                    it.get("itemCount", 0) < 64:
                it["itemCount"] += 1
                cur["itemCount"] -= 1
                self._store_set(store, slot, it)
                self.cursor = cur if cur["itemCount"] > 0 else \
                    dict(self._EMPTY_SLOT)
        if was_result_take and self.cursor.get("itemCount", 0) > 0:
            # Crafting result taken: consume one of each grid ingredient.
            for gs in (1, 2, 3, 4):
                git = dict(self._store_get(self.inv, gs))
                if git.get("itemCount", 0) > 1:
                    git["itemCount"] -= 1
                    self._store_set(self.inv, gs, git)
                else:
                    self._store_set(self.inv, gs, dict(self._EMPTY_SLOT))
        if store is self.inv:
            self._refresh_craft_result()
        return True

    def _shift_click(self, store: dict[int, dict[str, Any]],
                     slot: int, max_slot: int) -> bool:
        """Mode-1 quick-move for container windows (last 36 slots are the
        player inventory section)."""
        if store is self.inv or max_slot < 36:
            return False
        container_end = max_slot + 1 - 36
        src = dict(self._store_get(store, slot))
        if src.get("itemCount", 0) <= 0:
            return True
        if slot < container_end:
            dest_range = range(container_end, max_slot + 1)
        else:
            dest_range = range(0, container_end)
        # Merge into same-id stacks first, then first empty slot.
        remaining = src["itemCount"]
        for d in dest_range:
            if remaining <= 0:
                break
            dst = dict(self._store_get(store, d))
            if dst.get("itemCount", 0) > 0 and \
                    dst.get("itemId") == src.get("itemId") and \
                    dst.get("itemCount", 0) < 64:
                room = 64 - dst["itemCount"]
                mv = min(room, remaining)
                dst["itemCount"] += mv
                remaining -= mv
                self._store_set(store, d, dst)
        if remaining > 0:
            for d in dest_range:
                if remaining <= 0:
                    break
                if self._store_get(store, d).get("itemCount", 0) <= 0:
                    moved = dict(src)
                    moved["itemCount"] = remaining
                    self._store_set(store, d, moved)
                    remaining = 0
        leftover = dict(src)
        leftover["itemCount"] = remaining
        self._store_set(store, slot,
                        leftover if remaining > 0 else
                        dict(self._EMPTY_SLOT))
        return True

    # -- minimal crafting -------------------------------------------------------

    def _craft_recipes(self) -> list:
        """Lazily built recipe list: (kind, key, result_id, result_count)."""
        if self._craft_index is None:
            from leafish.data.registry import get_gamedata
            gd = get_gamedata(self.codec.minecraft_version)
            idx = []
            for variants in gd.recipes().values():
                for var in variants or []:
                    if not isinstance(var, dict):
                        continue
                    res = var.get("result") or {}
                    rid, rc = res.get("id"), int(res.get("count") or 1)
                    if rid is None:
                        continue
                    if "inShape" in var:
                        grid = var["inShape"] or []
                        cells = [
                            (r, c, g)
                            for r, row in enumerate(grid)
                            for c, g in enumerate(row)
                            if g is not None
                        ]
                        if not cells:
                            continue
                        r0 = min(r for r, _, _ in cells)
                        r1 = max(r for r, _, _ in cells)
                        c0 = min(c for _, c, _ in cells)
                        c1 = max(c for _, c, _ in cells)
                        shape = []
                        for r in range(r0, r1 + 1):
                            row = []
                            for c in range(c0, c1 + 1):
                                gid = grid[r][c] if c < len(grid[r]) else None
                                row.append(gid)
                            shape.append(tuple(row))
                        idx.append(("shape", (r1 - r0 + 1, c1 - c0 + 1),
                                    tuple(shape), rid, rc))
                    else:
                        ings = tuple(sorted(
                            g for g in (var.get("ingredients") or [])
                            if g is not None
                        ))
                        if ings:
                            idx.append(("shapeless", ings, None, rid, rc))
            self._craft_index = idx
        return self._craft_index

    def _grid_shape(self):
        """Normalize the 2x2 grid (slots 1-4) to (h, w, shape-tuple)."""
        pat = {}
        for i, s in enumerate((1, 2, 3, 4)):
            it = self._slot_get(s)
            if it.get("itemCount", 0) > 0:
                pat[(i // 2, i % 2)] = it.get("itemId")
        if not pat:
            return None
        rs = [r for r, _ in pat]
        cs = [c for _, c in pat]
        r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
        h, w = r1 - r0 + 1, c1 - c0 + 1
        shape = []
        for r in range(r0, r1 + 1):
            row = []
            for c in range(c0, c1 + 1):
                row.append(pat.get((r, c)))
            shape.append(tuple(row))
        return (h, w, tuple(shape))

    def _refresh_craft_result(self) -> None:
        """Recompute crafting slot 0 from the 2x2 grid contents."""
        gs = self._grid_shape()
        result = None
        if gs is not None:
            h, w, shape = gs
            flat = tuple(sorted(g for row in shape for g in row if g is not None))
            for kind, key, sshape, rid, rc in self._craft_recipes():
                if kind == "shape" and key == (h, w) and sshape == shape:
                    result = (rid, rc)
                    break
                if kind == "shapeless" and key == flat and len(flat) <= 4:
                    result = (rid, rc)
                    break
        if result is None:
            self._slot_set(0, dict(self._EMPTY_SLOT))
        else:
            rid, rc = result
            self._slot_set(0, self._item_dict(rid, rc))

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
            elif name == "window_click" and conn.state == "play":
                wid = int(params.get("windowId", 0))
                store = conn.inv
                win = None
                if wid != 0:
                    win = conn.windows.get(wid)
                    if win is None:
                        continue
                    store = win["slots"]
                applied = conn._apply_click(
                    store,
                    int(params.get("slot", -1)),
                    int(params.get("mouseButton", 0)),
                    int(params.get("mode", 0)),
                )
                if applied:
                    if wid == 0:
                        conn.state_id += 1
                        await conn.sync_inventory()
                    else:
                        assert win is not None
                        win["state_id"] += 1
                        await conn.sync_window(wid)
            elif name == "set_creative_slot" and conn.state == "play":
                conn._slot_set(int(params.get("slot", -1)),
                               params.get("item") or {"itemCount": 0})
                conn.state_id += 1
                await conn.sync_inventory()

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
