# Pathfinder API

`bot.pathfinder` is a `Pathfinder` — A* over the loaded collision grid.

## Pathfinder

```python
path = bot.find_path(start, goal, **kwargs)     # list[BlockPos]
ok   = await bot.goto(goal, timeout=None)       # pathfind + walk
await bot.move_to(vec3, timeout=None)           # straight-line walk
bot.pathfinder.stop()                           # cancel current goto
bot.pathfinder.is_walkable(pos)                 # collision check
```

`goto` accepts `Vec3`/`BlockPos`/tuples (coerced to `GoalBlock`) or
any `Goal`. `find_path` returns waypoints without moving.

## Goals (`leafish.pathfinder.goals`)

```python
from leafish.pathfinder import (
    Goal, GoalBlock, GoalNear, GoalXZ, GoalNearXZ, GoalY,
    GoalGetToBlock, GoalLookAtBlock, GoalFollow, GoalFollowEntity,
    GoalComposite, GoalInvert,
)
```

| Goal | Constructor | `is_end` when |
|---|---|---|
| `GoalBlock` | `(x, y, z)` | Exact position reached. |
| `GoalNear` | `(x, y, z, range=1.0)` | Within `range` of point. |
| `GoalXZ` / `GoalNearXZ` | `(x, z, range=0.0)` | XZ within `range`, any Y. |
| `GoalY` | `(y, range=0.0)` | Y within `range`. |
| `GoalGetToBlock` | `(x, y, z)` | Adjacent to the block. |
| `GoalLookAtBlock` | `(x, y, z, range=4.0)` | In line-of-sight. |
| `GoalFollow` / `GoalFollowEntity` | `(entity, range=2.0)` | Within `range` of entity (dynamic — replans). |
| `GoalComposite` | `(goals, all_goals=True)` | All (AND) or any (OR) sub-goals met. |
| `GoalInvert` | `(goal)` | The wrapped goal is *not* met. |

### Custom goals

Subclass `Goal` and implement `is_end(pos)`, `heuristic(pos)`, and
(optionally) `target()`/`target_at(pos)`:

```python
class GoalNearWater(Goal):
    def is_end(self, pos): ...
    def heuristic(self, pos): ...
```

`coerce_goal(goal)` normalizes any accepted goal-like value.

## Events

`path_update` fires as the path replans; `move`/`forced_move` track
position packets.
