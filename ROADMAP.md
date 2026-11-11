# Roadmap

## Phase 0 — Foundation & scaffolding
- [x] Project structure, packaging, lint/type/test tooling
- [x] README, LICENSE, CONTRIBUTING, CHANGELOG
- [x] ROADMAP / IMPLEMENTATION_STATUS tracking

## Phase 1 — Core foundation
- [x] Exception hierarchy
- [x] Configuration
- [x] Vector / math / geometry utilities
- [x] NBT parsing & serialization
- [x] Async event emitter

## Phase 2 — Protocol stack
- [x] VarInt/VarLong, packet framing, size limits
- [x] Packet compression (zlib threshold)
- [x] AES/CFB8 encryption
- [x] ProtoDef schema compiler driven by minecraft-data `protocol.json`
- [x] Connection state machine (handshake → status → login → configuration → play)
- [x] Keepalive handling
- [x] Versioned protocol adapters + vendored minecraft-data
- [ ] Full coverage of per-version custom packet types

## Phase 3 — Basic bot
- [x] Bot creation API (`Leafish.create_bot`)
- [x] Spawn/login/configuration handling
- [x] Chat send/receive
- [x] Movement controls, look/look_at
- [x] Position tracking, health, hunger

## Phase 4 — World & entities
- [x] Chunk decoding, sections, palettes, light data
- [x] Block registry & lookups
- [x] Entity registry & tracking
- [x] Raycasting / line of sight

## Phase 5 — Inventory & interaction
- [x] Inventory/items/windows/transactions
- [x] Block digging & placement
- [x] Containers
- [x] Item collection

## Phase 6 — Automation
- [x] Crafting + recipe planner
- [x] Physics (movement, collision)
- [x] Pathfinder (A*, goals, movements)
- [x] Combat
- [x] Fishing, farming

## Phase 7 — Extensibility
- [x] Plugin framework
- [x] Multi-bot manager
- [x] Examples

## Phase 8 — Compatibility & release
- [ ] Additional protocol versions
- [ ] Performance pass
- [x] Full documentation (MkDocs)
- [ ] Release

## Parity backlog (reference_api.md)
- [ ] Remaining bot methods/properties/events parity items
- [ ] Typed windows (Furnace, EnchantmentTable, Villager)
- [ ] Pathfinder goal classes
- [ ] `bot.creative` namespace
- [ ] Scoreboards / teams / boss bars
