"""Auto-collect: dig blocks in a small area around the bot.

Requires the bot to have a pickaxe (or be in creative mode). Digs every
diggable block within `radius` of the spawn point, one at a time.

    python examples/collector.py localhost 25565 MyBot
"""

import asyncio
import sys

from leafish import Leafish
from leafish.utils.vectors import BlockPos

RADIUS = 3


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "LeafishMiner"

    bot = await Leafish.create_bot(
        host=host, port=port, username=username, auth="offline",
        version="1.21.11",
    )

    @bot.on("spawn")
    async def on_spawn():
        assert bot.entity is not None
        origin = bot.entity.position.floor()
        print(f"Mining around {origin}")
        dug = 0
        for dx in range(-RADIUS, RADIUS + 1):
            for dz in range(-RADIUS, RADIUS + 1):
                for dy in range(-1, 3):
                    pos = BlockPos(origin.x + dx, origin.y + dy, origin.z + dz)
                    block = bot.block_at(pos)
                    if block is None or not bot.can_dig_block(block):
                        continue
                    try:
                        await bot.dig(pos)
                        dug += 1
                    except Exception as exc:
                        print(f"  skip {pos}: {exc}")
        print(f"Done: dug {dug} blocks")

    try:
        await bot.wait_until_disconnected()
    except KeyboardInterrupt:
        pass
    finally:
        await bot.quit()


if __name__ == "__main__":
    asyncio.run(main())
