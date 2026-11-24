"""08 - Navigating to Coordinates.

Demonstrates A* pathfinding and 3D navigation in Leafish:
- Navigation to exact coordinates (``GoalBlock``) or proximity radii (``GoalNear``).
- Horizontal navigation without vertical constraints (``GoalXZ`` / ``GoalNearXZ``).
- Stepping up blocks, 8-directional movement, and corner-cutting avoidance.
- Swimming up through water and climbing ladders/vines.
- Off-thread path calculation keeping the asyncio event loop responsive.
- Stuck detection and automatic replanning.

Usage:
    python examples/08_navigating_coordinates.py [host] [port] [username] [x] [y] [z]
"""

import asyncio
import sys

from leafish import BlockPos, Bot
from leafish.pathfinder.goals import GoalNear


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "NavigatorBot"

    target_pos = None
    if len(sys.argv) >= 7:
        target_pos = BlockPos(int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))

    bot = Bot(host=host, port=port, username=username, auth="offline", version="auto")

    async def navigate_to(pos: BlockPos):
        print(f"[*] Calculating path to {pos}...")
        await bot.chat(f"Navigating to ({pos.x}, {pos.y}, {pos.z})...")
        goal = GoalNear(pos.x + 0.5, pos.y, pos.z + 0.5, range=1.5)

        try:
            # goto executes path steps while physics updates ground, fluids, and collisions
            arrived = await bot.pathfinder.goto(goal, timeout=60.0)
            if arrived:
                current = bot.entity.position
                print(f"[+] Arrived at ({current.x:.1f}, {current.y:.1f}, {current.z:.1f})!")
                await bot.chat("Arrived at target!")
            else:
                print("[-] Could not reach target (unreachable or timed out).")
                await bot.chat("Path blocked or unreachable.")
        except Exception as exc:
            print(f"[!] Pathfinding error: {exc}")

    @bot.on("spawn")
    async def on_spawn():
        print(f"[*] Navigator ready at {bot.entity.position:.1f}")
        await bot.chat("Say '!goto <x> <y> <z>' to send me anywhere.")
        if target_pos:
            await asyncio.sleep(1.0)
            await navigate_to(target_pos)

    @bot.on("chat")
    async def on_chat(sender, message, *_rest):
        if sender == bot.username:
            return
        parts = message.strip().split()
        if parts and parts[0] == "!goto" and len(parts) >= 4:
            try:
                x, y, z = int(parts[1]), int(parts[2]), int(parts[3])
                await navigate_to(BlockPos(x, y, z))
            except ValueError:
                await bot.chat("Usage: !goto <x> <y> <z>")

    async with bot:
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
