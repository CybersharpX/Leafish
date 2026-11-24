# World interaction

## Querying blocks

```python
block = bot.world.block_at(pos)          # Block | None
blocks = bot.world.find_blocks(["oak_log", "birch_log"], max_distance=32)
nearest = bot.world.find_block("diamond_ore")
bot.world.is_block_loaded(pos)
bot.world.light_at(pos)                  # (block_light, sky_light)
```

`block_at` returns `None` for unloaded chunks. `find_blocks` /
`find_block` search loaded chunks only.

## `Block` objects

| Attribute | Meaning |
|---|---|
| `name` | Registry name (`"stone"`, `"oak_log"`, ...). |
| `position` | `BlockPos`. |
| `state_id` / `block_id` | Wire ids. |
| `hardness` / `hardness_seconds` | Dig difficulty. |
| `diggable` | Whether the block can be mined at all. |
| `is_air` / `is_fluid` | Convenience predicates. |
| `state_properties` | Parsed properties (`facing`, `age`, ...). |
| `property(name, default)` | Single property lookup. |
| `block_entity` | Tile-entity NBT when present. |

## Digging

```python
await bot.dig(block)                    # mine to completion
await bot.dig(block, force=True)        # skip reach checks
bot.can_dig_block(block)                # reach + tool check
bot.dig_time(block)                     # seconds with held tool
await bot.stop_digging()                # cancel mid-dig
```

`dig` sends start/abort/finish dig packets; the fake server and real
servers confirm with `block_change`/`multi_block_change`, which update
`bot.world` automatically.

## Placing

```python
await bot.place_block(reference_block, face="top")   # or Vec3 face index
```

`face` accepts a direction name or numeric face index. The bot looks
at the face, sends the placement packet, and swings the arm.

## Interacting (right-click)

```python
await bot.interact_block(block, face=None)     # generic right-click
await bot.open_container(block)                # right-click + await window
view = await bot.open_window(block)            # typed window (chest, furnace, ...)
await bot.activate_block(block, direction, cursor_pos)
await bot.use_item()                            # use held item (bow, food)
await bot.activate_item(off_hand=True)          # start using off-hand
await bot.deactivate_item()                     # stop using
await bot.consume()                             # eat/drink held item
```

## Raycasts & line-of-sight

```python
hit = bot.world.raycast(origin, direction, max_distance=6)
# hit -> (block, RaycastHit(position, face_normal, previous_free_position))

cursor_block = bot.block_at_cursor(max_distance=5.0)
cursor_ent  = bot.entity_at_cursor(max_distance=5.0)

bot.can_see_block(block_or_pos)     # loaded + unobstructed
bot.can_see_entity(entity)          # entity AABB along eye ray
```

`RaycastHit` is a `geometry` dataclass with `position`,
`face_normal`, and `previous_free_position` — the free space just
before impact, useful for placing blocks.

## Entity queries

```python
bot.entity                     # own Player entity
bot.entity_at(position)        # entity whose bounding box contains pos
bot.nearest_entity(pred, max_distance)
bot.find_entity(pred)
bot.entities                   # EntityManager -> .all()/.nearest()/.get(id)
```

Entity types: `Player`, `Mob`, `ItemEntity`, `Projectile`, `Vehicle`.
See [Entities](../api/entities.md).

## Block updates

Incoming `block_change`/`multi_block_change` packets update
`bot.world` automatically. Subscribe to `block_update` /
`block_entity_update` events for reactive logic (e.g. farmland
trampling, pistons).
