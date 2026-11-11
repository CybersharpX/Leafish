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
  detection, fluid drag)
- ✅ End-to-end integration test vs fake server (connect → spawn → chat →
  move)
- 🚧 Entity tracking: spawn/despawn/metadata/equipment/velocity/teleport
  handled; richer entity types partial

## Phase 4 — World & entities
- ✅ World model: chunk columns, palette-container section decoding
  (single/indirect/direct), block get/set API, block search, raycast
- 🚧 Entities: typed entity classes (Player/Mob/ItemEntity/Projectile/Vehicle)
- ✅ Modern 1.21.x chunk column decoding (heightmaps, block entities,
  light masks parsed; sky/block light arrays stored but not fully exposed)
- ✅ Raycast against loaded world

## Phase 5 — Inventory & interaction
- 🚧 Inventory model: slots, items, equipment tracking
- 🚧 Window/container click transactions: mode-0 (pickup/place/merge)
  and mode-2 (hotbar swap) clicks with state-id sync; shift-click and
  non-player windows partial
- ✅ Crafting: shaped + shapeless recipes via the 2x2 inventory grid;
  3x3 crafting-table recipes detected but rejected (table windows not
  yet implemented)
- ✅ Digging (`start_dig`/`stop_dig`/`dig` with status packets + local
  state), block placement with face/direction handling
- ✅ Item collection (`bot.collect` paths to nearby item entities)
- ✅ Attack (`attack`) and equip (`equip`) actions

## Phase 6 — Automation
- ✅ Pathfinder: A* over the collision grid with step-ups, `goto`
  execution with stuck detection and replan
- ✅ Combat: `bot.pvp` target acquisition + engage loop with pathfinder
  approach and attack cooldown; `bot.attack` for single hits
- ✅ Fishing: `bot.fish` cast/bite/reel with best-effort bite detection
- ✅ Farming: `bot.harvest`/`bot.plant`/`bot.tend_farm` for
  wheat/carrots/potatoes/beetroots (no hoe-tilling yet)

## Phase 7 — Extensibility
- ✅ Plugin loader: `bot.load_plugin` / `unload_plugin` for callables and
  inject/unload objects
- ✅ Multiple bot instances: independent `LeafishBot`s plus
  `Leafish.create_bots` for concurrent creation
- ✅ Examples: `examples/` (echo bot, goto, collector) — runnable against
  a real server, not covered by automated tests

## Phase 8 — Compatibility & release
- ⬜ Additional versions
- ⬜ Performance pass
- 🚧 Docs (MkDocs skeleton present; API docs incomplete)
- 🚧 pip-installable package metadata present; not yet released

## Version compatibility

| Minecraft version | Protocol | Status |
|---|---|---|
| Java 1.21.11 | 774 | 🚧 connect/spawn/chat/move verified vs fake server; real-server validation pending |

## Known limitations / bugs
- Chunk light data is stored but not exposed; chunk data does not yet
  handle every 1.21.x edge case (e.g. some multi-block-change variants).
- Microsoft auth flow is implemented but unverified against live Xbox Live
  endpoints.
- Encryption path is implemented but only exercised by unit-level tests,
  not a real encrypted server.
- Many play-state packets are acknowledged and emitted as generic events
  without dedicated handling.
