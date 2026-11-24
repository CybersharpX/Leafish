"""05 - Mining Blocks.

Demonstrates world block queries, automatic tool selection, and mining:
- Searching for blocks by name (e.g. ``iron_ore``, ``diamond_ore``, ``coal_ore``)
  with full multi-block-state resolution.
- Automatic tool selection (selecting diamond pickaxe for stone/ores, shovel for dirt, etc.).
- Navigating to the target block.
- Performing the dig operation with proper timing, packet handshakes, and animation.
- Handling dig progress and cancellation.

Usage:
    python examples/05_mining_blocks.py [host] [port] [username] [block_name]
"""

import asyncio
import sys

from leafish import Bot
from leafish.pathfinder.goals import GoalGetToBlock


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "MinerBot"
    target_block = sys.argv[4] if len(sys.argv) > 4 else "iron_ore"

    bot = Bot(host=host, port=port, username=username, auth="offline", version="auto")

    @bot.on("spawn")
    async def on_spawn():
        print(f"[*] Miner bot ready. Searching for '{target_block}'...")
        await bot.chat(f"Ready to mine! Say '!mine <block>' or I will look for {target_block}.")

    @bot.on("digging_started")
    def on_dig_start(block):
        print(f"[*] Started mining {block.name} at {block.position}")

    async def mine_target(block_name: str):
        # find_blocks searches loaded chunks, with all multi-state IDs and distance sorting
        positions = bot.world.find_blocks(block_name, max_distance=32, count=1)
        if not positions and not block_name.startswith("deepslate_") and "ore" in block_name:
            # Also try deepslate variant if searching for ore
            positions = bot.world.find_blocks(f"deepslate_{block_name}", max_distance=32, count=1)

        if not positions:
            await bot.chat(f"No '{block_name}' found within 32 blocks!")
            return

        pos = positions[0]
        block = bot.world.block_at(pos)
        print(f"[*] Located {block.name} at {pos}. Navigating...")
        await bot.chat(f"Found {block.name} at ({pos.x}, {pos.y}, {pos.z}). Walking there...")

        # Walk within reach of the block
        arrived = await bot.pathfinder.goto(GoalGetToBlock(pos.x, pos.y, pos.z), timeout=20.0)
        if not arrived:
            await bot.chat("Could not find a path to the block!")
            return

        # Auto tool selection: equips best pickaxe/shovel/axe before digging
        best_tool = bot.best_tool_for(block)
        tool_name = best_tool.name if best_tool else "bare hands"
        print(f"[*] Using tool: {tool_name}")

        # Execute dig (auto_tool=True automatically equips the optimal tool)
        await bot.dig(block, auto_tool=True)
        print(f"[+] Successfully mined {block.name}!")
        await bot.chat(f"Mined {block.name} successfully!")

    @bot.on("chat")
    async def on_chat(sender, message, *_rest):
        if sender == bot.username:
            return
        parts = message.strip().split()
        if parts and parts[0] == "!mine":
            name = parts[1] if len(parts) > 1 else target_block
            await mine_target(name)

    async with bot:
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
