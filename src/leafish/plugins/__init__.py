"""Plugin system for Leafish bots.

A plugin is any callable ``plugin(bot)`` — typically a function that
attaches attributes, registers event handlers, or adds methods. Plugins
can also be objects exposing ``inject(bot)`` / ``unload(bot)``.

Example::

    def greet_plugin(bot):
        @bot.on("spawn")
        async def _greet():
            await bot.chat("Hello!")

    bot.load_plugin(greet_plugin)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..exceptions import PluginError

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.plugins")

Plugin = Callable[["LeafishBot"], Any]

__all__ = ["Plugin", "PluginManager"]


class PluginManager:
    """Tracks loaded plugins for one bot."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self._plugins: list[tuple[str, Any]] = []

    @property
    def plugins(self) -> list[str]:
        return [name for name, _ in self._plugins]

    def load(self, plugin: Plugin | Any, name: str | None = None) -> str:
        """Load *plugin* into the bot; returns the plugin name.

        *plugin* may be:
        - a callable ``fn(bot)``
        - an object with ``inject(bot)`` and optionally ``unload(bot)``
        """
        if name is None:
            name = getattr(plugin, "__name__", None) or \
                getattr(plugin, "name", None) or repr(plugin)
        try:
            inject = getattr(plugin, "inject", None)
            if callable(inject):
                inject(self.bot)
            elif callable(plugin):
                plugin(self.bot)
            else:
                raise PluginError(
                    f"Plugin {name!r} is neither callable nor has inject()"
                )
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(f"Plugin {name!r} failed to load: {exc}") from exc
        self._plugins.append((name, plugin))
        log.debug("Loaded plugin %r", name)
        self.bot.emit("plugin_loaded", name)
        return name

    def unload(self, name: str) -> bool:
        """Unload the plugin registered as *name*. Returns True if found."""
        for i, (pname, plugin) in enumerate(self._plugins):
            if pname == name:
                unload = getattr(plugin, "unload", None)
                if callable(unload):
                    try:
                        unload(self.bot)
                    except Exception:
                        log.exception("Plugin %r unload failed", name)
                del self._plugins[i]
                self.bot.emit("plugin_unloaded", name)
                return True
        return False
