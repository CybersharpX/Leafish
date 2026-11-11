# LeafishBot API

`LeafishBot` is the central object — one per connected bot. Create
bots via `Leafish.create_bot(...)` or `Leafish.create_bots([...])`.

## Connection & lifecycle

| Method | Description |
|---|---|
| `await bot.quit()` | Disconnect cleanly. |
| `await bot.respawn()` | Respawn after death. |
| `await bot.wait_for(event, timeout)` | Wait for an event once. |
| `bot.on(event, fn)` / `bot.once(...)` / `bot.off(...)` | Event subscription. |

Attributes: `bot.spawned`, `bot.entity` (own `Player`), `bot.username`,
`bot.game` (version info), `bot.current_window_id`.

## Chat & commands

| Method | Description |
|---|---|
| `await bot.chat(msg)` | Send a chat message. |
| `await bot.chat_command(cmd)` | Send a slash command. |
| `await bot.whisper(user, msg)` / `bot.me(msg)` | `/msg`, `/me`. |
| `bot.on("chat", fn)` | Incoming chat: `(username, message)`. |

## Movement & look

| Method | Description |
|---|---|
| `await bot.set_control_state(state, on)` | `forward`/`back`/`left`/`right`/`jump`/`sneak`/`sprint`. |
| `await bot.stop_moving()` | Release all controls. |
| `await bot.look(yaw, pitch)` | Set view angles (degrees). |
| `await bot.look_at(point)` | Look at a `Vec3`/entity. |
| `await bot.goto(goal)` | Pathfind & walk to a `Vec3`/entity. |
| `await bot.find_path(goal)` | Compute an A* path without walking. |
| `bot.pathfinder.stop()` | Cancel an in-progress `goto`. |

## World

| Method | Description |
|---|---|
| `bot.world.block_at(pos)` | `Block` at a `Vec3`/`BlockPos`. |
| `bot.world.find_block(name, ...)` | Nearest matching block. |
| `bot.world.raycast(origin, direction, ...)` | Ray vs loaded world. |
| `bot.world.is_block_loaded(pos)` | Chunk presence check. |

## Actions

| Method | Description |
|---|---|
| `await bot.dig(block, force=False)` | Mine a block. |
| `await bot.stop_digging()` | Cancel digging. |
| `await bot.place_block(ref, face=None)` | Place held item. |
| `await bot.interact_block(block, face=None)` | Right-click (open chests, buttons). |
| `await bot.attack(entity)` | Single melee hit. |
| `await bot.equip(item_name, destination)` | Move item to hand/armor. |
| `bot.held_item` | Currently held `Item`. |

## Inventory & containers

| Method | Description |
|---|---|
| `bot.inventory.slots` / `.count(name)` / `.slot(i)` / `.held_item` | Inventory queries. |
| `await bot.set_quick_bar_slot(i)` | Select hotbar slot 0-8. |
| `await bot.click_window(wid, slot, button=0, mode=0)` | Raw window click. |
| `await bot.shift_click(wid, slot)` | Quick-move a slot. |
| `await bot.deposit_all(wid, name=None)` | Shift-click inventory → container. |
| `await bot.withdraw(wid, name, count=None)` | Shift-click container → inventory. |
| `await bot.close_window(wid=None)` | Close the current window. |
| `bot.containers.window(wid)` | `WindowState` with slots/state id. |

## Crafting

| Method | Description |
|---|---|
| `await bot.craft(name, count=1, crafting_table=False)` | Craft via 2×2 grid or open table window. |
| `bot.recipes_for(name)` | All recipe variants for an item. |
| `bot.craftable_recipes()` | Everything craftable right now. |
| `bot.missing_ingredients(recipe)` | Per-ingredient shortfall report. |
| `await bot.repair(item, material=None)` | Anvil repair/rename. |

## Automation

| Method | Description |
|---|---|
| `await bot.collect(max_distance=8, count=None)` | Pick up nearby item drops. |
| `await bot.fish(timeout=60)` | Cast and catch one fish. |
| `await bot.harvest(names=None, max_distance=32)` | Reap mature crops. |
| `await bot.plant(seed_name=None, max_distance=16)` | Plant seeds on farmland. |
| `await bot.tend_farm(names=None, max_distance=32)` | Harvest + replant. |
| `bot.pvp.start(target)` / `bot.pvp.stop()` | Combat loop. |

## Plugins

```python
from leafish.plugins import plugin

@plugin(name="greeter", dependencies=("chat",), overrides=())
def greeter(bot):
    @bot.on("chat")
    async def on_chat(user, msg):
        await bot.chat(f"hi {user}")

bot.load_plugin(greeter)
bot.unload_plugin("greeter")
```

`@plugin` metadata: `name`, `dependencies` (plugin names or callables,
auto-loaded first), `overrides` (existing `bot` attributes the plugin
intentionally replaces — undeclared replacements raise `PluginError`).

## State properties

