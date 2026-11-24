# Exceptions

All errors derive from `LeafishError` (`leafish.exceptions`).

| Exception | Raised when |
|---|---|
| `LeafishError` | Base class / generic failures (e.g. unknown auth mode). |
| `ConnectionError` | Socket/transport failures. |
| `DisconnectError` | Server-initiated disconnect (carries `reason`). |
| `AuthenticationError` | Microsoft/offline auth failures. |
| `ProtocolError` | Base for protocol problems. |
| `UnsupportedVersionError` | Requested version has no vendored data. |
| `PacketDecodeError` / `PacketEncodeError` | ProtoDef codec failures. |
| `MovementError` | Movement/look/control failures. |
| `PathfindingError` | No path found / goal unreachable. |
| `InventoryError` | Window/inventory operations (missing items, bad slots, trade index out of range). |
| `DiggingError` | Dig failures (unreachable, undiggable). |
| `CraftingError` | Recipe/crafting failures. |
| `FishingError` | Fishing timeouts/failures. |
| `PluginError` | Plugin load/unload/override/dependency problems. |

!!! tip
    Catch `LeafishError` for "any Leafish failure"; catch the specific
    subclass when you want to distinguish e.g. a missing ingredient
    (`InventoryError`/`CraftingError`) from a dropped connection.
