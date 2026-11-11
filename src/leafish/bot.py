"""LeafishBot: the central public API object."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
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
from .inventory.item import Item
from .modules.actions import ActionsModule
from .modules.anvil import AnvilModule
from .modules.chat import ChatModule
from .modules.client import ClientModule
from .modules.collector import CollectorModule
from .modules.containers import ContainerModule, SimpleClick
from .modules.crafting import CraftingModule
from .modules.creative import CreativeModule
from .modules.farming import FarmingModule
from .modules.fishing import FishingModule
from .modules.health import HealthModule
from .modules.movement import CONTROL_STATES, MovementModule
from .modules.pathfinder import Pathfinder
from .modules.physics import PhysicsEngine
from .modules.player import PlayerModule
from .modules.pvp import PVPModule
from .modules.scoreboard import BossBar, Particle, ScoreBoard, Team
from .modules.state import (
    AbilitiesInfo,
    ExperienceInfo,
    GameInfo,
    SettingsInfo,
    TimeInfo,
)
from .modules.windows import (
    AnvilWindow,
    EnchantmentTableWindow,
    FurnaceWindow,
)
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
        self.vitals = HealthModule(self)
        self.chat_module = ChatModule(self)
        self.actions = ActionsModule(self)
        self.crafting = CraftingModule(self)
        self.pathfinder = Pathfinder(self)
        self.pvp = PVPModule(self)
        self.fishing = FishingModule(self)
        self.collector = CollectorModule(self)
        self.farming = FarmingModule(self)
        self.containers = ContainerModule(self)
        self.anvil = AnvilModule(self)
        self.creative = CreativeModule(self)
        self.player = PlayerModule(self)
        self.client = ClientModule(self)
        self.simple_click = SimpleClick(self)
        self.plugins = PluginManager(self)

        # State objects -----------------------------------------------------
        self.chat_patterns: dict[str, dict] = {}
        self.feature_flags: set[str] | None = None
        self._game = GameInfo()
        self._time = TimeInfo()
        self._abilities = AbilitiesInfo()
        self._experience = ExperienceInfo()
        self.settings = SettingsInfo(view_distance=config.view_distance)

        # Scoreboard / team / boss-bar / title state -------------------------
        self.scoreboards: dict[str, ScoreBoard] = {}
        self.teams: dict[str, Team] = {}
        self.boss_bars: dict[str, BossBar] = {}
        self._title_state: dict[str, Any] = {}
        self._scoreboard_slots: dict[int, str] = {}
        self.cursor_item: Item | None = None

        # Movement control states --------------------------------------------
        self.control_states: dict[str, bool] = {c: False for c in CONTROL_STATES}
        self.using_held_item: bool = False
        """Whether the held item is currently activated (bow drawn, eating)."""

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
        # Stop any in-progress automation so tasks don't outlive the
        # connection. Each stop is best-effort.
        for stop in (
            self.pathfinder.stop,
            self.pvp.stop,
            self.movement.stop_moving,
        ):
            with contextlib.suppress(Exception):  # cleanup must not raise
                await stop()
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
            elif name == "feature_flags":
                self.feature_flags = set(params.get("features") or [])
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
        ws = params.get("worldState", params.get("commonPlayerSpawnInfo", {}))
        self.game_mode = ws.get("gamemode")
        self._game.game_mode = self.game_mode
        self._game.hardcore = bool(params.get("isHardcore", False))
        self._game.max_players = params.get("maxPlayers")
        self._game.view_distance = params.get("viewDistance")
        self._game.simulation_distance = params.get("simulationDistance")
        names = params.get("worldNames") or []
        if names:
            self._game.level_type = names[0]
        self.world.apply_dimension(ws.get("name"), ws.get("dimension"))
        self._game.dimension = ws.get("name") or self.world.dimension
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
        self._game.game_mode = self.game_mode
        self._game.dimension = ws.get("name")
        self.world.apply_dimension(ws.get("name"), ws.get("dimension"))
        self._game.min_y = self.world.min_y
        self._game.height = self.world.height
        self.world.chunks.clear()
        self.entities.clear()
        self.player._sleeping = False
        self.emit("respawn")
        self.emit("spawn_reset")
        self.spawned = False
        self._first_position_received = False

    def _packet_player_chat(self, params: dict[str, Any]) -> None:
        sender_uuid = params.get("senderUuid")
        username = self._player_name(sender_uuid) or str(sender_uuid)
        message = params.get("plainMessage") or ""
        self.emit("chat", username, message)
        self.emit("player_chat", username, message, params)
        self._dispatch_chat_patterns(username, message)

    def _packet_system_chat(self, params: dict[str, Any]) -> None:
        text = component_to_text(nbt_to_python(params.get("content")))
        self.emit("chat", None, text)
        self.emit("message", {"type": "system", "text": text})

    def _packet_profileless_chat(self, params: dict[str, Any]) -> None:
        message = component_to_text(nbt_to_python(params.get("message")))
        name = component_to_text(nbt_to_python(params.get("name"))) or None
        self.emit("chat", name, message)
        self._dispatch_chat_patterns(name, message)

    def _dispatch_chat_patterns(self, username, message: str) -> None:
        """Emit ``chat:<name>`` for registered chat patterns."""
        for name, spec in self.chat_patterns.items():
            chat_type = spec.get("chatType", "chat")
            if chat_type != "chat":
                continue
            patterns = spec.get("patterns") or [spec.get("pattern")]
            for pattern in patterns:
                if pattern is None:
                    continue
                m = pattern.search(message or "")
                if m is not None:
                    self.emit(f"chat:{name}", username, message, m)
                    break

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
        old = self.vitals.health
        self.vitals.update_health(params)
        self.emit("health", self.vitals.health, self.vitals.food)
        self.emit("food", self.vitals.food, self.vitals.food_saturation)
        if old != self.vitals.health:
            self.emit("entity_hurt", self.entity)

    def _packet_experience(self, params: dict[str, Any]) -> None:
        self.vitals.update_experience(params)
        self._experience.level = self.vitals.experience_level
        self._experience.progress = self.vitals.experience_progress
        self._experience.points = self.vitals.experience_total
        self._experience.total = self.vitals.experience_total
        self.emit("experience", self.vitals.experience_level,
                  self.vitals.experience_progress)

    def _packet_held_item_slot(self, params: dict[str, Any]) -> None:
        # Clientbound slot is the hotbar index (0-8) in modern versions.
        slot_id = int(params.get("slot", params.get("slotId", 0)))
        if not 0 <= slot_id <= 8:
            return
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

    def _packet_craft_progress_bar(self, params: dict[str, Any]) -> None:
        wid = int(params.get("windowId", 0))
        prop = int(params.get("property", 0))
        value = int(params.get("value", 0))
        self.containers.set_property(wid, prop, value)
        self.emit("window_property", wid, prop, value)

    def _packet_trade_list(self, params: dict[str, Any]) -> None:
        wid = int(params.get("windowId", 0))
        trades = params.get("trades", [])
        self.containers.set_extras(
            wid,
            trades=trades,
            villagerLevel=params.get("villagerLevel"),
            experience=params.get("experience"),
            isRegularVillager=params.get("isRegularVillager"),
            canRestock=params.get("canRestock"),
        )
        self.emit("trade_list", wid, trades)
        self.emit("villager_trade_list", wid, trades)

    def _packet_open_horse_window(self, params: dict[str, Any]) -> None:
        wid = params.get("windowId")
        self.current_window_id = wid
        if wid is not None:
            nb = int(params.get("nbSlots", 0))
            self.containers.open_window(
                int(wid), "Horse", None)
            self.containers.set_extras(
                int(wid), entityId=params.get("entityId"),
                slotCount=nb)
            win = self.containers.windows.get(int(wid))
            if win is not None:
                win.player_offset = max(0, nb)
        self.emit("open_horse_window", params)

    def _packet_declare_recipes(self, params: dict[str, Any]) -> None:
        self.emit("declare_recipes", params)

    def _packet_craft_recipe_response(self, params: dict[str, Any]) -> None:
        self.emit("craft_recipe_response", params)

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
        self.world.apply_light_update(cx, cz, params)
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
        self.world.apply_light_update(
            params.get("chunkX", 0), params.get("chunkZ", 0), params,
        )
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
        age = int(params.get("age", 0))
        day_time = int(params.get("time", 0))
        tick = bool(params.get("tickDayTime", False))
        self.world.set_time(age, day_time, tick)
        self._time.big_time = age
        self._time.time = day_time
        self._time.tick_day_time = tick
        self._time.do_daylight_cycle = tick
        self.emit("time_update", self.world.time, self.world.time_of_day)
        self.emit("time", self._time)

    def _packet_abilities(self, params: dict[str, Any]) -> None:
        flags = params.get("flags", 0)
        # Abilities flags byte (i8): bit0 invulnerable, bit1 flying,
        # bit2 allow-flying, bit3 creative/instabuild, bit4 god-mode.
        ab = self._abilities
        value = int(flags) if isinstance(flags, int) else 0
        ab.invulnerable = bool(value & 0x01)
        ab.flying = bool(value & 0x02)
        ab.may_fly = bool(value & 0x04)
        ab.instabuild = bool(value & 0x08)
        ab.may_build = True  # no dedicated flag in modern protocol
        ab.flying_speed = float(params.get("flyingSpeed", ab.flying_speed))
        ab.walking_speed = float(params.get("walkingSpeed", ab.walking_speed))
        self.emit("abilities", params)
        self.emit("abilities_update", ab)

    def _packet_entity_status(self, params: dict[str, Any]) -> None:
        self.emit("entity_status", params.get("entityId"), params.get("entityStatus"))

    def _packet_entity_update_attributes(self, params: dict[str, Any]) -> None:
        self.emit("entity_update_attributes", params)

    def _packet_explosion(self, params: dict[str, Any]) -> None:
        self.client.record_explosion(params)
        self.emit("explosion", params)

    def _packet_world_event(self, params: dict[str, Any]) -> None:
        self.emit("world_event", params)

    def _packet_entity_head_rotation(self, params: dict[str, Any]) -> None:
        e = self.entities.get(params["entityId"])
        if e is not None:
            e.head_yaw = float(params.get("headYaw", 0)) * 360.0 / 256.0

    def _packet_update_view_position(self, params: dict[str, Any]) -> None:
        self.emit("update_view_position", params)

    def _packet_spawn_position(self, params: dict[str, Any]) -> None:
        # RespawnData: {globalPos: {dimension, pos: {x,y,z}}, yaw, pitch}
        gp = params.get("globalPos") or {}
        pos = gp.get("pos") or {}
        with contextlib.suppress(AttributeError, TypeError, ValueError):
            self.world.spawn_point = BlockPos(
                int(pos.get("x", 0)), int(pos.get("y", 0)), int(pos.get("z", 0))
            )
        self.emit("spawn_position", params)

    def _packet_difficulty(self, params: dict[str, Any]) -> None:
        self._game.difficulty = params.get("difficulty")
        self._game.extra["difficulty_locked"] = params.get("difficultyLocked")
        self.emit("difficulty", params.get("difficulty"))

    def _packet_server_data(self, params: dict[str, Any]) -> None:
        motd = component_to_text(nbt_to_python(params.get("motd")))
        if motd:
            self._game.server_brand = motd
        self.emit("server_data", params)

    def _packet_tab_complete(self, params: dict[str, Any]) -> None:
        self.emit("tab_complete_response", params)

    def _packet_open_sign_entity(self, params: dict[str, Any]) -> None:
        pos = _pos_from_bitfield(params.get("location"))
        self.emit("open_sign_entity", params)
        self.emit("sign_open", pos)

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

    # -- combat / damage ---------------------------------------------------------

    def _packet_hurt_animation(self, params: dict[str, Any]) -> None:
        e = self.entities.get(_entity_id(params, "entityId"))
        if e is not None:
            e.set_rotation(e.yaw, e.pitch, head_yaw=params.get("yaw"))
        self.emit("entity_hurt", e, params)
        self.emit("entity_hurt_animation", params)

    def _packet_damage_event(self, params: dict[str, Any]) -> None:
        e = self.entities.get(_entity_id(params, "entityId"))
        self.emit("entity_hurt", e, params)
        self.emit("entity_damaged", e, params)
        self.emit("damage_event", params)

    def _packet_death_combat_event(self, params: dict[str, Any]) -> None:
        e = self.entities.get(_entity_id(params, "playerId"))
        if e is not None:
            e.health = 0.0
        text = component_to_text(nbt_to_python(params.get("message")))
        if e is not None and e.id == self.entity_id:
            self.emit("death", text)
        self.emit("entity_dead", e, text)
        self.emit("death_combat_event", params)

    def _packet_enter_combat_event(self, params: dict[str, Any]) -> None:
        self.emit("enter_combat")

    def _packet_end_combat_event(self, params: dict[str, Any]) -> None:
        self.emit("end_combat", params.get("duration"))

    def _packet_animation(self, params: dict[str, Any]) -> None:
        e = self.entities.get(_entity_id(params, "entityId"))
        if e is not None:
            self.emit("entity_swing_arm", e)
        self.emit("animation", params)

    # -- item pickup ---------------------------------------------------------------

    def _packet_collect(self, params: dict[str, Any]) -> None:
        collected = self.entities.get(_entity_id(params, "collectedEntityId"))
        collector = self.entities.get(_entity_id(params, "collectorEntityId"))
        count = int(params.get("pickupItemCount", 1))
        self.emit("player_collect", collector, collected, count)
        self.emit("item_collected", collected, collector, count)
        if collected is not None:
            self.entities.destroy([collected.id])
            self.emit("entity_destroy", collected)

    # -- block actions ---------------------------------------------------------------

    def _packet_block_action(self, params: dict[str, Any]) -> None:
        pos = _pos_from_bitfield(params.get("location"))
        block = self.world.block_at(pos) if pos is not None else None
        name = (block.name if block is not None else "") or ""
        byte1 = int(params.get("byte1", 0))
        byte2 = int(params.get("byte2", 0))
        if "piston" in name:
            self.emit("piston_move", block, byte1 == 0, byte2)
        elif "note_block" in name:
            self.emit("note_heard", block, byte1, byte2)
        elif any(k in name for k in (
            "chest", "barrel", "shulker", "furnace", "hopper",
            "dispenser", "dropper", "brewing", "enchanting", "anvil",
            "trapped_chest", "ender_chest",
        )):
            self.emit("chest_lid_move", block, bool(byte1), byte2)
        self.emit("block_action", block, params)

    def _packet_block_break_animation(self, params: dict[str, Any]) -> None:
        pos = _pos_from_bitfield(params.get("location"))
        block = self.world.block_at(pos) if pos is not None else None
        stage = int(params.get("destroyStage", 0))
        if stage < 0:
            self.emit("block_break_progress_end", block, params.get("entityId"))
        else:
            self.emit(
                "block_break_progress_observed",
                block, stage, params.get("entityId"),
            )

    # -- vehicles -------------------------------------------------------------------

    def _packet_attach_entity(self, params: dict[str, Any]) -> None:
        e = self.entities.get(_entity_id(params, "entityId"))
        vehicle_id = int(params.get("vehicleId", -1))
        if e is not None:
            vehicle = self.entities.get(vehicle_id) if vehicle_id >= 0 else None
            e.vehicle = vehicle
            if e.id == self.entity_id:
                self.player.vehicle = vehicle
                if vehicle is None:
                    self.emit("dismount", None)
                else:
                    self.emit("mount", vehicle)
        self.emit("entity_attach", e, vehicle_id)
        self.emit("attach_entity", params)

    def _packet_set_passengers(self, params: dict[str, Any]) -> None:
        e = self.entities.get(_entity_id(params, "entityId"))
        passengers = [
            self.entities.get(pid) for pid in params.get("passengers", [])
        ]
        if e is not None:
            e.passengers = [p for p in passengers if p is not None]
        self.emit("entity_passengers", e, passengers)

    # -- titles ---------------------------------------------------------------------

    def _packet_set_title_text(self, params: dict[str, Any]) -> None:
        text = component_to_text(nbt_to_python(params.get("text")))
        self._title_state["text"] = text
        self.emit("title", text, "title")

    def _packet_set_title_subtitle(self, params: dict[str, Any]) -> None:
        text = component_to_text(nbt_to_python(params.get("text")))
        self._title_state["subtitle"] = text
        self.emit("title", text, "subtitle")

    def _packet_set_title_time(self, params: dict[str, Any]) -> None:
        times = (
            int(params.get("fadeIn", 0)),
            int(params.get("stay", 0)),
            int(params.get("fadeOut", 0)),
        )
        self._title_state.update(
            {"fadeIn": times[0], "stay": times[1], "fadeOut": times[2]}
        )
        self.emit("title_times", *times)

    def _packet_clear_titles(self, params: dict[str, Any]) -> None:
        self._title_state.clear()
        self.emit("title_clear", bool(params.get("reset", True)))

    # -- particles / sounds -----------------------------------------------------------

    def _packet_world_particles(self, params: dict[str, Any]) -> None:
        particle_obj = params.get("particle")
        particle_id = (
            particle_obj.get("id") if isinstance(particle_obj, dict)
            else particle_obj
        )
        particle = Particle(
            particle_id=particle_id,
            name=_sound_name(particle_id),
            position=Vec3(
                float(params.get("x", 0)),
                float(params.get("y", 0)),
                float(params.get("z", 0)),
            ),
            offset=Vec3(
                float(params.get("offsetX", 0)),
                float(params.get("offsetY", 0)),
                float(params.get("offsetZ", 0)),
            ),
            max_speed=float(params.get("velocityOffset", 0) or 0),
            count=int(params.get("amount", 0) or 0),
            long_distance_render=bool(params.get("longDistance", False)),
            always_show=bool(params.get("alwaysShow", False)),
            data=particle_obj.get("data") if isinstance(particle_obj, dict) else None,
        )
        self.emit("particle", particle)
        self.emit("world_particles", params)

    def _packet_sound_effect(self, params: dict[str, Any]) -> None:
        name = _sound_name(params.get("sound"))
        pos = Vec3(
            int(params.get("x", 0)) / 8.0,
            int(params.get("y", 0)) / 8.0,
            int(params.get("z", 0)) / 8.0,
        )
        self.emit(
            "sound_effect_heard", name, pos,
            float(params.get("volume", 1.0)), float(params.get("pitch", 1.0)),
        )
        self.emit("sound_effect", params)

    def _packet_entity_sound_effect(self, params: dict[str, Any]) -> None:
        name = _sound_name(params.get("sound"))
        e = self.entities.get(_entity_id(params, "entityId"))
        self.emit(
            "entity_sound_effect_heard", name, e,
            float(params.get("volume", 1.0)), float(params.get("pitch", 1.0)),
        )
        self.emit("entity_sound_effect", params)

    def _packet_entity_effect(self, params: dict[str, Any]) -> None:
        e = self.entities.get(_entity_id(params, "entityId"))
        effect = {
            "id": params.get("effectId"),
            "amplifier": params.get("amplifier"),
            "duration": params.get("duration"),
            "flags": params.get("flags"),
        }
        if e is not None:
            e.effects[effect["id"]] = effect
        self.emit("entity_effect", e, effect)

    def _packet_remove_entity_effect(self, params: dict[str, Any]) -> None:
        e = self.entities.get(_entity_id(params, "entityId"))
        eid = params.get("effectId")
        if e is not None:
            e.effects.pop(eid, None)
        self.emit("entity_effect_end", e, eid)
        self.emit("remove_entity_effect", params)

    # -- scoreboard / teams / boss bars ------------------------------------------------

    def _packet_boss_bar(self, params: dict[str, Any]) -> None:
        uuid = params.get("entityUUID")
        action = int(params.get("action", 0))
        bar = self.boss_bars.get(str(uuid))
        if action == 0:  # add
            bar = BossBar(uuid=uuid or "")
            self.boss_bars[str(uuid)] = bar
            self._apply_boss_bar(bar, params)
            self.emit("boss_bar_created", bar)
        elif action == 1:  # remove
            bar = self.boss_bars.pop(str(uuid), None)
            if bar is not None:
                self.emit("boss_bar_deleted", bar)
        elif bar is not None:
            self._apply_boss_bar(bar, params)
            self.emit("boss_bar_updated", bar)

    def _apply_boss_bar(self, bar: BossBar, params: dict[str, Any]) -> None:
        if "title" in params:
            bar.title = _component_text(params.get("title"))
        if "health" in params:
            bar.health = float(params.get("health", bar.health))
        if "color" in params:
            bar.color = params.get("color")
        if "dividers" in params:
            bar.division = int(params.get("dividers", bar.division))
        if "flags" in params:
            flags = int(params.get("flags", 0))
            bar.flags = flags
            bar.darkened_sky = bool(flags & 0x01)
            bar.dragon_bar = bool(flags & 0x02)
            bar.create_fog = bool(flags & 0x04)

    def _packet_teams(self, params: dict[str, Any]) -> None:
        name = params.get("team", "")
        mode = params.get("mode")
        mode_name = mode if isinstance(mode, str) else str(mode)
        if mode_name == "add":
            team = Team(name=name)
            self._apply_team_fields(team, params)
            self.teams[name] = team
            self.emit("team_created", team)
        elif mode_name == "remove":
            team = self.teams.pop(name, None)
            if team is not None:
                self.emit("team_removed", team)
        elif mode_name == "change":
            team = self.teams.get(name)
            if team is not None:
                self._apply_team_fields(team, params)
                self.emit("team_updated", team)
        elif mode_name in ("join", "leave"):
            team = self.teams.get(name)
            if team is None:
                return
            for pname in params.get("players", []) or []:
                if mode_name == "join":
                    team.members.add(pname)
                    self.emit("team_member_added", team, pname)
                else:
                    team.members.discard(pname)
                    self.emit("team_member_removed", team, pname)

    def _apply_team_fields(self, team: Team, params: dict[str, Any]) -> None:
        team.display_name = _component_text(params.get("name")) or team.name
        flags = params.get("flags")
        if isinstance(flags, dict):
            team.friendly_fire = int(bool(flags.get("friendly_fire")))
        elif flags is not None:
            team.friendly_fire = int(flags)
        if params.get("nameTagVisibility") is not None:
            team.name_tag_visibility = params.get("nameTagVisibility")
        if params.get("formatting") is not None:
            team.color = params.get("formatting")
        if params.get("collisionRule") is not None:
            team.collision_rule = params.get("collisionRule")
        team.prefix = _component_text(params.get("prefix"))
        team.suffix = _component_text(params.get("suffix"))

    @property
    def team_map(self) -> dict[str, Team]:
        """Teams keyed by team name."""
        return dict(self.teams)

    def _packet_scoreboard_objective(self, params: dict[str, Any]) -> None:
        name = params.get("name", "")
        action = int(params.get("action", 0))
        if action == 1:  # remove
            board = self.scoreboards.pop(name, None)
            if board is not None:
                self.emit("scoreboard_deleted", board)
            return
        board = self.scoreboards.get(name)
        if board is None:
            board = ScoreBoard(name=name)
            self.scoreboards[name] = board
            self.emit("scoreboard_created", board)
        if "displayText" in params:
            board.title = _component_text(params.get("displayText"))
        if "type" in params:
            board.type = params.get("type")
        self.emit("scoreboard_title_changed", board)

    def _packet_scoreboard_display_objective(self, params: dict[str, Any]) -> None:
        position = int(params.get("position", 0))
        name = params.get("name", "")
        self._scoreboard_slots[position] = name
        board = self.scoreboards.get(name)
        self.emit("scoreboard_position", position, board or name)

    def _packet_scoreboard_score(self, params: dict[str, Any]) -> None:
        score_name = params.get("scoreName", "")
        board = self.scoreboards.get(score_name)
        if board is None:
            return
        item = board.update(params)
        self.emit("score_updated", board, item)

    def _packet_reset_score(self, params: dict[str, Any]) -> None:
        entity_name = params.get("entity_name", "")
        objective = params.get("objective_name")
        if objective is None:
            for board in self.scoreboards.values():
                for key in [k for k, v in board.items_map.items()
                            if v.name == entity_name]:
                    board.items_map.pop(key, None)
        else:
            board = self.scoreboards.get(objective)
            if board is not None:
                for key in [k for k, v in board.items_map.items()
                            if v.name == entity_name]:
                    board.items_map.pop(key, None)
        self.emit("score_removed", entity_name, objective)

    @property
    def scoreboard(self):
        """The sidebar scoreboard (position 1) when present."""
        name = self._scoreboard_slots.get(1)
        return self.scoreboards.get(name) if name else None

    # -- misc packets -----------------------------------------------------------------

    def _packet_update_view_distance(self, params: dict[str, Any]) -> None:
        vd = params.get("viewDistance")
        if vd is not None:
            self.settings.view_distance = int(vd)
            self._game.view_distance = int(vd)
        self.emit("update_view_distance", params)

    def _packet_set_cursor_item(self, params: dict[str, Any]) -> None:
        item = Item.from_slot(params.get("contents", {}))
        if item is not None and item.item_id is not None and item.name is None:
            item.name = self.world.gamedata.item_name(item.item_id)
        self.cursor_item = item
        self.emit("cursor_item", item)

    def _packet_tags(self, params: dict[str, Any]) -> None:
        self.emit("tags", params)

    def _packet_open_book(self, params: dict[str, Any]) -> None:
        self.emit("open_book", params)

    def _packet_map(self, params: dict[str, Any]) -> None:
        self.emit("map", params)

    def _packet_chat_suggestions(self, params: dict[str, Any]) -> None:
        self.emit("chat_suggestions", params)

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
        """Entity whose collision box contains *position*.

        When several entities overlap, the nearest to the point wins;
        returns ``None`` if no entity contains the position.
        """
        point = position if isinstance(position, Vec3) else Vec3(*position)
        best = None
        best_d = float("inf")
        for e in self.entities.all():
            if not e.contains_point(point):
                continue
            d = point.distance_squared_to(e.position)
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

    def recipes_for(self, item_name: str):
        """All recipe variants producing *item_name*."""
        return self.crafting.recipes_for(item_name)

    def craftable_recipes(self):
        """Recipes the bot can currently craft from its inventory."""
        return self.crafting.craftable_recipes()

    def missing_ingredients(self, recipe):
        """Ingredients still required for *recipe* (name -> count)."""
        return self.crafting.missing_ingredients(recipe)

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

    async def deposit_all(self, window_id: int,
                          name: str | None = None) -> int:
        """Shift-click player-inventory items into an open container."""
        return await self.containers.deposit_all(window_id, name)

    async def withdraw(self, window_id: int, name: str,
                       count: int | None = None) -> int:
        """Shift-click items out of a container into the player inventory."""
        return await self.containers.withdraw(window_id, name, count)

    async def repair(self, item_name: str, material_name: str | None = None,
                     window_id: int | None = None) -> int:
        """Repair/rename via an anvil window; returns items taken."""
        return await self.anvil.repair(item_name, material_name, window_id)

    async def interact_block(self, block, face=None) -> None:
        """Right-click a block (open containers, press buttons)."""
        await self.actions.interact_block(block, face)

    async def open_container(self, block, timeout: float = 5.0) -> int | None:
        """Right-click *block* and wait for a container window to open.

        Returns the new window id, or ``None`` if none opened in time.
        """
        return await self.containers.open_container(block, timeout)

    async def open_window(self, block, timeout: float = 5.0):
        """Open *block*'s window and return a typed window view.

        The concrete class depends on the container: ``FurnaceWindow``,
        ``EnchantmentTableWindow``, ``AnvilWindow``, ``VillagerWindow``
        or the generic ``Window``. Returns ``None`` on timeout.
        """
        return await self.containers.open_typed(block, timeout)

    async def open_furnace(self, block, timeout: float = 5.0) -> FurnaceWindow | None:
        """Open a furnace/blast furnace/smoker at *block*."""
        win = await self.open_window(block, timeout)
        return win if isinstance(win, FurnaceWindow) else None

    async def open_enchantment_table(
            self, block, timeout: float = 5.0) -> EnchantmentTableWindow | None:
        """Open an enchanting table at *block*."""
        win = await self.open_window(block, timeout)
        return win if isinstance(win, EnchantmentTableWindow) else None

    async def open_anvil(self, block, timeout: float = 5.0) -> AnvilWindow | None:
        """Open an anvil at *block*."""
        win = await self.open_window(block, timeout)
        return win if isinstance(win, AnvilWindow) else None

    async def open_villager(self, entity, timeout: float = 5.0):
        """Open a villager/trader *entity*'s trading window."""
        before = set(self.containers.windows)
        await self.actions.use_on(entity)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            new = [w for w in self.containers.windows if w not in before]
            if new:
                return self.containers.window_view(new[0])
            await asyncio.sleep(0.05)
        return None

    @property
    def current_window(self):
        """Typed view of the currently open window, or ``None``."""
        if self.current_window_id is None:
            return None
        return self.containers.window_view(self.current_window_id)

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

    async def unequip(self, destination: str = "hand"):
        """Move the item in *destination* back into the inventory."""
        await self.inventory.unequip(destination)

    # -- item use ------------------------------------------------------------------

    async def use_item(self, hand: int = 0) -> None:
        """Send ``use_item`` with the held item (or empty hand)."""
        await self.actions.use_item(hand)

    async def consume(self):
        """Eat/drink the held item."""
        await self.actions.consume()

    async def activate_item(self, off_hand: bool = False) -> None:
        """Start using the held item (bow, food, ...)."""
        await self.actions.activate_item(off_hand=off_hand)

    async def deactivate_item(self) -> None:
        """Stop using the held item."""
        await self.actions.deactivate_item()

    # -- entity / block interaction ---------------------------------------------------

    async def use_on(self, entity, point=None, hand: int = 0) -> None:
        """Right-click *entity* (mount, feed, trade, ...)."""
        await self.actions.use_on(entity, point=point, hand=hand)

    async def activate_entity(self, entity, hand: int = 0) -> None:
        await self.actions.activate_entity(entity, hand=hand)

    async def activate_entity_at(self, entity, position, hand: int = 0) -> None:
        await self.actions.activate_entity_at(entity, position, hand=hand)

    async def activate_block(self, block, direction=None, cursor_pos=None) -> None:
        """Right-click a block with explicit face/cursor position."""
        await self.actions.activate_block(block, direction, cursor_pos)

    async def place_entity(self, entity, face=None) -> None:
        """Place the held block against the block under *entity*."""
        await self.actions.place_entity(entity, face)

    # -- player state ------------------------------------------------------------------

    async def respawn(self) -> None:
        """Request respawn (after death or dimension change)."""
        await self.player.respawn()

    async def sleep(self, bed_block) -> None:
        """Sleep in *bed_block*."""
        await self.player.sleep(bed_block)

    async def wake(self) -> None:
        """Wake up from sleep."""
        await self.player.wake()

    @property
    def is_sleeping(self) -> bool:
        """Whether the bot believes it is sleeping."""
        return self.player.is_abed

    async def is_abed(self, bed_block=None) -> bool:
        """Whether the bot is currently sleeping.

        When *bed_block* is given, also verifies the bot is near that bed.
        """
        if not self.player.is_abed:
            return False
        if bed_block is None:
            return True
        pos = getattr(bed_block, "position", bed_block)
        entity = self.entity
        if entity is None or pos is None:
            return False
        p = pos if isinstance(pos, Vec3) else Vec3(*pos)
        return entity.position.distance_to(p) < 4.0

    async def elytra_fly(self) -> None:
        """Deploy elytra (requires elytra equipped and airborne)."""
        await self.player.elytra_fly()

    async def mount(self, entity) -> None:
        """Mount *entity* (boat, minecart, horse, ...)."""
        await self.player.mount(entity)

    async def dismount(self) -> None:
        """Dismount the current vehicle."""
        await self.player.dismount()

    async def move_vehicle(self, left: float = 0.0, forward: float = 0.0) -> None:
        """Steer the mounted vehicle."""
        await self.player.move_vehicle(left, forward)

    # -- inventory helpers ---------------------------------------------------------------

    async def toss(self, item, count: int | None = None) -> None:
        """Drop *count* items (or the whole stack) from *item*'s slot."""
        await self.inventory.toss(item, count)

    async def toss_stack(self, item) -> None:
        """Drop the entire stack held by *item*'s slot."""
        await self.inventory.toss_stack(item)

    async def move_slot_item(self, source_slot: int, dest_slot: int) -> None:
        await self.inventory.move_slot_item(source_slot, dest_slot)

    async def put_away(self, slot: int) -> None:
        await self.inventory.put_away(slot)

    async def transfer(self, options: dict | None = None) -> None:
        await self.inventory.transfer(options)

    async def put_selected_item_range(self, start: int, end: int,
                                      window_id: int | None = None,
                                      slot: int | None = None) -> None:
        await self.inventory.put_selected_item_range(
            start, end, window_id=window_id, slot=slot
        )

    # -- digging / item info ---------------------------------------------------------------

    def dig_time(self, block_or_pos) -> float:
        """Estimated digging time in seconds for a block/position."""
        return self.actions.dig_time(block_or_pos)

    # -- client helpers ---------------------------------------------------------------------

    async def tab_complete(self, text: str, assume_command: bool = False,
                           timeout: float = 5.0) -> list[str]:
        """Request chat/command tab-completion; returns matches."""
        return await self.client.tab_complete(
            text, assume_command=assume_command, timeout=timeout
        )

    async def accept_resource_pack(self) -> None:
        await self.client.accept_resource_pack()

    async def deny_resource_pack(self) -> None:
        await self.client.deny_resource_pack()

    async def update_sign(self, block, text, back: bool = False,
                          timeout: float = 5.0) -> bool:
        """Write text onto a sign block. Returns True on success."""
        return await self.client.update_sign(block, text, back=back,
                                             timeout=timeout)

    async def write_book(self, hand: int, pages: list[str],
                         title: str | None = None) -> None:
        """Write *pages* into the book held in *hand* (0 or 1)."""
        await self.client.write_book(hand, pages, title=title)

    async def set_command_block(self, pos, command: str, *, mode: int = 0,
                                flags: int = 0) -> None:
        """Update the command block at *pos*."""
        await self.client.set_command_block(pos, command, mode=mode, flags=flags)

    async def update_held_item(self) -> None:
        """Re-send the current hotbar selection to the server."""
        await self.client.update_held_item()

    def support_feature(self, name: str) -> bool:
        """Whether the server advertised feature flag *name*."""
        return self.client.support_feature(name)

    def set_settings(self, options: dict) -> None:
        """Update client settings.

        Recognized keys mirror Mineflayer's ``bot.settings``: ``chat``,
        ``colorsEnabled``, ``viewDistance``, ``difficulty``,
        ``skinParts``, ``enableTextFiltering``, ``enableServerListing``,
        ``particleStatus``, ``mainHand``. Values are stored locally; only
        settings the protocol can actually change are applied.
        """
        mapping = {
            "chat": "chat_colors",
            "colorsEnabled": "chat_colors",
            "viewDistance": "view_distance",
            "difficulty": "difficulty",
            "skinParts": "skin_parts",
            "enableTextFiltering": "enable_text_filtering",
            "enableServerListing": "enable_server_listing",
            "particleStatus": "particle_status",
            "mainHand": "main_hand",
        }
        for key, value in options.items():
            attr = mapping.get(key)
            if attr is None:
                continue
            setattr(self.settings, attr, value)
            if attr == "view_distance":
                self.config.view_distance = int(value)

    def has_plugin(self, name: str) -> bool:
        """Whether a plugin named *name* is loaded."""
        return name in self.plugins.plugins

    def load_plugins(self, plugins: dict) -> None:
        """Load several plugins from a ``{name: plugin}`` mapping."""
        for name, plugin in plugins.items():
            self.load_plugin(plugin, name=name)

    def get_explosion_damages(self, entity=None, position=None,
                              radius: float = 0.0,
                              raw_damages: bool = False) -> dict:
        """Explosion damage exposure for *entity* (default: the bot)."""
        return self.client.get_explosion_damages(
            entity, position, radius, raw_damages
        )

    # -- chat -------------------------------------------------------------------------

    async def await_message(self, pattern=None, timeout: float = 30.0,
                            chat_type: str = "chat"):
        """Wait for an incoming message; see :meth:`ChatModule.await_message`."""
        return await self.chat_module.await_message(
            pattern, timeout=timeout, chat_type=chat_type
        )

    def add_chat_pattern(self, name: str, pattern, chat_type: str = "chat") -> None:
        self.chat_module.add_chat_pattern(name, pattern, chat_type)

    def add_chat_pattern_set(self, name: str, patterns,
                             chat_type: str = "chat") -> None:
        self.chat_module.add_chat_pattern_set(name, patterns, chat_type)

    def remove_chat_pattern(self, name: str) -> None:
        self.chat_module.remove_chat_pattern(name)

    # -- movement extras ------------------------------------------------------------------

    def get_control_state(self, control: str) -> bool:
        return self.movement.get_control_state(control)

    async def clear_control_states(self) -> None:
        await self.movement.clear_control_states()

    async def wait_for_ticks(self, ticks: int) -> None:
        """Wait approximately *ticks* server ticks (20 ticks = 1s)."""
        await asyncio.sleep(ticks / 20.0)

    async def wait_for_chunks_to_load(self, timeout: float = 10.0) -> bool:
        """Wait until the chunk containing the bot is loaded.

        Returns ``True`` when loaded, ``False`` on timeout.
        """
        entity = self.entity
        if entity is None:
            return False
        cx = int(entity.position.x) >> 4
        cz = int(entity.position.z) >> 4
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        def loaded() -> bool:
            return self.world.chunk_at(cx, cz) is not None

        while not loaded():
            if loop.time() >= deadline:
                return False
            fut = self.emitter.wait_for_nowait("chunk_column_load")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    fut, timeout=max(0.05, deadline - loop.time())
                )
        return True

    async def swing_arm(self):
        await self._send_play("arm_animation", {"hand": 0})

    # -- state properties ---------------------------------------------------------------

    @property
    def health(self) -> float:
        """Current health (0-20)."""
        return self.vitals.health

    @property
    def food(self) -> int:
        """Current food level (0-20)."""
        return self.vitals.food

    @property
    def food_saturation(self) -> float:
        return self.vitals.food_saturation

    @property
    def oxygen_level(self) -> int | None:
        """Breath/air level; ``None`` — modern servers don't send it."""
        return None

    @property
    def experience(self) -> ExperienceInfo:
        """Experience level/progress/points."""
        return self._experience

    @property
    def quick_bar_slot(self) -> int:
        """Currently selected hotbar slot (0-8)."""
        return self.inventory.held_slot

    @property
    def spawn_point(self):
        """World spawn position (BlockPos) or ``None``."""
        return self.world.spawn_point

    @property
    def game(self) -> GameInfo:
        """Server/game information (dimension, difficulty, game mode...)."""
        return self._game

    @property
    def abilities(self) -> AbilitiesInfo:
        """Player abilities (flying, invulnerable, ...)."""
        return self._abilities

    @property
    def time(self) -> TimeInfo:
        """World clock state."""
        return self._time

    @property
    def is_raining(self) -> bool:
        return bool(self.world.weather.get("raining"))

    @property
    def rain_state(self) -> float:
        return float(self.world.weather.get("rain_level", 0.0))

    @property
    def thunder_state(self) -> float:
        return float(self.world.weather.get("thunder_level", 0.0))

    @property
    def physics_enabled(self) -> bool:
        """Whether client-side physics simulation is running."""
        return self.physics.enabled

    @physics_enabled.setter
    def physics_enabled(self, value: bool) -> None:
        self.physics.enabled = bool(value)

    @property
    def target_dig_block(self):
        """The block currently being dug, or ``None``."""
        pos = self.actions._digging
        return self.world.block_at(pos) if pos is not None else None

    @property
    def tablist(self) -> dict:
        """Player tab-list entries keyed by UUID."""
        return dict(self.entities.players)

    @property
    def players(self) -> dict:
        """All tracked player entities keyed by UUID."""
        return dict(self.entities.players)


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
        plugins = kwargs.pop("plugins", None) or {}
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
        for name, plugin in plugins.items():
            bot.load_plugin(plugin, name=name)
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


def _entity_id(params: dict[str, Any], key: str) -> int:
    """Extract an entity id, returning -1 (never a real id) when absent."""
    value = params.get(key)
    return int(value) if value is not None else -1


def _sound_name(value: Any) -> str | None:
    """Extract a sound/particle/holder name from a decoded value."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("id", "name", "value", "key"):
            v = value.get(key)
            if isinstance(v, str):
                return v
            if isinstance(v, dict) and "value" in v:
                return str(v["value"])
    return str(value)


def _component_text(value: Any) -> str:
    """Best-effort chat-component/NBT -> plain text extraction."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return component_to_text(nbt_to_python(value)) or ""
    except Exception:
        return ""
