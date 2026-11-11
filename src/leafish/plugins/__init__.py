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

__all__ = ["Plugin", "PluginManager", "plugin"]


def plugin(name: str | None = None, *,
           dependencies: tuple | list = (),
           overrides: tuple | list = ()):
    """Decorator marking a callable as a Leafish plugin.

    Attaches ``{name, dependencies}`` metadata that
    :meth:`PluginManager.load` uses for naming and dependency checks::

        @plugin(name="greeter", dependencies=("chat",))
        def greeter(bot):
            @bot.on("chat")
            async def on_chat(user, msg):
                await bot.chat(f"hi {user}")

    Dependencies may be plugin names (must already be loaded) or
    plugin callables (loaded automatically first). *overrides* lists
    existing ``bot`` attribute names the plugin intentionally replaces;
    undeclared replacements raise :class:`PluginError`.
    """

    def decorator(fn):
        fn._leafish_plugin = {
            "name": name or getattr(fn, "__name__", None) or repr(fn),
            "dependencies": tuple(dependencies),
            "overrides": tuple(overrides),
        }
        return fn

    return decorator


class PluginManager:
    """Tracks loaded plugins for one bot."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self._plugins: list[tuple[str, Any]] = []

    @property
    def plugins(self) -> list[str]:
        return [name for name, _ in self._plugins]

    def _meta(self, plugin: Any) -> dict:
        return getattr(plugin, "_leafish_plugin", None) or {}

    def _resolve_dependencies(self, plugin: Any, name: str) -> None:
        """Ensure declared dependencies are loaded before *plugin*."""
        for dep in self._meta(plugin).get("dependencies", ()):
            if callable(dep) and not isinstance(dep, str):
                dep_name = getattr(dep, "__name__", repr(dep))
                if dep_name not in self.plugins:
                    self.load(dep, name=dep_name)
                continue
            if dep not in self.plugins:
                raise PluginError(
                    f"Plugin {name!r} depends on {dep!r}, which is not loaded"
                )

    def load(self, plugin: Plugin | Any, name: str | None = None) -> str:
        """Load *plugin* into the bot; returns the plugin name.

        *plugin* may be:
        - a callable ``fn(bot)``
        - an object with ``inject(bot)`` and optionally ``unload(bot)``
        - a callable decorated with :func:`plugin`
        """
        meta = self._meta(plugin)
        if name is None:
            name = meta.get("name") or getattr(plugin, "__name__", None) or \
                getattr(plugin, "name", None) or repr(plugin)
        self._resolve_dependencies(plugin, name)
        before = self._snapshot_bot(plugin)
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
        self._check_overrides(name, plugin, before)
        self._plugins.append((name, plugin))
        log.debug("Loaded plugin %r", name)
        self.bot.emit("plugin_loaded", name)
        return name

    def _snapshot_bot(self, plugin: Any) -> dict[str, Any]:
        """Snapshot callable attributes a plugin might replace."""
        snap: dict[str, Any] = {}
        for attr in dir(self.bot):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(self.bot, attr)
            except Exception:
                continue
            if callable(value):
                snap[attr] = value
        return snap

    def _check_overrides(self, name: str, plugin: Any,
                         before: dict[str, Any]) -> None:
        """Reject undeclared replacement of existing bot methods."""
        allowed = set(self._meta(plugin).get("overrides", ()))
        replaced = []
        for attr, old in before.items():
            try:
                new = getattr(self.bot, attr)
            except Exception:
                continue
            # Bound methods are re-created per access; compare the
            # underlying function to detect real replacement.
            old_core = getattr(old, "__func__", old)
            new_core = getattr(new, "__func__", new)
            if callable(new) and new_core is not old_core \
                    and attr not in allowed:
                replaced.append(attr)
        if replaced:
            raise PluginError(
                f"Plugin {name!r} replaced bot attributes without declaring "
                f"them in overrides=(): {sorted(replaced)}"
            )

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
