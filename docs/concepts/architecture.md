# Architecture

Leafish is a native, data-driven Minecraft Java bot framework. The
design goal is Mineflayer-equivalent architecture — plugin modules,
events, injected namespaces — implemented from scratch in Python.

## Layers

```
┌────────────────────────────────────────────────────┐
│ LeafishBot  (public API, event emitter, state)     │
├────────────────────────────────────────────────────┤
│ Modules: actions, crafting, containers, pathfinder,│
│   pvp, farming, fishing, creative, physics, ...    │
├────────────────────────────────────────────────────┤
│ World / Entities / Inventory / Windows models      │
├────────────────────────────────────────────────────┤
│ Protocol: session state machine + ProtoDef codec   │
│   (handshaking → status → login → config → play)   │
├────────────────────────────────────────────────────┤
│ Transport: asyncio streams, compression, RSA+AES   │
├────────────────────────────────────────────────────┤
│ Vendored minecraft-data JSONs per version          │
└────────────────────────────────────────────────────┘
```

## Key design decisions

### Data-driven protocol

Packet layouts are **never hardcoded**. Each supported version ships
`protocol.json` (a ProtoDef schema) plus game-data registries
(blocks, items, entities, recipes, windows, ...). `ProtocolCodec`
compiles the schema once per (version, state, direction) and
`protolib` handles serialization. Adding a Minecraft version means
vendoring its JSON — no code changes.

### Injected modules

`LeafishBot` composes small module objects (`bot.physics`,
`bot.pathfinder`, `bot.pvp`, `bot.creative`, `bot.containers`,
`bot.inventory`, `bot.world`, `bot.entities`, ...). Modules are plain
Python classes holding a `bot` reference — the same extension model
Mineflayer uses, so third-party plugins can add namespaces the same
way.

### Server-authoritative gameplay

Where Minecraft's protocol is server-authoritative (furnace results,
crafting outputs, anvil repairs, trades), Leafish **moves items and
waits** rather than simulating outcomes. Client-side recipe data is
used only for *planning* (finding ingredient shortfalls), never for
predicting results.

### Async event emitter

`bot.on(event, handler)` accepts sync or async handlers; handlers run
as tasks with error isolation (a failing handler reports to `error`
events instead of killing the bot). See [Events](events.md).

### Version registry

`leafish.version` + `leafish.data.registry` resolve version strings
(`"latest"`, `"1.21.11"`) to vendored data directories under
`src/leafish/data/versions/`. See
[Versions & data](versions-and-data.md).

## Source layout

```
src/leafish/
├── bot.py               # LeafishBot + Leafish factory
├── config.py            # BotConfig
├── auth/                # offline + Microsoft auth
├── protocol/            # framing, compression, encryption, session
├── data/                # registry + vendored versions/*/ JSONs
├── world/               # World, Chunk, Block, chunk codec
├── entities/            # Entity model + manager
├── inventory/           # Item + Inventory models
├── modules/             # gameplay modules (one file each)
├── pathfinder/          # goals package
├── plugins/             # plugin decorator + PluginManager
├── events/              # emitter + canonical event names
├── utils/               # vectors, geometry, NBT, math, text
└── exceptions.py        # error hierarchy
```
