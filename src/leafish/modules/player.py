"""Player-state actions: respawn, sleep, vehicles, elytra."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ..exceptions import LeafishError, MovementError

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.player")


class PlayerModule:
    """High-level actions tied to the player entity itself."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self._sleeping = False
        self.vehicle: Any = None
        """The entity the bot is currently riding, if any."""

    # -- respawn ------------------------------------------------------------------

    async def respawn(self) -> None:
        """Request respawn after death (client_command perform_respawn)."""
        await self.bot._send_play(
            "client_command", {"actionId": "perform_respawn"}
        )
        self._sleeping = False
        self.bot.emit("respawn_request")

    # -- sleeping -----------------------------------------------------------------

    async def sleep(self, bed_block) -> None:
        """Right-click *bed_block* to sleep. Returns after the interact
        packet is sent; the server decides whether sleep actually starts."""
        await self.bot.interact_block(bed_block)
        # Optimistic flag; cleared on wake/damage/respawn.
        self._sleeping = True
        self.bot.emit("sleep")

    async def wake(self) -> None:
        """Stop sleeping (entity_action stop_sleeping)."""
        entity_id = self.bot.entity_id
        if entity_id is not None:
            await self.bot._send_play(
                "entity_action",
                {"entityId": entity_id, "actionId": "stop_sleeping",
                 "jumpBoost": 0},
            )
        self._sleeping = False
        self.bot.emit("wake")

    @property
    def is_abed(self) -> bool:
        """Whether the bot believes it is sleeping."""
        return self._sleeping

    # -- elytra --------------------------------------------------------------------

    async def elytra_fly(self) -> None:
        """Start elytra flight (entity_action start_fall_flying).

        Requires the bot to be airborne with elytra equipped; the server
        validates the actual preconditions.
        """
        entity_id = self.bot.entity_id
        if entity_id is None:
            raise MovementError("Bot has no entity id")
        await self.bot._send_play(
            "entity_action",
            {"entityId": entity_id, "actionId": "start_fall_flying",
             "jumpBoost": 0},
        )
        self.bot.emit("elytra_start")

    # -- vehicles -------------------------------------------------------------------

    async def mount(self, entity) -> None:
        """Mount *entity* (right-click a boat/minecart/horse/...)."""
        if entity is None:
            raise LeafishError("mount() requires an entity")
        await self.bot.actions.use_on(entity)
        self.vehicle = entity
        self.bot.emit("mount", entity)

    async def dismount(self) -> None:
        """Dismount the current vehicle.

        Sends a sneak (shift) input pulse, which is how the vanilla
        client signals dismount while riding.
        """
        if self.vehicle is None:
            return
        await self._send_inputs(sneak=True)
        await asyncio.sleep(0.05)
        await self._send_inputs(sneak=False)
        self.vehicle = None
        self.bot.emit("dismount")

    async def move_vehicle(self, left: float = 0.0, forward: float = 0.0) -> None:
        """Steer the mounted vehicle.

        Boats receive ``steer_boat`` paddle input; other vehicles get a
        ``vehicle_move`` position update is *not* sent (the server drives
        vehicle position). *left*/*forward* are -1..1.
        """
        if self.vehicle is None:
            raise MovementError("Bot is not riding a vehicle")
        vtype = self.vehicle.type
        name = vtype if isinstance(vtype, str) else ""
        if "boat" in name:
            await self.bot._send_play(
                "steer_boat",
                {
                    "leftPaddle": left < -0.5,
                    "rightPaddle": left > 0.5,
                },
            )
            # forward paddle is encoded via a second steer packet only in
            # older protocols; modern steer_boat has two paddles for
            # turning. Movement forward is implicit while paddling.
        else:
            # Horses/other mounts steer through player_input jump/forward.
            await self._send_inputs(
                forward=forward > 0.5, sneak=forward < -0.5
            )

    async def _send_inputs(self, *, sneak: bool = False,
                           forward: bool = False) -> None:
        """Send a ``player_input`` packet reflecting control states."""
        controls = self.bot.control_states
        inputs = {
            "forward": bool(controls.get("forward")) or forward,
            "backward": bool(controls.get("backward")),
            "left": bool(controls.get("left")),
            "right": bool(controls.get("right")),
            "jump": bool(controls.get("jump")),
            "shift": bool(controls.get("sneak")) or sneak,
            "sprint": bool(controls.get("sprint")),
        }
        await self.bot._send_play("player_input", {"inputs": inputs})
