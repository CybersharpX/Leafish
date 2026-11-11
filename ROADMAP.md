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
- [ ] Bot creation API (`Leafish.create_bot`)
- [ ] Spawn/login/configuration handling
- [ ] Chat send/receive
- [ ] Movement controls, look/look_at
- [ ] Position tracking, health, hunger

## Phase 4 — World & entities
- [ ] Chunk decoding, sections, palettes
- [ ] Block registry & lookups
- [ ] Entity registry & tracking
- [ ] Raycasting / line of sight

## Phase 5 — Inventory & interaction
- [ ] Inventory/items/windows/transactions
- [ ] Block digging & placement
- [ ] Containers
- [ ] Item collection

## Phase 6 — Automation
- [ ] Crafting + recipe planner
- [ ] Physics (movement, collision)
- [ ] Pathfinder (A*, goals, movements)
- [ ] Combat
- [ ] Fishing, farming

## Phase 7 — Extensibility
- [ ] Plugin framework
- [ ] Multi-bot manager
- [ ] Examples

## Phase 8 — Compatibility & release
- [ ] Additional protocol versions
- [ ] Performance pass
- [ ] Full documentation
- [ ] Release
