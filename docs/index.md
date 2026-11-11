# Leafish

A pure Python, asynchronous reimplementation of
[Mineflayer](https://github.com/PrismarineJS/mineflayer) — a Minecraft
Java Edition bot framework. No Node.js, no JavaScript bridge, no
external bot process: Leafish speaks the Minecraft protocol natively
in Python.

## Features

- **Protocol**: full state machine (handshaking → login →
  configuration → play) with compression, RSA/AES-CFB8 encryption,
  offline and Microsoft authentication.
- **Data-driven versions**: packet schemas and game data (blocks,
  items, recipes, entities, windows) are vendored per Minecraft
  version; currently 1.21.11 (protocol 774) and 1.21.4 (769).
- **World**: chunk decoding with paletted sections, block queries,
  raycasts, AABB collision physics.
- **Gameplay**: digging, placement, containers (chests, crafting
  tables, anvils), 2×2 and 3×3 crafting, combat, fishing, farming,
  item collection, A* pathfinding.
- **Extensibility**: plugin loader, multi-bot support, async event
  emitter.

## Quickstart

```python
import asyncio
from leafish import Leafish

async def main():
    bot = await Leafish.create_bot(
        host="localhost", port=25565,
        username="LeafishBot", auth="offline",
    )
    await bot.chat("Hello, Minecraft!")
    await bot.goto(bot.entity.position + __import__("leafish").Vec3(4, 0, 0))
    await bot.quit()

asyncio.run(main())
```

See the [API reference](api/index.md) for the full surface, and
`examples/` in the repository for runnable scripts.
