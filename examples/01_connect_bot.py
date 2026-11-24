"""01 - Connecting a Bot.

Demonstrates connecting a Minecraft bot using Leafish:
- High-level ``Bot`` wrapper with Mineflayer-style API.
- Async context manager (``async with Bot(...) as bot:``) for automatic cleanup.
- Configurable host, port, username, and automatic version detection.
- Event listeners registered before start.
- Auto-reconnect with exponential back-off.

Usage:
    python examples/01_connect_bot.py [host] [port] [username]
"""

import asyncio
import sys

from leafish import Bot


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "LeafishBot"

    # Initialize the bot; handlers registered before start() are buffered.
    bot = Bot(
        host=host,
        port=port,
        username=username,
        auth="offline",
        version="auto",  # Automatically detects server protocol version
        auto_reconnect=True,  # Reconnect automatically if connection drops
        reconnect_delay=5.0,  # Exponential back-off starting at 5s
    )

    @bot.on("spawn")
    async def on_spawn():
        pos = bot.entity.position
        print(f"[*] Bot spawned at ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f})")
        print(f"[*] Game mode: {bot.game_mode}")
        print(f"[*] Server version: {bot.config.version}")
        await bot.chat("Hello from Leafish!")

    @bot.on("health")
    def on_health(health):
        print(f"[*] Health: {health:.1f} HP | Food: {bot.food} | Saturation: {bot.food_saturation}")

    @bot.on("end")
    def on_end(reason):
        print(f"[*] Disconnected: {reason}")

    # Use async context manager for robust lifecycle management
    async with bot:
        print(f"Connecting to {host}:{port} as '{username}'...")
        # Keep running until disconnected or interrupted
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
