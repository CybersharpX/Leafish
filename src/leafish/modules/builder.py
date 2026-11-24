"""Construction planning and structure building module.

Provides high-level construction planning (walls, platforms, boxes, columns,
or custom schematics) with material requirement calculation, inventory
validation, placement ordering (ground-up), and automated placement execution.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..exceptions import InventoryError, LeafishError
from ..utils.vectors import BlockPos, Vec3

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.builder")


@dataclass(frozen=True, slots=True)
class BlockPlacement:
    """A single block placement action in a construction plan."""

    position: BlockPos
    block_name: str
    face: int | None = None  # Placement face if specific, else auto-selected


class ConstructionPlan:
    """A blueprint of block placements with analysis and construction ordering."""

    def __init__(self, placements: list[BlockPlacement] | None = None) -> None:
        self.placements: list[BlockPlacement] = list(placements or [])

    def add(self, pos: BlockPos | tuple[int, int, int], block_name: str, face: int | None = None) -> ConstructionPlan:
        """Add a placement to this plan."""
        bp = pos if isinstance(pos, BlockPos) else BlockPos(*pos)
        self.placements.append(BlockPlacement(bp, block_name, face))
        return self

    def required_materials(self) -> dict[str, int]:
        """Return the count of each block item required for the plan."""
        counts: dict[str, int] = {}
        for p in self.placements:
            counts[p.block_name] = counts.get(p.block_name, 0) + 1
        return counts

    def validate_inventory(self, bot: LeafishBot) -> tuple[bool, dict[str, int]]:
        """Check if *bot*'s inventory contains enough materials.

        Returns ``(has_all_materials, missing_dict)``.
        """
        required = self.required_materials()
        inv_counts: dict[str, int] = {}
        if bot.inventory is not None:
            items = []
            res = bot.inventory.items() if callable(getattr(bot.inventory, "items", None)) else None
            if isinstance(res, list):
                items = res
            elif isinstance(getattr(bot.inventory, "slots", None), dict):
                items = list(bot.inventory.slots.values())
            elif isinstance(getattr(bot.inventory, "slots", None), (list, tuple)):
                items = [getattr(s, "item", s) for s in bot.inventory.slots]
            for item in items:
                if item and getattr(item, "name", None) and not getattr(item, "empty", False):
                    name = item.name
                    inv_counts[name] = inv_counts.get(name, 0) + item.count

        missing: dict[str, int] = {}
        for name, needed in required.items():
            have = inv_counts.get(name, 0)
            if have < needed:
                missing[name] = needed - have

        return len(missing) == 0, missing

    def order_for_construction(self) -> list[BlockPlacement]:
        """Order placements from bottom-up (Y ascending) so blocks have supports."""
        return sorted(self.placements, key=lambda p: (p.position.y, p.position.x, p.position.z))

    def __len__(self) -> int:
        return len(self.placements)

    # -- procedural construction shapes ---------------------------------------

    @classmethod
    def column(cls, start: BlockPos | tuple[int, int, int], height: int, block_name: str) -> ConstructionPlan:
        """Build a vertical column of *height* blocks."""
        base = start if isinstance(start, BlockPos) else BlockPos(*start)
        placements = [
            BlockPlacement(BlockPos(base.x, base.y + dy, base.z), block_name)
            for dy in range(height)
        ]
        return cls(placements)

    @classmethod
    def platform(
        cls,
        start: BlockPos | tuple[int, int, int],
        end: BlockPos | tuple[int, int, int],
        block_name: str,
    ) -> ConstructionPlan:
        """Build a flat horizontal platform between *start* and *end*."""
        s = start if isinstance(start, BlockPos) else BlockPos(*start)
        e = end if isinstance(end, BlockPos) else BlockPos(*end)
        min_x, max_x = min(s.x, e.x), max(s.x, e.x)
        min_z, max_z = min(s.z, e.z), max(s.z, e.z)
        y = s.y
        placements = [
            BlockPlacement(BlockPos(x, y, z), block_name)
            for x in range(min_x, max_x + 1)
            for z in range(min_z, max_z + 1)
        ]
        return cls(placements)

    @classmethod
    def wall(
        cls,
        start: BlockPos | tuple[int, int, int],
        end: BlockPos | tuple[int, int, int],
        height: int,
        block_name: str,
    ) -> ConstructionPlan:
        """Build a vertical wall between *start* and *end* of given *height*."""
        s = start if isinstance(start, BlockPos) else BlockPos(*start)
        e = end if isinstance(end, BlockPos) else BlockPos(*end)
        dx = e.x - s.x
        dz = e.z - s.z
        steps = max(abs(dx), abs(dz))
        positions = set()
        if steps == 0:
            positions.add((s.x, s.z))
        else:
            for i in range(steps + 1):
                t = i / float(steps)
                x = round(s.x + dx * t)
                z = round(s.z + dz * t)
                positions.add((x, z))

        placements = []
        for dy in range(height):
            y = s.y + dy
            for x, z in sorted(positions):
                placements.append(BlockPlacement(BlockPos(x, y, z), block_name))
        return cls(placements)

    @classmethod
    def box(
        cls,
        start: BlockPos | tuple[int, int, int],
        end: BlockPos | tuple[int, int, int],
        block_name: str,
        hollow: bool = True,
    ) -> ConstructionPlan:
        """Build a 3D rectangular box/structure, hollow or solid."""
        s = start if isinstance(start, BlockPos) else BlockPos(*start)
        e = end if isinstance(end, BlockPos) else BlockPos(*end)
        min_x, max_x = min(s.x, e.x), max(s.x, e.x)
        min_y, max_y = min(s.y, e.y), max(s.y, e.y)
        min_z, max_z = min(s.z, e.z), max(s.z, e.z)

        placements = []
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                for z in range(min_z, max_z + 1):
                    if hollow:
                        is_edge = (
                            x in (min_x, max_x)
                            or y in (min_y, max_y)
                            or z in (min_z, max_z)
                        )
                        if not is_edge:
                            continue
                    placements.append(BlockPlacement(BlockPos(x, y, z), block_name))
        return cls(placements)


class BuilderModule:
    """Construction execution engine."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self._building = False

    def plan_wall(
        self,
        start: BlockPos | tuple[int, int, int],
        end: BlockPos | tuple[int, int, int],
        height: int,
        block_name: str,
    ) -> ConstructionPlan:
        """Create a wall construction plan."""
        return ConstructionPlan.wall(start, end, height, block_name)

    def plan_platform(
        self,
        start: BlockPos | tuple[int, int, int],
        end: BlockPos | tuple[int, int, int],
        block_name: str,
    ) -> ConstructionPlan:
        """Create a platform construction plan."""
        return ConstructionPlan.platform(start, end, block_name)

    def plan_box(
        self,
        start: BlockPos | tuple[int, int, int],
        end: BlockPos | tuple[int, int, int],
        block_name: str,
        hollow: bool = True,
    ) -> ConstructionPlan:
        """Create a box construction plan."""
        return ConstructionPlan.box(start, end, block_name, hollow=hollow)

    def plan_column(
        self,
        start: BlockPos | tuple[int, int, int],
        height: int,
        block_name: str,
    ) -> ConstructionPlan:
        """Create a column construction plan."""
        return ConstructionPlan.column(start, height, block_name)

    def _find_reference_block(self, target: BlockPos) -> tuple[BlockPos, int] | None:
        """Find an adjacent solid block and face to place against."""
        world = self.bot.world
        # Check standard neighbors: below (place on top face 1), north, south, west, east, above
        neighbors = [
            (target.offset(0, -1, 0), 1),   # Block below: face up (1)
            (target.offset(0, 0, 1), 2),    # Block south: face north (2)
            (target.offset(0, 0, -1), 3),   # Block north: face south (3)
            (target.offset(1, 0, 0), 4),    # Block east: face west (4)
            (target.offset(-1, 0, 0), 5),   # Block west: face east (5)
            (target.offset(0, 1, 0), 0),    # Block above: face down (0)
        ]
        for ref_pos, face in neighbors:
            block = world.block_at(ref_pos)
            if block is not None and not block.is_air and not block.is_fluid:
                return ref_pos, face
        return None

    async def build(
        self,
        plan: ConstructionPlan,
        *,
        reach: float = 4.5,
        navigate: bool = True,
        check_materials: bool = True,
    ) -> bool:
        """Execute *plan*, placing blocks from bottom to top.

        Args:
            plan: The ConstructionPlan to execute.
            reach: Maximum placement distance in blocks.
            navigate: When True, uses pathfinding to walk in reach of targets.
            check_materials: When True, validates inventory before starting.

        Returns:
            ``True`` if all placements succeeded.
        """
        if self._building:
            raise LeafishError("Construction already in progress")

        if check_materials and self.bot.game_mode != "creative":
            has_mats, missing = plan.validate_inventory(self.bot)
            if not has_mats:
                missing_str = ", ".join(f"{k} x{v}" for k, v in missing.items())
                raise InventoryError(f"Missing required construction materials: {missing_str}")

        self._building = True
        self.bot.emit("build_started", plan)
        ordered = plan.order_for_construction()
        total = len(ordered)

        try:
            for i, placement in enumerate(ordered):
                target_pos = placement.position
                block_name = placement.block_name

                # Check if block is already placed
                existing = self.bot.world.block_at(target_pos)
                if existing is not None and existing.name == block_name:
                    self.bot.emit("build_progress", i + 1, total, target_pos, block_name)
                    continue

                # Ensure matching block item is held in main hand
                held = self.bot.inventory.held_item
                if held is None or held.name != block_name:
                    if self.bot.game_mode == "creative":
                        await self.bot.creative.set_slot(self.bot.inventory.held_slot + 36, block_name, count=64)
                    else:
                        await self.bot.equip(block_name, "hand")

                # Navigate in reach if needed
                entity = self.bot.entity
                if entity is not None and navigate:
                    dist = entity.position.distance_to(Vec3(target_pos.x + 0.5, target_pos.y + 0.5, target_pos.z + 0.5))
                    if dist > reach:
                        from ..pathfinder.goals import GoalNear
                        await self.bot.goto(
                            GoalNear(target_pos.x + 0.5, target_pos.y, target_pos.z + 0.5, range=max(1.0, reach - 1.0)),
                            timeout=10.0,
                        )

                # Locate solid reference neighbor
                ref = self._find_reference_block(target_pos)
                if ref is None:
                    # Place below target or directly against target if force
                    ref_pos = target_pos.offset(0, -1, 0)
                    face = placement.face if placement.face is not None else 1
                else:
                    ref_pos, face = ref
                    if placement.face is not None:
                        face = placement.face

                await self.bot.actions.place_block(ref_pos, face=face)
                self.bot.emit("build_progress", i + 1, total, target_pos, block_name)
                await asyncio.sleep(0.05)

            self.bot.emit("build_complete", plan)
            return True
        finally:
            self._building = False
