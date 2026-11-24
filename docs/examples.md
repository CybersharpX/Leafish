# Examples

Runnable scripts live in `examples/` at the repository root. Each
connects to a Java 1.21.11 server (offline auth works on
`online-mode=false` servers).

## Running

```bash
pip install -e .
python examples/echo_bot.py localhost 25565 MyBot
```

## Available examples

| Script | Demonstrates |
|---|---|
| `echo_bot.py` | Connect, wait for `spawn`, send/receive chat. |
| `goto_example.py` | `bot.goto` pathfinding across terrain. |
| `collector.py` | World queries (`block_at`, `can_dig_block`) + `bot.dig`. |

## Writing your own

The smallest bot is ~15 lines — see the
[Quickstart](getting-started/quickstart.md). From there, compose the
modules documented in the [API reference](api/index.md):

```python
import asyncio
from leafish import Leafish
from leafish.pathfinder import GoalNear

async def main():
    bot = await Leafish.create_bot(host="localhost", username="Farmer")
    await bot.wait_for("spawn", timeout=10)

    @bot.on("chat")
    async def on_chat(user, msg):
        if msg == "come":
            await bot.goto(GoalNear(bot.entity.position.x,
                                    bot.entity.position.y,
                                    bot.entity.position.z, range=2))

    await bot.tend_farm()          # harvest + replant crops
    await bot.collect()            # pick up drops
    await bot.quit()

asyncio.run(main())
```

For reusable behavior, write a [plugin](concepts/plugins.md) instead of
monkey-patching the bot.
