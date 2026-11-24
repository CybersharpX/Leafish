# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security & Critical Fixes (QA Audit & Finalization)
- **Zlib decompression bomb DoS (`protocol/compression.py`)**: Bounded decompressed packet size to 8 MiB via `zlib.decompressobj().decompress(..., data_length + 1)`, verified exact decompressed length, and disabled compression on negative thresholds (`threshold < 0`).
- **AES/CFB8 stream cipher concurrency race (`protocol/connection.py`)**: Moved `_frame_outgoing()` inside `_write_lock` so concurrent `send()` calls never transmit encrypted frames out of stream order. Fixed self-cancellation deadlock in `close()` and socket cleanup on reader error.
- **Online-mode Notchian server hash (`protocol/session.py`)**: Fixed `_compute_server_hash` from base-10 decimal (`"d"`) to signed lowercase hexadecimal (`"x"`); added 1.20.5+ `shouldAuthenticate` check and `select_known_packs` configuration response.
- **Microsoft Xbox Live token exchange (`auth/microsoft.py`, `auth/session.py`)**: Fixed missing `{uhs};` user hash in `XBL3.0 x={uhs};{xsts_token}`, restricted token cache file permissions to `0600`, added RFC 8628 `slow_down` interval backoff, and redacted `AuthSession.access_token` from `repr()`.
- **Bot creation & lifecycle (`bot.py`)**: Fixed `Leafish.create_bot` to forward `auth` and `username` to `BotConfig`; attached `Bot` pre-start handlers before connecting so `login`/`connect`/`spawn` events are never missed; added `auto_tool` to `LeafishBot.dig()`; updated `self.entity` metadata so `bot.oxygen_level` updates; prevented `auto_reconnect` after manual `disconnect()`; fixed `entity_hurt` firing on healing and `thundering` reset.
- **World, Entities, Builder, Actions, NBT, Text & Config**: Fixed `BuilderModule` `GoalNear` crash, `ActionsModule._dig_face` sign bug, `Block.hardness_seconds` bedrock bug, `World.can_dig_block` on air, `ScoreBoard.update` entity keying, `EventEmitter` error-handler recursion & waiter cleanup, `component_to_text` `"extra"` preservation, `strip_colors`, NBT/chunk bounds & depth limits, `version.py` path-traversal protection, `BotConfig` validation, and 6 broken examples.
- **Performance**: Optimized `encode_varint`, `World.find_blocks` (nearest-first + palette pruning), `PalettedContainer.values()`, `GameData.block_state`, `version.py` caching, `EntityManager.nearest`, and added `slots=True` to `Vec3`/`Vec2`/`BlockPos`.
- **Reports**: Added 11 independent QA/engineering reports in `reports/` and 20 regression tests in `tests/unit/test_qa_regressions.py`.


### Added

#### Construction & Building Module
- New `BuilderModule` (`bot.builder`) and `ConstructionPlan` (`from leafish import ConstructionPlan, BlockPlacement`).
- Procedural shape generators: `ConstructionPlan.wall(...)`, `ConstructionPlan.platform(...)`, `ConstructionPlan.box(...)` (hollow or solid), `ConstructionPlan.column(...)`.
- Automatic material requirement analysis (`plan.required_materials()`) and inventory validation (`plan.validate_inventory(bot)`).
- Ground-up construction ordering (`plan.order_for_construction()`) so placed blocks always have stable supports.
- Automated building execution (`await bot.build(plan)`): validates resources, navigates within reach, finds adjacent solid reference faces, places blocks, and emits `build_started`, `build_progress`, and `build_complete`.

#### Tool & Weapon Selection
- Mining tool intelligence: `ActionsModule.best_tool_for(block_or_pos)` and `ActionsModule.equip_for_block(block_or_pos)` automatically determine optimal tool category (pickaxe, shovel, axe, hoe, shears) and highest tier in inventory.
- Automatic tool equipping during mining: `bot.dig(block, auto_tool=True)` equips the best tool before digging begins.
- Combat weapon intelligence: `PVPModule.best_weapon()` and `PVPModule.equip_best_weapon()` find and equip the highest-damage weapon (swords/axes ranked across netherite, diamond, iron, stone, golden, wooden tiers).
- Combat auto-weapon toggle: `bot.pvp.start(auto_weapon=True)` ensures the best weapon is equipped prior to attacking.

