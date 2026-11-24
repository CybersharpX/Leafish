"""07 - Building Structures.

Demonstrates structural construction planning and automated building:
- Creating high-level ``ConstructionPlan``s (walls, platforms, boxes, columns).
- Computing required material counts.
- Validating inventory resources prior to execution.
- Ordering placements from ground up (bottom to top) so blocks have stable support.
- Walking into placement reach and placing blocks against valid neighbor faces.
- Monitoring construction progress events.

Usage:
    python examples/07_building_structures.py [host] [port] [username]
"""

import asyncio
import sys

from leafish import BlockPos, Bot, ConstructionPlan


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "BuilderBot"

    bot = Bot(host=host, port=port, username=username, auth="offline", version="auto")

    @bot.on("build_started")
    def on_build_start(plan):
        print(f"[*] Started building structure ({len(plan)} total blocks)...")

    @bot.on("build_progress")
    def on_progress(current, total, pos, block_name):
        percent = int(current / total * 100)
        print(
            f"  [{percent:3d}%] Placed {block_name} at ({pos.x}, {pos.y}, {pos.z}) ({current}/{total})"
        )

    @bot.on("build_complete")
    def on_build_done(plan):
        print(f"[+] Construction complete! ({len(plan)} blocks placed)")

    async def build_demonstration():
        pos = bot.entity.position.floor()
        # Create a small 3-block-wide, 2-block-high stone wall 2 blocks in front of the bot
        start = BlockPos(pos.x + 2, pos.y, pos.z - 1)
        end = BlockPos(pos.x + 2, pos.y, pos.z + 1)
        block_type = "cobblestone"

        plan = ConstructionPlan.wall(start, end, height=2, block_name=block_type)
        print(f"[*] Blueprint created for {len(plan)} {block_type} blocks.")

        # Check required materials
        req = plan.required_materials()
        print(f"[*] Materials needed: {req}")

        has_mats, missing = plan.validate_inventory(bot)
        if not has_mats and bot.game_mode != "creative":
            print(f"[!] Missing materials: {missing}")
            await bot.chat(f"I need more materials: {missing}")
            return

        await bot.chat("Starting construction...")
        try:
            # Execute plan: orders placements bottom-up, moves in range, and places blocks
            await bot.build(plan, reach=4.5, navigate=True)
            await bot.chat("Wall completed!")
        except Exception as exc:
            print(f"[!] Build error: {exc}")
            await bot.chat(f"Build failed: {exc}")

    @bot.on("spawn")
    async def on_spawn():
        print(f"[*] Builder bot spawned at {bot.entity.position:.1f}")
        await bot.chat("Say '!build' to start building a demo wall.")

    @bot.on("chat")
    async def on_chat(sender, message, *_rest):
        if sender == bot.username:
            return
        if message.strip() == "!build":
            await build_demonstration()

    async with bot:
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
