# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project scaffolding: packaging, lint/type/test tooling, docs skeleton.
- Core exception hierarchy, configuration, vector/math/NBT utilities.
- Async event emitter with async handler support and error isolation.
- Protocol stack: packet framing, compression, AES/CFB8 encryption,
  ProtoDef serialization via `protolib`, full state machine
  (handshaking/status/login/configuration/play).
- Authentication: offline mode + Microsoft device-code/OAuth/Xbox Live/XSTS
  flow.
- Vendored minecraft-data for Java 1.21.11 (protocol 774) and version registry.
- `LeafishBot`: connect/spawn/chat/movement/health, entity tracking,
  inventory model, world model, physics engine.
- World: chunk column/section decoding with palette containers
  (single/indirect/direct), block search, raycast, block updates.
- Actions: digging, block placement, attack, equip.
- Physics: AABB collision, ground detection, fluid movement.
- Pathfinder: A* with step-ups and `goto` execution.
- Crafting: shaped/shapeless recipes via 2x2 grid clicks; fake server
  gained an inventory model and minimal recipe matching.
- Combat (`bot.pvp`), fishing (`bot.fish`), item collection
  (`bot.collect`), farming (`bot.harvest`/`plant`/`tend_farm`).
- Plugins (`bot.load_plugin`), `Leafish.create_bots`, examples,
  disconnect cleanup for physics.
- Container windows: `bot.open_window`/`close_window`/`shift_click`/
  `window_click` with per-window slot stores, `windows.json` layouts,
  and fake-server shift-click simulation.
- Crafting tables: 3x3 recipes (e.g. diamond_pickaxe) craft inside an
  open crafting-table window via `bot.craft(..., crafting_table=True)`.
- Container helpers (`bot.deposit_all`/`bot.withdraw`) and anvil repair
  (`bot.repair`) with fake-server anvil simulation.
- Fake protocol server + end-to-end integration tests.
- `tools/fetch_mcdata.py` for vendoring minecraft-data JSON.
- Complete interaction surface: `use_item`, `consume`,
  `activate_item`/`deactivate_item`, entity/block interactions,
  signs, books, tab-complete, resource packs, respawn, sleep/wake,
  elytra, mount/dismount/vehicle steering.
- Bot state objects & properties: game info, abilities, world time,
  experience, weather, settings, physics toggle, scoreboard/team/
  boss-bar collections.
- Typed windows (`bot.open_window` → `FurnaceWindow`,
  `EnchantmentTableWindow`, `AnvilWindow`, `VillagerWindow`,
  `HorseWindow`) with progress/trade/rename APIs.
- `bot.creative` namespace for creative-mode inventory ops.
- `leafish.pathfinder` goals package (`GoalNear`, `GoalFollow`,
  `GoalComposite`, ...) with dynamic-goal replanning.
- `@plugin` decorator with dependencies and override protection.
- New packet handlers: boss bars, teams, scoreboards, titles,
  particles, sounds, vehicles, block actions, item pickup, combat
  events, window properties, trades, horse windows.
- Chunk light accessors (`world.light_at`), entity bounding boxes,
  tool-aware dig times.
- Fixed: `Particle` data switch missing `default: void` in vendored
  protocol data (broke particle encode/decode).
