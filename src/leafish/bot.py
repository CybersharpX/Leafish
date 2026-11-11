"""LeafishBot: the central public API object."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from .auth.microsoft import MicrosoftAuth
from .auth.offline import OfflineAuth
from .auth.session import AuthSession
from .config import BotConfig
from .entities.entity import Player
from .entities.manager import EntityManager
from .events.emitter import EventEmitter
from .exceptions import LeafishError
from .inventory.inventory import Inventory
from .modules.actions import ActionsModule
from .modules.chat import ChatModule
from .modules.collector import CollectorModule
from .modules.containers import ContainerModule
from .modules.crafting import CraftingModule
from .modules.farming import FarmingModule
from .modules.fishing import FishingModule
from .modules.health import HealthModule
from .modules.movement import CONTROL_STATES, MovementModule
from .modules.pathfinder import Pathfinder
from .modules.physics import PhysicsEngine
from .modules.pvp import PVPModule
from .plugins import PluginManager
from .protocol.protodef import ProtocolCodec
from .protocol.session import ClientSession
from .utils.text import component_to_text, nbt_to_python
from .utils.vectors import BlockPos, Vec3
from .world.chunk_codec import ChunkDecodeError, decode_chunk_sections
from .world.world import World

log = logging.getLogger("leafish.bot")


class LeafishBot:
    """A connected (or connecting) Minecraft bot."""

    def __init__(
        self,
        config: BotConfig,
        auth: AuthSession,
        codec: ProtocolCodec,
    ) -> None:
        self.config = config
        self.auth = auth
        self.codec = codec
        self.emitter = EventEmitter()

        # Core state -----------------------------------------------------
        self.entity: Player | None = None
        """The bot's own player entity."""
        self.entity_id: int | None = None
        self.username: str = auth.username
        self.uuid: str = auth.uuid
        self.game_mode: str | None = None
        self.server_brand: str | None = None
        self.spawned = False

        # Subsystems -------------------------------------------------------
        self.world = World(self, codec.minecraft_version)
        self.entities = EntityManager(self.world.gamedata.entity_type_ids)
        self.inventory = Inventory(self)
        self.physics = PhysicsEngine(self)
        self.movement = MovementModule(self)
        self.health = HealthModule(self)
        self.chat_module = ChatModule(self)
        self.actions = ActionsModule(self)
        self.crafting = CraftingModule(self)
        self.pathfinder = Pathfinder(self)
        self.pvp = PVPModule(self)
        self.fishing = FishingModule(self)
        self.collector = CollectorModule(self)
        self.farming = FarmingModule(self)
        self.containers = ContainerModule(self)
        self.plugins = PluginManager(self)

        # Movement control states --------------------------------------------
        self.control_states: dict[str, bool] = {c: False for c in CONTROL_STATES}

        # Window state --------------------------------------------------------
        self.current_window_id: int | None = None
        self.inventory_state_id: int = 0

        # Session -------------------------------------------------------------
        self.session: ClientSession | None = None
        self._disconnect_waiters: list[asyncio.Future] = []
        self._first_position_received = False
        self._ended = False
        self._disconnect_task: asyncio.Task | None = None

    # -- event API (delegated to emitter) ----------------------------------------

    def on(self, event: str, handler=None):
        return self.emitter.on(event, handler)

    def once(self, event: str, handler=None):
        return self.emitter.once(event, handler)

    def off(self, event: str, handler=None):
        self.emitter.off(event, handler)

    def emit(self, event: str, *args, **kwargs) -> None:
        self.emitter.emit(event, *args, **kwargs)

    async def wait_for(self, event: str, timeout: float | None = None):
        return await self.emitter.wait_for(event, timeout)

    async def wait_until_disconnected(self) -> None:
        if self.session is not None:
            await self.session.wait_until_disconnected()

    # -- connection lifecycle ----------------------------------------------------

    async def _start(self) -> None:
        self.session = ClientSession(
            self.config,
            self.codec,
            on_packet=self._on_packet,
            on_state_change=self._on_state_change,
        )
        await self.session.connect_and_login(
            self.username,
            self.uuid,
            access_token=self.auth.access_token,
        )
        self.physics.start()
        self._disconnect_task = asyncio.create_task(
            self._watch_disconnect(), name="leafish-disconnect-watch"
        )

    async def _watch_disconnect(self) -> None:
        """Stop subsystems and emit ``end`` when the connection drops."""
        assert self.session is not None
        await self.session.wait_until_disconnected()
        await self._cleanup_after_disconnect()

    async def _cleanup_after_disconnect(self) -> None:
        if self._ended:
            return
        self._ended = True
        await self.physics.stop()
        reason = "client disconnect"
        if self.session is not None:
            reason = self.session.state.disconnect_reason or reason
        self.emit("end", reason)

    async def disconnect(self, reason: str = "client disconnect") -> None:
        """Disconnect gracefully."""
        if self.session is not None:
            await self.session.disconnect(reason)
        await self.physics.stop()
        await self._cleanup_after_disconnect()

    async def quit(self, reason: str = "client quit") -> None:
        """Alias for :meth:`disconnect`."""
        await self.disconnect(reason)

    # -- packet plumbing ---------------------------------------------------------

    async def _send_play(self, name: str, params: dict[str, Any] | None = None) -> None:
        if self.session is None:
            raise LeafishError("Bot is not connected")
        await self.session.send("play", "toServer", name, params)

    async def _on_state_change(self, state: str) -> None:
        if state == "play":
            self.emit("login")

    async def _on_packet(
        self, state: str, direction: str, name: str, params: dict[str, Any]
    ) -> None:
        if direction != "toClient":
            return
        if state == "configuration":
            if name == "registry_data":
                self._on_registry_data(params)
            return
        if state != "play":
            return
        handler = getattr(self, f"_packet_{name}", None)
        if handler is not None:
            try:
                result = handler(params)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                log.exception("Packet handler for '%s' failed", name)
                self.emit("error", name, params)

    async def _click_window_slot(
        self, window_id: int, slot: int, button: int = 0,
        state_id: int | None = None,
    ) -> None:
        await self._send_play(
            "window_click",
            {
                "windowId": window_id,
                "stateId": (
                    self.inventory_state_id if state_id is None else state_id
                ),
                "slot": slot,
                "mouseButton": button,
                "mode": 0,
                "changedSlots": [],
                "cursorItem": None,
            },
        )

    def _on_registry_data(self, params: dict[str, Any]) -> None:
        """Capture synchronized registries sent during the config state."""
        reg = params.get("id")
        entries = params.get("entries") or []
        if reg == "minecraft:dimension_type":
            for entry in entries:
                value = nbt_to_python(entry.get("value"))
                if isinstance(value, dict):
                    self.world.dimension_types[entry.get("key", "")] = {
                        "min_y": int(value.get("min_y", -64)),
                        "height": int(value.get("height", 384)),
                    }
        elif reg == "minecraft:dimension":
            for entry in entries:
                value = nbt_to_python(entry.get("value"))
                if isinstance(value, dict):
                    self.world.dimensions[entry.get("key", "")] = value
        elif reg == "minecraft:worldgen/biome":
            self.world.biome_count = len(entries)

    # -- play-state packet handlers -------------------------------------------------

    def _packet_login(self, params: dict[str, Any]) -> None:
        self.entity_id = params.get("entityId")
        ws = params.get("worldState", {})
        self.game_mode = ws.get("gamemode")
        self.world.apply_dimension(ws.get("name"), ws.get("dimension"))
        if self.entity is None and self.entity_id is not None:
            self.entity = Player(id=self.entity_id, uuid=self.uuid, name=self.username)

    async def _packet_position(self, params: dict[str, Any]) -> None:
        entity = self.entity
        if entity is None:
            return
        flags = params.get("flags") or {}
        if isinstance(flags, dict):
            flag_set = {k for k, v in flags.items() if v and k != "_value"}
        else:
            flag_set = set(flags if isinstance(flags, list) else [flags])
        x = float(params.get("x", 0))
        y = float(params.get("y", 0))
        z = float(params.get("z", 0))
        if "x" in flag_set:
            x += entity.position.x
        if "y" in flag_set:
            y += entity.position.y
        if "z" in flag_set:
            z += entity.position.z
        entity.set_position(x, y, z)
        vx = float(params.get("dx", 0))
        vy = float(params.get("dy", 0))
        vz = float(params.get("dz", 0))
        if "dx" in flag_set:
            vx += entity.velocity.x
        if "dy" in flag_set:
            vy += entity.velocity.y
        if "dz" in flag_set:
            vz += entity.velocity.z
        entity.velocity = Vec3(vx, vy, vz)
        yaw = float(params.get("yaw", entity.yaw))
        pitch = float(params.get("pitch", entity.pitch))
        if "yaw" in flag_set:
            yaw += entity.yaw
        if "pitch" in flag_set:
            pitch += entity.pitch
        entity.set_rotation(yaw, pitch)
        entity.on_ground = "onGround" in flag_set or (
            isinstance(flags, dict) and bool(flags.get("onGround"))
        ) or (isinstance(flags, int) and bool(flags & 1))
        # Confirm the teleport.
        teleport_id = params.get("teleportId")
        if teleport_id is not None:
            await self._send_play("teleport_confirm", {"teleportId": teleport_id})
        if not self._first_position_received:
            self._first_position_received = True
            self.spawned = True
            self.emit("spawn")
        else:
            self.emit("forced_move")

    def _packet_respawn(self, params: dict[str, Any]) -> None:
        ws = params.get("worldState", params.get("commonPlayerSpawnInfo", {}))
        self.game_mode = ws.get("gamemode")
        self.world.apply_dimension(ws.get("name"), ws.get("dimension"))
        self.world.chunks.clear()
        self.entities.clear()
        self.emit("respawn")
        self.spawned = False
        self._first_position_received = False

    def _packet_player_chat(self, params: dict[str, Any]) -> None:
        sender_uuid = params.get("senderUuid")
        username = self._player_name(sender_uuid) or str(sender_uuid)
        message = params.get("plainMessage") or ""
        self.emit("chat", username, message)
        self.emit("player_chat", username, message, params)

    def _packet_system_chat(self, params: dict[str, Any]) -> None:
        text = component_to_text(nbt_to_python(params.get("content")))
        self.emit("chat", None, text)
        self.emit("message", {"type": "system", "text": text})

    def _packet_profileless_chat(self, params: dict[str, Any]) -> None:
        message = component_to_text(nbt_to_python(params.get("message")))
        name = component_to_text(nbt_to_python(params.get("name"))) or None
        self.emit("chat", name, message)

    def _packet_player_info(self, params: dict[str, Any]) -> None:
        action = params.get("action") or {}
        if isinstance(action, dict):
            actions = {k for k, v in action.items() if v and k != "_value"}
        else:
            actions = set(action if isinstance(action, list) else [action])
        for entry in params.get("data", []):
            uuid_str = entry.get("uuid")
            player = entry.get("player") or {}
            name = None
            if isinstance(player, dict):
                name = player.get("name")
            if "add_player" in actions or "update_display_name" in actions:
                from .entities.entity import Player as _P

                existing = self.entities.players.get(uuid_str)
                if existing is None:
                    existing = _P(id=-1, uuid=uuid_str, name=name)
                    self.entities.players[uuid_str] = existing
                    self.emit("player_join", existing)
                if name:
                    existing.name = name
                if "update_game_mode" in actions:
                    existing.game_mode = entry.get("gamemode")
                if "update_latency" in actions:
                    existing.latency = entry.get("latency")
                self.emit("player_updated", existing)
            if "remove_player" in actions or "remove" in actions:
                removed = self.entities.players.pop(uuid_str, None)
                if removed is not None:
                    self.emit("player_leave", removed)

    def _packet_player_remove(self, params: dict[str, Any]) -> None:
        for uuid_str in params.get("players", []):
            removed = self.entities.players.pop(uuid_str, None)
            if removed is not None:
                self.emit("player_leave", removed)

    def _packet_playerlist_header(self, params: dict[str, Any]) -> None:
        self.emit("playerlist_header", params)

    def _packet_update_health(self, params: dict[str, Any]) -> None:
        old = self.health.health
        self.health.update_health(params)
        self.emit("health", self.health.health, self.health.food)
        self.emit("food", self.health.food, self.health.food_saturation)
        if old != self.health.health:
            self.emit("entity_hurt", self.entity)

    def _packet_experience(self, params: dict[str, Any]) -> None:
        self.health.update_experience(params)
        self.emit("experience", self.health.experience_level,
                  self.health.experience_progress)

    def _packet_held_item_slot(self, params: dict[str, Any]) -> None:
        slot_id = int(params.get("slotId", params.get("slot", 0)))
        # slotId is a window slot (36-44) or a hotbar index depending on version.
        if 36 <= slot_id <= 44:
            slot_id -= 36
        self.inventory.held_slot = slot_id
        self.emit("held_item_changed", slot_id)

    def _packet_set_player_inventory(self, params: dict[str, Any]) -> None:
        self.inventory.update_slot(0, int(params.get("slotId", 0)), params.get("contents", {}))
        self.emit("inventory_update")

    def _packet_set_slot(self, params: dict[str, Any]) -> None:
        wid = int(params.get("windowId", 0))
        slot = int(params.get("slot", 0))
        if wid == 0:
            self.inventory_state_id = int(params.get("stateId", 0))
            self.inventory.update_slot(wid, slot, params.get("item", {}))
        else:
            self.containers.set_state(wid, int(params.get("stateId", 0)))
            self.containers.update_slot(wid, slot, params.get("item", {}))
        self.emit("inventory_update")

    def _packet_window_items(self, params: dict[str, Any]) -> None:
        wid = int(params.get("windowId", 0))
        items = params.get("items", [])
        if wid == 0:
            self.inventory_state_id = int(params.get("stateId", 0))
            self.inventory.update_contents(
                wid, items, params.get("carriedItem"),
            )
        else:
            self.containers.set_state(wid, int(params.get("stateId", 0)))
            self.containers.update_contents(wid, items)
        self.emit("inventory_update")

    def _packet_open_window(self, params: dict[str, Any]) -> None:
        wid = params.get("windowId")
        title = component_to_text(nbt_to_python(params.get("windowTitle")))
        self.current_window_id = wid
        if wid is not None:
            self.containers.open_window(
                int(wid), title, params.get("inventoryType"),
            )
        self.emit("window_open", self.current_window_id, title, params)

    def _packet_close_window(self, params: dict[str, Any]) -> None:
        wid = params.get("windowId", self.current_window_id)
        if self.current_window_id == wid:
            self.current_window_id = None
        if wid is not None:
            self.containers.close_window(int(wid))
        self.emit("window_close", wid)

    # -- entities -----------------------------------------------------------------

    def _packet_spawn_entity(self, params: dict[str, Any]) -> None:
        entity = self.entities.spawn(params)
        self.emit("entity_spawn", entity)

    def _packet_entity_metadata(self, params: dict[str, Any]) -> None:
        entity = self.entities.update_metadata(
            params["entityId"], params.get("metadata", [])
        )
        if entity is not None:
            self.emit("entity_metadata_update", entity)

    def _packet_entity_equipment(self, params: dict[str, Any]) -> None:
        entity = self.entities.update_equipment(
            params["entityId"], params.get("equipments", [])
        )
        if entity is not None:
            self.emit("entity_equipment_update", entity)

    def _packet_entity_destroy(self, params: dict[str, Any]) -> None:
        removed = self.entities.destroy(params.get("entityIds", []))
        for e in removed:
            self.emit("entity_destroy", e)

    def _packet_entity_velocity(self, params: dict[str, Any]) -> None:
        e = self.entities.get(params["entityId"])
        if e is not None:
            v = params.get("velocity", {})
            e.velocity = Vec3(v.get("x", 0), v.get("y", 0), v.get("z", 0))
            self.emit("entity_update", e)

    def _packet_sync_entity_position(self, params: dict[str, Any]) -> None:
        e = self.entities.teleport(params["entityId"], params)
        if e is not None:
            self.emit("entity_teleport", e)

    def _packet_entity_teleport(self, params: dict[str, Any]) -> None:
        e = self.entities.teleport(params["entityId"], params)
        if e is not None:
            self.emit("entity_teleport", e)

    def _packet_entity_move_look(self, params: dict[str, Any]) -> None:
        e = self.entities.move_relative(
            params["entityId"],
            params.get("dX", 0), params.get("dY", 0), params.get("dZ", 0),
            yaw=params.get("yaw"), pitch=params.get("pitch"),
            on_ground=params.get("onGround"),
        )
        if e is not None:
            self.emit("entity_move", e)

    def _packet_rel_entity_move(self, params: dict[str, Any]) -> None:
        e = self.entities.move_relative(
            params["entityId"],
            params.get("dX", 0), params.get("dY", 0), params.get("dZ", 0),
            on_ground=params.get("onGround"),
        )
        if e is not None:
            self.emit("entity_move", e)

    def _packet_entity_look(self, params: dict[str, Any]) -> None:
        e = self.entities.get(params["entityId"])
        if e is not None:
            e.set_rotation(
                float(params.get("yaw", 0)) * 360.0 / 256.0,
                float(params.get("pitch", 0)) * 360.0 / 256.0,
            )
            e.on_ground = bool(params.get("onGround", False))
            self.emit("entity_update", e)

    # -- world ---------------------------------------------------------------------

    def _packet_map_chunk(self, params: dict[str, Any]) -> None:
        cx, cz = int(params.get("x", 0)), int(params.get("z", 0))
        raw = params.get("chunkData")
        if raw is None:
            data = b""
        elif isinstance(raw, (bytes, bytearray)):
            data = bytes(raw)
        else:
            data = bytes(raw)
        heightmaps = {
            hm.get("type"): hm.get("data")
            for hm in (params.get("heightmaps") or [])
            if isinstance(hm, dict)
        }
        block_entities = params.get("blockEntities") or []
        try:
            sections = decode_chunk_sections(
                data,
                section_count=self.world.section_count,
                min_section_y=self.world.min_section_y,
            )
        except ChunkDecodeError:
            log.exception("Failed to decode chunk column (%d, %d)", cx, cz)
            sections = []
        self.world.load_chunk_data(
            cx, cz, sections,
            heightmaps=heightmaps, block_entities=block_entities,
        )
        self.emit("chunk_column_load", cx, cz)

    def _packet_unload_chunk(self, params: dict[str, Any]) -> None:
        cx, cz = params.get("chunkX", 0), params.get("chunkZ", 0)
        self.world.unload_chunk(cx, cz)
        self.emit("chunk_column_unload", cx, cz)

    def _packet_block_change(self, params: dict[str, Any]) -> None:
        loc = params.get("location", {})
        pos = _pos_from_bitfield(loc)
        state_id = params.get("type")
        if pos is not None and isinstance(state_id, int):
            self.world.set_block_state(pos, state_id)
            self.emit("block_update", pos, state_id)

    def _packet_multi_block_change(self, params: dict[str, Any]) -> None:
        coords = params.get("chunkCoordinates") or {}
        try:
            cx = int(coords.get("x", 0))
            cz = int(coords.get("z", 0))
            section_y = int(coords.get("y", 0))
        except (AttributeError, TypeError, ValueError):
            return
        for record in params.get("records") or []:
            record = int(record)
            state_id = record >> 12
            local = record & 0xFFF
            lx = (local >> 8) & 0xF
            lz = (local >> 4) & 0xF
            ly = local & 0xF
            pos = BlockPos(cx * 16 + lx, section_y * 16 + ly, cz * 16 + lz)
            self.world.set_block_state(pos, state_id)
        self.emit("multi_block_change", params)

    def _packet_tile_entity_data(self, params: dict[str, Any]) -> None:
        pos = _pos_from_bitfield(params.get("location"))
        nbt = nbt_to_python(params.get("nbtData"))
        block = self.world.block_at(pos) if pos is not None else None
        if block is not None:
            block.block_entity = nbt if isinstance(nbt, dict) else {"data": nbt}
        self.emit("block_entity_data", pos, nbt, params)

    def _packet_update_light(self, params: dict[str, Any]) -> None:
        self.emit("update_light", params)

    def _packet_chunk_biomes(self, params: dict[str, Any]) -> None:
        # Biome-only updates carry raw paletted-container bytes per chunk;
        # stored for consumers until light/biome queries are needed.
        self.emit("chunk_biomes", params)

    def _packet_game_state_change(self, params: dict[str, Any]) -> None:
        reason = params.get("reason")
        self.emit("game_state_change", reason, params.get("gameMode"))
        if reason in ("start_raining", "stop_raining", "rain_level_change",
                      "thunder_level_change"):
            self.world.set_weather({"raining": reason == "start_raining"})
            self.emit("weather_update", self.world.weather)

    def _packet_update_time(self, params: dict[str, Any]) -> None:
        self.world.set_time(
            params.get("age", 0), params.get("time", 0),
            bool(params.get("tickDayTime", False)),
        )
        self.emit("time_update", self.world.time, self.world.time_of_day)

    def _packet_abilities(self, params: dict[str, Any]) -> None:
        self.emit("abilities", params)

    def _packet_entity_status(self, params: dict[str, Any]) -> None:
        self.emit("entity_status", params.get("entityId"), params.get("entityStatus"))

    def _packet_entity_effect(self, params: dict[str, Any]) -> None:
        self.emit("entity_effect", params)

    def _packet_remove_entity_effect(self, params: dict[str, Any]) -> None:
        self.emit("remove_entity_effect", params)

    def _packet_entity_update_attributes(self, params: dict[str, Any]) -> None:
        self.emit("entity_update_attributes", params)

    def _packet_explosion(self, params: dict[str, Any]) -> None:
        self.emit("explosion", params)

    def _packet_damage_event(self, params: dict[str, Any]) -> None:
        self.emit("damage_event", params)

    def _packet_world_event(self, params: dict[str, Any]) -> None:
        self.emit("world_event", params)

    def _packet_world_particles(self, params: dict[str, Any]) -> None:
        self.emit("world_particles", params)

    def _packet_sound_effect(self, params: dict[str, Any]) -> None:
        self.emit("sound_effect", params)

    def _packet_entity_sound_effect(self, params: dict[str, Any]) -> None:
        self.emit("entity_sound_effect", params)

    def _packet_entity_head_rotation(self, params: dict[str, Any]) -> None:
        e = self.entities.get(params["entityId"])
        if e is not None:
            e.head_yaw = float(params.get("headYaw", 0)) * 360.0 / 256.0

    def _packet_attach_entity(self, params: dict[str, Any]) -> None:
        self.emit("attach_entity", params)

    def _packet_update_view_position(self, params: dict[str, Any]) -> None:
        self.emit("update_view_position", params)

    def _packet_spawn_position(self, params: dict[str, Any]) -> None:
        self.emit("spawn_position", params)

    def _packet_chunk_batch_start(self, params: dict[str, Any]) -> None:
        self.emit("chunk_batch_start")

    def _packet_chunk_batch_finished(self, params: dict[str, Any]) -> None:
        self.emit("chunk_batch_finished", params)

    def _packet_custom_payload(self, params: dict[str, Any]) -> None:
        self.emit("custom_payload", params.get("channel"), params.get("data"))

    async def _packet_cookie_request(self, params: dict[str, Any]) -> None:
        # Acknowledge cookie requests to keep the server happy.
        with contextlib.suppress(Exception):
            await self._send_play(
                "custom_payload",
                {"channel": "minecraft:cookie", "data": b""},
            )

    def _packet_kick_disconnect(self, params: dict[str, Any]) -> None:
        text = component_to_text(nbt_to_python(params.get("reason")))
        self.emit("kicked", text)

    # -- lookups ---------------------------------------------------------------------

    def _player_name(self, uuid_str: str | None) -> str | None:
        if not uuid_str:
            return None
        p = self.entities.players.get(uuid_str)
        return p.name if p else None

    def nearest_entity(self, predicate=None, max_distance: float | None = None):
        if self.entity is None:
            return None
        return self.entities.nearest(self.entity.position, predicate, max_distance)

    def entity_at(self, position) -> Any:
        """Entity whose bounding box contains *position*."""
        point = position if isinstance(position, Vec3) else Vec3(*position)
        best = None
        best_d = float("inf")
        for e in self.entities.all():
            d = point.distance_to(e.position)
            if d < best_d:
                best_d = d
                best = e
        return best

    def find_entity(self, predicate) -> Any:
        for e in self.entities.all():
            if predicate(e):
                return e
        return None

    # -- world lookups -----------------------------------------------------------------

    def block_at(self, position):
        return self.world.block_at(position)

    def find_block(self, names, **kwargs):
        return self.world.find_block(names, **kwargs)

    def find_blocks(self, names, **kwargs):
        return self.world.find_blocks(names, **kwargs)

    def can_dig_block(self, block) -> bool:
        return self.world.can_dig_block(block)

    # -- chat -------------------------------------------------------------------------

    async def chat(self, message: str) -> None:
        await self.chat_module.chat(message)

    async def command(self, command: str) -> None:
        await self.chat_module.command(command)

    # -- movement -----------------------------------------------------------------------

    async def set_control_state(self, control: str, value: bool) -> None:
        await self.movement.set_control_state(control, value)

    async def look(self, yaw: float, pitch: float) -> None:
        await self.movement.look(yaw, pitch)

    async def look_at(self, target) -> None:
        await self.movement.look_at(target)

    async def move_to(self, target, timeout: float | None = None) -> None:
        await self.movement.move_to(target, timeout)

    # -- pathfinding -----------------------------------------------------------------

    def find_path(self, start, goal, **kwargs):
        return self.pathfinder.find_path(start, goal, **kwargs)

    async def goto(self, goal, timeout: float | None = None) -> bool:
        return await self.pathfinder.goto(goal, timeout=timeout)

    async def stop_moving(self) -> None:
        await self.movement.stop_moving()

    # -- plugins ------------------------------------------------------------------

    def load_plugin(self, plugin, name: str | None = None) -> str:
        """Load a plugin (callable ``fn(bot)`` or object with inject/unload)."""
        return self.plugins.load(plugin, name)

    def unload_plugin(self, name: str) -> bool:
        return self.plugins.unload(name)

    # -- inventory ------------------------------------------------------------------------

    @property
    def held_item(self):
        return self.inventory.held_item

    async def set_quick_bar_slot(self, slot: int) -> None:
        await self.inventory.set_held_slot(slot)

    async def craft(self, item_name: str, count: int = 1,
                    crafting_table: bool = False) -> int:
        """Craft *count* of *item_name*; returns items actually crafted."""
        return await self.crafting.craft(item_name, count, crafting_table)

    async def fish(self, timeout: float = 60.0, **opts) -> bool:
        """Cast the fishing rod and catch one fish."""
        return await self.fishing.fish(timeout, **opts)

    async def collect(self, max_distance: float = 8.0, count: int | None = None,
                      **kwargs) -> int:
        """Pick up nearby dropped-item entities; returns count collected."""
        return await self.collector.collect(max_distance, count, **kwargs)

    async def harvest(self, names=None, max_distance: int = 32) -> int:
        """Dig mature crops in range; returns blocks harvested."""
        return await self.farming.harvest(names, max_distance)

    async def plant(self, seed_name: str | None = None,
                    max_distance: int = 16) -> int:
        """Plant seeds on empty farmland in range."""
        return await self.farming.plant(seed_name, max_distance)

    async def tend_farm(self, names=None, max_distance: int = 32) -> dict:
        """Harvest mature crops and replant with available seeds."""
        return await self.farming.tend(names, max_distance)

    # -- containers -----------------------------------------------------------------

    async def click_window(self, window_id: int, slot: int, button: int = 0,
                           mode: int = 0) -> None:
        """Send a window_click on any open window."""
        await self.containers.click(window_id, slot, button, mode)

    async def shift_click(self, window_id: int, slot: int) -> None:
        """Shift-click (quick-move) a slot in an open window."""
        await self.containers.shift_click(window_id, slot)

    async def close_window(self, window_id: int | None = None) -> None:
        """Close an open window (defaults to the current one)."""
        await self.containers.close(window_id)

    async def interact_block(self, block, face=None) -> None:
        """Right-click a block (open containers, press buttons)."""
        await self.actions.interact_block(block, face)

    # -- world actions ------------------------------------------------------------------

    async def dig(self, block, force: bool = False):
        await self.actions.dig(block, force=force)

    async def stop_digging(self):
        await self.actions.stop_digging()

    async def place_block(self, block, face=None):
        await self.actions.place_block(block, face)

    async def attack(self, entity):
        await self.actions.attack(entity)

    async def equip(self, item, destination: str | None = None):
        await self.actions.equip(item, destination)

    async def consume(self):
        raise LeafishError("consume() is not implemented yet")

    async def activate_item(self):
        raise LeafishError("activate_item() is not implemented yet")

    async def deactivate_item(self):
        raise LeafishError("deactivate_item() is not implemented yet")

    async def swing_arm(self):
        await self._send_play("arm_animation", {"hand": 0})


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class Leafish:
    """Entry point for creating bots."""

    @staticmethod
    async def create_bot(
        host: str = "localhost",
        port: int = 25565,
        username: str | None = None,
        auth: str = "offline",
        version: str = "latest",
        **kwargs,
    ) -> LeafishBot:
        """Create and connect a bot.

        Args:
            host: Server hostname or IP.
            port: Server port (default 25565).
            username: Minecraft username (required for offline auth; for
                Microsoft auth the profile name is used).
            auth: ``"offline"`` or ``"microsoft"``.
            version: Minecraft version string or ``"latest"``.
        """
        config = BotConfig(host=host, port=port, version=version, **{
            k: v for k, v in kwargs.items() if k in BotConfig.__dataclass_fields__
        })
        if username is not None and not config.username:
            config.username = username

        codec = ProtocolCodec.for_version(version)

        if config.auth == "offline":
            name = username or config.username
            provider = OfflineAuth()
            auth_session = await provider.authenticate(name)
        elif config.auth == "microsoft":
            provider = MicrosoftAuth(cache_path=config.token_cache_path)
            try:
                auth_session = await provider.authenticate(username)
            finally:
                await provider.close()
        else:
            raise LeafishError(f"Unknown auth mode '{config.auth}'")

        config.username = auth_session.username
        bot = LeafishBot(config, auth_session, codec)
        await bot._start()
        bot.emit("connect")
        return bot

    @staticmethod
    async def create_bots(*configs: dict) -> list[LeafishBot]:
        """Create several bots concurrently.

        Each config is a kwargs dict for :meth:`create_bot`, e.g.::

            bots = await Leafish.create_bots(
                {"host": "localhost", "username": "Alice", "auth": "offline"},
                {"host": "localhost", "username": "Bob", "auth": "offline"},
            )
        """
        return list(await asyncio.gather(
            *(Leafish.create_bot(**cfg) for cfg in configs)
        ))


def _pos_from_bitfield(loc: Any) -> BlockPos | None:
    """Convert a decoded ``position`` bitfield dict to BlockPos."""
    if not isinstance(loc, dict):
        return None
    try:
        return BlockPos(int(loc["x"]), int(loc["y"]), int(loc["z"]))
    except (KeyError, TypeError, ValueError):
        return None
