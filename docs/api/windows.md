# Windows API

A **window** is a container UI — chest, furnace, crafting table, anvil,
villager, horse, or the player's own inventory (window 0). Each open
window has a `WindowState` (slots + server state id) and a typed
`Window` view.

## WindowState

`bot.containers.window(wid)` returns the raw state:

| Member | Description |
|---|---|
| `window_id` | Protocol window id. |
| `title` | Decoded window title. |
| `slots` | `dict[int, Item]` — every non-empty slot. |
| `state_id` | Last server state id (send back on clicks). |
| `properties` | Crafting progress / furnace burn values. |
| `extras` | Type-specific data (trades, horse entity id, ...). |
| `player_offset` | Index where the 36 player slots begin. |
| `container_slots` / `player_slots` | `range` objects (properties, not callables). |
| `size` | Total slot count. |

## Window (typed views)

`bot.containers.window_view(wid)` / `bot.open_window(block)` /
`bot.current_window` return the most specific subclass:

| Class | Extras |
|---|---|
| `Window` | `item(slot)`, `item_name(slot)`, `slots`, `click`, `shift_click`, `deposit`, `withdraw`, `close`. |
| `FurnaceWindow` | `input_slot`/`fuel_slot`/`output_slot`, `input_item`/`fuel_item`/`output_item`, `burn_time`, `burn_time_total`, `cook_time`, `cook_time_total`, `progress`, `take_output()`. |
| `EnchantmentTableWindow` | `item_slot`/`lapis_slot`/`result_slot`, `offers`, `enchant(option)`. |
| `AnvilWindow` | `input_item`/`material_item`/`result_item`, `repair_cost`, `rename(text)`, `take_result()`. |
| `VillagerWindow` | `trades`, `villager_level`, `experience`, `is_regular_villager`, `can_restock`, `select_trade(i)`. |
| `HorseWindow` | `entity_id`, `slot_count`. |

Detection is title-based (`typed_window` in `windows.py`) — works
across versions where `inventoryType` ids differ.

## Opening windows

```python
await bot.open_container(block)                 # generic right-click
wid  = await bot.open_container(block)          # returns window id
view = await bot.open_window(block)             # typed view
furn = await bot.open_furnace(block)
ench = await bot.open_enchantment_table(block)
anvil = await bot.open_anvil(block)
vil  = await bot.open_villager(entity)
view = bot.current_window                       # currently open view
await view.close()
```

## Events

`window_open`, `window_close`, `window_property`, `cursor_item`.
