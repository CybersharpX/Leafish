"""Typed container windows.

Wraps :class:`~leafish.modules.containers.WindowState` with
container-specific accessors for furnaces, enchantment tables, anvils
and villager trading windows. All state remains server-authoritative;
these classes only expose slots/properties the server already sent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..exceptions import InventoryError
from ..inventory.item import Item

if TYPE_CHECKING:
    from ..bot import LeafishBot
    from ..modules.containers import WindowState

__all__ = [
    "AnvilWindow",
    "EnchantmentTableWindow",
    "FurnaceWindow",
    "HorseWindow",
    "VillagerWindow",
    "Window",
    "typed_window",
]


def _item_name(bot: LeafishBot, item: Item | None) -> str | None:
    if item is None:
        return None
    if item.name is None and item.item_id is not None:
        item.name = bot.world.gamedata.item_name(item.item_id)
    return item.name


class Window:
    """Base typed view over a server window."""

    def __init__(self, bot: LeafishBot, state: WindowState) -> None:
        self.bot = bot
        self.state = state

    @property
    def window_id(self) -> int:
        return self.state.window_id

    @property
    def title(self) -> str | None:
        return self.state.title

    @property
    def slots(self) -> dict[int, Item]:
        return self.state.slots

    def item(self, slot: int) -> Item | None:
        """Item in absolute window slot *slot* (``None`` if empty)."""
        return self.state.slots.get(slot)

    def item_name(self, slot: int) -> str | None:
        return _item_name(self.bot, self.item(slot))

    @property
    def container_slots(self) -> range:
        return self.state.container_slots()

    @property
    def player_slots(self) -> range:
        return self.state.player_slots()

    async def click(self, slot: int, button: int = 0, mode: int = 0) -> None:
        await self.bot.containers.click(
            self.window_id, slot, button=button, mode=mode)

    async def shift_click(self, slot: int) -> None:
        await self.bot.containers.shift_click(self.window_id, slot)

    async def deposit(self, name: str, count: int | None = None) -> int:
        """Shift-click matching player slots into the container section."""
        moved = 0
        for slot in list(self.player_slots):
            item = self.item(slot)
            if item is None or item.empty:
                continue
            if item.name != name and _item_name(self.bot, item) != name:
                continue
            if count is not None and moved >= count:
                break
            await self.shift_click(slot)
            moved += item.count if count is None else min(
                item.count, count - moved)
        return moved

    async def withdraw(self, name: str, count: int | None = None) -> int:
        """Shift-click matching container slots into the player section."""
        moved = 0
        for slot in list(self.container_slots):
            item = self.item(slot)
            if item is None or item.empty:
                continue
            if item.name != name and _item_name(self.bot, item) != name:
                continue
            if count is not None and moved >= count:
                break
            await self.shift_click(slot)
            moved += item.count if count is None else min(
                item.count, count - moved)
        return moved

    async def close(self) -> None:
        await self.bot.containers.close(self.window_id)


class FurnaceWindow(Window):
    """Furnace / blast furnace / smoker window.

    Slot layout: 0 = input, 1 = fuel, 2 = output, then player inventory.
    Progress comes from ``craft_progress_bar`` window properties.
    """

    @property
    def input_slot(self) -> int:
        return 0

    @property
    def fuel_slot(self) -> int:
        return 1

    @property
    def output_slot(self) -> int:
        return 2

    @property
    def input_item(self) -> Item | None:
        return self.item(0)

    @property
    def fuel_item(self) -> Item | None:
        return self.item(1)

    @property
    def output_item(self) -> Item | None:
        return self.item(2)

    def _prop(self, key: int) -> int:
        return int(self.state.properties.get(key, 0))

    @property
    def burn_time(self) -> int:
        """Remaining fuel burn time in ticks (property 0)."""
        return self._prop(0)

    @property
    def burn_time_total(self) -> int:
        """Total burn time of the current fuel in ticks (property 1)."""
        return self._prop(1)

    @property
    def cook_time(self) -> int:
        """Progress of the current item in ticks (property 2)."""
        return self._prop(2)

    @property
    def cook_time_total(self) -> int:
        """Total cook time for the current item in ticks (property 3)."""
        return self._prop(3)

    @property
    def progress(self) -> float:
        """Cooking progress 0.0-1.0."""
        total = self.cook_time_total
        return self.cook_time / total if total > 0 else 0.0

    async def take_output(self) -> None:
        """Shift-click the output slot to collect the smelted item."""
        if self.output_item is not None:
            await self.shift_click(self.output_slot)


class EnchantmentTableWindow(Window):
    """Enchanting table window.

    Slot layout: 0 = item to enchant, 1 = lapis lazuli, 2 = result.
    Enchant options are server-computed; ``enchant`` chooses one.
    """

    @property
    def item_slot(self) -> Item | None:
        return self.item(0)

    @property
    def lapis_slot(self) -> Item | None:
        return self.item(1)

    @property
    def result_slot(self) -> Item | None:
        return self.item(2)

    async def enchant(self, option: int) -> None:
        """Pick enchant option *option* (0-2) for the current item."""
        if not 0 <= option <= 2:
            raise InventoryError("Enchant option must be 0, 1 or 2")
        await self.bot._send_play(
            "enchant_item", {"windowId": self.window_id, "enchantment": option})

    @property
    def offers(self) -> list[dict[str, Any]]:
        """Best-effort enchant offers decoded from slot components.

        Modern versions deliver enchant options through data components
        on the placed item rather than a dedicated packet; this returns
        whatever ``enchantable``-style entries it can find.
        """
        offers: list[dict[str, Any]] = []
        item = self.item_slot
        if item is None:
            return offers
        for comp in item.components or []:
            text = str(comp)
            if "enchant" in text.lower():
                offers.append(comp if isinstance(comp, dict) else {"raw": comp})
        return offers


class AnvilWindow(Window):
    """Anvil window.

    Slot layout: 0 = input tool, 1 = material/sacrifice, 2 = result.
    """

    @property
    def input_item(self) -> Item | None:
        return self.item(0)

    @property
    def material_item(self) -> Item | None:
        return self.item(1)

    @property
    def result_item(self) -> Item | None:
        return self.item(2)

    @property
    def repair_cost(self) -> int:
        """Anvil use cost in levels (window property 0)."""
        return int(self.state.properties.get(0, 0))

    async def rename(self, name: str) -> None:
        """Set the anvil's rename text (empty string clears it)."""
        await self.bot._send_play("name_item", {"name": name})

    async def take_result(self) -> None:
        """Shift-click the result slot."""
        if self.result_item is not None:
            await self.shift_click(2)


