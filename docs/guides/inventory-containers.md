# Inventory & containers

## Player inventory

`bot.inventory` (an `Inventory`) mirrors the 36 player slots plus
cursor state:

```python
bot.inventory.slots                # dict[int, Item]
bot.inventory.count("iron_ingot")  # total across all slots
bot.inventory.find_item("torch")   # first match or None
bot.inventory.find_items("torch")  # all matches
bot.inventory.empty_slots()        # indices of empty slots
bot.inventory.held_item            # item in the selected hotbar slot
bot.held_item                      # same, via bot
bot.cursor_item                    # item on the cursor (if any)
```

### Selecting the hotbar

```python
await bot.set_quick_bar_slot(3)    # 0-8
await bot.update_held_item()      # re-announce held slot to server
```

### Moving items

```python
await bot.equip("diamond_sword", "hand")   # find + move to equipment
await bot.unequip("hand")
await bot.toss(item_or_slot, count=None)
await bot.toss_stack(item)
await bot.move_slot_item(src, dst)
await bot.put_away(slot)
await bot.transfer(options)                  # bulk move matching items
await bot.put_selected_item_range(start, end, dest)
```

`bot.simple_click` exposes raw `left_mouse(slot)` / `right_mouse(slot)`
window-0 clicks for custom interaction code.

## Windows & containers

Right-clicking a chest, furnace, crafting table, anvil, villager, or
horse opens a **window** — a slot grid with a server-side state id.

```python
await bot.open_container(block)             # generic right-click
view = await bot.open_window(block)         # typed Window view
wid  = bot.current_window_id
win  = bot.containers.window(wid)           # WindowState
view = bot.containers.window_view(wid)      # typed Window
```

`WindowState.slots` maps slot index → `Item`; `player_offset` marks
where the 36 player-inventory slots begin inside the window.

### Raw clicks

```python
await bot.click_window(wid, slot, button=0, mode=0)
await bot.shift_click(wid, slot)            # quick-move
await bot.close_window(wid)
```

Click modes (Minecraft protocol):

| Mode | Button | Effect |
|---|---|---|
| 0 | 0/1 | Pick up / place stack (left/right click). |
| 1 | — | Shift-click: move between container and player inventory. |
| 2 | 0-8 | Swap with hotbar slot. |

State ids are tracked automatically (`WindowState.state_id`) — wait
for `window_property`/`set_slot` updates rather than sleeping when
synchronizing with server results.

### Bulk transfer helpers

```python
await bot.deposit_all(wid, name="cobblestone")   # inventory → container
await bot.withdraw(wid, "diamond", count=3)      # container → inventory
```

Typed `Window` views (`bot.open_window`, `bot.current_window`) add
`deposit(name, count)` / `withdraw(name, count)` shortcuts plus
`click`/`shift_click`/`close`.

## Slot layout conventions

- Window **0** is the player inventory (crafting output at slot 0 in
  older protocol versions; modern uses the 2×2 grid slots 1-4).
- Container windows append the player's 36 inventory slots after the
  container's own slots — `Window.player_slots` is a `range`, not a
  callable.
- Furnace: input `0`, fuel `1`, output `2`.
- Crafting table: result `0`, grid `1-9`, then player inventory.
- Anvil: input `0`, material `1`, result `2`.
