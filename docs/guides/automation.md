# Automation: fishing, farming, collecting

## Item collection

```python
await bot.collect(max_distance=8, count=None)   # pick up nearby drops
bot.collector.nearby_items(8)                    # ItemEntity list
```

Walks to each `ItemEntity` within range and picks it up; stops when
`count` items are collected or none remain.

## Fishing

```python
caught = await bot.fish(timeout=60)   # True if a bite was reeled in
await bot.fish.reel_in()              # reel without waiting
```

Flow: find water, face it, `use_item` (fishing rod), wait for the
bobber entity, wait for the bite event, reel. `timeout` bounds the
whole cast; `**opts` pass through to the internal wait helpers.

## Farming

```python
bot.farming.mature_crops()                       # list of ready blocks
await bot.harvest(names=["wheat", "carrots"])    # reap mature crops
await bot.plant(seed_name="wheat_seeds")         # plant on farmland
await bot.tend_farm(names=["wheat"])             # harvest + replant
await bot.tend(names=["potatoes"])               # module-level alias
```

`harvest` digs mature crops (age property at max) and collects drops;
`plant` finds a seed in inventory and plants on nearby farmland;
`tend_farm` does both in one pass.

## Health & vitals

```python
bot.health            # 0-20 (float)
bot.food              # 0-20
bot.food_saturation   # 0-20 float
bot.oxygen            # air bubbles remaining, None when not needed
bot.experience        # ExperienceInfo(level, points, progress)
```

Subscribe to `health`, `food`, `experience` events for reactive
behavior (eat when hungry, flee when low).

## Physics & ticks

```python
bot.physics_enabled = True    # default; AABB collision + gravity
await bot.wait_for_ticks(20)  # ~1 second of server ticks
await bot.wait_for_chunks_to_load(timeout=10)
await bot.swing_arm()         # arm-swing animation packet
```

`wait_for_chunks_to_load` is the right gate before pathfinding into
unexplored terrain.