class VillagerWindow(Window):
    """Villager / wandering trader window.

    ``trades`` is populated from the ``trade_list`` packet; offers are
    the decoded trade dicts the server sent.
    """

    @property
    def trades(self) -> list[dict[str, Any]]:
        return list(self.state.extras.get("trades", []))

    @property
    def villager_level(self) -> int:
        return int(self.state.extras.get("villagerLevel", 0))

    @property
    def experience(self) -> int:
        return int(self.state.extras.get("experience", 0))

    @property
    def is_regular_villager(self) -> bool:
        return bool(self.state.extras.get("isRegularVillager", True))

    @property
    def can_restock(self) -> bool:
        return bool(self.state.extras.get("canRestock", False))

    async def select_trade(self, index: int) -> None:
        """Choose trade *index* (server expects the offer slot id)."""
        if not 0 <= index < len(self.trades):
            raise InventoryError(
                f"Trade index {index} out of range ({len(self.trades)} offers)")
        await self.bot._send_play("select_trade", {"slot": index})


class HorseWindow(Window):
    """Horse / mule / donkey inventory window."""

    @property
    def entity_id(self) -> int | None:
        return self.state.extras.get("entityId")

    @property
    def slot_count(self) -> int:
        return int(self.state.extras.get("slotCount", 0))


def typed_window(bot: LeafishBot, state: WindowState) -> Window:
    """Return the most specific :class:`Window` subclass for *state*.

    Detection is title-based because modern protocol ``inventoryType``
    ids vary between versions; container slot counts disambiguate
    within a family.
    """
    title = (state.title or "").lower()
    extras = state.extras
    if "trades" in extras or "villager" in title or "trader" in title:
        return VillagerWindow(bot, state)
    if "anvil" in title:
        return AnvilWindow(bot, state)
    if "enchant" in title:
        return EnchantmentTableWindow(bot, state)
    if any(k in title for k in ("furnace", "smoker", "blast")):
        return FurnaceWindow(bot, state)
    if "horse" in title or (extras.get("entityId") is not None and \
            state.player_offset is not None and state.player_offset < 3):
        return HorseWindow(bot, state)
    return Window(bot, state)
