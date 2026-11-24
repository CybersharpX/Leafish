# Utilities

## Vectors (`leafish.utils.vectors`)

| Class | Fields | Notes |
|---|---|---|
| `Vec3` | `x`, `y`, `z` | World-space position/vector. |
| `Vec2` | `x`, `y` | 2D (yaw/pitch helpers). |
| `BlockPos` | `x`, `y`, `z` (ints) | Integer block position. |

### `Vec3` operations

```python
v + v2, v - v2, v * scalar, v / scalar, -v
v.length(), v.length_squared(), v.normalized()
v.dot(other), v.cross(other)
v.distance_to(other), v.distance_squared_to(other), v.distance_to_block(other)
v.floor() -> BlockPos
v.offset(dx, dy, dz) -> Vec3
v.yaw_pitch() -> (yaw, pitch)
```

### `BlockPos`

`+`/`-` with other `BlockPos`, `.offset(dx, dy, dz)`, `.vec3()`,
`.distance_to`, `.to_tuple()`, iterable/unpackable as `(x, y, z)`.

`chunk_coords(pos, chunk_shift=4)` converts a position to chunk coords.

## Geometry (`leafish.utils.geometry`)

| Class/Function | Description |
|---|---|
| `BoundingBox` | AABB: `from_points`, `unit()`, `offset`, `intersects`, `contains`. |
| `RaycastHit` | `position`, `face_normal`, `previous_free_position`. |
| `ray_box_distance(...)` | Ray vs AABB intersection distance. |
| `raycast_voxels(...)` | DDA voxel traversal (backs `world.raycast`). |

## NBT (`leafish.utils.nbt`)

Binary NBT read/write plus SNBT:

```python
from leafish.utils.nbt import read_compound, write_compound, parse_snbt, to_snbt

compound = parse_snbt('{display:{Name:"\"Steve\""}}')
data = write_compound(compound)
back = read_compound(io.BytesIO(data))
```

`NBTByte`/`NBTShort`/`NBTLong`/`NBTFloat` are typed int/float
subclasses for round-tripping NBT tag types; `nbt_type_of` reports a
value's tag type.

## Math (`leafish.utils.math`)

`clamp`, `lerp`, `angle_diff`, `yaw_pitch_to_direction(yaw, pitch)`,
`direction_to_yaw_pitch(dx, dy, dz)`.

## Text (`leafish.utils.text`)

`component_to_text(component)` flattens Minecraft chat components to
plain text; `strip_colors` removes formatting codes;
`nbt_to_python` converts NBT tag structures to plain Python.
