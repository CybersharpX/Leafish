# Plugins

Plugins are the extension mechanism — the same model Mineflayer uses.
A plugin is any callable `plugin(bot)` that attaches state, handlers,
or methods to the bot.

## Writing a plugin

```python
# my_plugin.py
def auto_rejoin(bot):
    @bot.on("kicked")
    async def on_kick(reason):
        # schedule a reconnect however you like
        print("kicked:", reason)

    bot.auto_rejoin = True   # plugins may add attributes
```

Load it after connecting:

```python
bot = await Leafish.create_bot(..., plugins={"auto_rejoin": auto_rejoin})
# or later:
bot.load_plugin(auto_rejoin, name="auto_rejoin")
bot.unload_plugin("auto_rejoin")
bot.has_plugin("auto_rejoin")     # True
```

## The `@plugin` decorator

`leafish.plugins.plugin` attaches metadata used by `PluginManager`:

```python
from leafish.plugins import plugin

@plugin(name="greeter", dependencies=("chat",), overrides=())
def greeter(bot):
    @bot.on("spawn")
    async def _greet():
        await bot.chat("hi")

bot.load_plugin(greeter)
```

| Option | Meaning |
|---|---|
| `name` | Registry name (defaults to the function's `__name__`). |
| `dependencies` | Plugin names or callables loaded first, recursively. |
| `overrides` | Names of existing `bot` attributes the plugin may replace. Any other shadowing raises `PluginError`. |

`load_plugins(dict)` bulk-loads a name → plugin mapping.

## Plugin objects

Anything with `inject(bot)` / `unload(bot)` methods also works:

```python
class MyPlugin:
    def inject(self, bot): ...
    def unload(self, bot): ...

bot.load_plugin(MyPlugin())
```

## Rules

- Plugin exceptions during load propagate as `PluginError` (or the
  original error).
- `unload` restores the bot attributes snapshotted at load time and
  removes handlers the plugin registered — provided the plugin didn't
  declare overrides.
- Keep plugins idempotent: `load_plugin` on an already-loaded name is
  a no-op unless you `unload` first.
