# Versions & game data

Leafish is **architecture-first** for multi-version support: everything
version-specific lives in vendored JSON, not code.

## Vendored data

`src/leafish/data/versions/<version>/` contains the minecraft-data
extracts for each supported version:

| File | Contents |
|---|---|
| `protocol.json` | ProtoDef packet schemas (states, directions, types) |
| `blocks.json` / `blockCollisionShapes.json` | Block registry + physics shapes |
| `items.json` | Item registry |
| `entities.json` | Entity type registry |
| `recipes.json` | Crafting recipes |
| `windows.json` | Container window layouts |
| `biomes.json`, `effects.json`, `enchantments.json`, `foods.json`, `materials.json`, `particles.json`, `attributes.json`, `loginPacket.json`, `sounds.json`, `tints.json`, `mapIcons.json`, `blockLoot.json`, `commands.json`, `language.json`, `version.json` | Auxiliary registries |

Current versions: **1.21.11** (protocol 774) and **1.21.4** (769).

## Fetching a version

```bash
python tools/fetch_mcdata.py 1.21.11
```

The fetcher pulls plain JSON from the PrismarineJS
`minecraft-data` repository — no Node.js involved. The directory must
contain at minimum `protocol.json` and `version.json` for the codec to
load; other files are loaded lazily by `GameData`.

## Using the registry

```python
from leafish.data.registry import get_gamedata, list_versions

gd = get_gamedata("1.21.11")
gd.block_by_name("diamond_ore")        # block dict
gd.item_by_name("iron_ingot")         # item dict
gd.entity_by_name("zombie")           # entity dict
gd.block_state_id("furnace", {"facing": "north"})
gd.raw("recipes")                     # full recipes table

list_versions()                       # ["1.21.4", "1.21.11"]
```

`get_gamedata` caches per version; data files load lazily on first
access.

## Version resolution

`Leafish.create_bot(version=...)` accepts a vendored version string,
`"latest"` (resolved by `leafish.version.resolve_version` to the
highest vendored protocol version) or `"auto"` — the default — which
pings the server's status endpoint before login and selects the
vendored version matching the reported protocol number
(`leafish.protocol.status.detect_server_protocol`). An unknown version
or an undetectable/unsupported server protocol raises
`UnsupportedVersionError`.

## Protocol codec

`ProtocolCodec.for_version(version)` compiles the ProtoDef schema once
and caches per (state, direction). Packet handlers in `bot.py` are
data-driven off packet names — adding a packet handler never requires
touching serialization code.
