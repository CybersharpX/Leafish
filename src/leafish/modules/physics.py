"""Player physics: gravity, friction, jumping, collision and fluids.

The server remains authoritative — position corrections from ``position``
packets always win. Collision uses the loaded world: blocks whose
``bounding_box`` is ``"block"`` are treated as full cubes. Partial shapes
(slabs, stairs, fences) are refined later via ``blockCollisionShapes.json``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
from typing import TYPE_CHECKING

from ..utils.vectors import BlockPos, Vec3

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.physics")

TICK_RATE = 20.0
TICK_DT = 1.0 / TICK_RATE

GRAVITY = 0.08
TERMINAL_VELOCITY = 3.92
JUMP_VELOCITY = 0.42
WATER_GRAVITY = 0.02
WATER_DRAG = 0.8
LAVA_DRAG = 0.5
AIR_ACCEL = 0.02
GROUND_ACCEL = 0.1
GROUND_FRICTION = 0.6
SPRINT_MULTIPLIER = 1.3
SNEAK_MULTIPLIER = 0.3

PLAYER_HALF_WIDTH = 0.3
PLAYER_HEIGHT = 1.8
EYE_HEIGHT = 1.62


class PhysicsEngine:
    """Integrates player movement and emits position packets."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self.velocity = Vec3(0, 0, 0)
        self.on_ground = True
        self._tick_task: asyncio.Task | None = None
        self.horizontal_collision = False
        self.enabled = False

    # -- lifecycle ---------------------------------------------------------------

    def start(self) -> None:
        if self._tick_task is None or self._tick_task.done():
            self._tick_task = asyncio.create_task(self._tick_loop(), name="leafish-physics")

    async def stop(self) -> None:
        if self._tick_task is not None:
            self._tick_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tick_task
            self._tick_task = None

    # -- collision ---------------------------------------------------------------

    def _is_solid(self, pos: BlockPos) -> bool:
        block = self.bot.world.block_at(pos)
        if block is None:
            return False  # unloaded chunks don't block movement
        return block.bounding_box == "block"

    def _collides(self, pos: Vec3) -> bool:
        """Whether the player AABB at *pos* (feet position) overlaps solids."""
        min_x = pos.x - PLAYER_HALF_WIDTH
        max_x = pos.x + PLAYER_HALF_WIDTH
        min_y = pos.y
        max_y = pos.y + PLAYER_HEIGHT
        min_z = pos.z - PLAYER_HALF_WIDTH
        max_z = pos.z + PLAYER_HALF_WIDTH
        for bx in range(math.floor(min_x), math.floor(max_x) + 1):
            for by in range(math.floor(min_y), math.floor(max_y) + 1):
                for bz in range(math.floor(min_z), math.floor(max_z) + 1):
                    if not self._is_solid(BlockPos(bx, by, bz)):
                        continue
                    # Block AABB is the unit cube [bx,bx+1] etc.
                    if (min_x < bx + 1 and max_x > bx
                            and min_y < by + 1 and max_y > by
                            and min_z < bz + 1 and max_z > bz):
                        return True
        return False

    def _move_axis(self, pos: Vec3, axis: str, delta: float) -> tuple[Vec3, bool]:
        """Attempt to move *pos* along one axis; returns (new_pos, collided)."""
        if delta == 0:
            return pos, False
        if axis == "x":
            candidate = Vec3(pos.x + delta, pos.y, pos.z)
        elif axis == "y":
            candidate = Vec3(pos.x, pos.y + delta, pos.z)
        else:
            candidate = Vec3(pos.x, pos.y, pos.z + delta)
        if not self._collides(candidate):
            return candidate, False
        # Binary-search the largest fraction of the move that stays clear.
        lo, hi = 0.0, 1.0
        for _ in range(12):
            mid = (lo + hi) / 2.0
            probe = Vec3(
                pos.x + (candidate.x - pos.x) * mid,
                pos.y + (candidate.y - pos.y) * mid,
                pos.z + (candidate.z - pos.z) * mid,
            )
            if self._collides(probe):
                hi = mid
            else:
                lo = mid
        moved = Vec3(
            pos.x + (candidate.x - pos.x) * lo,
            pos.y + (candidate.y - pos.y) * lo,
            pos.z + (candidate.z - pos.z) * lo,
        )
        return moved, True

    def _in_fluid(self, pos: Vec3) -> str | None:
        feet = pos.floor()
        mid = BlockPos(feet.x, feet.y + 1, feet.z)
        for p in (feet, mid):
            block = self.bot.world.block_at(p)
            if block is not None and block.is_fluid:
                return "lava" if "lava" in (block.name or "") else "water"
        return None

    # -- per-tick update ------------------------------------------------------------

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_DT)
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Physics tick failed")

    async def tick(self) -> None:
        """Advance physics one tick and send movement if needed."""
        bot = self.bot
        entity = bot.entity
        if entity is None:
            return

        controls = bot.control_states
        yaw_rad = math.radians(entity.yaw)

        forward = (1.0 if controls.get("forward") else 0.0) - (
            1.0 if controls.get("backward") else 0.0
        )
        strafe = (1.0 if controls.get("right") else 0.0) - (
            1.0 if controls.get("left") else 0.0
        )

        sin_yaw = math.sin(yaw_rad)
        cos_yaw = math.cos(yaw_rad)
        wish_x = -sin_yaw * forward + cos_yaw * strafe
        wish_z = cos_yaw * forward + sin_yaw * strafe
        wish_len = math.hypot(wish_x, wish_z)
        if wish_len > 0:
            wish_x /= wish_len
            wish_z /= wish_len

        fluid = self._in_fluid(entity.position)
        speed = 0.1 * (0.6 if fluid else 1.0)
        if controls.get("sprint"):
            speed *= SPRINT_MULTIPLIER
        if controls.get("sneak"):
            speed *= SNEAK_MULTIPLIER

        accel = (GROUND_ACCEL if self.on_ground else AIR_ACCEL) * (0.4 if fluid else 1.0)
        if wish_len > 0:
            self.velocity = Vec3(
                self.velocity.x + wish_x * accel * speed * 10,
                self.velocity.y,
                self.velocity.z + wish_z * accel * speed * 10,
            )

        if self.on_ground:
            friction = GROUND_FRICTION * (0.4 if fluid else 1.0)
            self.velocity = Vec3(
                self.velocity.x * friction,
                self.velocity.y,
                self.velocity.z * friction,
            )

        if controls.get("jump") and self.on_ground:
            self.velocity = Vec3(self.velocity.x, JUMP_VELOCITY, self.velocity.z)
            self.on_ground = False

        gravity = WATER_GRAVITY if fluid == "water" else (
            WATER_GRAVITY * 0.5 if fluid == "lava" else GRAVITY
        )
        terminal = TERMINAL_VELOCITY * (0.4 if fluid else 1.0)
        self.velocity = Vec3(
            self.velocity.x,
            max(self.velocity.y - gravity, -terminal),
            self.velocity.z,
        )
        if fluid:
            drag = WATER_DRAG if fluid == "water" else LAVA_DRAG
            self.velocity = Vec3(
                self.velocity.x * drag, self.velocity.y * drag, self.velocity.z * drag
            )

        # Clamp horizontal speed.
        hs = math.hypot(self.velocity.x, self.velocity.z)
        max_speed = 0.28 * (SPRINT_MULTIPLIER if controls.get("sprint") else 1.0)
        if hs > max_speed:
            scale = max_speed / hs
            self.velocity = Vec3(
                self.velocity.x * scale, self.velocity.y, self.velocity.z * scale
            )

        # Axis-separated collision move.
        pos = entity.position
        self.horizontal_collision = False
        pos, hit_x = self._move_axis(pos, "x", self.velocity.x)
        pos, hit_z = self._move_axis(pos, "z", self.velocity.z)
        pos, hit_y = self._move_axis(pos, "y", self.velocity.y)
        if hit_x:
            self.velocity = Vec3(0, self.velocity.y, self.velocity.z)
            self.horizontal_collision = True
        if hit_z:
            self.velocity = Vec3(self.velocity.x, self.velocity.y, 0)
            self.horizontal_collision = True
        if hit_y:
            if self.velocity.y < 0:
                self.on_ground = True
            self.velocity = Vec3(self.velocity.x, 0, self.velocity.z)
        elif self.velocity.y != 0:
            self.on_ground = False

        entity.set_position(pos.x, pos.y, pos.z)
        entity.on_ground = self.on_ground
        entity.velocity = self.velocity

        flags = {
            "onGround": self.on_ground,
            "hasHorizontalCollision": self.horizontal_collision,
        }
        await bot._send_play(
            "position_look",
            {
                "x": pos.x,
                "y": pos.y,
                "z": pos.z,
                "yaw": entity.yaw,
                "pitch": entity.pitch,
                "flags": flags,
            },
        )
        bot.emit("physics_tick")
