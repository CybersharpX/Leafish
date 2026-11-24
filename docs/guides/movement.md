# Movement & pathfinding

## Low-level movement

```python
await bot.set_control_state("forward", True)   # walk
await bot.set_control_state("jump", True)      # hop
await bot.set_control_state("sprint", True)    # sprint
await bot.set_control_state("sneak", True)     # sneak
await bot.stop_moving()                        # release everything

bot.get_control_state("forward")               # -> bool
await bot.clear_control_states()
```

Valid controls: `forward`, `back`, `left`, `right`, `jump`, `sneak`,
`sprint`.

## Looking

```python
await bot.look(yaw=90.0, pitch=0.0)            # degrees
await bot.look_at(target)                       # Vec3 / BlockPos / entity
```

`bot.look_at` accepts entities too — it aims at their eye position.

## Walking to a point

```python
await bot.move_to(target_vec3, timeout=15)     # straight-line walk
await bot.goto(target_vec3, timeout=15)        # A* pathfind + walk
await bot.goto(block_or_pos)
await bot.find_path(start, goal)               # compute path, don't walk
```

`goto`/`move_to` return when within reach or raise on timeout. Cancel
an in-progress walk with `bot.pathfinder.stop()`.

## Pathfinding

The pathfinder is A* over the collision grid — it understands step-ups,
jumps, and avoids solid blocks. `find_path` returns a list of
`BlockPos` waypoints.

### Goals

Pass any of these to `bot.pathfinder.goto(goal)` or `bot.goto(goal)`:

| Goal | Reaches |
|---|---|
| `GoalBlock(x, y, z)` | Exact block position. |
| `GoalNear(x, y, z, range=r)` | Within `r` blocks of a point. |
| `GoalXZ(x, z, range=r)` / `GoalNearXZ` | Horizontal proximity, any Y. |
| `GoalY(y, range=r)` | A target height. |
| `GoalGetToBlock(x, y, z)` | Adjacent to a block (for digging/placing). |
| `GoalLookAtBlock(x, y, z, range=r)` | Within line-of-sight of a block. |
| `GoalFollow(entity, range=r)` / `GoalFollowEntity` | Tracks a moving entity, replans automatically. |
| `GoalComposite(goals, all_goals=True)` | AND (`all_goals`) or OR of sub-goals. |
| `GoalInvert(goal)` | Anywhere *except* the goal. |

Plain positions, tuples, `Vec3`, and `BlockPos` are coerced to
`GoalBlock`, so `await bot.goto(Vec3(100, 64, -20))` just works.

### Dynamic goals

`GoalFollow` re-evaluates its target each tick — the path replans as
the entity moves. Use it for escort/follow behavior:

```python
from leafish.pathfinder import GoalFollow

zombie = bot.nearest_entity(lambda e: e.name == "zombie")
await bot.pathfinder.goto(GoalFollow(zombie, range=3))
```

## Physics

`bot.physics_enabled` toggles the AABB physics engine (default on).
Disable it if you want raw protocol-level movement without local
collision simulation:

```python
bot.physics_enabled = False
```

Physics handles gravity, jumping, fluid drag, and axis-separated
collision against loaded blocks — so `goto` doesn't clip through
walls even on uneven terrain.
