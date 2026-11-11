"""Block model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utils.vectors import BlockPos


@dataclass
class Block:
    """A block in the world at a specific position."""

    state_id: int
    """Global block-state id (palette index on the wire)."""

    block_id: int
    """Block type id within the block registry."""

    name: str
    position: BlockPos

    hardness: float = 0.0
    diggable: bool = False
    material: str | None = None
    transparent: bool = False
    emit_light: int = 0
    filter_light: int = 0
    bounding_box: str = "block"
    states: list[dict] = field(default_factory=list)
    state_properties: dict[str, Any] = field(default_factory=dict)
    block_entity: dict | None = None

    @property
    def hardness_seconds(self) -> float:
        """Approximate bare-hand dig time in seconds."""
        if self.hardness <= 0:
            return 0.0
        if self.hardness < 0:
            return float("inf")
        return self.hardness * 1.5

    @property
    def is_air(self) -> bool:
        return self.name == "air"

    @property
    def is_fluid(self) -> bool:
        return self.name in ("water", "lava") or "water" in self.name or "lava" in self.name

    def property(self, name: str, default=None):
        return self.state_properties.get(name, default)

    def __repr__(self) -> str:
        props = ""
        if self.state_properties:
            props = "[" + ",".join(f"{k}={v}" for k, v in self.state_properties.items()) + "]"
        return f"Block({self.name}{props} @ {self.position})"
