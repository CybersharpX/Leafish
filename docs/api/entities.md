# Entities API

`bot.entities` is an `EntityManager`; individual entities are `Entity`
subclasses.

## EntityManager

```python
bot.entities.get(entity_id)          # Entity | None
bot.entities.by_uuid(uuid_str)       # Entity | None
bot.entities.all()                   # list[Entity]
bot.entities.nearest(pos=None, predicate=None, max_distance=None)
bot.entities.spawn(params)           # internal: packet -> entity
bot.entities.destroy([ids])
bot.entities.clear()
```

Convenience lookups on the bot: `bot.nearest_entity(pred, max_dist)`,
`bot.find_entity(pred)`, `bot.entity_at(position)` (bounding-box
containment).

## Entity

| Attribute | Meaning |
|---|---|
| `id` / `uuid` | Server ids. |
| `type` / `name` | Entity type id or resolved registry name; display name. |
| `position` / `velocity` | `Vec3` world state. |
| `yaw` / `pitch` / `head_yaw` | Orientation (degrees). |
| `on_ground` | Grounded flag. |
| `eye_height` / `width` / `height` | Dimensions for raycasts/AABBs. |
| `metadata` | Raw entity-metadata dict. |
| `equipment` | Equipment slot → item. |
| `health` | Health from metadata, `None` if unknown. |
| `vehicle` / `passengers` | Riding relationships. |
| `effects` | Active status effects. |

Queries: `is_player`, `distance_to(other)`,
`distance_to_point(point)`, `bounding_box()` → `BoundingBox`,
`contains_point(point)`, `consume_position_changed()`.

## Subclasses

| Class | Used for |
|---|---|
| `Player` | Players (including `bot.entity`). |
| `Mob` | Monsters, animals, villagers. |
| `ItemEntity` | Dropped items. |
| `Projectile` | Arrows, fireballs, etc. |
| `Vehicle` | Boats, minecarts, horses. |

## Events

`entity_spawn`, `entity_update`, `entity_move`, `entity_destroy`,
`entity_hurt`, `entity_equipment_update`,
`entity_metadata_update`, `entity_attach`/`attach_entity`, `mount`,
`dismount`, `entity_passengers`, `entity_swing_arm`,
`entity_hurt_animation`, `entity_damaged`.
