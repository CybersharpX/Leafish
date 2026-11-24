"""04 - Collecting Resources.

Demonstrates discovering and collecting dropped item entities:
- Querying tracked entities for dropped items (``ItemEntity``).
- Prioritizing items by proximity to the bot.
- Navigating to each item's location and collecting it.
- Tracking inventory changes when items are picked up.

Usage:
    python examples/04_collect_resources.py [host] [port] [username]
"""

import asyncio
import sys

from leafish import Bot


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "ScavengerBot"

    bot = Bot(host=host, port=port, username=username, auth="offline", version="auto")

    @bot.on("spawn")
    async def on_spawn():
        print(f"[*] {bot.username} spawned! Ready to collect items.")
        await bot.chat("Drop items near me or say '!collect' to vacuum the area.")

    @bot.on("item_collected")
    def on_pickup(collected_item, collector=None, count=1):
        item_id = getattr(collected_item, "id", collected_item)
        print(f"[+] Picked up item entity #{item_id} (x{count})!")

    async def collect_all():
        # High-level collector module collects nearby item entities
        collected = await bot.collector.collect(max_distance=32.0)
        if collected:
            await bot.chat("Successfully collected nearby item!")
        else:
            await bot.chat("No dropped items found within 32 blocks.")

    @bot.on("chat")
    async def on_chat(sender, message, *_rest):
        if sender == bot.username:
            return
        if message.strip() == "!collect":
            await collect_all()

    async with bot:
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
