# Quickstart

The smallest useful Leafish program connects to a server, waits for
spawn, and says hello.

```python
import asyncio
from leafish import Leafish, Vec3

async def main():
    bot = await Leafish.create_bot(
        host="localhost",
        port=25565,
        username="LeafishBot",
        auth="offline",
        version="1.21.11",
    )

    # Wait until the server finishes spawning the player.
    if not bot.spawned:
        await bot.wait_for("spawn", timeout=10)

    await bot.chat("Hello from Leafish!")

    # Walk a few blocks east.
    assert bot.entity is not None
    await bot.goto(bot.entity.position + Vec3(4, 0, 0), timeout=10)

    # Mine the block below-forward and report what we found.
    block = bot.world.block_at(bot.entity.position.offset(1, -1, 0).floor())
    if block and bot.can_dig_block(block):
        await bot.dig(block)

    await bot.quit()

asyncio.run(main())
```

## Key concepts

- **`Leafish.create_bot(...)`** resolves auth, loads the protocol
  codec for the requested version, connects, and returns a
  `LeafishBot`.
- **`bot.spawned` / `wait_for("spawn")`** — the server streams chunks
  and entities before the player is fully in-world; gate world
  interactions on this.
- **`bot.entity`** is the bot's own `Player` entity; `bot.entity.position`
  is a `Vec3` in world coordinates.
- **Everything is async** — all I/O goes through `asyncio`. Synchronous
  helpers (`bot.world.block_at`, `bot.inventory.count`) only read
  already-received state.
- **`await bot.quit()`** disconnects cleanly and stops background
  tasks (physics, pathfinder, pvp loops).

## Multiple bots

```python
bots = await Leafish.create_bots(
    {"host": "localhost", "username": "Alice", "auth": "offline"},
    {"host": "localhost", "username": "Bob",   "auth": "offline"},
)
```

See [Configuration](configuration.md) for every `create_bot` option and
[Authentication](authentication.md) for Microsoft sign-in.
