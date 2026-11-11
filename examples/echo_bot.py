"""Minimal Leafish bot: connect, say hello, echo chat back.

Run against any Java 1.21.11 server (offline mode works on servers with
online-mode=false):

    python examples/echo_bot.py localhost 25565 MyBot
"""

import asyncio
import sys

from leafish import Leafish


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "LeafishEcho"

    bot = await Leafish.create_bot(
        host=host, port=port, username=username, auth="offline",
        version="1.21.11",
    )

    @bot.on("spawn")
    async def on_spawn():
        assert bot.entity is not None
        print(f"Spawned at {bot.entity.position}")
        await bot.chat("Hello from Leafish!")

    @bot.on("chat")
    async def on_chat(username, message, *rest):
        print(f"<{username}> {message}")
        if username != bot.username:
            await bot.chat(f"echo: {message}")

    @bot.on("kicked")
    def on_kicked(reason):
        print("Kicked:", reason)

    try:
        await bot.wait_until_disconnected()
    except KeyboardInterrupt:
        pass
    finally:
        await bot.quit()


if __name__ == "__main__":
    asyncio.run(main())
