"""Viewport review overlay (P1-7): canonical ghost skeleton with confidence
colors, drawn over the scene while the "Pose review overlay" toggle is on.

Honest scope (v1): the handler draws the same FK chains the pose will drive
(core ``review.skeleton_segments``) anchored to the rig's origin, colored by
per-joint confidence bands (<0.55 red, <0.75 amber, else green). Image-plane
projection, joint picking, and per-flip toggling are the P1-11 polish pass;
the data side (``review_items``) is already the MCP/review contract.

Headless verification: ``xtask/verify_pose_apply.sh`` registers the handler,
builds the line data from a real payload, and attempts a GPUOffScreen draw —
a background Blender without a GPU context reports SKIPPED, never a fake pass.
"""
from __future__ import annotations

from typing import Any

#: confidence band -> (RGBA)
COLOR_LOW = (0.90, 0.25, 0.20, 1.0)
COLOR_MID = (0.95, 0.72, 0.20, 1.0)
COLOR_OK = (0.30, 0.85, 0.40, 1.0)

_draw_handle = None  # bpy handle from draw_handler_add


def color_for_conf(conf: float | None) -> tuple[float, float, float, float]:
    if conf is None:
        return COLOR_MID
    if conf < 0.55:
        return COLOR_LOW
    if conf < 0.75:
        return COLOR_MID
    return COLOR_OK


def line_data(pose: Any, segments: list[tuple[str, str]], scale: float, origin: tuple[float, float, float]) -> list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float, float]]]:
    """Segment world endpoints + color, ready for a gpu batch (pure math)."""
    out = []
    for parent, child in segments:
        p = pose.positions[parent]
        c = pose.positions[child]
        conf = pose.joint_confidence.get(child, pose.joint_confidence.get(parent))
        color = color_for_conf(conf)
        a = (origin[0] + p[0] * scale, origin[1] + p[1] * scale, origin[2] + p[2] * scale)
        b = (origin[0] + c[0] * scale, origin[1] + c[1] * scale, origin[2] + c[2] * scale)
        out.append((a, b, color))
    return out


def _anchor(context: Any) -> tuple[float, float, float, float]:
    """(origin, scale) for the ghost: rig origin + rig height / 1.82 units."""
    obj = context.active_object
    if obj is not None and obj.type == "ARMATURE":
        z = [v for b in obj.data.bones for v in (b.head_local[2], b.tail_local[2])]
        height = (max(z) - min(z)) if z else 1.7
        return (obj.location.x, obj.location.y, obj.location.z), max(height / 1.82, 1e-3)
    return (0.0, 0.0, 0.0), 1.0


def _draw_callback() -> None:
    import bpy
    import gpu
    from gpu_extras.batch import batch_for_shader

    context = bpy.context
    settings = getattr(context.scene, "rm_settings", None)
    if settings is None or not settings.overlay_enabled:
        return
    core = _core()
    if core is None:
        return
    pose = effective_pose(settings, core)
    if pose is None:
        return

    origin, scale = _anchor(context)
    segments = core.skeleton_segments(pose)
    data = line_data(pose, segments, scale, origin)
    if not data:
        return

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.line_width_set(3.0)
    for color in (COLOR_LOW, COLOR_MID, COLOR_OK):
        verts = [a for a, _b, c in data if c == color] + [b for _a, b, c in data if c == color]
        idx = [(i, i + 1) for i in range(0, len(verts), 2)]
        if not idx:
            continue
        batch = batch_for_shader(shader, "LINES", {"pos": verts}, indices=idx)
        shader.uniform_float("color", color)
        batch.draw(shader)
    gpu.state.line_width_set(1.0)

    # joint dots (P1-11): same confidence bands, drawn as POINTS so picks make sense
    points = core.joint_points(pose, origin=origin, scale=scale)
    gpu.state.point_size_set(7.0)
    for color in (COLOR_LOW, COLOR_MID, COLOR_OK):
        verts = [
            p for role, p in points.items()
            if color_for_conf(pose.joint_confidence.get(role)) == color
        ]
        if not verts:
            continue
        batch = batch_for_shader(shader, "POINTS", {"pos": verts})
        shader.uniform_float("color", color)
        batch.draw(shader)
    gpu.state.point_size_set(1.0)


def _core():
    try:
        import riggermortis as core

        return core
    except ImportError:
        return None


def _cached_pose(settings: Any):
    """Parse the payload's selected-figure pose once per (path, mtime); None when unavailable."""
    import json
    import os

    path = settings.payload_path
    if not path or not os.path.isfile(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        cache = getattr(_cached_pose, "_cache", None)
        if cache and cache[0] == path and cache[1] == mtime:
            return cache[2]
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        core = _core()
        if core is None:
            return None
        pose_dict = _payload_module().pose_for_figure(payload, None)
        pose = core.CanonicalPose.from_dict(pose_dict)
        if settings.mirror:
            pose = pose.mirrored()
        _cached_pose._cache = (path, mtime, pose)  # type: ignore[attr-defined]
        return pose
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def _payload_module() -> Any:
    import riggermortis.payload as payload_mod  # noqa: PLC0415

    return payload_mod


def effective_pose(settings: Any, core: Any) -> Any:
    """Cached pose with the session's manual flips composed (P1-11 review state).

    Cache key = (path, mtime, mirror, manual_flips): toggling a flip recomputes
    once, then draws stay cheap. None when no readable pose exists.
    """
    base = _cached_pose(settings)
    if base is None:
        return None
    flips = tuple(sorted(f for f in str(settings.manual_flips).split(",") if f))
    key = (settings.payload_path, _mtime_of(settings.payload_path), settings.mirror, flips)
    cache = getattr(effective_pose, "_cache", None)
    if cache and cache[0] == key:
        return cache[1]
    pose = base
    for flip in flips:
        pose = pose.toggled(flip)
    effective_pose._cache = (key, pose)  # type: ignore[attr-defined]
    return pose


def _mtime_of(path: str) -> float:
    import os

    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def register() -> None:
    global _draw_handle
    import bpy

    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback, (), "WINDOW", "POST_VIEW"
        )


def unregister() -> None:
    global _draw_handle
    import bpy

    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        _draw_handle = None