#### World & Environment Enhancements
- Biome querying: `GameData.biome_by_id`, `GameData.biome_by_name`, `World.biome_at(pos)`, `bot.biome_at(pos)`, and `bot.biome` property returning full biome metadata.
- Multi-state block resolution: `GameData.block_state_ids(name)` resolves all orientation and variant state IDs for a given block.
- `World.find_blocks` now finds all block state variations and returns results sorted by nearest Euclidean distance to the bot.
- Tilling module: `FarmingModule.till(block_or_pos)` and `FarmingModule.till_area(start, end)` till dirt and grass into farmland using an inventory hoe.

#### Connection Diagnostics & Metrics
- `Connection.diagnostics()` tracks `bytes_sent`, `bytes_received`, `packets_sent`, `packets_received`, `uptime_seconds`, and `latency_ms`.
- Exposed via `bot.diagnostics`, `bot.latency`, and `bot.ping`.

#### Developer Experience & High-Level API
- Async context manager support on both `Bot` and `LeafishBot` (`async with Bot(...) as bot:` and `async with bot:`).
- Enhanced player lookups: `bot.players` property (accessible by both username and UUID), `bot.nearest_player()`, and `bot.player_by_name()`.
- Flight control: `bot.set_flying(bool)` sends abilities update packet when permitted.
- Complete suite of 10 runnable, documented examples in `examples/01_...` through `examples/10_...`.

### Fixed
- **Connection frame framing (`BufferError`)**: Replaced memoryview export in `connection._drain_frames` with `decode_varint_from_buffer` which reads up to 5 bytes directly from the bytearray without allocating exports or buffers, completely eliminating `BufferError: Existing exports of data: object cannot be re-sized`.
- **Event priority ordering**: Fixed `EventEmitter.emit` and `emit_async` to merge and sort standard and `once` listeners by priority (`(-priority, seq)`) rather than appending `once` handlers to the end.
- **Block placement hit coordinates**: Corrected placement face hit coordinates (`cursorX`, `cursorY`, `cursorZ`) in `ActionsModule.place_block`, `interact_block`, and `use_on` to stay in `[0.0, 1.0]` relative block face space instead of erroneously subtracting absolute world coordinates.
- **Cryptography deprecation**: Added graceful fallback to `cryptography.hazmat.decrepit.ciphers.modes.CFB8` for AES CFB8 encryption mode, future-proofing for `cryptography>=49.0.0`.
- **Inventory duck typing**: Standardized inventory item traversal across `ActionsModule`, `PVPModule`, `FarmingModule`, and `BuilderModule` using `_inventory_items`, ensuring compatibility with both `Inventory.items()` and `Inventory.slots` mappings.

#### High-level Bot API
- New `Bot` convenience class (`from leafish import Bot`) with Mineflayer-inspired
  API: `Bot(host=…, username=…)`, event handler decorators before `await bot.start()`,
  and transparent proxy to the underlying `LeafishBot` after start.
- Buffered event handlers: handlers registered before `start()` via `bot.on()` /
  `bot.once()` are queued and flushed once the bot connects.

#### Reconnection
- `LeafishBot.reconnect(delay=None)` — reset all connection-dependent state and
  re-run the full login sequence without recreating the bot or its event handlers.
- `BotConfig.auto_reconnect: bool` (default `False`) — when `True`, the bot
  schedules `_auto_reconnect_loop()` after each unexpected disconnect.
- `BotConfig.reconnect_delay: float` (default `5.0`) — base delay (seconds)
  between auto-reconnect attempts; doubles on each failure, capped at 300 s.

#### Event system
- `EventEmitter.on()` / `once()` now accept an optional `priority: int = 0`
  keyword argument. Higher-priority handlers run first; ties break in FIFO
  registration order.
- Both are still fully backward-compatible (the default `priority=0` preserves
  existing ordering semantics).

#### Pathfinder
- **Swimming support**: fluid blocks (water, lava) are now walkable with ×1.5
  movement cost; `_neighbors` yields vertical swim-up/down moves inside fluids.
- **Ladder/vine climbing**: climbable blocks (`ladder`, `vine`, scaffolding, cave
  vines, etc.) are walkable; vertical moves along them are yielded with ×2.0 cost.
- `_follow()` now detects fluid and ladder contexts and applies correct controls:
  `jump=True` to swim up, `sneak=True` to sink/descend on ladders.
- `_CLIMBABLE` and `_FLUID` frozen-sets centralise block-name classification.
- Diagonal movement still uses corner-cutting prevention.

#### Entity tracking
- `Entity.air_supply: int | None` — populated from entity metadata index 1
  (air supply ticks). Previously missing.
