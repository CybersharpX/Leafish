# Modules API

`LeafishBot` injects gameplay modules as attributes. Most bot methods
delegate to them; you can also call the modules directly for advanced
use.

| Attribute | Module | Highlights |
|---|---|---|
| `bot.world` | `World` | Chunk/block store, raycasts, light. |
| `bot.entities` | `EntityManager` | Entity tracking. |
| `bot.inventory` | `Inventory` | Slots, items, equipment. |
| `bot.physics` | `PhysicsEngine` | AABB collision, fluids, gravity. Toggle via `bot.physics_enabled`. |
| `bot.movement` | `MovementModule` | `look`, `look_at`, `set_control_state`, `move_to`. |
| `bot.vitals` | `HealthModule` | Health/food/XP packet updates. |
| `bot.chat_module` | `ChatModule` | `chat`, `command`, `whisper`, chat patterns, `await_message`. |
| `bot.actions` | `ActionsModule` | `dig`, `place_block`, `interact_block`, `attack`, `equip`, `use_item`, entity/block activation. |
| `bot.crafting` | `CraftingModule` | `craft`, `recipes_for`, `find_recipe`, `missing_ingredients`, `craftable_recipes`. |
| `bot.containers` | `ContainerModule` | Window state, clicks, `deposit_all`/`withdraw`, typed views. |
| `bot.anvil` | `AnvilModule` | `find_window`, `repair` helpers. |
| `bot.smelting` | `SmeltingModule` | `smelt`, `open_furnace_window`. |
| `bot.creative` | `CreativeModule` | `set_slot`, `give`, `clear`, `set_held_item`. |
| `bot.player` | `PlayerModule` | `respawn`, `sleep`/`wake`, `elytra_fly`, `mount`/`dismount`/`move_vehicle`. |
| `bot.client` | `ClientModule` | `tab_complete`, resource-pack responses, signs, books, command blocks, `support_feature`, `get_explosion_damages`. |
| `bot.pathfinder` | `Pathfinder` | `find_path`, `goto`, `stop`, `is_walkable`. |
| `bot.pvp` | `PVPModule` | `start`/`stop`/`attack`/`nearest_target`. |
| `bot.fishing` | `FishingModule` | `fish`, `reel_in`. |
| `bot.collector` | `CollectorModule` | `nearby_items`, `collect`. |
| `bot.farming` | `FarmingModule` | `mature_crops`, `harvest`, `plant`, `tend`. |
| `bot.simple_click` | `SimpleClick` | `left_mouse(slot)` / `right_mouse(slot)` on window 0. |
| `bot.plugins` | `PluginManager` | `load`, `unload`, `plugins`. |

## Notes

- Module methods raise domain exceptions (`DiggingError`,
  `CraftingError`, `InventoryError`, `PathfindingError`,
  `FishingError`) — see [Exceptions](exceptions.md).
- `bot.chat_module.whisper(user, msg)` is the module-level whisper;
  the bot-level `command`/`chat_command` cover slash commands.
- `bot.player.is_abed(bed_block=None)` checks sleep state.
