import pytest

from leafish.utils.vectors import BlockPos, Vec3, chunk_coords


def test_vec3_arithmetic():
    a = Vec3(1, 2, 3)
    b = Vec3(4, 5, 6)
    assert a + b == Vec3(5, 7, 9)
    assert b - a == Vec3(3, 3, 3)
    assert a * 2 == Vec3(2, 4, 6)
    assert a / 2 == Vec3(0.5, 1.0, 1.5)
    assert -a == Vec3(-1, -2, -3)


def test_vec3_length_and_distance():
    v = Vec3(3, 4, 0)
    assert v.length == pytest.approx(5.0)
    assert Vec3(0, 0, 0).distance_to(Vec3(1, 2, 2)) == pytest.approx(3.0)


def test_vec3_normalized():
    v = Vec3(0, 0, 10).normalized
    assert v == Vec3(0, 0, 1)
    assert Vec3(0, 0, 0).normalized.length == 0


def test_vec3_dot_cross():
    a = Vec3(1, 0, 0)
    b = Vec3(0, 1, 0)
    assert a.dot(b) == 0
    assert a.cross(b) == Vec3(0, 0, 1)


def test_vec3_floor_and_offset():
    v = Vec3(1.9, -0.5, 3.2)
    assert v.floor() == BlockPos(1, -1, 3)
    assert v.offset(1, 1, 1) == Vec3(2.9, 0.5, 4.2)


def test_blockpos():
    p = BlockPos(1, 2, 3)
    assert p.offset(1, -1, 0) == BlockPos(2, 1, 3)
    assert p.vec3 == Vec3(1.5, 2.5, 3.5)
    assert tuple(p) == (1, 2, 3)
    assert BlockPos(0, 0, 0).distance_squared_to(BlockPos(1, 2, 2)) == 9


def test_chunk_coords():
    assert chunk_coords(BlockPos(15, 0, 15)) == (0, 0)
    assert chunk_coords(BlockPos(16, 0, -1)) == (1, -1)
    assert chunk_coords(Vec3(15.9, 0, 0)) == (0, 0)
    assert chunk_coords(Vec3(16.0, 0, 0)) == (1, 0)
