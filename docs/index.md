# Leafish

A pure Python, asynchronous reimplementation of
[Mineflayer](https://github.com/PrismarineJS/mineflayer) — a Minecraft
Java Edition bot framework. No Node.js, no JavaScript bridge, no
external bot process: Leafish speaks the Minecraft protocol natively
in Python.

## Why Leafish

- **Native protocol** — handshaking, login, configuration, and play
  states implemented from the vendored ProtoDef schemas; compression,
  RSA key exchange, and AES/CFB8 encryption included.
- **Data-driven versions** — packet layouts and game data (blocks,
  items, recipes, entities, windows) are per-version JSON; currently
  1.21.11 (protocol 774) and 1.21.4 (769).
- **Mineflayer-style architecture** — injected modules
  (`bot.pvp`, `bot.pathfinder`, `bot.creative`), an async event
  emitter, and a plugin system with dependency resolution.
- **Server-authoritative gameplay** — crafting, smelting, anvils, and
  trades move items and wait for the server rather than simulating
  outcomes.

## Feature highlights

- Offline + Microsoft (device-code OAuth → Xbox Live → XSTS) auth.
- Chunk decoding with paletted sections, block queries, raycasts,
  AABB collision physics, block/entity light.
- Digging, placement, containers (chests, furnaces, crafting tables,
  anvils, enchant tables, villagers, horses), 2×2 and 3×3 crafting,
  furnace smelting, anvil repair.
- A* pathfinding with a goals package (`GoalNear`, `GoalFollow`,
  `GoalComposite`, ...).
- Combat (`bot.pvp`), fishing, farming, item collection.
- Creative-mode inventory ops, plugin decorators with dependencies,
  multi-bot support.

## Quickstart

```python
import asyncio
from leafish import Leafish, Vec3

async def main():
    bot = await Leafish.create_bot(
        host="localhost", port=25565,
        username="LeafishBot", auth="offline",
    )
    if not bot.spawned:
        await bot.wait_for("spawn", timeout=10)
    await bot.chat("Hello, Minecraft!")
    await bot.goto(bot.entity.position + Vec3(4, 0, 0))
    await bot.quit()

asyncio.run(main())
```

## Documentation map

- **[Getting started](getting-started/installation.md)** — install,
  quickstart, authentication, configuration.
- **[Concepts](concepts/architecture.md)** — architecture, events,
  plugins, versions & data.
- **[Guides](guides/chat.md)** — task-oriented walkthroughs (chat,
  movement, world, inventory, crafting, combat, automation,
  creative).
- **[API reference](api/index.md)** — complete `LeafishBot` surface,
  world/entities/inventory/windows models, pathfinder goals, modules,
  state, plugins, auth, game data, events, exceptions, utilities.

## Project status

See `IMPLEMENTATION_STATUS.md` in the repository for the authoritative
feature/limitation list. The project is alpha — the API surface is
broad and tested against a fake protocol server, but real-server
coverage is still growing.
