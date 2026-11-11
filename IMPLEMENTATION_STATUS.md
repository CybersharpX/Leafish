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
- ✅ Physics engine (gravity, collision-aware movement ticks)
- ✅ End-to-end integration test vs fake server (connect → spawn → chat →
  move)
- 🚧 Entity tracking: spawn/despawn/metadata/equipment/velocity/teleport
  handled; richer entity types partial

## Phase 4 — World & entities
- 🚧 World model: chunk column storage, block get/set API
- 🚧 Entities: typed entity classes (Player/Mob/ItemEntity/Projectile/Vehicle)
- ⬜ Full chunk packet decoding (modern 1.21.x chunk format is complex)
- ⬜ Raycast against loaded world

## Phase 5 — Inventory & interaction
- 🚧 Inventory model: slots, items, equipment tracking
- ⬜ Window/container click transactions
- ⬜ Crafting
- ⬜ Digging/placing
- ⬜ Item collection

## Phase 6 — Automation
- ⬜ Pathfinder
- ⬜ Combat
- ⬜ Fishing/farming

## Phase 7 — Extensibility
- ⬜ Plugin loader
- 🚧 Multiple bot instances (each `LeafishBot` is independent; no shared
  manager/orchestration API yet)
- ⬜ Examples

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
- Chunk decoding for the modern format is incomplete — `world` block lookups
  only work for data injected manually or via simple paths.
- Microsoft auth flow is implemented but unverified against live Xbox Live
  endpoints.
- Encryption path is implemented but only exercised by unit-level tests,
  not a real encrypted server.
- Many play-state packets are acknowledged and emitted as generic events
  without dedicated handling.
