# Configuration

`Leafish.create_bot` accepts a fixed set of keyword arguments that map
onto `leafish.config.BotConfig`:

```python
bot = await Leafish.create_bot(
    host="play.example.com",      # hostname or IP
    port=25565,                   # server port
    username="LeafishBot",        # offline-mode name / MS override
    auth="offline",               # "offline" | "microsoft"
    version="auto",               # "auto" | "latest" | version string
    brand="Leafish",              # client brand string
    view_distance=10,             # requested view distance (chunks)
    timeout=30.0,                 # connect timeout (seconds)
    auto_respond_keepalive=True,  # answer keepalives automatically
    token_cache_path=Path(...),   # MS token cache location
    plugins={"name": callable},   # plugins loaded after connect
    # ...any other BotConfig field via **kwargs
)
```

Unknown kwargs are silently dropped — only fields declared on
`BotConfig` are honored, so typos won't fail loudly. Prefer passing
explicit keywords.

## BotConfig fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `host` | `str` | `"localhost"` | Server hostname or IP. |
| `port` | `int` | `25565` | `DEFAULT_PORT`. |
| `username` | `str` | `"LeafishBot"` | Overridden by Microsoft profile name. |
| `auth` | `"offline" \| "microsoft"` | `"offline"` | |
| `version` | `str` | `"auto"` | `"auto"` detects via status ping; `"latest"` or a version string also accepted. See [Versions & data](../concepts/versions-and-data.md). |
| `brand` | `str` | `"Leafish"` | Sent in client-information packet. |
| `view_distance` | `int` | `10` | Chunk view distance requested. |
| `timeout` | `float` | `30.0` | Connect/auth timeout. |
| `auto_respond_keepalive` | `bool` | `True` | Disable to handle keepalives manually. |
| `token_cache_path` | `Path` | `~/.leafish/` | Microsoft token cache. |
| `options` | `dict` | `{}` | Passthrough protocol options. |

## Runtime settings

Some server-facing settings can be changed after connect:

```python
bot.set_settings({"view_distance": 12, "particle_status": "decreased"})
bot.set_command_block(pos, "say hi", mode=1)   # redstone/chain/ repeating
```

See `SettingsInfo` in the [state reference](../api/state.md) for the
full settings surface.
