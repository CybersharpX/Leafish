"""Math helpers for gameplay calculations."""

from __future__ import annotations

import math


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def angle_diff(a: float, b: float) -> float:
    """Smallest signed difference between two angles in degrees, in [-180, 180]."""
    return (a - b + 180.0) % 360.0 - 180.0


def yaw_pitch_to_direction(yaw: float, pitch: float) -> tuple[float, float, float]:
    """Convert Minecraft yaw/pitch (degrees) to a unit direction vector."""
    yaw_rad = math.radians(yaw)
    pitch_rad = math.radians(pitch)
    x = -math.sin(yaw_rad) * math.cos(pitch_rad)
    y = -math.sin(pitch_rad)
    z = math.cos(yaw_rad) * math.cos(pitch_rad)
    return x, y, z


def direction_to_yaw_pitch(dx: float, dy: float, dz: float) -> tuple[float, float]:
    """Convert a direction vector to Minecraft yaw/pitch in degrees."""
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length == 0:
        return 0.0, 0.0
    yaw = math.degrees(math.atan2(-dx, dz))
    pitch = math.degrees(-math.asin(clamp(dy / length, -1.0, 1.0)))
    return yaw, pitch
