# Implementation Status

This file is the source of truth for what Leafish can actually do today.
Nothing is listed as complete unless it is implemented and covered by tests.

Legend: ✅ done · 🚧 partial · ⬜ not started · ❌ unsupported/known issue

## Phase 0 — Scaffolding
- ✅ Package skeleton (`src/leafish`), `pyproject.toml`, pytest/ruff/ty config
- ✅ README, LICENSE, CONTRIBUTING, CHANGELOG, ROADMAP

## Phase 1 — Foundation
- ✅ Exception hierarchy (`LeafishError` and subclasses)
- ✅ Configuration (`BotConfig`)
- ✅ `Vec3`/`Vec2`/`BlockPos`, math, geometry, raycast helpers
- ✅ NBT parse/serialize (SNBT + binary)
- ✅ Async event emitter (`on`/`once`/`off`/`wait_for`/`emit`, error isolation)

## Phase 2 — Protocol
- ✅ VarInt/VarLong encode/decode, packet framing, max-size validation
- ✅ Compression (threshold + zlib)
- ✅ AES/CFB8 encryption
- ✅ ProtoDef compiler: schema → packet defs → encode/decode
- ✅ Protocol states & transition handling (handshaking/status/login/configuration/play)
- ✅ Keepalive
- ✅ Version registry + vendored minecraft-data JSON loader
- 🚧 Custom packet types: implemented lazily as handlers require them

## Phase 3 — Basic bot
- ⬜ `Leafish.create_bot`, `LeafishBot`
- ⬜ Spawn/login/configuration packet handling
- ⬜ Chat
- ⬜ Movement
- ⬜ Health/hunger

## Phase 4 — World & entities
- ⬜ Chunks/sections/palettes
- ⬜ Blocks registry & lookups
- ⬜ Entities
- ⬜ Raycast in-world

## Phase 5 — Inventory & interaction
- ⬜ Inventory/items/windows
- ⬜ Digging/placing
- ⬜ Containers
- ⬜ Item collection

## Phase 6 — Automation
- ⬜ Crafting
- ⬜ Physics
- ⬜ Pathfinder
- ⬜ Combat
- ⬜ Fishing/farming

## Phase 7 — Extensibility
- ⬜ Plugins
- ⬜ Multi-bot
- ⬜ Examples

## Phase 8 — Compatibility & release
- ⬜ Additional versions
- ⬜ Performance pass
- ⬜ Docs

## Version compatibility

| Minecraft version | Protocol | Status |
|---|---|---|
| — | — | none yet |

## Known limitations / bugs
- None recorded yet.
