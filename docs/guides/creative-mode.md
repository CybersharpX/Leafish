# Creative mode

When the bot is in creative mode (`bot.abilities.instabuild` or
server-side creative), `bot.creative` exposes direct inventory
manipulation via the `set_creative_slot` packet — no clicking, no
cooldowns.

```python
await bot.creative.set_slot(36, "diamond_sword", count=1)
await bot.creative.give("diamond", count=64)          # first empty slot
await bot.creative.clear(36)                          # empty a slot
await bot.creative.set_held_item("netherite_pickaxe")  # give + select
```

| Method | Description |
|---|---|
| `set_slot(slot, item, count=1)` | Set a player-inventory slot (0-35 window slots; pass an `Item` or name). |
| `give(name, count=1, slot=None)` | Give an item; auto-picks an empty slot when `slot` is omitted. |
| `clear(slot)` | Empty a slot. |
| `set_held_item(name, count=1)` | Give the item and select its hotbar slot. |

`item` accepts an item name string, an `Item`, or a raw slot dict —
`_build_item` normalizes all three.

!!! note
    Creative ops are server-authoritative: the server must actually be
    in creative mode or it will ignore/reject the packets.
