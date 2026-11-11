"""Pathfind to a set of coordinates and report arrival.

    python examples/goto_example.py localhost 25565 MyBot 100 64 -50
"""

import asyncio
import sys

from leafish import Leafish
from leafish.utils.vectors import BlockPos


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "LeafishWalker"
    goal = BlockPos(
        int(sys.argv[4]) if len(sys.argv) > 4 else 32,
        int(sys.argv[5]) if len(sys.argv) > 5 else 64,
        int(sys.argv[6]) if len(sys.argv) > 6 else 32,
    )

    bot = await Leafish.create_bot(
        host=host, port=port, username=username, auth="offline",
        version="1.21.11",
    )

    @bot.on("spawn")
    async def on_spawn():
        print(f"Spawned at {bot.entity.position}; pathing to {goal}")
        try:
            arrived = await bot.goto(goal, timeout=60)
            print("Arrived!" if arrived else "Failed to arrive (timeout/stuck)")
        except Exception as exc:
            print("goto failed:", exc)

    try:
        await bot.wait_until_disconnected()
    except KeyboardInterrupt:
        pass
    finally:
        await bot.quit()


if __name__ == "__main__":
    asyncio.run(main())
