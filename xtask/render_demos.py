#!/usr/bin/env python
"""Headless demo-media pipeline (runs INSIDE Blender).

RULE 5 of the mission: the repo films itself — every GIF/render in the README
is produced headlessly from scripted demo scenes by this module, and CI
regenerates media on release. No stale, hand-made, or faked media ships.

    blender -b -P xtask/render_demos.py -- --demo boom --out media

--demo boom: the Phase 1 launch asset. Appends the real metarig, renders a
turntable of the REST pose ("before"), applies the real ``rigpose pose``
payload through the add-on's own apply path (self-check must pass), then
renders the same turntable ("after"). Frames land in <out>/boom/ with a
manifest.json; xtask/render_boom.sh chains the GIF assembler (encoding stays
outside Blender).

Output paths are confined: like the other edge scripts, ``--out`` must resolve
inside the current directory or the system temp dir, and ``..`` segments are
refused outright (Mimosa gate).
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path

DEMOS = ("boom",)


def _safe_out_dir(raw: str) -> Path:
    """Normalize and confine the output root to cwd or the temp dir."""
    path = Path(raw).expanduser()
    if any(part == os.pardir for part in path.parts):
        raise SystemExit(f"error: output path must not contain {os.pardir} segments: {raw}")
    resolved = path.resolve()
    allowed = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(resolved == base or base in resolved.parents for base in allowed):
        raise SystemExit(
            "error: output path must be inside the current directory or the "
            f"system temp dir: {raw}"
        )
    return resolved


def _parse_args(argv: list[str]) -> tuple[str, Path, int, int, int]:
    demo = "boom"
    out = Path("media")
    frames = 24
    width, height = 640, 480
    i = 0
    while i < len(argv):
        if argv[i] == "--demo" and i + 1 < len(argv):
            demo = argv[i + 1]
            i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            out = Path(argv[i + 1])
            i += 2
        elif argv[i] == "--frames" and i + 1 < len(argv):
            frames = int(argv[i + 1])
            i += 2
        elif argv[i] == "--size" and i + 2 < len(argv):
            width, height = int(argv[i + 1]), int(argv[i + 2])
            i += 3
        else:
            print(f"unknown argument: {argv[i]}", file=sys.stderr)
            raise SystemExit(64)
    if demo not in DEMOS:
        print(f"error: no scripted demo {demo!r} (known: {', '.join(DEMOS)})", file=sys.stderr)
        raise SystemExit(64)
    if frames < 2 or frames > 120:
        raise SystemExit("error: --frames must be between 2 and 120")
    return demo, _safe_out_dir(str(out)), frames, width, height


def _required_env_file(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or not os.path.isfile(value):
        print(
            f"error: {name} must point to an existing file (got {value!r})",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return value


def _setup_scene(metarig_blend: str):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(metarig_blend, link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    for obj in tuple(bpy.data.objects):
        if obj.type != "ARMATURE":
            bpy.data.objects.remove(obj, do_unlink=True)
    armature = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    if armature.name not in bpy.context.collection.objects:
        bpy.context.collection.objects.link(armature)
    armature.location = (0.0, 0.0, 0.0)
    _add_bone_proxy_mesh(armature)
    return armature


def _add_bone_proxy_mesh(armature) -> None:
    """One mesh visualizing every bone as an octahedron, deformed by the rig.

    Armature bones are viewport-only overlays — a plain render of an armature
    scene is an empty frame. This proxy is the honest stand-in: octahedrons in
    vertex groups named after their bones, driven by an armature modifier, so
    the render shows exactly the pose the payload applied.
    """
    import bpy
    from mathutils import Vector

    verts, faces, groups = [], [], []
    for bone in armature.data.bones:
        h = Vector(bone.head_local)
        t = Vector(bone.tail_local)
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
        verts.extend((h, t, ring_c + w * r, ring_c - w * r, ring_c + v * r, ring_c - v * r))
        faces.extend(
            (
                (base, base + 2, base + 3), (base, base + 3, base + 4),
                (base, base + 4, base + 5), (base, base + 5, base + 2),
                (base + 1, base + 3, base + 2), (base + 1, base + 4, base + 3),
                (base + 1, base + 5, base + 4), (base + 1, base + 2, base + 5),
            )
        )
        groups.append((bone.name, base, base + 6))

    mesh = bpy.data.meshes.new("rm_bone_proxy")
    mesh.from_pydata([tuple(p) for p in verts], [], faces)
    mesh.update()
    obj = bpy.data.objects.new("rm_bone_proxy", mesh)
    bpy.context.collection.objects.link(obj)
    for name, start, end in groups:
        group = obj.vertex_groups.new(name=name)
        group.add(list(range(start, end)), 1.0, "REPLACE")
    modifier = obj.modifiers.new("rm_armature", type="ARMATURE")
    modifier.object = armature
    modifier.use_bone_envelopes = False
    modifier.use_vertex_groups = True


def _stage_scene(frames: int, width: int, height: int):
    """Workbench shading, camera + sun; returns (aim, set_target).

    The orbit target is mutable (P1-11 B3): the caller re-centers it on the
    rendered geometry's bound-box center, so a posed figure that drifts off
    the rest-pose centroid stays framed.
    """
    import bpy
    from mathutils import Vector

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (0.55, 0.62, 0.72)
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"

    cam = bpy.data.objects.new("boom_cam", bpy.data.cameras.new("boom_cam"))
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    sun = bpy.data.objects.new(
        "boom_sun", bpy.data.lights.new("boom_sun", type="SUN")
    )
    sun.data.energy = 3.0
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0.0, math.radians(30))

    state = {"target": Vector((0.0, 0.0, 0.82))}
    radius = 3.8
    _ = frames  # orbit is angle-driven; frames only bound the caller's loop

    def set_target(vec: Vector) -> None:
        state["target"] = Vector(vec)

    def aim(angle: float) -> None:
        target = state["target"]
        cam.location = target + Vector(
            (math.sin(angle) * radius, -math.cos(angle) * radius, 0.45)
        )
        direction = target - cam.location
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    cam.data.lens = 45
    return aim, set_target


def _proxy_center():
    """World-space center of the rendered geometry (deformed bone proxy)."""
    import bpy
    from mathutils import Vector

    bpy.context.view_layer.update()
    proxy = bpy.data.objects["rm_bone_proxy"]
    evaluated = proxy.evaluated_get(bpy.context.evaluated_depsgraph_get())
    corners = [evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box]
    return sum(corners, Vector((0.0, 0.0, 0.0))) / len(corners)


def _render_turntable(aim, frames: int, out_dir: Path, prefix: str) -> list[str]:
    import bpy

    scene = bpy.context.scene
    paths = []
    for i in range(frames):
        aim(2.0 * math.pi * i / frames)
        scene.render.filepath = str(out_dir / f"{prefix}_{i:02d}.png")
        bpy.ops.render.render(write_still=True)
        paths.append(scene.render.filepath)
        print(f"RM_RENDER {prefix} {i + 1}/{frames}")
    return paths


def main(argv: list[str]) -> int:
    demo, out_dir, frames, width, height = _parse_args(argv)
    if demo != "boom":
        return 1
    import bpy  # noqa: F401 — asserts we are inside Blender

    metarig = _required_env_file("RM_METARIG_BLEND")
    payload_path = _required_env_file("RM_PAYLOAD")

    out_dir = out_dir / "boom"
    out_dir.mkdir(parents=True, exist_ok=True)

    armature = _setup_scene(metarig)
    aim, set_target = _stage_scene(frames, width, height)
    rest_center = _proxy_center()
    set_target(rest_center)  # rest pose: frame the actual geometry
    rest_frames = _render_turntable(aim, frames, out_dir, "rest")

    # Apply the real payload through the add-on's own apply path; ship nothing
    # if its self-check disagrees with the payload's promise.
    sys.path.insert(0, os.environ["RM_CORE_SRC"])
    sys.path.insert(0, os.environ["RM_ADDON_DIR"])
    from riggermortis_addon import pose_apply

    with open(payload_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    report = pose_apply.apply_payload(armature, payload, mirror=False)
    if report["worst_deg"] > 0.5:
        print(
            f"error: payload self-check failed ({report['worst_deg']:.3f} deg) "
            "— refusing to ship media",
            file=sys.stderr,
        )
        return 1
    print(f"RM_RENDER payload applied, worst {report['worst_deg']:.4f} deg")

    posed_center = _proxy_center()
    shift = (posed_center - rest_center).length
    if shift > 1e-4:
        set_target(posed_center)  # P1-11 B3: track the posed centroid
        print(f"RM_RENDER camera target tracked posed centroid (shift {shift:.3f} m)")
    posed_frames = _render_turntable(aim, frames, out_dir, "posed")

    manifest = {
        "demo": "boom",
        "frames": frames,
        "rest": rest_frames,
        "posed": posed_frames,
        "self_check_worst_deg": round(report["worst_deg"], 4),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"RM_RENDER BOOM FRAMES DONE: {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]))
