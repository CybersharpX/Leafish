import pytest

from leafish.utils.math import (
    angle_diff,
    clamp,
    direction_to_yaw_pitch,
    lerp,
    yaw_pitch_to_direction,
)


def test_clamp_lerp():
    assert clamp(5, 0, 3) == 3
    assert clamp(-1, 0, 3) == 0
    assert lerp(0, 10, 0.5) == 5


def test_angle_diff():
    assert angle_diff(10, 350) == 20
    assert angle_diff(350, 10) == -20
    assert angle_diff(0, 180) == -180 or angle_diff(0, 180) == 180


def test_yaw_pitch_roundtrip():
    for yaw, pitch in [(0, 0), (45, -30), (-120, 60), (270, 89)]:
        dx, dy, dz = yaw_pitch_to_direction(yaw, pitch)
        y2, p2 = direction_to_yaw_pitch(dx, dy, dz)
        assert angle_diff(y2, yaw) == pytest.approx(0, abs=1e-6)
        assert p2 == pytest.approx(pitch, abs=1e-6)
