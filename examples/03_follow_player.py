"""03 - Following a Player.

Demonstrates tracking and following players:
- Finding players by name (``bot.player_by_name``) or proximity (``bot.nearest_player``).
- Goal-based pathfinding with dynamic target tracking (``GoalFollow``).
- Continuous recalculation as the target player moves.
- Handling obstacles, jumping up blocks, and stopping when close enough.

Usage:
    python examples/03_follow_player.py [host] [port] [username] [target_player]
"""

import asyncio
import sys

from leafish import Bot
from leafish.pathfinder.goals import GoalFollow


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "FollowBot"
    target_name = sys.argv[4] if len(sys.argv) > 4 else None

    bot = Bot(host=host, port=port, username=username, auth="offline", version="auto")

    following_task = None

    async def follow_loop(target_player):
        print(f"[*] Started following {target_player.name}...")
        await bot.chat(f"Following you, {target_player.name}!")
        # GoalFollow dynamically recalculates paths as the target moves
        goal = GoalFollow(target_player, max_distance=2.5, dynamic=True)
        try:
            await bot.pathfinder.goto(goal, timeout=120.0)
        except Exception as exc:
            print(f"[*] Follow ended or interrupted: {exc}")

    @bot.on("chat")
    async def on_chat(sender, message, *_rest):
        nonlocal following_task
        if sender == bot.username:
            return

        clean = message.strip()
        if clean == "!follow":
            player = bot.player_by_name(sender) or bot.nearest_player()
            if player is None:
                await bot.chat("I cannot see you nearby!")
                return

            if following_task and not following_task.done():
                following_task.cancel()
            following_task = asyncio.create_task(follow_loop(player))

        elif clean == "!stop":
            if following_task and not following_task.done():
                following_task.cancel()
            await bot.pathfinder.stop()
            await bot.chat("Stopped following.")

    follow_tasks = set()

    @bot.on("spawn")
    async def on_spawn():
        print("[*] Bot ready. Type '!follow' in Minecraft chat or pass target username.")
        if target_name:
            await asyncio.sleep(1.0)
            player = bot.player_by_name(target_name)
            if player:
                t = asyncio.create_task(follow_loop(player))
                follow_tasks.add(t)
                t.add_done_callback(follow_tasks.discard)
            else:
                print(f"[!] Target player '{target_name}' not found yet.")

    async with bot:
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