- `bot.oxygen_level` / `bot.oxygen` now returns the actual air supply from the
  bot's own entity metadata instead of always returning `None`.

#### Performance
- **Block prototype cache** (`World._block_proto_cache`): `block_at()` avoids
  repeated registry lookups for the same block state. Prototypes are built once,
  then shallow-copied with the caller's position stamped in. FIFO eviction at
  8 192 entries.
- **Memoryview receive buffer**: `connection._drain_frames` now wraps the receive
  `bytearray` in a `memoryview` for the varint-header read, eliminating one full
  buffer copy per received packet.

#### Configuration
- `BotConfig.token_cache_path` now uses `field(default_factory=_default_token_path)`
  so each instance gets an independent `Path` object (safe to mutate without
  affecting other instances).
- Module-level `DEFAULT_TOKEN_PATH` constant preserved for backward compatibility.

#### Physics
- Conditional position send: `physics.tick()` now only emits `position_look` when
  the position, rotation, or ground-state has changed, **or** every 20 ticks as a
  forced heartbeat. This reduces network overhead by up to 95 % when the bot is
  standing still.

### Fixed
- **Encryption handshake** (`protocol/session.py`): server's RSA public key is now
  used with `PKCS1v15` padding to encrypt the shared secret and verify token.
  Previously AES was incorrectly applied, breaking online-mode login.
- **AES key derivation** (`protocol/encryption.py`): `EncryptionHandler.enable()`
  now uses the 16-byte shared secret directly as both AES key and IV. Previously
  `SHA1(secret)[0:16]` was used, which is wrong and incompatible with Mojang's
  protocol.
- **Physics velocity multiplier** (`modules/physics.py`): removed erroneous `× 10`
  factor from the wish-direction velocity accumulation formula.
- **`ConnectionError` shadows builtin** (`exceptions.py`): renamed to
  `BotConnectionError`; backward-compatible alias `ConnectionError = BotConnectionError`
  preserved.
- **`wait_for_chunks_to_load` future leak** (`bot.py`): replaced manual
  `asyncio.wait_for` wrapping of `wait_for_nowait` futures with
  `emitter.wait_for(event, timeout=remaining)`, which correctly removes waiters
  on cancellation.
- **`_goto_task` never assigned** (`modules/pathfinder.py`): the goto async task is
  now tracked in `self._goto_task` and properly cancelled by `stop()`.
- **Pathfinder blocks event loop** (`modules/pathfinder.py`): A* now runs in a
  shared `ThreadPoolExecutor` via `loop.run_in_executor()` so the event loop
  stays responsive during pathfinding.
- **`bot.oxygen_level` always `None`**: fixed by reading air-supply from entity
  metadata index 1 (now populated by `Entity.update_metadata`).
- **`BotConfig.token_cache_path` shared mutable default**: changed from a
  module-level `Path` default to `field(default_factory=…)`.

### Tests
- New `tests/unit/test_encryption.py`: AES/CFB8 roundtrip, stream continuity,
  key-length validation, `EncryptionHandler` enable/passthrough/before-enable,
  Notch-signed SHA-1 known test vectors (`Notch`, empty, `jeb_`), and
  `_compute_server_hash` format validation.
- New `tests/unit/test_emitter_priority.py`: priority ordering, FIFO within same
  priority, decorator form, `once` with priority, `off` by identity, `off` all,
  `listeners()` order, error isolation with priorities.
- New `tests/unit/test_bot_wrapper.py`: `BotConfig` default token path factory,
  per-instance independence, auto-reconnect config, `Bot` repr/attr-before-start
  error, pre-start handler buffering for `on` and `once`.

- Multi-version support: minecraft-data vendored for 18 protocol
  versions (1.8, 1.9, 1.10, 1.11, 1.12, 1.13, 1.14, 1.15, 1.16, 1.17,
  1.18, 1.19, 1.20, 1.21, 1.21.4, 1.21.9, 1.21.11, 26.1).
- Era-aware protocol layer: `protocol.compat` adapts outbound packets
  (chat, window clicks, block place/dig, movement, creative slots,
  entity actions) to each version's field layout; slot encoding
  supports legacy `blockId`/`itemDamage`, flat `itemId`, `present`
  and modern component formats.
- Era-aware session state machine: versions without the configuration
  state (pre-1.20.2) and without `login_acknowledged` go straight from
  login to play.
- Chunk decoding for every era: 1.8 fixed-layout sections, 1.9-1.13
  masked palette sections with in-section light, 1.14-1.17 block
  counts and i64 section masks, 1.18-1.21.4 sequential sections,
  1.21.5+ computed long counts, and 26.1 fluid counts.
