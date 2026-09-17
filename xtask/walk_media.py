#!/usr/bin/env python3
"""P2-8 clip-retarget media pipeline (runs INSIDE Blender).

Phase-2 close deliverable: one walk rendered across three real rigs, before
and after the documented cleanup pipeline. Every GIF the repo ships is
generated headlessly by THIS script (media rule) — never hand-made.

The clip is the labeled SYNTHETIC generator shared with the published gate
numbers (``xtask/hip_stab_gate.py``: the drift + breathing walk) — the real
walking clip stays NEEDS-HUMAN (out/video_smoke/SOURCES.md), so nothing here
is presented as real-clip footage. The run exercises the documented pipeline
end to end per rig: ``condition_action(hip_stabilize=0.7, min_cutoff=None)``
->``detect_contacts`` -> ``lock_feet`` -> the add-on's real ``bake_action``
(``contacts=`` on the locked pass), then renders frames of the baked action
with the bone-proxy visualizer. ``mode=raw`` bakes the conditioned frames
WITHOUT the contact lock — that is the honest "before" half.

    RM_CORE_SRC=... RM_ADDON_DIR=... \
      blender -b -P xtask/walk_media.py -- \
      --rig out/real_rigs/metarig.blend --label metarig --mode locked \
      --out out/p28 --stride 2 --size 640 480

Writes ``<out>/<label>_<mode>/frame_XXX.png`` plus
``<out>/<label>_<mode>.manifest.json`` carrying the per-rig numbers the docs
block cites (bake FK fidelity, lock cost, per-interval ankle drift in rig
space). Smoothing and keyframe reduction are deliberately disabled for the
media pass (``min_cutoff=None, tolerance=None`` — the CI-certified
composition): the GIF shows the stabilized + locked motion at the
generator's native frame count. The FK self-check gate applies —
fidelity above the bar refuses to ship frames. Output paths are confined to
the current directory or the temp dir; ``..`` segments are refused outright.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

XTASK = Path(__file__).resolve().parent

BLENDER_FRAME_OFFSET = 1  # bake maps source frame i -> Blender frame i + 1
DRIFT_BAR_M = 0.010  # same bar as the RM_FOOT_LOCK probe (docs/BENCHMARKS.md)


def _safe_out_dir(raw: str) -> Path:
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


def _parse_args(argv: list[str]) -> dict[str, object]:
    defaults: dict[str, object] = {
        "rig": "", "label": "", "mode": "locked", "out": "out/p28",
        "stride": 2, "size": (640, 480), "bar_deg": 0.5,
        "color": None,
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--rig" and i + 1 < len(argv):
            defaults["rig"] = argv[i + 1]
            i += 2
        elif arg == "--label" and i + 1 < len(argv):
            defaults["label"] = argv[i + 1]
            i += 2
        elif arg == "--mode" and i + 1 < len(argv):
            defaults["mode"] = argv[i + 1]
            i += 2
        elif arg == "--out" and i + 1 < len(argv):
            defaults["out"] = argv[i + 1]
            i += 2
        elif arg == "--stride" and i + 1 < len(argv):
            defaults["stride"] = int(argv[i + 1])
            i += 2
        elif arg == "--size" and i + 2 < len(argv):
            defaults["size"] = (int(argv[i + 1]), int(argv[i + 2]))
            i += 3
        elif arg == "--bar-deg" and i + 1 < len(argv):
            defaults["bar_deg"] = float(argv[i + 1])
            i += 2
        elif arg == "--color" and i + 3 < len(argv):
            defaults["color"] = tuple(float(argv[i + 1 + k]) for k in range(3))
            i += 4
        else:
            print(f"unknown argument: {argv[i]}", file=sys.stderr)
            raise SystemExit(64)
    if not defaults["rig"] or not defaults["label"]:
        raise SystemExit("error: --rig and --label are required")
    if defaults["mode"] not in ("raw", "locked"):
        raise SystemExit("error: --mode must be raw or locked")
    if int(defaults["stride"]) < 1:  # type: ignore[operator]
        raise SystemExit("error: --stride must be >= 1")
    defaults["out"] = str(_safe_out_dir(str(defaults["out"])))
    return defaults


def _load_core_and_generator():
    core_src = os.environ.get("RM_CORE_SRC", "")
    if not core_src or not os.path.isdir(core_src):
        raise SystemExit("error: RM_CORE_SRC must point at core/src")
    sys.path.insert(0, core_src)
    sys.path.insert(0, str(XTASK))
    import hip_stab_gate
    import riggermortis as core

    return core, hip_stab_gate


def _build_pipeline(core, generator, mode: str):
    """The CI-certified composition (test_pipeline_condition_detect_lock_
    still_gates): stabilization only — the 1€ pass with beta=0 lags a swing
    foot's landing into its stance phase (phantom contact-phase glide, and
    the lock's pins go unreachable), so smoothing and reduction stay OFF
    here exactly as the gate runs them."""
    raw = generator.build_walk(drift=True, wobble=0.005)
    conditioned = core.condition_action(
        raw, hip_stabilize=0.7, min_cutoff=None, tolerance=None
    )
    report = core.detect_contacts(conditioned.frames)
    if mode == "locked":
        locked, lock = core.lock_feet(conditioned, report)
        return locked.frames, report, lock
    return conditioned.frames, report, None


def _hide_non_armature(armature) -> None:
    """Hide imported meshes from renders; the bone proxy is the visualizer
    (armature bones do not render). Hiding keeps parenting/transforms
    intact, deleting would not."""
    import bpy

    for obj in bpy.context.scene.objects:
        if obj.type != "ARMATURE":
            obj.hide_render = True
    _ = armature


def _load_rig(path: Path):
    """Open the rig scene; returns the armature object. Never switch scenes
    after this point (S8 lesson: factory settings invalidate bpy references)."""
    import bpy

    suffix = path.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    elif suffix in (".vrm", ".glb", ".gltf"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        raise SystemExit(f"error: unsupported rig format {suffix!r} ({path})")

    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if not armatures:
        raise SystemExit(f"error: no armature found in {path}")
    armature = armatures[0]
    # Imported rigs bring meshes (VRM/MLB) — hide them from renders; the
    # bone proxy is the visualizer (armature bones do not render). Hiding
    # keeps parenting/transforms intact, deleting would not.
    for obj in bpy.context.scene.objects:
        if obj.type != "ARMATURE":
            obj.hide_render = True
    return armature


def _repair_imported_tails(armature) -> int:
    """Repair glTF-imported bone tails WHEN they disagree with the skeleton.

    glTF has no bone-tail concept; importers synthesize one, and on the
    Mixamo glb the synthesized tails are ~100x the true joint spacing. The
    garbage tails break three consumers: the 2-bone lock solve (fixed
    separately in bake via head distances), Blender's EVALUATED bone
    placement (children ladder away from their parents), and the bone-proxy
    visualizer. Deterministic and conditional: a bone whose rest tail
    already matches its nearest child's head (or is a sane leaf stub) is
    left untouched, so Blender-native rigs are bit-for-bit no-ops.
    Returns the number of bones repaired (0 = nothing touched).
    """
    import bpy
    from mathutils import Vector

    data = armature.data
    children: dict[str, list] = {}
    for bone in data.bones:
        if bone.parent is not None:
            children.setdefault(bone.parent.name, []).append(bone)

    def _nearest_child_span(bone) -> float | None:
        kids = children.get(bone.name)
        if not kids:
            return None
        return min((k.head_local - bone.head_local).length for k in kids)

    spans = [s for s in (_nearest_child_span(b) for b in data.bones) if s]
    median_span = sorted(spans)[len(spans) // 2] if spans else 1.0
    leaf_stub = 0.3 * median_span

    changed = []
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        edit_bones = data.edit_bones
        for bone in data.bones:
            expected = _nearest_child_span(bone)
            if expected is not None:
                if abs(bone.length - expected) <= 0.01 * expected:
                    continue  # sane chain tail — untouched
                new_tail = min(
                    children[bone.name],
                    key=lambda k: (k.head_local - bone.head_local).length,
                ).head_local
            elif bone.parent is not None:
                if bone.length <= 3.0 * median_span:
                    continue  # leaf stub of plausible size — untouched
                direction = Vector(bone.head_local) - Vector(bone.parent.head_local)
                if direction.length <= 1e-9:
                    continue
                new_tail = bone.head_local + direction.normalized() * leaf_stub
            else:
                continue  # parentless root — leave alone
            edit_bones[bone.name].tail = new_tail
            changed.append(bone.name)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    if changed:
        print(f"RM_WALK TAILS: repaired {len(changed)} bone tail(s)")
    return len(changed)


def _ankle_drift(obj, mapping, report) -> tuple[float, int, list[str]]:
    """Max ankle world drift WITHIN one contact interval, in WORLD units
    (meters for meter-scaled rigs — armature-local units are NOT comparable
    across rigs: the Mixamo glb imports with 0.01 object scale).

    Per-interval — not global max-pairwise — because a real walk replants
    each foot at a new spot every cycle; the lock pins the plant, not the
    stride. Mirrors the RM_FOOT_LOCK probe's measurement.
    """
    import bpy

    bones = {}
    missing = []
    for foot in ("foot.L", "foot.R"):
        assignment = mapping.assignments.get(foot)
        pb = obj.pose.bones.get(assignment.bone) if assignment else None
        if pb is None:
            missing.append(foot)
        else:
            bones[foot] = pb
    worst = 0.0
    measured = 0
    world = obj.matrix_world
    for interval in report.intervals:
        pb = bones.get(interval.foot)
        if pb is None:
            continue
        points = []
        for f in range(interval.start, interval.end + 1):
            bpy.context.scene.frame_set(f + BLENDER_FRAME_OFFSET)
            bpy.context.view_layer.update()
            points.append(world @ pb.matrix.to_translation())
        for i, a in enumerate(points):
            for b in points[i + 1:]:
                worst = max(worst, (a - b).length)
        measured += 1
    return worst, measured, missing


def _render(obj, mapping, frames, out_dir: Path, stride: int,
            size: tuple[int, int],
            color: tuple[float, float, float]) -> list[dict[str, object]]:
    """Fixed-camera workbench render of the baked action (deterministic:
    one 3/4 view angle, target = proxy center of the FIRST rendered frame)."""
    import math

    import bpy
    import render_demos
    # Visualize the MAPPED bones: exactly the set the pipeline drives.
    render_demos._add_bone_proxy_mesh(
        obj, {a.bone for a in mapping.assignments.values()}
    )
    aim, set_target = render_demos._stage_scene(frames, size[0], size[1])
    scene = bpy.context.scene
    # FLAT unlit shading + an explicit background world: the sun/STUDIO setup
    # silhouettes the figure from some camera angles, and glTF imports can
    # carry a black world that swallows the frame entirely. A fixed unlit
    # color keeps the proxy visible and the pipeline deterministic.
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = color
    scene.display.shading.background_type = "WORLD"
    world = bpy.data.worlds.new("rm_walk_world")
    world.use_nodes = False
    world.color = (0.055, 0.055, 0.06)
    scene.world = world

    angle = math.radians(60.0)  # 3/4 front-left; character faces -Y
    selected = frames[::stride]
    first = selected[0]
    scene.frame_set(first.frame + BLENDER_FRAME_OFFSET)
    bpy.context.view_layer.update()
    set_target(render_demos._proxy_center())

    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for af in selected:
        scene.frame_set(af.frame + BLENDER_FRAME_OFFSET)
        aim(angle)
        scene.render.filepath = str(out_dir / f"frame_{af.frame:03d}.png")
        bpy.ops.render.render(write_still=True)
        rendered.append({"frame": af.frame, "path": scene.render.filepath})
        print(f"RM_WALK FRAME {af.frame}")
    return rendered


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    core, generator = _load_core_and_generator()
    mode = str(args["mode"])
    label = str(args["label"])

    frames, report, lock = _build_pipeline(core, generator, mode)
    if not frames:
        raise SystemExit("error: the pipeline produced no frames — refusing to render")

    import bpy  # noqa: F401 — asserts we are inside Blender

    rig_path = Path(str(args["rig"])).resolve()
    if not rig_path.is_file():
        raise SystemExit(f"error: rig file not found: {rig_path}")
    armature = _load_rig(rig_path)
    _repair_imported_tails(armature)
    bone_count = len(armature.data.bones)

    sys.path.insert(0, os.environ["RM_ADDON_DIR"])
    from riggermortis_addon import bake, bpy_bridge, pose_apply

    mapping = pose_apply.mapping_from_props(armature, core) or core.map_rig(
        core.RigData.from_dict(bpy_bridge.rig_data_from_armature(armature))
    )

    baked = bake.bake_action(
        armature, frames, core,
        name=f"rm_walk_{label}_{mode}",
        contacts=report if mode == "locked" else None,
    )
    bar = float(args["bar_deg"])
    if baked["worst_deg"] > bar:
        print(
            f"error: bake FK self-check failed on {label} "
            f"({baked['worst_deg']:.4f} deg > {bar}) — refusing to ship media",
            file=sys.stderr,
        )
        return 1

    drift, intervals_measured, missing = _ankle_drift(armature, mapping, report)
    if missing:
        print(f"RM_WALK DRIFT SKIP: unmapped ankle(s) {missing}")

    color = args["color"] if args["color"] else (
        (0.72, 0.60, 0.52) if mode == "raw" else (0.53, 0.66, 0.72)
    )
    out_root = Path(str(args["out"]))
    frames_dir = out_root / f"{label}_{mode}"
    rendered = _render(
        armature, mapping, frames, frames_dir, int(args["stride"]),  # type: ignore[arg-type]
        tuple(args["size"]), color,  # type: ignore[arg-type]
    )

    manifest = {
        "label": label,
        "mode": mode,
        "rig": str(rig_path),
        "rig_kind": rig_path.suffix.lower().lstrip("."),
        "bones": bone_count,
        "generator": "xtask/hip_stab_gate.py build_walk(drift=True, wobble=0.005) "
                     "(SYNTHETIC — real-clip NEEDS-HUMAN, out/video_smoke/SOURCES.md)",
        "pipeline": "condition_action(hip_stabilize=0.7, min_cutoff=None, "
                    "tolerance=None) -> "
                    "detect_contacts -> "
                    + ("lock_feet -> bake_action(contacts=...)" if mode == "locked"
                       else "bake_action (no contact lock)"),
        "worst_deg": round(baked["worst_deg"], 4),
        "worst_role": baked["worst_role"],
        "keys": baked["keys"],
        "locked_frames": baked["locked_frames"],
        "lock_dev_deg": round(baked["lock_dev_deg"], 4),
        "lock_clamped": baked["lock_clamped"],
        "mapping_source": baked["mapping_source"],
        "ankle_drift_m": round(drift, 6),
        "drift_intervals": intervals_measured,
        "drift_bar_m": DRIFT_BAR_M,
        "drift_pass": bool(drift <= DRIFT_BAR_M),
        "stride": int(args["stride"]),  # type: ignore[call-overload]
        "frames": rendered,
    }
    manifest_path = out_root / f"{label}_{mode}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if lock is not None:
        print(
            f"RM_WALK LOCK: slide_after={lock.slide_after.total:.4f}u "
            f"locked_frames={baked['locked_frames']} "
            f"knee<={max(lock.max_knee_shift.values(), default=0.0):.4f}u"
        )
    print(
        f"RM_WALK {label} {mode}: PASS worst={baked['worst_deg']:.4f}deg "
        f"({baked['worst_role']}) drift={drift:.4f}m/{intervals_measured}iv "
        f"({'PASS' if drift <= DRIFT_BAR_M else 'FAIL'}) "
        f"lock_dev={baked['lock_dev_deg']:.2f}deg clamped={baked['lock_clamped']} "
        f"frames={len(rendered)} -> {manifest_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]))
