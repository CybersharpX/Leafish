# Implementation Status

This file is the source of truth for what Leafish can actually do today.
Nothing is listed as complete unless it is implemented and covered by tests.

Legend: ✅ done · 🚧 partial · ⬜ not started · ❌ unsupported/known issue

## Phase 0 — Scaffolding
- ✅ Package skeleton (`src/leafish`), `pyproject.toml`, pytest/ruff/ty config
- ✅ README, LICENSE, CONTRIBUTING, CHANGELOG, ROADMAP
- ✅ Git repository initialized

## Phase 1 — Foundation
- ✅ Exception hierarchy (`LeafishError` and subclasses; `BotConnectionError` renamed, `ConnectionError` alias kept)
- ✅ Configuration (`BotConfig`; `auto_reconnect`, `reconnect_delay` added; `token_cache_path` now per-instance via `default_factory`)
- ✅ `Vec3`/`Vec2`/`BlockPos`, math, geometry, raycast helpers
- ✅ NBT parse/serialize (SNBT + binary)
- ✅ Async event emitter (`on`/`once`/`off`/`wait_for`/`emit`, error isolation, **priority ordering** added)
- ✅ Chat text component → plain text conversion

## Phase 2 — Protocol
- ✅ VarInt/VarLong encode/decode, packet framing, max-size validation
- ✅ Compression (threshold + zlib)
- ✅ **AES/CFB8 encryption** (corrected: shared secret used directly as key+IV; RSA PKCS1v15 for handshake; covered by unit tests)
- ✅ ProtoDef serialization via `protolib` (all Minecraft composite types:
  slots, entity metadata, NBT, registry holders, bitflags, etc.)
- ✅ Protocol states & transitions (handshaking/status/login/configuration/play)
- ✅ Login flow: offline mode, encryption request/response, login success,
  compression negotiation, disconnect handling
- ✅ Configuration-state packets (finish configuration, registry data stubs)
- ✅ Keepalive
- ✅ Version registry + vendored minecraft-data JSON loader
- ✅ Fake asyncio protocol server for hermetic integration tests
- ✅ **Receive buffer optimization**: memoryview used in `_drain_frames` (no full buffer copy per packet)
- 🚧 Microsoft authentication: device-code OAuth → Xbox Live → XSTS →
  Minecraft Services implemented, not yet verified against live services
- 🚧 Some play-state packet handlers are stubs/partial (see Phase 3-5)

## Phase 2b — Minecraft data
- ✅ Vendored `minecraft-data` JSON for Java 1.21.11 (protocol 774):
  blocks, items, entities, recipes, biomes, windows, effects, attributes,
  particles, sounds, languages, etc.
- ✅ Registry computes block-state IDs from property descriptors
- ⬜ Additional versions

## Phase 3 — Basic bot
- ✅ `LeafishBot` orchestration: connect, spawn, chat send/receive,
  position tracking, health/hunger/experience updates
- ✅ **`Bot` convenience wrapper** (`from leafish import Bot`): Mineflayer-style API,
  pre-start handler buffering, transparent proxy post-start
- ✅ **`bot.reconnect()`** with exponential back-off; `BotConfig.auto_reconnect` toggle
- ✅ Movement module (position/look/ground packets, teleport confirm)
- ✅ **Physics engine** (AABB collision, axis-separated movement, ground detection,
  fluid drag, `physics.enabled` toggle; **conditional position send** — only
  transmits when pos/rot/ground changes or every 20 ticks)
- ✅ Full interaction surface: `use_item`, `consume`,
  `activate_item`/`deactivate_item`, `use_on`, `activate_entity`,
  `activate_block`, `place_entity`, signs (`update_sign`), books,
  tab-complete, resource-pack responses, command blocks, respawn,
  sleep/wake, elytra, mount/dismount/vehicle steering
- ✅ State objects/properties: `game`, `abilities`, `time`,
  `experience`, `health`/`food`/`food_saturation`/`oxygen` (now live from metadata),
  `weather`, `settings`, `physics_enabled`, `is_sleeping`,
  `spawn_point`, `tablist`, `quick_bar_slot`, `target_dig_block`,
  `cursor_item`, `has_plugin`/`load_plugins`
- ✅ End-to-end integration test vs fake server (connect → spawn → chat →
  move) plus game-state packet tests (boss bars, teams, scoreboards,
  titles, particles, vehicles)
