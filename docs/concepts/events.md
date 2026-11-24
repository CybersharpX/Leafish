# Events

Leafish uses an async event emitter (`bot.on`, `bot.once`, `bot.off`,
`bot.emit`, `bot.wait_for`). Handlers may be sync or `async def`;
async handlers are scheduled as tasks and exceptions are isolated —
a broken handler emits an `error` event rather than crashing the bot.

## Subscribing

```python
@bot.on("spawn")
async def on_spawn():
    await bot.chat("I'm alive!")

bot.once("kicked", lambda reason: print("kicked:", reason))
bot.off("chat", handler)          # remove a specific handler
```

## Waiting

```python
await bot.wait_for("spawn", timeout=30)     # one-shot wait
await bot.wait_until_disconnected()          # resolve on disconnect
```

`bot.emit("my_event", payload)` lets plugins define custom events.

## Core events

Constants live in `leafish.events.events`; all are plain strings.

| Group | Events |
|---|---|
| Lifecycle | `connect`, `login`, `spawn`, `end`, `error`, `kicked`, `disconnect`, `reconnect` |
| Player | `chat`, `whisper`, `player_join`, `player_leave`, `player_updated` |
| World | `chunk_column_load`, `chunk_column_unload`, `block_update`, `block_entity_update`, `weather_update`, `time_update`, `game_state_change` |
| Entities | `entity_spawn`, `entity_update`, `entity_move`, `entity_destroy`, `entity_hurt`, `entity_equipment_update`, `entity_metadata_update` |
| Inventory | `inventory_update`, `window_open`, `window_close`, `held_item_changed`, `health`, `food`, `experience` |
| Movement | `move`, `forced_move`, `physics_tick`, `path_update` |
| Actions | `digging_started`, `digging_completed`, `digging_aborted`, `block_placed`, `item_crafted`, `item_collected` |

## Extended events

Beyond the core set the bot emits: `title`, `title_times`,
`title_clear`, `particle`, `world_particles`, `sound_effect_heard`,
`entity_sound_effect_heard`, `piston_move`, `note_heard`,
`chest_lid_move`, `block_break_progress_observed`/`_end`,
`entity_swing_arm`, `entity_hurt_animation`, `entity_damaged`,
`damage_event`, `death`, `death_combat_event`, `enter_combat`,
`end_combat`, `player_collect`, `item_collected`, `entity_attach`/
`attach_entity`, `mount`, `dismount`, `entity_passengers`,
`boss_bar_created`/`_updated`/`_deleted`,
`team_created`/`_removed`/`_updated`/`_member_added`/`_member_removed`,
`scoreboard_created`/`_deleted`/`_title_changed`/`_position`,
`score_updated`/`score_removed`, `trade_list`,
`villager_trade_list`, `window_property`, `cursor_item`, `tags`,
`open_book`, `map`, `chat_suggestions`, `update_view_distance`,
`declare_recipes`, `craft_recipe_response`, `creative_slot_set`.

## Chat patterns

`bot.add_chat_pattern(name, regex, chat_type="chat")` registers a
pattern whose matches are emitted as events; `bot.await_message(...)`
waits for chat matching a regex. Useful for detecting deaths,
advancements, and server messages:

```python
bot.add_chat_pattern("death", r"(\w+) (?:was|fell|drowned|burned).*", "chat")
bot.on("death", lambda m: print("died:", m))
```

## Disconnect cleanup

On `disconnect`/`end` the bot stops physics ticks, the pathfinder,
pvp loops, and pending tasks automatically.
