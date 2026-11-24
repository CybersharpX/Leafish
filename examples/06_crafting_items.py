"""06 - Crafting Items.

Demonstrates crafting recipes in Leafish:
- Inspecting inventory ingredients.
- Crafting 2x2 recipes directly in the player's inventory grid (e.g. planks, sticks, torches).
- Opening and using a 3x3 crafting table container window for complex recipes.
- Handling window state synchronization and recipe planning.

Usage:
    python examples/06_crafting_items.py [host] [port] [username]
"""

import asyncio
import sys

from leafish import Bot


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "CraftBot"

    bot = Bot(host=host, port=port, username=username, auth="offline", version="auto")

    @bot.on("spawn")
    async def on_spawn():
        print(f"[*] {bot.username} spawned!")
        print("\n--- Current Inventory Items ---")
        for item in bot.inventory.items():
            print(f"  Slot {item.slot:2d}: {item.name} x{item.count}")

        # Check for wood logs to turn into planks
        log_types = ["oak_log", "birch_log", "spruce_log", "jungle_log", "acacia_log", "dark_oak_log"]
        held_logs = [i for i in bot.inventory.items() if i.name in log_types]

        if held_logs:
            chosen_log = held_logs[0]
            plank_name = chosen_log.name.replace("_log", "_planks")
            print(f"\n[*] Found {chosen_log.name}. Crafting {plank_name} in 2x2 grid...")
            try:
                await bot.craft(plank_name, count=4)
                print(f"[+] Crafted {plank_name} successfully!")
                await bot.chat(f"Crafted {plank_name}!")
            except Exception as exc:
                print(f"[!] Crafting failed: {exc}")
        else:
            print("\n[*] No wood logs in inventory. To test, drop an oak_log to the bot.")
            await bot.chat("Drop logs to me or say '!craft <item>'")

    @bot.on("chat")
    async def on_chat(sender, message, *_rest):
        if sender == bot.username:
            return
        parts = message.strip().split()
        if parts[0] == "!craft" and len(parts) > 1:
            item_name = parts[1]
            count = int(parts[2]) if len(parts) > 2 else 1
            try:
                await bot.craft(item_name, count=count)
                await bot.chat(f"Crafted {item_name} x{count}!")
            except Exception as exc:
                await bot.chat(f"Could not craft {item_name}: {exc}")

    async with bot:
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
