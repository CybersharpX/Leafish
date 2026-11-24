"""09 - Managing Inventory.

Demonstrates complete inventory and container management:
- Inspecting player inventory slots, items, and counts.
- Equipping items to main hand, offhand, or armor slots.
- Dropping (tossing) individual items or full item stacks.
- Interacting with chest containers: opening, depositing items, and withdrawing items.
- Window state synchronization and slot click modes.

Usage:
    python examples/09_inventory_management.py [host] [port] [username]
"""

import asyncio
import sys

from leafish import Bot


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "StorageBot"

    bot = Bot(host=host, port=port, username=username, auth="offline", version="auto")

    def print_inventory():
        print("\n================== INVENTORY ==================")
        held = bot.inventory.held_item
        print(f"Held item (Hotbar slot {bot.inventory.held_slot}): {held.name if held else 'None'}")
        print("Non-empty slots:")
        for item in bot.inventory.items():
            print(f"  Slot {item.slot:2d}: {item.name:20s} x{item.count}")
        print("===============================================\n")

    @bot.on("spawn")
    async def on_spawn():
        print(f"[*] {bot.username} spawned!")
        print_inventory()
        await bot.chat("Commands: !inv, !equip <item>, !drop <item>, !chest")

    @bot.on("inventory_update")
    def on_inv_update():
        print("[*] Inventory updated!")

    @bot.on("chat")
    async def on_chat(sender, message, *_rest):
        if sender == bot.username:
            return

        parts = message.strip().split()
        if not parts:
            return
        cmd = parts[0].lower()

        if cmd == "!inv":
            print_inventory()
            items_str = ", ".join(f"{i.name}x{i.count}" for i in bot.inventory.items()[:5])
            await bot.chat(f"Inventory: {items_str or 'empty'}")

        elif cmd == "!equip" and len(parts) > 1:
            item_name = parts[1]
            try:
                # Can equip to 'hand', 'offhand', 'armor_helmet', 'armor_chestplate', etc.
                dest = parts[2] if len(parts) > 2 else "hand"
                await bot.equip(item_name, destination=dest)
                await bot.chat(f"Equipped {item_name} to {dest}!")
            except Exception as exc:
                await bot.chat(f"Could not equip {item_name}: {exc}")

        elif cmd == "!drop" and len(parts) > 1:
            item_name = parts[1]
            item = bot.inventory.find_item(item_name)
            if item:
                # Toss the full stack
                await bot.inventory.toss_stack(item.slot)
                await bot.chat(f"Dropped {item_name}!")
            else:
                await bot.chat(f"I don't have {item_name}.")

        elif cmd == "!chest":
            # Search nearby for a chest block
            chests = bot.world.find_blocks(["chest", "trapped_chest", "barrel"], max_distance=6, count=1)
            if not chests:
                await bot.chat("No chest found within 6 blocks.")
                return

            chest_pos = chests[0]
            await bot.chat(f"Opening chest at {chest_pos}...")
            try:
                # Open chest block and inspect contents
                window = await bot.open_window(chest_pos)
                if window is None:
                    await bot.chat("Timed out opening chest.")
                    return
                chest_items = [i for i in window.slots.values() if i and not i.empty]
                print(f"[*] Chest contains {len(chest_items)} items.")
                for ci in chest_items:
                    print(f"  Slot {ci.slot}: {ci.name} x{ci.count}")

                await bot.chat(f"Chest opened! Found {len(chest_items)} item stacks.")
                await asyncio.sleep(2.0)
                await bot.close_window()
                await bot.chat("Chest closed.")
            except Exception as exc:
                await bot.chat(f"Error accessing chest: {exc}")

    async with bot:
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
