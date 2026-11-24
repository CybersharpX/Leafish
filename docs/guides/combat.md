# Combat & PvP

## Single attacks

```python
await bot.attack(entity)         # one melee hit + arm swing
await bot.use_on(entity)         # right-click interact (boats, nametags)
await bot.activate_entity(entity)
await bot.activate_entity_at(entity, position)
```

The server enforces attack cooldowns and reach; Leafish sends the
attack packet and lets the server decide damage.

## PvP loop

`bot.pvp` runs a background combat loop:

```python
bot.pvp.start()                              # auto-target hostiles
bot.pvp.start(target_entity)                 # focus one entity
bot.pvp.start(target, max_distance=6, reachable=True)
bot.pvp.stop()
bot.pvp.nearest_target(max_distance=16)      # manual target pick
bot.pvp.attack(target)                       # single hit via module
```

The loop approaches via the pathfinder (`GoalNear`-style), attacks on
cooldown, and retargets when the current target dies or leaves range.
`pvp.start` accepts predicate options to filter targets (hostile-only,
players-only, custom callable).

## Defense

- `bot.health` / `bot.food` / `bot.oxygen` expose vitals — watch them
  in your own loop or via `health`/`food` events.
- `bot.is_sleeping`, `bot.experience` for status.
- Damage arrives as `entity_hurt`, `damage_event`, `death`,
  `death_combat_event` events.

## Vehicles

```python
await bot.mount(entity)              # horse, boat, minecart
await bot.dismount()
await bot.move_vehicle(left=-1.0, forward=1.0)
entity.passengers / entity.vehicle   # relationship queries
```

`HorseWindow` (saddle/armor slots) opens via `bot.open_window` when
you right-click a horse with the right item — see
[Typed windows](../api/windows.md).
