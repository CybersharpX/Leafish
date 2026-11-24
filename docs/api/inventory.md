# Inventory API

## Item

`leafish.inventory.item.Item` — a stack:

| Field | Meaning |
|---|---|
| `item_id` | Registry id (version-dependent). |
| `name` | Resolved registry name (`"diamond"`). |
| `count` | Stack size. |
| `components` / `remove_components` | Raw data components (enchants, damage, ...). |
| `slot` | Window slot it occupies, if known. |

`Item.empty` is `True` for air/none stacks; `Item.from_slot(dict)`
builds from wire data.

## Inventory

`bot.inventory` tracks the player inventory (window 0, 36 slots +
cursor).

| Member | Description |
|---|---|
| `slots` | `dict[int, Item]` of non-empty slots. |
| `slot(i)` | `Item` at index or `None`. |
| `items()` | All non-empty items. |
| `items_by_name(name)` / `find_item(name)` / `find_items(name)` | Lookups. |
| `count(name)` | Total count across slots. |
| `empty_slots()` | Indices of empty slots. |
| `held_item` | Item in the selected hotbar slot. |

### Mutations (all async, all send window clicks)

| Method | Description |
|---|---|
| `set_held_slot(slot)` | Select hotbar slot. |
| `toss(slot_or_item, count=None)` | Drop items on the ground. |
| `toss_stack(...)` / `drop_slot(slot)` | Drop a whole stack / by index. |
| `move_slot_item(src, dst)` | Move between window-0 slots. |
| `put_away(slot)` | Move to a safe storage slot. |
| `transfer(options)` | Bulk-move matching items. |
| `put_selected_item_range(start, end, dest)` | Move a slot range. |
| `unequip(destination="hand")` | Remove equipment. |

The bot exposes the same operations as top-level methods
(`bot.toss`, `bot.move_slot_item`, `bot.put_away`, `bot.transfer`,
`bot.put_selected_item_range`, `bot.unequip`) — see
[LeafishBot](bot.md).

## Window clicks

Low-level clicking goes through `bot.click_window(wid, slot, button,
mode)` / `bot.shift_click(wid, slot)` — see [Windows](windows.md) and
the [Inventory & containers guide](../guides/inventory-containers.md).
