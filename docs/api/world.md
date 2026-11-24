# World API

`bot.world` is a `World` instance tracking loaded chunks, blocks, and
dimension state.

## Chunks

```python
chunk = bot.world.chunk_at(cx, cz)        # Chunk | None
chunk = bot.world.load_chunk(cx, cz)      # get-or-create
bot.world.load_chunk_data(cx, cz, params) # internal: packet -> model
bot.world.unload_chunk(cx, cz)
bot.world.is_block_loaded(pos)
```

`Chunk` holds 16×16 columns of `ChunkSection`s; `ChunkSection`
exposes `get_state(index)` / `set_state` / `iter_states` over the
paletted container and `biome_at(index)`.

Dimension bounds (`min_section_y`, `section_count`,
`set_dimension_bounds`, `apply_dimension`) adjust automatically from
login/respawn packets — overworld, nether, and end heights differ.

## Blocks

```python
bot.world.block_at(pos)                   # Block | None
bot.world.set_block_state(pos, state_id)  # local update
bot.world.find_blocks(names, **kwargs)    # list[Block]
bot.world.find_block(names, **kwargs)     # nearest Block | None
bot.world.can_dig_block(block)            # reach/tool check
bot.world.raycast(origin, direction, max_distance=6, ...)  # -> (Block|None, RaycastHit|None)
bot.world.light_at(pos)                   # (block_light, sky_light)
```

`find_blocks`/`find_block` accept a name or list of names plus
`max_distance`/`point` filters — see `World.find_blocks` for the full
signature.

`raycast` marches voxels from `origin` along `direction` (a `Vec3`)
and returns the first solid hit plus a `RaycastHit` (`position`,
`face_normal`, `previous_free_position`).

`light_at` returns the decoded light nibbles for a position —
`(block_light, sky_light)`, each `None` when the chunk isn't loaded.

## Time & weather

`bot.world.set_time(age, time, tick_day_time)` and
`set_weather(params)` are fed by `time_update`/`game_state_change`
packets; read the resulting state via `bot.time` and `bot.weather`
(see [State](state.md)).

## Events

`chunk_column_load`, `chunk_column_unload`, `block_update`,
`block_entity_update`, `time_update`, `weather_update` fire as chunks
and blocks change.
