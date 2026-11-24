"""High-level Bot API demo — Mineflayer-style quickstart.

Shows the ``Bot`` convenience class: register events before connecting,
then call ``await bot.start()``.  The bot auto-reconnects on disconnect.

    python examples/bot_api_demo.py localhost 25565 LeafishBot
"""

import asyncio
import sys

from leafish import Bot


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "LeafishBot"

    # Create the bot instance; it isn't connected yet.
    bot = Bot(
        host=host,
        port=port,
        username=username,
        auth="offline",
        version="1.21.11",
        auto_reconnect=True,  # automatically reconnect on drop
        reconnect_delay=5.0,  # start with a 5 s delay, doubles each attempt
    )

    # Register events BEFORE start() — handlers are buffered and flushed once
    # the connection is established.

    @bot.on("spawn")
    async def on_spawn():
        pos = bot.entity.position  # transparent proxy to LeafishBot after start()
        print(f"[spawn] Bot spawned at {pos:.1f}")
        await bot.chat("Hello from Leafish!")

    @bot.on("chat")
    async def on_chat(username_sender, message, *_rest):
        if username_sender != bot.username:
            print(f"[chat] <{username_sender}> {message}")
            # Echo back to the sender.
            await bot.chat(f"echo: {message}")

    @bot.on("health")
    async def on_health(health):
        print(f"[health] HP={health:.1f} food={bot.food} oxygen={bot.oxygen_level}")

    @bot.on("end")
    def on_end(reason):
        print(f"[disconnect] {reason}")

    @bot.on("error")
    def on_error(event, handler_name, exc):
        print(f"[error] in handler {handler_name!r} for {event!r}: {exc}")

    # Connect and wait until done.
    print(f"Connecting to {host}:{port} as {username!r}…")
    await bot.start()

    try:
        await bot.wait_until_disconnected()
    except KeyboardInterrupt:
        print("Interrupted — stopping bot")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
