# Crafting & smelting

## Crafting

`bot.craft` is recipe-driven: it looks up the recipe in vendored
`recipes.json`, verifies ingredients, moves items into the grid, and
takes the result.

```python
await bot.craft("crafting_table")            # 2x2 inventory grid
await bot.craft("iron_pickaxe", count=1)

# 3x3 recipes need an open crafting-table window:
table = bot.world.find_block("crafting_table")
await bot.interact_block(table)
await bot.craft("diamond_pickaxe", crafting_table=True)
```

### Recipe queries

```python
bot.recipes_for("iron_ingot")      # all variants of a recipe
bot.craftable_recipes()            # everything craftable now
bot.find_recipe("torch", count=4)
bot.missing_ingredients(recipe)    # {item_name: missing_count}
bot.can_craft(recipe)
```

`Recipe` objects expose the ingredient map, result item, and whether
they're shaped or shapeless.

### How it works

- The 2×2 grid lives in window 0 slots 1-4; the result is slot 0.
- `crafting_table=True` uses the open table window's 3×3 grid (slots
  1-9) plus its result slot.
- Ingredients are pulled from inventory, placed, the result clicked,
  and leftovers returned — all via normal window clicks, so the
  server stays authoritative.

## Smelting

`bot.smelt` drives any furnace-type window (`FurnaceWindow`):

```python
# With a furnace already open (or pass block= to open one):
made = await bot.smelt("iron_ore", count=4)
made = await bot.smelt("raw_beef", count=8, fuel="coal")
made = await bot.smelt("cobblestone", count=16, block=furnace_block)
```

Returns the number of output items collected. Fuel defaults to the
first available from coal → charcoal → blaze rod → lava bucket → ...;
pass `fuel=` to override. `timeout` (default 120s) bounds the wait for
server-side smelting.

### FurnaceWindow API

```python
win = bot.open_furnace_window()      # or bot.open_furnace(block)
win.input_item / win.fuel_item / win.output_item
win.burn_time / win.burn_time_total  # remaining/total burn ticks
win.cook_time / win.cook_time_total  # cook progress
win.progress                          # 0.0-1.0
await win.take_output()               # shift-click result slot
```

Smokers and blast furnaces share `FurnaceWindow` — the server decides
what smelts; the client only moves items.

## Anvil repair & rename

```python
await bot.repair("iron_pickaxe", material="iron_ingot")
# or with an open anvil:
win = await bot.open_anvil(anvil_block)
await win.rename("Excalibur")
await win.take_result()
```

`AnvilWindow.repair_cost` reports the XP-level cost (window property
0) before you commit.
