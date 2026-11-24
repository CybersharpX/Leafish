
import pytest

from leafish.utils.geometry import BoundingBox, raycast_voxels
from leafish.utils.vectors import BlockPos, Vec3


def test_bounding_box_intersects():
    a = BoundingBox(0, 0, 0, 1, 1, 1)
    b = BoundingBox(0.5, 0.5, 0.5, 2, 2, 2)
    c = BoundingBox(5, 5, 5, 6, 6, 6)
    assert a.intersects(b)
    assert not a.intersects(c)


def test_bounding_box_contains():
    box = BoundingBox(0, 0, 0, 2, 2, 2)
    assert box.contains(Vec3(1, 1, 1))
    assert not box.contains(Vec3(3, 1, 1))


def test_raycast_voxels_hits_wall():
    # Solid plane at x=5
    solid = lambda p: p.x == 5  # noqa: E731
    hit = raycast_voxels(Vec3(0.5, 0.5, 0.5), Vec3(1, 0, 0), 20, solid)
    assert hit is not None
    assert hit.position == BlockPos(5, 0, 0)
    assert hit.face == (-1, 0, 0)


def test_raycast_voxels_miss():
    hit = raycast_voxels(Vec3(0.5, 0.5, 0.5), Vec3(0, 1, 0), 5, lambda p: False)
    assert hit is None


def test_ray_box_distance_hit_and_miss():
    from leafish.utils.geometry import ray_box_distance
    box = BoundingBox(2, -1, -1, 4, 1, 1)
    # Ray along +x from origin hits the box face at x=2 -> distance 2.
    t = ray_box_distance(Vec3(0, 0, 0), Vec3(1, 0, 0), box)
    assert t == pytest.approx(2.0)
    # Diagonal ray through the box.
    t2 = ray_box_distance(Vec3(0, 0, 0), Vec3(1, 0.5, 0).normalized, box)
    assert t2 is not None and t2 > 0
    # Ray passing above the box misses.
    assert ray_box_distance(Vec3(0, 5, 0), Vec3(1, 0, 0), box) is None
    # Origin inside the box counts as a hit at distance 0.
    assert ray_box_distance(Vec3(3, 0, 0), Vec3(1, 0, 0), box) == 0.0
