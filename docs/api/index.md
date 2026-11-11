# API Reference

Leafish's public surface is centered on `LeafishBot` (one instance per
connected bot) and the `Leafish` factory class.

## Core

- `Leafish.create_bot` / `Leafish.create_bots` — factory methods.
- [`LeafishBot`](bot.md) — connection, chat, movement, events.

## Modules (bot attributes)

| Attribute | Module | Purpose |
|---|---|---|
| `bot.world` | World | chunks, blocks, raycasts |
| `bot.entities` | EntityManager | entity tracking & queries |
| `bot.inventory` | Inventory | slots, items, equipment |
| `bot.physics` | PhysicsEngine | collision, gravity, fluids |
| `bot.movement` | MovementModule | control states |
| `bot.health` | HealthModule | health/hunger/XP |
| `bot.crafting` | CraftingModule | recipes & crafting |
| `bot.containers` | ContainerModule | windows & clicks |
| `bot.anvil` | AnvilModule | anvil repair/rename |
| `bot.pathfinder` | Pathfinder | A* pathfinding |
| `bot.actions` | ActionsModule | dig/place/attack/equip |
| `bot.pvp` | PVPModule | combat loop |
| `bot.fishing` | FishingModule | `bot.fish()` |
| `bot.collector` | CollectorModule | `bot.collect()` |
| `bot.farming` | FarmingModule | harvest/plant/tend |
| `bot.plugins` | PluginManager | plugin lifecycle |

## Events

`LeafishBot` is an async event emitter (`on`/`once`/`emit`). Notable
events: `spawn`, `chat`, `health`, `death`, `kicked`, `end`, `window_open`,
`window_close`, `inventory_update`, `entity_spawn`, `entity_removed`,
`block_update`, `crafted`, `block_place`, `block_interact`.
