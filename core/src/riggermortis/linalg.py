"""Minimal pure-stdlib 3D vector helpers.

The core engine stays dependency-free through Phase 0; numpy arrives with the
ONNX pose-estimation modules in Phase 1. Vectors are plain ``(x, y, z)`` tuples
in Blender world convention: Z up, characters face -Y, so a character's left
side is +X.
"""
from __future__ import annotations

import math

Vec3 = tuple[float, float, float]

X = (1.0, 0.0, 0.0)
Y = (0.0, 1.0, 0.0)
Z = (0.0, 0.0, 1.0)
ZERO = (0.0, 0.0, 0.0)


def v_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def v_len(a: Vec3) -> float:
    return math.sqrt(v_dot(a, a))


def v_dist(a: Vec3, b: Vec3) -> float:
    return v_len(v_sub(a, b))


def v_norm(a: Vec3) -> Vec3:
    n = v_len(a)
    if n <= 1e-12:
        return ZERO
    return (a[0] / n, a[1] / n, a[2] / n)


def mid(a: Vec3, b: Vec3) -> Vec3:
    return v_scale(v_add(a, b), 0.5)


def dominant_axis(a: Vec3) -> str:
    ax, ay, az = abs(a[0]), abs(a[1]), abs(a[2])
    if ax >= ay and ax >= az:
        return "x"
    if ay >= az:
        return "y"
    return "z"


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))
