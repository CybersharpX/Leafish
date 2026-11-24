# LeafishBot API

`LeafishBot` is the central object — one per connected bot. Create
bots via `Leafish.create_bot(...)` or `Leafish.create_bots([...])`.
See [Configuration](../getting-started/configuration.md) for options.

## Connection & lifecycle

| Method | Description |
|---|---|
| `await bot.quit()` | Disconnect cleanly, stop background tasks. |
| `await bot.disconnect(reason=...)` | Disconnect without the quit semantics. |
| `await bot.respawn()` | Respawn after death. |
| `await bot.wait_for(event, timeout)` | Wait for an event once. |
| `await bot.wait_until_disconnected()` | Resolve when the connection drops. |
| `bot.on/once/off/emit` | Event subscription (see [Events](events.md)). |

Attributes: `bot.spawned`, `bot.entity` (own `Player`), `bot.username`,
`bot.uuid`, `bot.game`, `bot.current_window_id`, `bot.entity_id`,
`bot.server_brand`, `bot.game_mode`.

## Chat & commands

| Method | Description |
|---|---|
| `await bot.chat(msg)` | Send a chat message. |
| `await bot.command(cmd)` / `bot.chat_command(cmd)` | Slash command. |
| `await bot.tab_complete(text, assume_command=False)` | Request completions. |
| `bot.add_chat_pattern` / `add_chat_pattern_set` / `remove_chat_pattern` | Chat regex patterns → events. |
| `await bot.await_message(pattern, timeout=30)` | Wait for matching chat. |
| `bot.chat_module.whisper(user, msg)` | `/msg` via module. |

Incoming chat arrives as `chat`/`whisper` events — see the
[Chat guide](../guides/chat.md).

## Movement & look

| Method | Description |
|---|---|
| `await bot.set_control_state(state, on)` | `forward`/`back`/`left`/`right`/`jump`/`sneak`/`sprint`. |
| `bot.get_control_state(state)` / `await bot.clear_control_states()` | Control queries/reset. |
| `await bot.stop_moving()` | Release all controls. |
| `await bot.look(yaw, pitch)` | Set view angles (degrees). |
| `await bot.look_at(target)` | Look at a `Vec3`/`BlockPos`/entity. |
| `await bot.move_to(target, timeout)` | Straight-line walk. |
| `await bot.goto(goal, timeout)` | Pathfind (A*) + walk. |
| `bot.find_path(start, goal)` | Compute path without walking. |
| `bot.pathfinder.stop()` | Cancel in-progress `goto`. |
| `await bot.wait_for_ticks(n)` | Wait ~n server ticks. |
| `await bot.wait_for_chunks_to_load(timeout)` | Gate on chunk streaming. |
| `await bot.swing_arm()` | Arm-swing animation. |

See the [Movement guide](../guides/movement.md) and
[Pathfinder API](pathfinder.md).

## World queries

| Method | Description |
|---|---|
| `bot.world.block_at(pos)` | `Block` at position (`None` if unloaded). |
| `bot.world.find_block(s)(names, **kwargs)` | Search loaded chunks. |
| `bot.world.raycast(origin, dir, ...)` | Ray vs world → `(Block, RaycastHit)`. |
| `bot.block_at(pos)` / `find_block(s)` | Bot-level shortcuts. |
| `bot.can_dig_block(block)` | Reach/tool check. |
| `bot.dig_time(block_or_pos)` | Dig duration with held tool. |
| `bot.block_at_cursor(max_distance=5)` | Block under crosshair ray. |
| `bot.entity_at_cursor(max_distance=5)` | Entity under crosshair ray. |
| `bot.entity_at(position)` | Entity whose AABB contains point. |
| `bot.nearest_entity(pred, max_dist)` / `bot.find_entity(pred)` | Entity queries. |
| `bot.can_see_block(x)` / `bot.can_see_entity(e)` | Line-of-sight checks. |
| `bot.get_explosion_damages(entity, position, ...)` | Estimate explosion damage. |

See [World API](world.md) and [Entities API](entities.md).

## Actions

| Method | Description |
|---|---|
| `await bot.dig(block, force=False)` | Mine a block. |
| `await bot.stop_digging()` | Cancel digging. |
| `await bot.place_block(ref, face=None)` | Place held item. |
| `await bot.interact_block(block, face=None)` | Right-click block. |
| `await bot.activate_block(block, direction, cursor)` | Explicit face/cursor click. |
| `await bot.place_entity(entity, face=None)` | Place against entity. |
| `await bot.attack(entity)` | Single melee hit. |
| `await bot.use_on(entity, point=None)` | Interact with entity. |
| `await bot.activate_entity(e)` / `activate_entity_at(e, pos)` | Entity right-click variants. |
| `await bot.equip(item, destination)` | Move item to hand/armor. |
| `await bot.unequip(destination="hand")` | Remove equipment. |
| `await bot.use_item(hand=0)` | Use held item. |
| `await bot.consume()` | Eat/drink held item. |
| `await bot.activate_item(off_hand=False)` / `deactivate_item()` | Start/stop item use. |
| `bot.held_item` | Currently held `Item`. |

