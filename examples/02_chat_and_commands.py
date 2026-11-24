"""02 - Sending and Receiving Chat.

Demonstrates communication in Leafish:
- Listening to general chat messages.
- Sending public chat, whispers (/msg), and server commands.
- Registering regular expression chat patterns.
- Team messaging support.

Usage:
    python examples/02_chat_and_commands.py [host] [port] [username]
"""

import asyncio
import sys

from leafish import Bot


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "ChattyBot"

    bot = Bot(host=host, port=port, username=username, auth="offline", version="auto")

    @bot.on("spawn")
    async def on_spawn():
        print(f"[*] {bot.username} joined! Type in Minecraft chat to interact.")
        await bot.chat("I am ready! Try saying '!help' or '!time'.")

    @bot.on("chat")
    async def on_chat(sender, message, *_rest):
        if sender == bot.username:
            return  # Ignore messages sent by ourselves

        print(f"[CHAT] <{sender}> {message}")

        # Command handling
        if message.startswith("!help"):
            await bot.chat(f"Hello {sender}! Commands: !help, !ping, !pos, !time")
        elif message.startswith("!ping"):
            diag = bot.diagnostics
            latency = bot.latency or "unknown"
            await bot.chat(
                f"Pong! Latency: {latency} ms | Uptime: {diag.get('uptime_seconds', 0)}s"
            )
        elif message.startswith("!pos"):
            p = bot.entity.position
            await bot.chat(f"Current position: ({p.x:.1f}, {p.y:.1f}, {p.z:.1f})")
        elif message.startswith("!time"):
            time_info = bot.time
            await bot.chat(f"World age: {time_info.age} ticks | Day time: {time_info.time_of_day}")

    @bot.on("chat:whisper")
    async def on_whisper(sender, text, match):
        author = match.group(1)
        body = match.group(2)
        print(f"[WHISPER] From {author}: {body}")
        await bot.chat_module.whisper(author, f"I received your whisper: '{body}'")

    async with bot:
        # Register regex chat patterns after bot starts
        bot.add_chat_pattern(
            name="whisper",
            pattern=r"^([a-zA-Z0-9_]+) whispers to you: (.+)$",
        )
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
