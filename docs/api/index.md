# API reference

Leafish's public surface is centered on `LeafishBot` — one instance
per connected bot. Most gameplay methods delegate to injected module
objects, so the namespace mirrors Mineflayer's (`bot.pvp`,
`bot.pathfinder`, `bot.creative`, ...).

## Core

| Page | Contents |
|---|---|
| [LeafishBot](bot.md) | Lifecycle, chat, movement, actions, automation — the main API. |
| [World](world.md) | `World`, `Chunk`, `Block` — block queries, raycasts, light. |
| [Entities](entities.md) | `Entity` hierarchy, `EntityManager`, bounding boxes. |
| [Inventory](inventory.md) | `Item`, `Inventory`, slot model. |
| [Windows](windows.md) | `Window`/`WindowState` + typed views (furnace, anvil, enchanting, villager, horse). |
| [Pathfinder](pathfinder.md) | `Pathfinder` + the `leafish.pathfinder.goals` package. |
| [Modules](modules.md) | Module namespaces attached to the bot. |
| [State](state.md) | `GameInfo`, `TimeInfo`, `ExperienceInfo`, `AbilitiesInfo`, `WeatherInfo`, `SettingsInfo`, scoreboard/team/boss-bar models. |
| [Plugins](plugins.md) | `@plugin` decorator, `PluginManager`, plugin protocol. |
| [Authentication](auth.md) | `AuthSession`, `OfflineAuth`, `MicrosoftAuth`. |
| [Game data](gamedata.md) | `GameData` registry, `get_gamedata`, version helpers. |
| [Events](events.md) | Emitter API + canonical event names. |
| [Exceptions](exceptions.md) | Error hierarchy. |
| [Utilities](utils.md) | `Vec3`/`Vec2`/`BlockPos`, `BoundingBox`, NBT, math helpers. |
