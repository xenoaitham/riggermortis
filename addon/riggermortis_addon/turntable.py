"""Turntable rendering for live sessions (P3-7) — the staging capability.

Session-side twin of the xtask staging (``xtask/render_demos.py`` + the FLAT
world lessons of ``xtask/walk_media.py``): a real user's Blender has only the
add-on on ``sys.path``, so the ``render_turntable`` session action carries its
own copy of the bone-proxy visualizer and scene staging here.

The honest-visualizer rules (S9 lessons, do not reintroduce):

- Armature bones are viewport overlays and DO NOT render — the proxy is one
  mesh of octahedrons in vertex groups named after their bones, driven by an
  armature modifier, built over the MAPPED bones (unmapped rest bones are
  static clutter) composed through the armature's ``matrix_world`` (imported
  rigs carry object scale — an armature-space proxy is a giant the camera
  sits inside).
- Workbench + FLAT unlit shading + an explicit background world: the
  STUDIO/sun setup silhouettes the figure from some orbit angles, and glTF
  imports can carry a black world that swallows the frame entirely.

Side-effect discipline: everything the render creates (proxy, camera, world)
is removed again and every scene setting it touches is restored — the
rendered PNGs and the report are the only residue. GIF assembly stays
OUTSIDE Blender (shell glue, media rule).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

MIN_FRAMES, MAX_FRAMES = 2, 120
MIN_SIZE, MAX_SIZE = 16, 4096
PROXY_NAME = "rm_session_proxy"
CAM_NAME = "rm_session_cam"
WORLD_NAME = "rm_session_world"
DEFAULT_COLOR = (0.53, 0.66, 0.72)  # the walk-media "locked" blue-grey


def safe_out_dir(raw: str) -> Path:
    """Confine the output root to the Blender cwd or the temp dir (no ``..``)."""
    path = Path(raw).expanduser()
    if any(part == os.pardir for part in path.parts):
        raise ValueError(
            f"out_dir must not contain {os.pardir!r} segments: {raw!r} "
            "(hint: pass an absolute path inside the project or temp dir)"
        )
    resolved = path.resolve()
    allowed = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(resolved == base or base in resolved.parents for base in allowed):
        raise ValueError(
            f"out_dir must be inside the Blender cwd or the system temp dir: "
            f"{raw!r} (cwd: {allowed[0]})"
        )
    return resolved


def _add_proxy(armature: Any, bone_names: set[str]) -> Any:
    """One octahedron-per-bone mesh over ``bone_names``, world-composed."""
    import bpy
    from mathutils import Vector

    verts: list[Vector] = []
    faces: list[tuple[int, ...]] = []
    groups: list[tuple[str, int, int]] = []
    mw = armature.matrix_world
    for bone in armature.data.bones:
        if bone.name not in bone_names:
            continue
        h = mw @ Vector(bone.head_local)
        t = mw @ Vector(bone.tail_local)
        length = (t - h).length
        if length <= 1e-9:
            continue
        u = (t - h) / length
        ref = Vector((0.0, 0.0, 1.0)) if abs(u.z) < 0.9 else Vector((1.0, 0.0, 0.0))
        w = u.cross(ref).normalized()
        v = u.cross(w).normalized()
        ring_c = h + u * (0.15 * length)
        r = 0.08 * length
        base = len(verts)
        verts.extend(
            (h, t, ring_c + w * r, ring_c - w * r, ring_c + v * r, ring_c - v * r)
        )
        faces.extend(
            (
                (base, base + 2, base + 3), (base, base + 3, base + 4),
                (base, base + 4, base + 5), (base, base + 5, base + 2),
                (base + 1, base + 3, base + 2), (base + 1, base + 4, base + 3),
                (base + 1, base + 5, base + 4), (base + 1, base + 2, base + 5),
            )
        )
        groups.append((bone.name, base, base + 6))

    mesh = bpy.data.meshes.new(PROXY_NAME)
    mesh.from_pydata([tuple(p) for p in verts], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(PROXY_NAME, mesh)
    bpy.context.collection.objects.link(obj)
    for name, start, end in groups:
        group = obj.vertex_groups.new(name=name)
        group.add(list(range(start, end)), 1.0, "REPLACE")
    modifier = obj.modifiers.new("rm_session_armature", type="ARMATURE")
    modifier.object = armature
    modifier.use_bone_envelopes = False
    modifier.use_vertex_groups = True
    return obj


def render_turntable(
    armature: Any,
    bone_names: set[str],
    out_dir: Path,
    *,
    frames: int = 24,
    width: int = 640,
    height: int = 480,
    play_action: bool = True,
    prefix: str = "turn",
) -> dict[str, Any]:
    """Orbit the armature's deformed proxy and render PNGs; nothing left behind.

    With ``play_action`` and an action on the armature, orbit step i also
    advances the scene frame cyclically through the action's range (the
    launch-GIF shot: walk-in-place while the camera comes around).
    """
    import math

    import bpy
    from mathutils import Vector

    if armature.type != "ARMATURE":
        raise ValueError(f"{armature.name!r} is not an armature")
    if not MIN_FRAMES <= frames <= MAX_FRAMES:
        raise ValueError(
            f"frames must be in {MIN_FRAMES}..{MAX_FRAMES} (got {frames})"
        )
    if not MIN_SIZE <= width <= MAX_SIZE or not MIN_SIZE <= height <= MAX_SIZE:
        raise ValueError(
            f"width/height must be in {MIN_SIZE}..{MAX_SIZE} "
            f"(got {width}x{height})"
        )
    if not bone_names:
        raise ValueError(
            "no mapped bones to visualize (hint: run inspect&map or "
            "apply_pose first — the proxy shows the mapped bone set)"
        )

    action = armature.animation_data.action if armature.animation_data else None
    played = False
    frame_start, span = 1, 0
    if play_action and action is not None:
        frange = action.frame_range  # works pre-5.x and on 5.x slotted actions
        frame_start = int(round(frange[0]))
        span = int(round(frange[1] - frange[0])) + 1
        played = span >= 2

    scene = bpy.context.scene
    saved = {
        "engine": scene.render.engine,
        "res_x": scene.render.resolution_x,
        "res_y": scene.render.resolution_y,
        "filepath": scene.render.filepath,
        "film": scene.render.film_transparent,
        "shading_light": scene.display.shading.light,
        "color_type": scene.display.shading.color_type,
        "single_color": tuple(scene.display.shading.single_color),
        "bg_type": scene.display.shading.background_type,
        "world": scene.world,
        "camera": scene.camera,
        "frame": scene.frame_current,
        "hidden": {
            obj.name: obj.hide_render
            for obj in scene.objects if obj.type not in {"ARMATURE", "CAMERA"}
        },
    }
    created: list[Any] = []
    created_worlds: list[Any] = []

    try:
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.film_transparent = False
        scene.render.image_settings.file_format = "PNG"
        # FLAT unlit shading + explicit world (S9): deterministic, no
        # silhouette angles, no swallowed frames from imported worlds.
        scene.display.shading.light = "FLAT"
        scene.display.shading.color_type = "SINGLE"
        scene.display.shading.single_color = DEFAULT_COLOR
        scene.display.shading.background_type = "WORLD"
        world = bpy.data.worlds.new(WORLD_NAME)
        world.use_nodes = False
        world.color = (0.055, 0.055, 0.06)
        scene.world = world
        created_worlds.append(world)

        for obj in scene.objects:
            if obj.type not in {"ARMATURE", "CAMERA"}:
                obj.hide_render = True  # imported meshes: the proxy is the visual

        proxy = _add_proxy(armature, set(bone_names))
        created.append(proxy)

        cam_data = bpy.data.cameras.new(CAM_NAME)
        cam_data.lens = 45
        cam = bpy.data.objects.new(CAM_NAME, cam_data)
        bpy.context.collection.objects.link(cam)
        created.append(cam)
        scene.camera = cam

        out_dir.mkdir(parents=True, exist_ok=True)
        bpy.context.view_layer.update()
        evaluated = proxy.evaluated_get(bpy.context.evaluated_depsgraph_get())
        corners = [evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box]
        target = sum(corners, Vector((0.0, 0.0, 0.0))) / len(corners)

        radius = 3.8
        rendered: list[dict[str, Any]] = []
        for i in range(frames):
            angle = 2.0 * math.pi * i / frames
            cam.location = target + Vector(
                (math.sin(angle) * radius, -math.cos(angle) * radius, 0.45)
            )
            direction = target - cam.location
            cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
            if played:
                scene.frame_set(frame_start + (i % span))
                bpy.context.view_layer.update()
            scene.render.filepath = str(out_dir / f"{prefix}_{i:02d}.png")
            bpy.ops.render.render(write_still=True)
            rendered.append({"frame": i, "path": scene.render.filepath})
    finally:
        scene.render.engine = saved["engine"]
        scene.render.resolution_x = saved["res_x"]
        scene.render.resolution_y = saved["res_y"]
        scene.render.filepath = saved["filepath"]
        scene.render.film_transparent = saved["film"]
        scene.display.shading.light = saved["shading_light"]
        scene.display.shading.color_type = saved["color_type"]
        scene.display.shading.single_color = saved["single_color"]
        scene.display.shading.background_type = saved["bg_type"]
        scene.world = saved["world"]
        scene.camera = saved["camera"]
        scene.frame_set(saved["frame"])
        for name, was_hidden in saved["hidden"].items():
            obj = bpy.data.objects.get(name)
            if obj is not None:
                obj.hide_render = was_hidden
        for obj in created:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:  # noqa: BLE001 — cleanup best-effort, never masks the report
                pass
        for world in created_worlds:  # worlds are datablocks, not objects
            try:
                bpy.data.worlds.remove(world)
            except Exception:  # noqa: BLE001
                pass

    return {
        "out_dir": str(out_dir),
        "engine": "BLENDER_WORKBENCH",
        "width": width,
        "height": height,
        "frames_requested": frames,
        "frames_rendered": len(rendered),
        "played_action": played,
        "action": action.name if played and action is not None else None,
        "bones_visualized": len(bone_names),
        "frames": rendered,
    }
