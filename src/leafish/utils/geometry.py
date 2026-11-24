"""Geometric helpers: bounding boxes and raycasting."""

from __future__ import annotations

from dataclasses import dataclass

from .vectors import BlockPos, Vec3


@dataclass(frozen=True)
class BoundingBox:
    """An axis-aligned bounding box."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @classmethod
    def from_points(cls, a: Vec3, b: Vec3) -> BoundingBox:
        return cls(
            min(a.x, b.x), min(a.y, b.y), min(a.z, b.z),
            max(a.x, b.x), max(a.y, b.y), max(a.z, b.z),
        )

    @classmethod
    def unit(cls) -> BoundingBox:
        """The unit cube at the origin, used for player-sized entities."""
        return cls(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)

    def offset(self, x: float, y: float, z: float) -> BoundingBox:
        return BoundingBox(
            self.min_x + x, self.min_y + y, self.min_z + z,
            self.max_x + x, self.max_y + y, self.max_z + z,
        )

    def intersects(self, other: BoundingBox) -> bool:
        return not (
            self.max_x <= other.min_x
            or self.min_x >= other.max_x
            or self.max_y <= other.min_y
            or self.min_y >= other.max_y
            or self.max_z <= other.min_z
            or self.min_z >= other.max_z
        )

    def contains(self, point: Vec3) -> bool:
        return (
            self.min_x <= point.x <= self.max_x
            and self.min_y <= point.y <= self.max_y
            and self.min_z <= point.z <= self.max_z
        )


@dataclass(frozen=True)
class RaycastHit:
    """Result of a voxel raycast."""

    position: BlockPos
    """The block position that was hit."""

    face: tuple[int, int, int]
    """The face normal of the hit block, e.g. ``(0, 1, 0)`` for top."""

    previous: BlockPos | None = None
    """The last free position before the hit (useful for placement)."""


def ray_box_distance(
    origin: Vec3,
    direction: Vec3,
    box: BoundingBox,
) -> float | None:
    """Distance along unit *direction* to the entry point of *box*.

    Returns ``None`` when the ray misses the box. *direction* is
    normalized internally, so the result is in world units.
    """
    direction = direction.normalized
    t_min = 0.0
    t_max = float("inf")
    for o, d, lo, hi in (
        (origin.x, direction.x, box.min_x, box.max_x),
        (origin.y, direction.y, box.min_y, box.max_y),
        (origin.z, direction.z, box.min_z, box.max_z),
    ):
        if d == 0:
            if o < lo or o > hi:
                return None
            continue
        t1 = (lo - o) / d
        t2 = (hi - o) / d
        if t1 > t2:
            t1, t2 = t2, t1
        t_min = max(t_min, t1)
        t_max = min(t_max, t2)
        if t_min > t_max:
            return None
    return max(t_min, 0.0) if t_max >= 0 else None


def raycast_voxels(
    origin: Vec3,
    direction: Vec3,
    max_distance: float,
    is_solid,
) -> RaycastHit | None:
    """Amanatides & Woo voxel traversal.

    Args:
        origin: Ray origin.
        direction: Ray direction (will be normalized).
        max_distance: Maximum distance to travel.
        is_solid: Callable ``(BlockPos) -> bool`` telling whether a block blocks rays.

    Returns:
        The first solid block hit, or ``None``.
    """
    direction = direction.normalized
    x, y, z = origin.x, origin.y, origin.z
    dx, dy, dz = direction.x, direction.y, direction.z

    block_x, block_y, block_z = int(x // 1), int(y // 1), int(z // 1)

    step_x = 1 if dx > 0 else -1 if dx < 0 else 0
    step_y = 1 if dy > 0 else -1 if dy < 0 else 0
    step_z = 1 if dz > 0 else -1 if dz < 0 else 0

    # Distance along the ray to the first voxel boundary on each axis.
    def _t_max(axis_pos: float, d: float, step: int) -> float:
        if d == 0:
            return float("inf")
        boundary = int(axis_pos // 1) + 1 if step > 0 else int(axis_pos // 1)
        return (boundary - axis_pos) / d

    t_max_x = _t_max(x, dx, step_x)
    t_max_y = _t_max(y, dy, step_y)
    t_max_z = _t_max(z, dz, step_z)

    # Distance between voxel boundary crossings on each axis.
    t_delta_x = abs(1.0 / dx) if dx != 0 else float("inf")
    t_delta_y = abs(1.0 / dy) if dy != 0 else float("inf")
    t_delta_z = abs(1.0 / dz) if dz != 0 else float("inf")

    t = 0.0
    last_free: BlockPos | None = None
    face = (0, 0, 0)

    while t <= max_distance:
        pos = BlockPos(block_x, block_y, block_z)
        if is_solid(pos):
            return RaycastHit(position=pos, face=face, previous=last_free)
        last_free = pos

        if t_max_x < t_max_y and t_max_x < t_max_z:
            block_x += step_x
            t = t_max_x
            t_max_x += t_delta_x
            face = (-step_x, 0, 0)
        elif t_max_y < t_max_z:
            block_y += step_y
            t = t_max_y
            t_max_y += t_delta_y
            face = (0, -step_y, 0)
        else:
            block_z += step_z
            t = t_max_z
            t_max_z += t_delta_z
            face = (0, 0, -step_z)

    return None
