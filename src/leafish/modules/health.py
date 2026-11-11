"""Health, hunger, experience and respawn handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..bot import LeafishBot


class HealthModule:
    """Tracks player vitals from server packets."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self.health: float = 20.0
        self.food: int = 20
        self.food_saturation: float = 5.0
        self.experience_level: int = 0
        self.experience_progress: float = 0.0
        self.experience_total: int = 0

    def update_health(self, params: dict) -> None:
        self.health = float(params.get("health", self.health))
        self.food = int(params.get("food", self.food))
        self.food_saturation = float(params.get("foodSaturation", self.food_saturation))

    def update_experience(self, params: dict) -> None:
        self.experience_progress = float(params.get("experienceBar", 0.0))
        self.experience_level = int(params.get("level", 0))
        self.experience_total = int(params.get("totalExperience", 0))
