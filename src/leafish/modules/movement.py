"""Movement controls: look, look_at, move_to, control states."""

from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING

from ..utils.math import direction_to_yaw_pitch
from ..utils.vectors import Vec3

if TYPE_CHECKING:
    from ..bot import LeafishBot

CONTROL_STATES = {"forward", "backward", "left", "right", "jump", "sneak", "sprint"}


class MovementModule:
    """High-level movement API."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self._move_task: asyncio.Task | None = None
        self._move_target: Vec3 | None = None

    # -- rotation ---------------------------------------------------------------

    async def look(self, yaw: float, pitch: float, *, force: bool = False) -> None:
        """Set view direction. *yaw*/*pitch* in degrees."""
        entity = self.bot.entity
        if entity is None:
            return
        yaw = (yaw + 180.0) % 360.0 - 180.0
        pitch = max(-90.0, min(90.0, pitch))
        entity.set_rotation(yaw, pitch, head_yaw=yaw)
        flags = {
            "onGround": self.bot.physics.on_ground,
            "hasHorizontalCollision": False,
        }
        await self.bot._send_play(
            "look", {"yaw": yaw, "pitch": pitch, "flags": flags}
        )
        self.bot.emit("move")

    async def look_at(self, target, *, force: bool = False) -> None:
        """Look at a position or entity."""
        entity = self.bot.entity
        if entity is None:
            return
        point = target.position if hasattr(target, "position") else target
        dx = point.x - entity.position.x
        dy = point.y - entity.position.y
        dz = point.z - entity.position.z
        yaw, pitch = direction_to_yaw_pitch(dx, dy, dz)
        await self.look(yaw, pitch, force=force)

    # -- control states ------------------------------------------------------------

    async def set_control_state(self, control: str, value: bool) -> None:
        """Enable/disable a movement control (forward, jump, sprint, ...)."""
        if control not in CONTROL_STATES:
            raise ValueError(f"Unknown control state '{control}'")
        self.bot.control_states[control] = value
        await self._sync_sprint_state()

    async def _sync_sprint_state(self) -> None:
        """Notify the server of sprint state changes via entity_action."""
        sprinting = self.bot.control_states.get("sprint", False)
        if sprinting == getattr(self, "_was_sprinting", False):
            return
        self._was_sprinting = sprinting
        entity_id = self.bot.entity_id
        if entity_id is None:
            return
        await self.bot._send_play(
            "entity_action",
            {
                "entityId": entity_id,
                "actionId": "start_sprinting" if sprinting else "stop_sprinting",
                "jumpBoost": 0,
            },
        )

    # -- direct movement -------------------------------------------------------------

    async def move_to(self, target, timeout: float | None = None) -> None:
        """Walk toward *target* (Vec3 or entity) until within ~0.5 blocks.

        Uses control states + physics; replaced by the pathfinder for
        obstacle-aware navigation in a later phase.
        """
        entity = self.bot.entity
        if entity is None:
            return
        point = target.position if hasattr(target, "position") else target
        self._move_target = point
        if self._move_task is None or self._move_task.done():
            self._move_task = asyncio.create_task(self._walk_loop(point))
        try:
            await asyncio.wait_for(asyncio.shield(self._move_task), timeout)
        except TimeoutError:
            await self.stop_moving()
            raise

    async def _walk_loop(self, target: Vec3) -> None:
        entity = self.bot.entity
        while True:
            if entity is None or self._move_target is None:
                return
            pos = entity.position
            dx = target.x - pos.x
            dz = target.z - pos.z
            dist = math.hypot(dx, dz)
            dy = target.y - pos.y
            if dist < 0.6 and abs(dy) < 2.0:
                await self.stop_moving()
                return
            # Face the target.
            yaw = math.degrees(math.atan2(-dx, dz))
            pitch = -math.degrees(math.atan2(dy, dist)) if dist > 0.01 else 0.0
            await self.look(yaw, pitch)
            # Set control states toward target.
            forward = dist > 0.6
            await self.set_control_state("forward", forward)
            await self.set_control_state("sprint", dist > 4.0)
            await asyncio.sleep(0.1)

    async def stop_moving(self) -> None:
        """Stop all movement controls."""
        for control in CONTROL_STATES:
            if self.bot.control_states.get(control):
                await self.set_control_state(control, False)
        self._move_target = None
        if self._move_task is not None and not self._move_task.done():
            self._move_task.cancel()
