# Events API

## EventEmitter

`bot.emitter` is an `EventEmitter`; the same API is delegated on the
bot (`bot.on`, `bot.once`, `bot.off`, `bot.emit`, `bot.wait_for`).

```python
bot.on(event, handler=None)          # subscribe; returns handler
bot.once(event, handler=None)        # one-shot
bot.off(event, handler=None)         # unsubscribe
bot.emit(event, *args, **kwargs)     # fire synchronously
bot.emit_async(event, *args, **kw)   # await all async handlers
bot.listeners(event)                 # list of handlers
await bot.wait_for(event, timeout)   # one-shot wait -> result
bot.wait_for_nowait(event)           # returns asyncio.Future
```

Handlers may be sync or `async def`; async handlers are scheduled as
tasks with error isolation — a raising handler emits `error` instead
of propagating.

## Canonical event names

`leafish.events.events` exports string constants — use them for
autocomplete, though plain strings work identically.

| Group | Constants |
|---|---|
| Lifecycle | `CONNECT`, `LOGIN`, `SPAWN`, `END`, `ERROR`, `KICKED`, `DISCONNECT`, `RECONNECT` |
| Player | `CHAT`, `WHISPER`, `PLAYER_JOIN`, `PLAYER_LEAVE`, `PLAYER_UPDATED` |
| World | `CHUNK_COLUMN_LOAD`, `CHUNK_COLUMN_UNLOAD`, `BLOCK_UPDATE`, `BLOCK_ENTITY_UPDATE`, `WEATHER_UPDATE`, `TIME_UPDATE`, `GAME_STATE_CHANGE` |
| Entities | `ENTITY_SPAWN`, `ENTITY_UPDATE`, `ENTITY_MOVE`, `ENTITY_DESTROY`, `ENTITY_HURT`, `ENTITY_EQUIPMENT_UPDATE`, `ENTITY_METADATA_UPDATE` |
| Inventory | `INVENTORY_UPDATE`, `WINDOW_OPEN`, `WINDOW_CLOSE`, `HELD_ITEM_CHANGED`, `HEALTH`, `FOOD`, `EXPERIENCE` |
| Movement | `MOVE`, `FORCED_MOVE`, `PHYSICS_TICK`, `PATH_UPDATE` |
| Actions | `DIGGING_STARTED`, `DIGGING_COMPLETED`, `DIGGING_ABORTED`, `BLOCK_PLACED`, `ITEM_CRAFTED`, `ITEM_COLLECTED` |

Plus the extended set documented in [Events](../concepts/events.md).
