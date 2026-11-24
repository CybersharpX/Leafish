# Game data API

`leafish.data.registry.GameData` is the per-version game-data
registry. Get instances via `get_gamedata(version)` (cached).

## Lookups

| Method | Returns |
|---|---|
| `block_by_name(name)` / `block_by_id(id)` | Block registry dict. |
| `block_state(state_id)` | `(block, state)` tuple for a wire state id. |
| `block_state_id(name, properties=None)` | Wire state id for name+props. |
| `item_by_name(name)` / `item_by_id(id)` / `item_name(id)` | Item registry. |
| `entity_by_name(name)` / `entity_type_name(id)` / `entity_type_ids()` | Entity registry. |
| `recipes()` | Full recipe table. |
| `item_id_by_name(name)` | Numeric item id. |
| `raw(name)` | Any vendored JSON file by basename. |

`get_gamedata(version)` raises for versions with no vendored
directory; `list_versions()` enumerates what's available.

## Internals worth knowing

- `_index_blocks` precomputes state-id → (block, properties) mapping
  because modern `blocks.json` stores property descriptors rather
  than per-state ids — state ids are derived by cartesian product.
- `_properties_for_state` / `_state_offset` map a state id back to its
  property dict.
- Data loads lazily per file on first access.

## Version helpers

`leafish.version`:

| Function | Description |
|---|---|
| `list_versions()` | Vendored version strings. |
| `resolve_version(requested)` | `"latest"` → highest vendored. |
| `get_version_info(version)` | `VersionInfo` (protocol number, etc.). |
| `load_version_json(version, name)` | Raw JSON for a data file. |
