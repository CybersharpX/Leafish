"""10 - Creating Custom Plugins.

Demonstrates creating and loading plugins in Leafish:
- Using the ``@plugin`` decorator with metadata, names, and dependencies.
- Class-based plugins with ``inject(bot)`` and ``unload(bot)`` lifecycle hooks.
- Attaching custom properties and namespaces to the bot.
- Registering event listeners from within plugins.
- Isolated plugin state and graceful unloading.

Usage:
    python examples/10_custom_plugin.py [host] [port] [username]
"""

import asyncio
import sys

from leafish import Bot
from leafish.plugins import plugin

# ---------------------------------------------------------------------------
# Example 1: Function-based plugin with @plugin decorator
# ---------------------------------------------------------------------------


@plugin(name="auto_greeter")
def auto_greeter_plugin(bot):
    """Automatically greets players when they join the server."""

    @bot.on("player_join")
    async def on_player_join(player):
        if player.name and player.name != bot.username:
            print(f"[AutoGreeter] Player {player.name} joined the server.")
            await bot.chat(f"Welcome to the server, {player.name}!")


# ---------------------------------------------------------------------------
# Example 2: Class-based plugin with lifecycle and state
# ---------------------------------------------------------------------------


class SentryPlugin:
    """A guard plugin that monitors entity proximity and sounds an alarm."""

    def __init__(self, alert_radius: float = 8.0) -> None:
        self.alert_radius = alert_radius
        self.bot = None
        self._check_task = None

    def inject(self, bot) -> None:
        """Called when the plugin is loaded into the bot."""
        self.bot = bot
        # Attach custom sentry API directly onto the bot
        bot.sentry = self

        @bot.on("spawn")
        def on_spawn():
            self._start_scanning()

        @bot.on("end")
        def on_end(reason):
            self._stop_scanning()

        print("[SentryPlugin] Injected into bot!")

    def unload(self, bot) -> None:
        """Called when the plugin is unloaded."""
        self._stop_scanning()
        if hasattr(bot, "sentry"):
            delattr(bot, "sentry")
        print("[SentryPlugin] Unloaded.")

    def _start_scanning(self):
        if self._check_task is None or self._check_task.done():
            self._check_task = asyncio.create_task(self._scan_loop())

    def _stop_scanning(self):
        if self._check_task:
            self._check_task.cancel()
            self._check_task = None

    async def _scan_loop(self):
        while True:
            await asyncio.sleep(2.0)
            if not self.bot or not self.bot.entity:
                continue

            # Check for nearby hostile mobs
            hostile = self.bot.pvp.nearest_target(max_distance=self.alert_radius, hostile_only=True)
            if hostile:
                print(
                    f"[SENTRY ALERT] Hostile mob detected: {hostile.type} at {hostile.position:.1f}!"
                )
                await self.bot.chat(f"Alert! {hostile.type} nearby!")


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    username = sys.argv[3] if len(sys.argv) > 3 else "PluginBot"

    bot = Bot(host=host, port=port, username=username, auth="offline", version="auto")

    @bot.on("spawn")
    async def on_spawn():
        # Load plugins dynamically after starting or before starting
        bot.load_plugin(auto_greeter_plugin)
        bot.load_plugin(SentryPlugin(alert_radius=10.0))

        print(f"[*] {bot.username} loaded plugins: {bot.plugins.names}")
        await bot.chat("Plugins active: auto_greeter, sentry")

    async with bot:
        await bot.wait_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
