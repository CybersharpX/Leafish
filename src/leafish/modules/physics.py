"""Minimal player physics for Phase 3.

Models gravity, friction, jumping and the basic control states. It is
deliberately simple: collision detection against the world arrives with the
full physics module in a later phase. The server remains authoritative —
position corrections from ``position`` packets always win.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
from typing import TYPE_CHECKING

from ..utils.vectors import Vec3

if TYPE_CHECKING:
    from ..bot import LeafishBot

TICK_RATE = 20.0
TICK_DT = 1.0 / TICK_RATE

GRAVITY = 0.08
TERMINAL_VELOCITY = 3.92
JUMP_VELOCITY = 0.42
WATER_GRAVITY = 0.02
WATER_DRAG = 0.8
AIR_ACCEL = 0.02
GROUND_ACCEL = 0.1
GROUND_FRICTION = 0.6
SPRINT_MULTIPLIER = 1.3
SNEAK_MULTIPLIER = 0.3


class PhysicsEngine:
    """Integrates player movement and emits position packets."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self.velocity = Vec3(0, 0, 0)
        self.on_ground = True
        self._tick_task: asyncio.Task | None = None
        self._pending_position: Vec3 | None = None
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

    # -- per-tick update ------------------------------------------------------------

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_DT)
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                import logging

                logging.getLogger("leafish.physics").exception("Physics tick failed")

    async def tick(self) -> None:
        """Advance physics one tick and send movement if needed."""
        bot = self.bot
        entity = bot.entity
        if entity is None:
            return

        controls = bot.control_states
        yaw_rad = math.radians(entity.yaw)

        # Wish direction from control states.
        forward = (1.0 if controls.get("forward") else 0.0) - (
            1.0 if controls.get("backward") else 0.0
        )
        strafe = (1.0 if controls.get("right") else 0.0) - (
            1.0 if controls.get("left") else 0.0
        )

        sin_yaw = math.sin(yaw_rad)
        cos_yaw = math.cos(yaw_rad)
        # Minecraft yaw=0 faces +Z; forward is (-sin(yaw), 0, cos(yaw)).
        wish_x = -sin_yaw * forward + cos_yaw * strafe
        wish_z = cos_yaw * forward + sin_yaw * strafe
        wish_len = math.hypot(wish_x, wish_z)
        if wish_len > 0:
            wish_x /= wish_len
            wish_z /= wish_len

        speed = 0.1
        if controls.get("sprint"):
            speed *= SPRINT_MULTIPLIER
        if controls.get("sneak"):
            speed *= SNEAK_MULTIPLIER

        accel = GROUND_ACCEL if self.on_ground else AIR_ACCEL
        if wish_len > 0:
            self.velocity = Vec3(
                self.velocity.x + wish_x * accel * speed * 10,
                self.velocity.y,
                self.velocity.z + wish_z * accel * speed * 10,
            )

        # Friction on ground.
        if self.on_ground:
            self.velocity = Vec3(
                self.velocity.x * GROUND_FRICTION,
                self.velocity.y,
                self.velocity.z * GROUND_FRICTION,
            )

        # Jump & gravity.
        if controls.get("jump") and self.on_ground:
            self.velocity = Vec3(self.velocity.x, JUMP_VELOCITY, self.velocity.z)
            self.on_ground = False
        self.velocity = Vec3(
            self.velocity.x,
            max(self.velocity.y - GRAVITY, -TERMINAL_VELOCITY),
            self.velocity.z,
        )

        # Clamp horizontal speed (simplified).
        hs = math.hypot(self.velocity.x, self.velocity.z)
        max_speed = 0.28 * (SPRINT_MULTIPLIER if controls.get("sprint") else 1.0)
        if hs > max_speed:
            scale = max_speed / hs
            self.velocity = Vec3(
                self.velocity.x * scale, self.velocity.y, self.velocity.z * scale
            )

        new_pos = entity.position + self.velocity
        entity.set_position(new_pos.x, new_pos.y, new_pos.z)

        # Send movement packet (position + rotation).
        flags = {"onGround": self.on_ground, "hasHorizontalCollision": False}
        await bot._send_play(
            "position_look",
            {
                "x": new_pos.x,
                "y": new_pos.y,
                "z": new_pos.z,
                "yaw": entity.yaw,
                "pitch": entity.pitch,
                "flags": flags,
            },
        )
        bot.emit("physics_tick")