- 🚧 Entity tracking: spawn/despawn/metadata/equipment/velocity/teleport
  handled; entity effects, passengers and vehicles tracked; richer
  entity-type behaviors (AI, attributes) partial

## Phase 4 — World & entities
- ✅ World model: chunk columns, palette-container section decoding
  (single/indirect/direct), block get/set API, block search, raycast
- ✅ **Block prototype cache**: `World._block_proto_cache` avoids repeated registry
  lookups for the same state id; FIFO eviction at 8 192 entries; zero extra
  copy on cache hit (shallow `__dict__` copy + position stamp)
- ✅ Entities: typed entity classes (Player/Mob/ItemEntity/Projectile/
  Vehicle) classified from versioned type ids, movement/metadata/
  equipment tracking, nearest-entity queries
- ✅ **`Entity.air_supply`** populated from metadata index 1; `bot.oxygen_level`
  now returns live air-supply ticks instead of always `None`
- ✅ Modern 1.21.x chunk column decoding (heightmaps, block entities,
  light masks parsed; sky/block light stored and exposed via
  `world.light_at(pos)` returning `(sky, block)` levels)
- ✅ Raycast against loaded world
- ✅ Entity bounding boxes and `contains_point`/`entity_at` lookups

## Phase 5 — Inventory & interaction
- ✅ Inventory model: slots, items, equipment tracking, `toss`,
  `toss_stack`, `unequip`, `move_slot_item`, `put_away`, `transfer`,
  `put_selected_item_range`, `simple_click`
- ✅ Window/container model: open/close tracking, `set_slot`/`window_items`
  state sync, container slot ranges from `windows.json`
- ✅ Typed windows: `Window` base + `FurnaceWindow` (burn/cook progress),
  `EnchantmentTableWindow` (`enchant`), `AnvilWindow` (`rename`,
  repair cost), `VillagerWindow` (trades, `select_trade`),
  `HorseWindow`; `bot.open_window`/`open_furnace`/`open_enchantment_table`/
  `open_anvil`/`open_villager`/`current_window`
- ✅ `bot.creative` namespace: `set_slot`/`give`/`clear`/`set_held_item`
  via `set_creative_slot`
- ✅ Window clicks: mode-0 (pickup/place/merge), mode-1 (shift-click
  transfer), mode-2 (hotbar swap) with per-window state-id sync
- ✅ Container helpers: `deposit_all`/`withdraw` bulk transfers
- ✅ Anvil: `bot.repair` places tool+material and takes the result
  (server-authoritative; fake server simulates result generation)
- ✅ Crafting: shaped + shapeless recipes via the 2x2 inventory grid and
  3x3 crafting-table windows (`crafting_table=True` with an open table)
- ✅ Smelting: `bot.smelt` drives `FurnaceWindow` (input/fuel/output
  slots, burn/cook progress); server-authoritative, no client recipe
  table needed
- ✅ Cursor & line-of-sight: `bot.block_at_cursor`/`bot.entity_at_cursor`,
  `utils.geometry` ray-vs-AABB intersection, entity bounding boxes
- ✅ Digging (`start_dig`/`stop_dig`/`dig` with status packets + local
  state), block placement with face/direction handling
- ✅ Item collection (`bot.collect` paths to nearby item entities)
- ✅ Attack (`attack`) and equip (`equip`) actions

## Phase 6 — Automation
- ✅ Pathfinder: A* over the collision grid with step-ups, 8-directional movement,
  diagonal corner-cutting prevention, `goto` execution with stuck detection and replan
- ✅ **Swimming support**: fluid blocks walkable at ×1.5 cost; vertical swim moves
- ✅ **Ladder/vine climbing**: climbable blocks walkable at ×2.0 cost; `_follow`
  applies correct controls (jump to swim up, sneak to descend on ladders)
- ✅ **A* runs off the event loop** via `ThreadPoolExecutor` (non-blocking)
- ✅ Pathfinder goals package (`leafish.pathfinder`): `GoalBlock`,
  `GoalNear`, `GoalXZ`/`GoalNearXZ`, `GoalY`, `GoalGetToBlock`,
  `GoalLookAtBlock`, `GoalFollow`/`GoalFollowEntity`, `GoalComposite`,
  `GoalInvert`; dynamic goals replan as targets move
- ✅ Combat: `bot.pvp` target acquisition + engage loop with pathfinder
  approach and attack cooldown; `bot.attack` for single hits
