"""3D vector and position types."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Vec3:
    """An immutable 3-component vector (x, y, z)."""

    x: float
    y: float
    z: float

    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vec3:
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> Vec3:
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)

    def __neg__(self) -> Vec3:
        return Vec3(-self.x, -self.y, -self.z)

    @property
    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    @property
    def length_squared(self) -> float:
        return self.x * self.x + self.y * self.y + self.z * self.z

    @property
    def normalized(self) -> Vec3:
        length = self.length
        if length == 0:
            return Vec3(0.0, 0.0, 0.0)
        return self / length

    def dot(self, other: Vec3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vec3) -> Vec3:
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def distance_to(self, other: Vec3) -> float:
        return (self - other).length

    def distance_squared_to(self, other: Vec3) -> float:
        return (self - other).length_squared

    def distance_to_block(self, other: Vec3) -> float:
        """Distance between block centers of the blocks containing these points."""
        return self.floor().distance_to(other.floor())

    def floor(self) -> BlockPos:
        return BlockPos(math.floor(self.x), math.floor(self.y), math.floor(self.z))

    def offset(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> Vec3:
        return Vec3(self.x + dx, self.y + dy, self.z + dz)

    def yaw_pitch(self) -> tuple[float, float]:
        """Return (yaw, pitch) in degrees looking from this point toward origin-free usage.

        Computes the rotation needed to look *at* the origin from this vector's
        perspective is unusual; this helper returns yaw/pitch of the vector itself.
        """
        yaw = math.degrees(math.atan2(-self.x, self.z))
        pitch = math.degrees(-math.asin(max(-1.0, min(1.0, self.y / max(self.length, 1e-9)))))
        return yaw, pitch


@dataclass(frozen=True)
class Vec2:
    """An immutable 2-component vector."""

    x: float
    y: float

    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    @property
    def length(self) -> float:
        return math.hypot(self.x, self.y)


@dataclass(frozen=True)
class BlockPos:
    """An integer block position."""

    x: int
    y: int
    z: int

    def __add__(self, other: BlockPos) -> BlockPos:
        return BlockPos(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: BlockPos) -> BlockPos:
        return BlockPos(self.x - other.x, self.y - other.y, self.z - other.z)

    def offset(self, dx: int = 0, dy: int = 0, dz: int = 0) -> BlockPos:
        return BlockPos(self.x + dx, self.y + dy, self.z + dz)

    @property
    def vec3(self) -> Vec3:
        """Center of this block as a Vec3."""
        return Vec3(self.x + 0.5, self.y + 0.5, self.z + 0.5)

    def distance_to(self, other: BlockPos) -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        )

    def distance_squared_to(self, other: BlockPos) -> int:
        return (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def to_tuple(self) -> tuple[int, int, int]:
        return (self.x, self.y, self.z)


def chunk_coords(pos: BlockPos | Vec3, chunk_shift: int = 4) -> tuple[int, int]:
    """Return the (chunk_x, chunk_z) containing *pos* (16 blocks per chunk)."""
    x = math.floor(pos.x / 16) if isinstance(pos, Vec3) else pos.x >> chunk_shift
    z = math.floor(pos.z / 16) if isinstance(pos, Vec3) else pos.z >> chunk_shift
    return x, z
