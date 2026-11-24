# Plugins API

## `@plugin` decorator

```python
from leafish.plugins import plugin

@plugin(name="greeter", dependencies=("chat",), overrides=())
def greeter(bot): ...
```

Attaches `_leafish_plugin` metadata consumed by `PluginManager`.
See the [Plugins guide](../concepts/plugins.md) for full semantics.

## PluginManager

`bot.plugins` (also reachable via `bot.load_plugin` /
`bot.unload_plugin` / `bot.has_plugin` / `bot.load_plugins`):

| Method | Description |
|---|---|
| `load(plugin, name=None)` | Load a plugin; resolves `@plugin` metadata and dependencies. Returns the registered name. |
| `unload(name)` | Unload and restore snapshotted bot attributes. Returns `True` if it was loaded. |
| `plugins` | List of loaded plugin names. |

### Plugin protocol

A plugin is any of:

- a callable `fn(bot)`;
- an object with `inject(bot)` / `unload(bot)`;
- a `@plugin`-decorated callable.

### Override protection

At load time the manager snapshots every `bot` attribute. On unload it
restores them — unless the plugin declared the name in `overrides`,
in which case the plugin's version wins permanently. Undeclared
shadowing raises `PluginError`.

### Dependencies

`dependencies` entries may be plugin names (strings) or callables;
they're resolved and loaded before the dependent plugin, recursively.
Circular dependencies raise `PluginError`.
