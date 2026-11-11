# Implementation Status

This file is the source of truth for what Leafish can actually do today.
Nothing is listed as complete unless it is implemented and covered by tests.

Legend: ✅ done · 🚧 partial · ⬜ not started · ❌ unsupported/known issue

## Phase 0 — Scaffolding
- ✅ Package skeleton (`src/leafish`), `pyproject.toml`, pytest/ruff/ty config
- ✅ README, LICENSE, CONTRIBUTING, CHANGELOG, ROADMAP
- ✅ Git repository initialized

## Phase 1 — Foundation
- ✅ Exception hierarchy (`LeafishError` and subclasses)
- ✅ Configuration (`BotConfig`)
- ✅ `Vec3`/`Vec2`/`BlockPos`, math, geometry, raycast helpers
- ✅ NBT parse/serialize (SNBT + binary)
- ✅ Async event emitter (`on`/`once`/`off`/`wait_for`/`emit`, error isolation)
- ✅ Chat text component → plain text conversion

## Phase 2 — Protocol
- ✅ VarInt/VarLong encode/decode, packet framing, max-size validation
- ✅ Compression (threshold + zlib)
- ✅ AES/CFB8 encryption (login handshake shared secret + transport cipher)
- ✅ ProtoDef serialization via `protolib` (all Minecraft composite types:
  slots, entity metadata, NBT, registry holders, bitflags, etc.)
- ✅ Protocol states & transitions (handshaking/status/login/configuration/play)
- ✅ Login flow: offline mode, encryption request/response, login success,
  compression negotiation, disconnect handling
- ✅ Configuration-state packets (finish configuration, registry data stubs)
- ✅ Keepalive
- ✅ Version registry + vendored minecraft-data JSON loader
- ✅ Fake asyncio protocol server for hermetic integration tests
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
- ✅ Movement module (position/look/ground packets, teleport confirm)
- ✅ Physics engine (AABB collision, axis-separated movement, ground
  detection, fluid drag, `physics.enabled` toggle)
- ✅ Full interaction surface: `use_item`, `consume`,
  `activate_item`/`deactivate_item`, `use_on`, `activate_entity`,
  `activate_block`, `place_entity`, signs (`update_sign`), books,
  tab-complete, resource-pack responses, command blocks, respawn,
  sleep/wake, elytra, mount/dismount/vehicle steering
- ✅ State objects/properties: `game`, `abilities`, `time`,
  `experience`, `health`/`food`/`food_saturation`/`oxygen`,
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
- ✅ Entities: typed entity classes (Player/Mob/ItemEntity/Projectile/
  Vehicle) classified from versioned type ids, movement/metadata/
  equipment tracking, nearest-entity queries
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
- ✅ Digging (`start_dig`/`stop_dig`/`dig` with status packets + local
  state), block placement with face/direction handling
- ✅ Item collection (`bot.collect` paths to nearby item entities)
- ✅ Attack (`attack`) and equip (`equip`) actions

## Phase 6 — Automation
- ✅ Pathfinder: A* over the collision grid with step-ups, `goto`
  execution with stuck detection and replan
- ✅ Pathfinder goals package (`leafish.pathfinder`): `GoalBlock`,
  `GoalNear`, `GoalXZ`/`GoalNearXZ`, `GoalY`, `GoalGetToBlock`,
  `GoalLookAtBlock`, `GoalFollow`/`GoalFollowEntity`, `GoalComposite`,
  `GoalInvert`; dynamic goals replan as targets move
- ✅ Combat: `bot.pvp` target acquisition + engage loop with pathfinder
  approach and attack cooldown; `bot.attack` for single hits
- ✅ Fishing: `bot.fish` cast/bite/reel with best-effort bite detection
- ✅ Farming: `bot.harvest`/`bot.plant`/`bot.tend_farm` for
  wheat/carrots/potatoes/beetroots (no hoe-tilling yet)

## Phase 7 — Extensibility
- ✅ Plugin loader: `bot.load_plugin` / `unload_plugin` for callables and
  inject/unload objects
- ✅ `@plugin` decorator with `name`/`dependencies`/`overrides` metadata;
  dependency auto-resolution and undeclared-override protection
- ✅ Multiple bot instances: independent `LeafishBot`s plus
  `Leafish.create_bots` for concurrent creation
- ✅ Examples: `examples/` (echo bot, goto, collector) — runnable against
  a real server, not covered by automated tests

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
- ⬜ Additional versions
- ⬜ Performance pass
- ✅ Docs: MkDocs site builds cleanly (index + API reference pages)
- 🚧 pip-installable package metadata present; not yet released

## Version compatibility

| Minecraft version | Protocol | Status |
|---|---|---|
| Java 1.21.11 | 774 | 🚧 connect/spawn/chat/move verified vs fake server; real-server validation pending |
| Java 1.21.4 | 769 | 🚧 connect/spawn/chat smoke test vs fake server |

## Known limitations / bugs
- Chunk light data is exposed via accessors but per-block lighting
  queries and dynamic light are not implemented.
- Chunk data does not yet handle every 1.21.x edge case (e.g. some
  multi-block-change variants).
- Microsoft auth flow is implemented but unverified against live Xbox Live
  endpoints.
- Encryption path is implemented but only exercised by unit-level tests,
  not a real encrypted server.
- Enchantment offers are best-effort (decoded from slot components);
  there is no dedicated enchant-options packet in 1.21.11.
- `GoalInvert` and `GoalY`/`GoalXZ` pathing is approximate; physics is
  client-predicted and the server remains authoritative.
- Some play-state packets are still acknowledged and emitted as generic
  events without dedicated handling (e.g. map data, recipe book UI).