- ✅ Fishing: `bot.fish` cast/bite/reel with best-effort bite detection
- ✅ Farming: `bot.harvest`/`bot.plant`/`bot.tend_farm` for
  wheat/carrots/potatoes/beetroots, plus hoe-tilling via `bot.farming.till` / `bot.farming.till_area`
- ✅ **Tool & weapon selection**: `bot.best_tool_for(block)`, `bot.equip_for_block(block)`,
  `bot.dig(auto_tool=True)` automatic tool equip, `bot.best_weapon()`, and `bot.equip_best_weapon()`
- ✅ **Construction & building**: `BuilderModule` (`bot.builder`, `bot.build(plan)`),
  `ConstructionPlan` procedural shapes (walls, platforms, boxes, columns), material requirements,
  inventory validation, ground-up ordering, and automated execution
- ✅ **World biome queries**: `world.biome_at(pos)` and `bot.biome` property with
  `GameData.biome_by_id` / `biome_by_name` resolution
- ✅ **Connection diagnostics**: `bot.diagnostics`, `bot.latency`, `bot.ping`
- ✅ **Async context manager**: `async with Bot(...)` and `async with LeafishBot`
- ✅ **Multi-state block search**: `GameData.block_state_ids` and distance-sorted `world.find_blocks`

## Phase 7 — Extensibility
- ✅ Plugin loader: `bot.load_plugin` / `unload_plugin` for callables and
  inject/unload objects
- ✅ `@plugin` decorator with `name`/`dependencies`/`overrides` metadata;
  dependency auto-resolution and undeclared-override protection
- ✅ Multiple bot instances: independent `LeafishBot`s plus
  `Leafish.create_bots` for concurrent creation
- ✅ Examples: Complete suite of 10 runnable, documented examples in `examples/`
  covering connection, chat, following, collecting, mining, crafting, building,
  navigation, inventory, and plugins

## Game-state models
- ✅ `ScoreBoard`/`ScoreItem`, `Team`, `BossBar`, `Particle` in
  `modules/scoreboard.py` with `scoreboard_*`, `teams`, `boss_bar`,
  `world_particles`, `craft_progress_bar`, `trade_list`,
  `open_horse_window` packet handlers
- ✅ Combat/damage events: `hurt_animation`, `damage_event`,
  `death_combat_event`, combat enter/end
- ✅ Vehicle tracking: `attach_entity`, `set_passengers`, mount/dismount
- ✅ Item pickup (`collect` → `player_collect`/`item_collected`),
  block actions (pistons, note blocks, container lids), block-break
  progress, titles, sounds, entity effects, tags, books, maps

## Phase 8 — Compatibility & release
- ✅ Additional versions: minecraft-data vendored for 18 protocol
  versions (1.8 through 26.1); era-aware login/configuration state
  machine, outbound packet adaptation, slot/item encoding, legacy
  block ids and chunk column formats for every era.
- ✅ Performance pass (benchmarks & multi-bot memory profile in `reports/performance-report.md`)
- ✅ Docs: MkDocs site builds cleanly (index + API reference pages)
- 🚧 pip-installable package metadata present; not yet released

## Version compatibility

| Minecraft version | Protocol | Status |
|---|---|---|
| Java 1.8 | 47 | 🚧 connect/spawn/chat/move verified vs fake server; real-server validation pending |
| Java 1.9 | 107 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.10 | 210 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.11 | 315 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.12 | 335 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.13 | 393 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.14 | 477 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.15 | 573 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.16 | 735 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.17 | 755 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.18 | 757 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.19 | 759 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.20 | 763 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.21 | 767 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.21.4 | 769 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.21.9 | 773 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 1.21.11 | 774 | 🚧 connect/spawn/chat/move verified vs fake server |
| Java 26.1 | 775 | 🚧 connect/spawn/chat/move verified vs fake server |

## Known limitations / bugs
- Chunk light data is exposed via accessors but per-block lighting
  queries and dynamic light are not implemented.
- Chunk data does not yet handle every 1.21.x edge case (e.g. some
  multi-block-change variants).
- Microsoft auth flow is implemented but unverified against live Xbox Live
  endpoints.
- Encryption path is implemented and covered by unit tests; not verified
  against a real encrypted server.
- Enchantment offers are best-effort (decoded from slot components);
  there is no dedicated enchant-options packet in 1.21.11.
- Physics is client-predicted; server remains authoritative for position
  corrections.
- Some play-state packets are still acknowledged and emitted as generic
  events without dedicated handling (e.g. map data, recipe book UI).
