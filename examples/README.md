# Leafish Examples

Runnable, production-quality example bots illustrating every core capability of the Leafish framework.

Each script supports optional command-line arguments `[host] [port] [username]`, connects to any Java edition server (with automatic version negotiation from 1.8 through 26.1), and uses modern Python async patterns.

| Script | Category | Demonstrates |
|---|---|---|
| [`01_connect_bot.py`](01_connect_bot.py) | **Connection & Lifecycle** | Mineflayer-style `Bot` API, `async with` context manager, auto-reconnect, and protocol auto-detection |
| [`02_chat_and_commands.py`](02_chat_and_commands.py) | **Communication** | Sending/receiving public chat, whispers (`/msg`), commands, and regex pattern matching |
| [`03_follow_player.py`](03_follow_player.py) | **Navigation** | Tracking players, `bot.nearest_player()`, and dynamic A* pathfinding via `GoalFollow` |
| [`04_collect_resources.py`](04_collect_resources.py) | **Items & Entities** | Scanning for dropped `ItemEntity`s, navigating to them, and tracking item pickup events |
| [`05_mining_blocks.py`](05_mining_blocks.py) | **World & Mining** | Multi-state block queries (`find_blocks`), auto tool selection (tier-based), and mining execution |
| [`06_crafting_items.py`](06_crafting_items.py) | **Crafting** | 2×2 inventory crafting and 3×3 crafting table windows with automated slot synchronization |
| [`07_building_structures.py`](07_building_structures.py) | **Building** | `ConstructionPlan` (walls, platforms, boxes), material validation, ground-up placement ordering |
| [`08_navigating_coordinates.py`](08_navigating_coordinates.py) | **Pathfinding** | A* coordinates navigation (`GoalBlock`, `GoalNear`, `GoalXZ`), obstacle evasion, swimming & ladder climbing |
| [`09_inventory_management.py`](09_inventory_management.py) | **Inventory** | Slot management, equipping armor and tools, item tossing, and opening/transferring chest containers |
| [`10_custom_plugin.py`](10_custom_plugin.py) | **Extensibility** | `@plugin` decorator, class-based plugins with `inject`/`unload` hooks, custom namespaces, and events |

## Running the Examples

Ensure Leafish is installed in your Python environment:

```bash
pip install -e .
```

Run any example script against a local or remote Minecraft server:

```bash
python examples/01_connect_bot.py localhost 25565 MyBot
python examples/05_mining_blocks.py localhost 25565 Miner iron_ore
python examples/07_building_structures.py localhost 25565 Builder
python examples/08_navigating_coordinates.py localhost 25565 Navigator 100 64 200
```