| Property | Description |
|---|---|
| `bot.health` / `bot.food` / `bot.food_saturation` / `bot.oxygen` | Vitals (20 hp, 20 food). |
| `bot.experience` | `ExperienceInfo` (level, points, progress). |
| `bot.time` | `TimeInfo` (world age, day time, daylight cycle). |
| `bot.game` | `GameInfo` (mode, difficulty, brand, level type). |
| `bot.abilities` | `AbilitiesInfo` (flying, may-fly, instabuild). |
| `bot.weather` | `WeatherInfo` (raining, thunder). |
| `bot.settings` | `SettingsInfo` (view distance). |
| `bot.physics_enabled` | Get/set physics engine toggle. |
| `bot.is_sleeping` / `bot.spawn_point` / `bot.tablist` | Misc state. |
| `bot.scoreboards` / `bot.teams` / `bot.boss_bars` | Live server state. |
| `bot.team_map` / `bot.scoreboard` | Sidebar scoreboard shortcut. |
| `bot.cursor_item` | Item on the mouse cursor. |
| `bot.quick_bar_slot` | Currently selected hotbar index. |

## Interaction & items

| Method | Description |
|---|---|
| `await bot.use_item(hand=0)` | Use held item (bow, food, ...). |
| `await bot.consume()` | Eat/drink held item. |
| `await bot.activate_item(off_hand=False)` / `deactivate_item()` | Start/stop item use. |
| `await bot.use_on(entity, point=None, hand=0)` | Interact with an entity. |
| `await bot.activate_entity(entity)` / `activate_entity_at(entity, pos)` | Entity right-click variants. |
| `await bot.activate_block(block, direction, cursor)` | Block right-click with explicit face/cursor. |
| `await bot.place_entity(entity, face=None)` | Place block against entity. |
| `await bot.respawn()` / `sleep(bed)` / `wake()` / `is_abed` | Player-state actions. |
| `await bot.elytra_fly()` | Deploy elytra. |
| `await bot.mount(entity)` / `dismount()` / `move_vehicle(l, f)` | Vehicles. |
| `await bot.update_sign(pos, side, line, text)` | Edit a sign. |
| `await bot.write_book(pages)` | Write a written book. |
| `await bot.tab_complete(text)` | Request tab-completion. |
| `await bot.accept_resource_pack()` / `deny_resource_pack()` | Resource-pack handshake. |
| `await bot.update_held_item(slot)` | Select hotbar slot (alias of `set_quick_bar_slot`). |
| `await bot.set_command_block(pos, command)` | Edit a command block. |
| `await bot.support_feature(feature)` | Answer a server feature-flags query. |

## Typed windows

`await bot.open_window(block)` returns a typed view —
`FurnaceWindow`, `EnchantmentTableWindow`, `AnvilWindow`,
`VillagerWindow`, `HorseWindow` or generic `Window`.
Convenience wrappers: `open_furnace`, `open_enchantment_table`,
`open_anvil`, `open_villager`. `bot.current_window` returns the typed
view of the open window.

All windows support `item(slot)`, `item_name(slot)`, `click`,
`shift_click`, `deposit(name, count)`, `withdraw(name, count)`, `close`.

| Class | Extras |
|---|---|
| `FurnaceWindow` | `input_item`/`fuel_item`/`output_item`, `burn_time`, `cook_time`, `progress`, `take_output()` |
| `EnchantmentTableWindow` | `item_slot`/`lapis_slot`/`result_slot`, `enchant(option)` |
| `AnvilWindow` | `input_item`/`material_item`/`result_item`, `repair_cost`, `rename(text)` |
| `VillagerWindow` | `trades`, `villager_level`, `select_trade(i)` |
| `HorseWindow` | `entity_id`, `slot_count` |

## Creative mode

`bot.creative` namespace (server must be in creative):

| Method | Description |
|---|---|
| `await bot.creative.set_slot(slot, item, count=1)` | Set a player-inventory slot. |
| `await bot.creative.give(name, count=1, slot=None)` | Give an item to an empty slot. |
| `await bot.creative.clear(slot)` | Empty a slot. |
| `await bot.creative.set_held_item(name, count=1)` | Give + select in hotbar. |

## Pathfinder goals

```python
from leafish.pathfinder import GoalNear, GoalFollow, GoalComposite

await bot.pathfinder.goto(GoalNear(100, 64, 100, range=2))
await bot.pathfinder.goto(GoalFollow(target_entity, range=3))
```

Goals: `GoalBlock`, `GoalNear`, `GoalXZ`/`GoalNearXZ`, `GoalY`,
`GoalGetToBlock`, `GoalLookAtBlock`, `GoalFollow`/`GoalFollowEntity`,
`GoalComposite`, `GoalInvert`. Positions and tuples still work — they
are coerced to `GoalBlock`. Dynamic goals (e.g. `GoalFollow`) replan
automatically as the target moves.

## Events

Beyond the core events, the bot emits: `title`, `title_times`,
`title_clear`, `particle`, `world_particles`, `sound_effect_heard`,
`entity_sound_effect_heard`, `piston_move`, `note_heard`,
`chest_lid_move`, `block_break_progress_observed`/`_end`,
`entity_swing_arm`, `entity_hurt`/`entity_hurt_animation`,
`entity_damaged`, `damage_event`, `death`, `death_combat_event`,
`enter_combat`, `end_combat`, `player_collect`, `item_collected`,
`entity_attach`/`attach_entity`, `mount`, `dismount`,
`entity_passengers`, `boss_bar_created`/`_updated`/`_deleted`,
`team_created`/`_removed`/`_updated`/`_member_added`/`_member_removed`,
`scoreboard_created`/`_deleted`/`_title_changed`/`_position`,
`score_updated`/`score_removed`, `trade_list`,
`villager_trade_list`, `window_property`, `cursor_item`, `tags`,
`open_book`, `map`, `chat_suggestions`, `update_view_distance`,
`declare_recipes`, `craft_recipe_response`, `creative_slot_set`.