- Legacy block id/metadata lookup for 1.8-1.12 registries.
- Fake server is era-aware (login flow, spawn packets, position
  flags) enabling per-version integration smoke tests.
- Fixed packet dispatch race: frames are now decoded and dispatched
  sequentially so state transitions apply before the next frame.
- Fixed switch types without a `default` case (e.g. 1.21.11
  particles) by injecting a `void` default at codec load.

### Fixed
- Login-time server disconnects and dropped connections now surface as
  `DisconnectError` instead of hanging until the login timeout.
- `"latest"` version resolution now sorts by protocol version rather
  than lexicographically.

### Added
- Version autodetection: `version="auto"` (now the default) pings the
  server's status endpoint before login and selects the vendored
  version matching the reported protocol number.
- Project scaffolding: packaging, lint/type/test tooling, docs skeleton.
- Core exception hierarchy, configuration, vector/math/NBT utilities.
- Async event emitter with async handler support and error isolation.
- Protocol stack: packet framing, compression, AES/CFB8 encryption,
  ProtoDef serialization via `protolib`, full state machine
  (handshaking/status/login/configuration/play).
- Authentication: offline mode + Microsoft device-code/OAuth/Xbox Live/XSTS
  flow.
- Vendored minecraft-data for Java 1.21.11 (protocol 774) and version registry.
- `LeafishBot`: connect/spawn/chat/movement/health, entity tracking,
  inventory model, world model, physics engine.
- World: chunk column/section decoding with palette containers
  (single/indirect/direct), block search, raycast, block updates.
- Actions: digging, block placement, attack, equip.
- Physics: AABB collision, ground detection, fluid movement.
- Pathfinder: A* with step-ups and `goto` execution.
- Crafting: shaped/shapeless recipes via 2x2 grid clicks; fake server
  gained an inventory model and minimal recipe matching.
- Combat (`bot.pvp`), fishing (`bot.fish`), item collection
  (`bot.collect`), farming (`bot.harvest`/`plant`/`tend_farm`).
- Plugins (`bot.load_plugin`), `Leafish.create_bots`, examples,
  disconnect cleanup for physics.
- Container windows: `bot.open_window`/`close_window`/`shift_click`/
  `window_click` with per-window slot stores, `windows.json` layouts,
  and fake-server shift-click simulation.
- Crafting tables: 3x3 recipes (e.g. diamond_pickaxe) craft inside an
  open crafting-table window via `bot.craft(..., crafting_table=True)`.
- Container helpers (`bot.deposit_all`/`bot.withdraw`) and anvil repair
  (`bot.repair`) with fake-server anvil simulation.
- Fake protocol server + end-to-end integration tests.
- `tools/fetch_mcdata.py` for vendoring minecraft-data JSON.
- Complete interaction surface: `use_item`, `consume`,
  `activate_item`/`deactivate_item`, entity/block interactions,
  signs, books, tab-complete, resource packs, respawn, sleep/wake,
  elytra, mount/dismount/vehicle steering.
- Bot state objects & properties: game info, abilities, world time,
  experience, weather, settings, physics toggle, scoreboard/team/
  boss-bar collections.
- Typed windows (`bot.open_window` → `FurnaceWindow`,
  `EnchantmentTableWindow`, `AnvilWindow`, `VillagerWindow`,
  `HorseWindow`) with progress/trade/rename APIs.
- `bot.creative` namespace for creative-mode inventory ops.
- `leafish.pathfinder` goals package (`GoalNear`, `GoalFollow`,
  `GoalComposite`, ...) with dynamic-goal replanning.
- `@plugin` decorator with dependencies and override protection.
- New packet handlers: boss bars, teams, scoreboards, titles,
  particles, sounds, vehicles, block actions, item pickup, combat
  events, window properties, trades, horse windows.
- Chunk light accessors (`world.light_at`), entity bounding boxes,
  tool-aware dig times.
- Fixed: `Particle` data switch missing `default: void` in vendored
  protocol data (broke particle encode/decode).
- Cursor/line-of-sight helpers: `bot.blockAtCursor`, `bot.entityAtCursor`,
  entity AABB queries, `utils.geometry` ray-vs-AABB helper.
- `bot.smelt(...)` furnace workflow (`SmeltingModule`) driving
  `FurnaceWindow` typed view; fake server now simulates furnace
  burn/cook ticks and container window clicks.
