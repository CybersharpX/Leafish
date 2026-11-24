# Leafish

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A pure Python, asynchronous Minecraft Java Edition bot framework inspired by
[Mineflayer](https://github.com/PrismarineJS/mineflayer).

Leafish lets you programmatically control Minecraft Java Edition clients from
Python: join servers, chat, move, mine, build, craft, fight, and automate —
all through a modern `asyncio` API with an event-driven architecture.

## Features (planned / in progress)

See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for the honest,
current state of every subsystem.

- Native Minecraft Java Edition protocol implementation (no Node.js, no
  external bot process)
- Offline and Microsoft authentication
- Async, event-driven API with plugin support
- World, chunk, entity, and inventory tracking
- Pathfinding, digging, placing, crafting, combat, containers
- Multi-version protocol support driven by vendored minecraft-data

## Requirements

- Python 3.11+

## Installation

```bash
pip install leafish
```

For development:

```bash
git clone https://github.com/leafish/leafish
cd leafish
pip install -e ".[dev]"
```

## Quick start

```python
import asyncio
from leafish import Leafish

async def main():
    bot = await Leafish.create_bot(
        host="localhost",
        port=25565,
        username="Leafish",
        auth="offline",
    )

    @bot.on("spawn")
    async def on_spawn():
        print("Leafish joined the world!")

    @bot.on("chat")
    async def on_chat(username, message):
        print(f"<{username}> {message}")

    await bot.wait_until_disconnected()

asyncio.run(main())
```

## Status

Leafish is under active development. The protocol layer, bot API, world model,
and automation modules are implemented incrementally — check
[ROADMAP.md](ROADMAP.md) and [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
for details. Features are not advertised until they are implemented and tested.

## License

MIT — see [LICENSE](LICENSE).