## Inventory & containers

| Method | Description |
|---|---|
| `bot.inventory.*` | Full inventory model (see [Inventory](inventory.md)). |
| `await bot.set_quick_bar_slot(i)` | Select hotbar slot 0-8. |
| `await bot.update_held_item()` | Re-announce held slot. |
| `await bot.click_window(wid, slot, button=0, mode=0)` | Raw window click. |
| `await bot.shift_click(wid, slot)` | Quick-move a slot. |
| `await bot.close_window(wid=None)` | Close window. |
| `await bot.deposit_all(wid, name=None)` | Inventory → container bulk. |
| `await bot.withdraw(wid, name, count=None)` | Container → inventory. |
| `await bot.open_container(block, timeout)` | Right-click + await window id. |
| `await bot.open_window(block, timeout)` | Typed `Window` view. |
| `bot.containers.window(wid)` | `WindowState`. |
| `bot.containers.window_view(wid)` | Typed `Window`. |
| `bot.current_window` | Currently open typed view. |
| `bot.simple_click.left_mouse/right_mouse(slot)` | Raw window-0 clicks. |
| `await bot.toss / toss_stack / move_slot_item / put_away / transfer / put_selected_item_range` | Inventory mutations. |

See the [Inventory & containers guide](../guides/inventory-containers.md)
and [Windows API](windows.md).

## Crafting, smelting & anvil

| Method | Description |
|---|---|
| `await bot.craft(name, count=1, crafting_table=False)` | Craft via 2×2 or table window. |
| `bot.recipes_for(name)` / `bot.find_recipe(...)` | Recipe lookup. |
| `bot.craftable_recipes()` / `bot.missing_ingredients(recipe)` / `bot.can_craft(recipe)` | Planning helpers. |
| `await bot.smelt(name, count=1, fuel=None, block=None, window_id=None, timeout=120)` | Furnace workflow. |
| `await bot.repair(item, material=None)` | Anvil repair/rename. |
| `await bot.open_furnace / open_enchantment_table / open_anvil / open_villager` | Typed window openers. |

See the [Crafting & smelting guide](../guides/crafting-smelting.md).

## Automation

| Method | Description |
|---|---|
| `await bot.collect(max_distance=8, count=None)` | Pick up nearby drops. |
| `await bot.fish(timeout=60)` | Cast and catch one fish. |
| `await bot.harvest(names=None, max_distance=32)` | Reap mature crops. |
| `await bot.plant(seed_name=None, max_distance=16)` | Plant seeds. |
| `await bot.tend_farm(names=None, max_distance=32)` | Harvest + replant. |
| `bot.pvp.start(target=None, **opts)` / `bot.pvp.stop()` | Combat loop. |
| `bot.farming.mature_crops()` | Ready-to-harvest blocks. |

## Player state & interaction

| Method | Description |
|---|---|
| `await bot.sleep(bed)` / `bot.wake()` / `bot.is_abed(bed=None)` | Bed sleep. |
| `await bot.elytra_fly()` | Deploy elytra. |
| `await bot.mount(entity)` / `bot.dismount()` / `bot.move_vehicle(l, f)` | Vehicles. |
| `await bot.update_sign(block, text, back=False, ...)` | Edit sign. |
| `await bot.write_book(hand, pages, ...)` | Write a book. |
| `await bot.set_command_block(pos, command, mode=0, ...)` | Edit command block. |
| `await bot.accept_resource_pack()` / `deny_resource_pack()` | Resource pack. |
| `bot.support_feature(name)` | Feature-flag query. |
| `bot.set_settings(options)` | Update client settings. |

## Plugins

```python
bot.load_plugin(plugin, name=None)
bot.load_plugins({"name": plugin})
bot.unload_plugin(name)
bot.has_plugin(name)
```

See the [Plugins guide](../concepts/plugins.md) and
[Plugins API](plugins.md).

## State properties

| Property | Description |
|---|---|
| `bot.health` / `bot.food` / `bot.food_saturation` / `bot.oxygen` | Vitals. |
| `bot.experience` | `ExperienceInfo`. |
| `bot.time` | `TimeInfo`. |
| `bot.game` | `GameInfo`. |
| `bot.abilities` | `AbilitiesInfo`. |
| `bot.weather` / `is_raining` / `rain_state` / `thunder_state` | Weather. |
| `bot.settings` | `SettingsInfo`. |
| `bot.physics_enabled` | Get/set physics toggle. |
| `bot.is_sleeping` / `bot.spawn_point` / `bot.tablist` / `bot.players` | Misc state. |
| `bot.scoreboards` / `bot.teams` / `bot.boss_bars` | Server state. |
| `bot.team_map` / `bot.scoreboard` | Sidebar shortcuts. |
| `bot.cursor_item` | Item on cursor. |
| `bot.quick_bar_slot` | Selected hotbar index. |
| `bot.target_dig_block` | Block being dug. |

See [State API](state.md) for the dataclass fields.

## Events

See [Events](events.md) for the canonical names and the full emitted
set.
