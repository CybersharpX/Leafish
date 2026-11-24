"""Inventory inspection and crafting demo.

Connects to a server, prints the bot's inventory, then attempts to craft
wooden planks from any oak logs it is holding.

    python examples/inventory_crafting.py localhost 25565 MyBot
"""

import asyncio
import sys

from leafish import Bot


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "LeafishCrafter"

    bot = Bot(host=host, port=port, username=username, auth="offline", version="1.21.11")

    @bot.on("spawn")
    async def on_spawn():
        print(f"Spawned at {bot.entity.position}")
        print("\n--- Inventory ---")
        for slot_idx, item in sorted(bot.inventory.slots.items()):
            if item is not None and not item.empty:
                print(f"  slot {slot_idx:3d}: {item.name} x{item.count}")

        # Try to craft oak planks if we have any oak logs.
        log_names = [
            "oak_log",
            "birch_log",
            "spruce_log",
            "jungle_log",
            "acacia_log",
            "dark_oak_log",
            "mangrove_log",
            "cherry_log",
        ]
        items = bot.inventory.items()
        log_item = next((it for it in items if it.name in log_names), None)
        if log_item is not None:
            log_name = log_item.name
            plank_name = log_name.replace("_log", "_planks")
            print(f"\nCrafting {plank_name} from {log_name}…")
            try:
                await bot.craft(plank_name, count=4)
                print("Crafting succeeded!")
            except Exception as exc:
                print(f"Crafting failed: {exc}")
        else:
            print("\nNo logs in inventory — nothing to craft.")

        await bot.quit()

    await bot.start()
    await bot.wait_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
