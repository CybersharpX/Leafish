"""World interaction actions: digging, placing, attacking, equipping."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING

from ..exceptions import DiggingError, InventoryError, LeafishError
from ..inventory.inventory import HOTBAR_END, HOTBAR_START
from ..utils.vectors import BlockPos, Vec3

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.actions")

#: block_dig statuses (serverbound).
DIG_START = 0
DIG_CANCEL = 1
DIG_FINISH = 2
DIG_DROP_STACK = 3
DIG_DROP_ITEM = 4
DIG_SWAP_HAND = 5

#: block_place directions (face index -> unit normal).
FACE_DIRECTIONS: dict[int, Vec3] = {
    0: Vec3(0, -1, 0),   # down
    1: Vec3(0, 1, 0),    # up
    2: Vec3(0, 0, -1),   # north (-Z)
    3: Vec3(0, 0, 1),    # south (+Z)
    4: Vec3(-1, 0, 0),   # west (-X)
    5: Vec3(1, 0, 0),    # east (+X)
}
def _normal_key(v: Vec3) -> tuple[int, int, int]:
    return (int(v.x), int(v.y), int(v.z))


_NORMAL_TO_FACE = {_normal_key(v): k for k, v in FACE_DIRECTIONS.items()}


class ActionsModule:
    """Digging, block placement, combat and equipment actions."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self._dig_sequence = 0
        self._use_sequence = 0
        self._digging: BlockPos | None = None

    # -- helpers -----------------------------------------------------------------

    def _next_sequence(self) -> int:
        self._dig_sequence = (self._dig_sequence + 1) & 0x7FFFFFFF
        return self._dig_sequence

    @staticmethod
    def _resolve_pos(block_or_pos) -> BlockPos:
        if isinstance(block_or_pos, BlockPos):
            return block_or_pos
        pos = getattr(block_or_pos, "position", None)
        if isinstance(pos, BlockPos):
            return pos
        if isinstance(block_or_pos, Vec3):
            return block_or_pos.floor()
        if isinstance(block_or_pos, tuple):
            return BlockPos(*block_or_pos)
        raise LeafishError(f"Cannot resolve block position from {block_or_pos!r}")

    @staticmethod
    def _face_index(face) -> int:
        """Normalize a face argument to a direction index 0-5."""
        if face is None:
            raise LeafishError("A face direction is required")
        if isinstance(face, int):
            if face not in FACE_DIRECTIONS:
                raise LeafishError(f"Invalid face index: {face}")
            return face
        if isinstance(face, Vec3):
            t = _normal_key(face)
            if t in _NORMAL_TO_FACE:
                return _NORMAL_TO_FACE[t]
        if isinstance(face, (tuple, list)) and len(face) == 3:
            return ActionsModule._face_index(Vec3(*face))
        if isinstance(face, str):
            mapping = {
                "down": 0, "up": 1, "north": 2, "south": 3,
                "west": 4, "east": 5,
                "bottom": 0, "top": 1,
            }
            key = face.lower()
            if key in mapping:
                return mapping[key]
            # vec3-ish strings are not supported
        raise LeafishError(f"Invalid face: {face!r}")

    async def _look_at_block(self, pos: BlockPos, face: int) -> None:
        """Aim the bot's view at the center of the clicked face."""
        normal = FACE_DIRECTIONS[face]
        target = Vec3(pos.x + 0.5 + normal.x * 0.5,
                      pos.y + 0.5 + normal.y * 0.5,
                      pos.z + 0.5 + normal.z * 0.5)
        await self.bot.look_at(target)

    # -- digging -----------------------------------------------------------------

    async def dig(self, block_or_pos, force: bool = False) -> None:
        """Dig the block at *block_or_pos* (Block, BlockPos, Vec3 or tuple).

        Sends ``block_dig`` start/finish packets with correct timing based on
        block hardness. Creative mode digs instantly.
        """
        pos = self._resolve_pos(block_or_pos)
        block = self.bot.world.block_at(pos)
        if block is None:
            raise DiggingError(f"Cannot dig unloaded position {pos}")
        if block.name in ("air", "cave_air", "void_air"):
            raise DiggingError(f"Cannot dig air at {pos}")
        if not self.bot.world.can_dig_block(block) and not force:
            raise DiggingError(f"Block {block.name} at {pos} is not diggable")

        # Face: dig the face pointing toward the bot (or top if unknown).
        face = self._dig_face(pos)
        await self._look_at_block(pos, face)

        seq = self._next_sequence()
        await self.bot._send_play(
            "block_dig",
            {
                "status": DIG_START,
                "location": {"x": pos.x, "y": pos.y, "z": pos.z},
                "face": face,
                "sequence": seq,
            },
        )
        self._digging = pos
        self.bot.emit("digging_started", block)

        dig_time = self._dig_time(block)
        if dig_time > 0:
            await asyncio.sleep(dig_time)

        await self.bot._send_play(
            "block_dig",
            {
                "status": DIG_FINISH,
                "location": {"x": pos.x, "y": pos.y, "z": pos.z},
                "face": face,
                "sequence": seq,
            },
        )
        self._digging = None
        self.bot.emit("digging_completed", block)

        # Wait briefly for the server's block update; fall back to an
        # optimistic local update so callers see consistent state.
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            current = self.bot.world.block_at(pos)
            if current is not None and current.name in ("air", "cave_air", "void_air"):
                break
            await asyncio.sleep(0.05)
        else:
            air_id = self.bot.world.gamedata.block_state_id("air")
            if air_id is not None:
                self.bot.world.set_block_state(pos, air_id)

    def _dig_face(self, pos: BlockPos) -> int:
        """Pick the block face most visible from the bot's eye position."""
        entity = self.bot.entity
        if entity is None:
            return 1
        eye = entity.position + Vec3(0, entity.eye_height, 0)
        center = Vec3(pos.x + 0.5, pos.y + 0.5, pos.z + 0.5)
        delta = center - eye
        # Face whose normal best opposes the view direction.
        best_face, best_dot = 1, -2.0
        for face, normal in FACE_DIRECTIONS.items():
            dot = normal.dot(delta.normalized if delta.length else Vec3(0, 1, 0))
            if dot < best_dot:
                best_dot, best_face = dot, face
        return best_face

    def _dig_time(self, block) -> float:
        """Approximate digging time in seconds."""
        if self.bot.game_mode == "creative":
            return 0.0
        hardness = getattr(block, "hardness", 0.0) or 0.0
        if hardness <= 0:
            return 0.0  # insta-break
        # Bare-hand estimate; tool/enchantment bonuses arrive with the
        # inventory/tool module.
        return max(hardness * 1.5, 0.05)

    async def stop_digging(self) -> None:
        """Cancel an in-progress dig."""
        pos = self._digging
        if pos is None:
            return
        seq = self._next_sequence()
        await self.bot._send_play(
            "block_dig",
            {
                "status": DIG_CANCEL,
                "location": {"x": pos.x, "y": pos.y, "z": pos.z},
                "face": 1,
                "sequence": seq,
            },
        )
        self._digging = None
        self.bot.emit("digging_cancelled", pos)

    # -- placing -----------------------------------------------------------------

    async def place_block(self, reference_block, face=None, swing: bool = True) -> None:
        """Place the held item against *reference_block* on *face*.

        *reference_block* may be a Block, BlockPos, Vec3 or tuple; *face* is a
        direction index (0-5), Vec3 normal, or name like ``"up"``/``"north"``.
        When *face* is omitted, the face pointing away from the bot is used.
        """
        pos = self._resolve_pos(reference_block)
        ref = self.bot.world.block_at(pos)
        if ref is None:
            raise LeafishError(f"Cannot place against unloaded block at {pos}")
        if face is None:
            face = self._placement_face(pos)
        face_index = self._face_index(face)
        normal = FACE_DIRECTIONS[face_index]
        target = BlockPos(
            pos.x + int(normal.x), pos.y + int(normal.y), pos.z + int(normal.z)
        )

        existing = self.bot.world.block_at(target)
        if existing is not None and existing.name not in (
            "air", "cave_air", "void_air", "water", "lava",
        ):
            raise LeafishError(
                f"Cannot place at {target}: occupied by {existing.name}"
            )

        held = self.bot.inventory.held_item
        if held is None or held.empty:
            raise InventoryError("No item in hand to place")

        await self._look_at_block(pos, face_index)

        seq = self._next_sequence()
        # Hit position within the clicked block face (center-ish).
        cursor = Vec3(0.5 + normal.x * 0.5, 0.5 + normal.y * 0.5, 0.5 + normal.z * 0.5)
        rel = cursor - Vec3(pos.x, pos.y, pos.z)
        await self.bot._send_play(
            "block_place",
            {
                "hand": 0,
                "location": {"x": pos.x, "y": pos.y, "z": pos.z},
                "direction": face_index,
                "cursorX": min(max(rel.x, 0.0), 1.0),
                "cursorY": min(max(rel.y, 0.0), 1.0),
                "cursorZ": min(max(rel.z, 0.0), 1.0),
                "insideBlock": False,
                "worldBorderHit": False,
                "sequence": seq,
            },
        )
        if swing:
            await self.bot._send_play("arm_animation", {"hand": 0})
        self.bot.emit("block_place", target, held, face_index)

    async def interact_block(self, reference_block, face=None) -> None:
        """Right-click *reference_block* (open chests, use buttons, ...).

        Sends the same ``block_place`` (use-item-on) packet as placement
        but does not require a placeable item in hand.
        """
        pos = self._resolve_pos(reference_block)
        ref = self.bot.world.block_at(pos)
        if ref is None:
            raise LeafishError(f"Cannot interact with unloaded block at {pos}")
        if face is None:
            face = self._placement_face(pos)
        face_index = self._face_index(face)
        normal = FACE_DIRECTIONS[face_index]
        await self._look_at_block(pos, face_index)
        seq = self._next_sequence()
        cursor = Vec3(0.5 + normal.x * 0.5, 0.5 + normal.y * 0.5,
                     0.5 + normal.z * 0.5)
        rel = cursor - Vec3(pos.x, pos.y, pos.z)
        await self.bot._send_play(
            "block_place",
            {
                "hand": 0,
                "location": {"x": pos.x, "y": pos.y, "z": pos.z},
                "direction": face_index,
                "cursorX": min(max(rel.x, 0.0), 1.0),
                "cursorY": min(max(rel.y, 0.0), 1.0),
                "cursorZ": min(max(rel.z, 0.0), 1.0),
                "insideBlock": False,
                "worldBorderHit": False,
                "sequence": seq,
            },
        )
        self.bot.emit("block_interact", pos, face_index)

    def _placement_face(self, pos: BlockPos) -> int:
        """Default face: the one whose neighbor is closest to the bot."""
        entity = self.bot.entity
        if entity is None:
            return 1
        eye = entity.position
        best_face, best_d = 1, float("inf")
        for face, normal in FACE_DIRECTIONS.items():
            neighbor = Vec3(pos.x + normal.x + 0.5, pos.y + normal.y + 0.5,
                            pos.z + normal.z + 0.5)
            d = eye.distance_squared_to(neighbor)
            if d < best_d:
                best_d, best_face = d, face
        return best_face

    # -- combat ---------------------------------------------------------------------

    async def attack(self, entity, swing: bool = True) -> None:
        """Attack *entity* once (left click)."""
        if entity is None:
            raise LeafishError("attack() requires an entity")
        target = getattr(entity, "position", None)
        if target is not None:
            with contextlib.suppress(Exception):
                await self.bot.look_at(target + Vec3(0, 0.9, 0))
        await self.bot._send_play(
            "use_entity",
            {
                "target": entity.id,
                "mouse": 1,  # attack
                "sneaking": bool(self.bot.control_states.get("sneak")),
            },
        )
        if swing:
            await self.bot._send_play("arm_animation", {"hand": 0})
        self.bot.emit("entity_attacked", entity)

    # -- equipment --------------------------------------------------------------------

    async def equip(self, item, destination: str | None = None) -> None:
        """Equip *item* (name, Item or slot) to hand/offhand/armor.

        Currently supports ``hand`` (hotbar selection or hotbar swap) and
        ``offhand`` via window clicks. Armor destinations raise until the
        container module lands.
        """
        destination = (destination or "hand").lower()
        inv = self.bot.inventory

        if isinstance(item, str):
            found = inv.find_item(item)
            if found is None:
                raise InventoryError(f"Item '{item}' not in inventory")
            item = found

        slot = getattr(item, "slot", None)
        if slot is None:
            raise InventoryError("Cannot determine inventory slot for item")

        if destination == "hand":
            if HOTBAR_START <= slot <= HOTBAR_END:
                await inv.set_held_slot(slot - HOTBAR_START)
                return
            # Swap the item into the currently held hotbar slot.
            held_window_slot = HOTBAR_START + inv.held_slot
            await self._window_click_mode2(slot, held_window_slot)
            return

        if destination == "offhand":
            offhand_slot = 45
            await self._window_click_mode2(slot, offhand_slot)
            return

        if destination.startswith("armor"):
            # Armor slots 5-8; destination may be 'armor' or 'armor_<slot>'.
            armor_slot = None
            if destination == "armor":
                # Pick the first empty armor slot, else helmet slot 5.
                armor_slot = next(
                    (s for s in range(5, 9)
                     if inv.slots.get(s) is None or inv.slots[s].empty),
                    5,
                )
            else:
                try:
                    armor_slot = int(destination.rsplit("_", 1)[1])
                except (ValueError, IndexError):
                    raise InventoryError(
                        f"Unknown armor destination '{destination}'"
                    ) from None
            if armor_slot is None or not 5 <= armor_slot <= 8:
                raise InventoryError(f"Invalid armor slot: {armor_slot}")
            await self._window_click_mode2(slot, armor_slot)
            return

        raise InventoryError(f"Unknown equip destination '{destination}'")

    async def _window_click_mode2(self, slot: int, hotbar_button_slot: int) -> None:
        """Swap *slot* with the inventory slot identified by mode-2 click.

        Mode 2 ("hotbar swap") uses ``mouseButton`` as the hotbar index 0-8
        for the player inventory, or the armor/offhand slot index directly
        for special slots. We encode: mouseButton = hotbar index when the
        target is a hotbar slot, otherwise the raw slot for special slots.
        """
        button = hotbar_button_slot - HOTBAR_START \
            if HOTBAR_START <= hotbar_button_slot <= HOTBAR_END \
            else hotbar_button_slot
        await self.bot._send_play(
            "window_click",
            {
                "windowId": 0,
                "stateId": self.bot.inventory_state_id,
                "slot": slot,
                "mouseButton": button,
                "mode": 2,
                "changedSlots": [],
                "cursorItem": None,
            },
        )
        self.bot.emit("inventory_update")
