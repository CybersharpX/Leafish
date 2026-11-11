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
bot.load_plugin(my_plugin)      # callable or object with inject()
bot.unload_plugin(my_plugin)
bot.emit_custom_event(...)      # via plugin manager
```
