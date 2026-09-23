#!/usr/bin/env python
"""P6-2 bridge sampler: an imported clip -> the format-1 motion clip JSON.

Run inside Blender (shell glue spawns it — D-009; the probe's recipe
productionized, docs/MOTION_LIBRARY.md):

    blender -b --python xtask/sample_clip.py -- <model> <out.json> \
        [--action NAME] [--rig NAME] [--stride N] [--fps F] [--tag LABEL]

Imports the file with Blender's BUILTIN importers (BVH pins the MEASURED
axis contract ``axis_forward='Y', axis_up='Z'`` — exporter-written files are
already Blender-world; the defaults land a 90 deg rotation and '-Y' lands a
vertical MIRROR), maps the source skeleton through the REAL core mapper,
then samples per frame: ``frame_set`` -> ``view_layer.update()`` -> every
mapped role's ``pb.matrix.to_translation()`` head (ARMATURE space; the
posed-head lesson — multiplying head_local by pb.matrix double-applies
rest). Output: the clip-sample JSON core ``MotionClip`` consumes (roles in
source meters, ``scale_ref`` = the source REST torso span, hips-anchored at
conversion time). Positions are never re-derived here and rotation modes
are never touched (forcing QUATERNION orphans the importer's euler fcurves
and silently freezes the motion).

Two independent sample passes run and must agree byte-for-byte (DETERM —
the probe's contract, now per-file). A near-static sample (all frames one
pose) is VALID input but prints a loud warning + a note: that is the frozen-
motion symptom, and the sampler refuses to ship it silently.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROUND_DIGITS = 6  # sub-micrometer on meter-scale rigs; stable bytes
STATIC_EXTENT_M = 1e-5  # below this the "motion" is one pose (warn, don't fail)


def _parse_args(argv):
    if not argv:
        print(
            "usage: sample_clip.py <model> <out.json> "
            "[--action NAME] [--rig NAME] [--stride N] [--fps F] [--tag LABEL]",
            file=sys.stderr,
        )
        raise SystemExit(64)
    model, out = argv[0], argv[1]
    opts = {"action": None, "rig": None, "stride": 1, "fps": None, "tag": None}
    i = 2
    while i < len(argv):
        arg = argv[i]
        if arg in ("--action", "--rig", "--tag") and i + 1 < len(argv):
            opts[arg[2:]] = argv[i + 1]
            i += 2
        elif arg in ("--stride", "--fps") and i + 1 < len(argv):
            opts[arg[2:]] = float(argv[i + 1])
            i += 2
        else:
            print(f"error: unknown argument {arg!r}", file=sys.stderr)
            raise SystemExit(64)
    if opts["stride"] < 1 or opts["stride"] != int(opts["stride"]):
        print("error: --stride must be a positive integer", file=sys.stderr)
        raise SystemExit(64)
    if not out:
        print("error: missing <out.json> argument", file=sys.stderr)
        raise SystemExit(64)
    return model, out, opts


def import_model(path):
    """BUILTIN importers only. The BVH axis flags are the MEASURED contract
    (docs/MOTION_LIBRARY.md § Probe answers) — do not 'fix' them."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".bvh":
        return bpy.ops.import_anim.bvh(  # type: ignore[name-defined]
            filepath=path, axis_forward="Y", axis_up="Z"
        )
    if ext == ".fbx":
        return bpy.ops.import_scene.fbx(filepath=path)  # type: ignore[name-defined]
    if ext in (".glb", ".gltf", ".vrm"):
        return bpy.ops.import_scene.gltf(filepath=path)  # type: ignore[name-defined]
    print(
        f"error: unsupported import type {ext!r} (supported: .bvh .fbx .glb .gltf .vrm)",
        file=sys.stderr,
    )
    raise SystemExit(64)


def find_armature(rig_filter):
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]  # type: ignore[name-defined]
    if rig_filter:
        for o in arms:
            if o.name == rig_filter:
                return o
        print(
            f"error: no armature named {rig_filter!r}; available: "
            f"{', '.join(sorted(o.name for o in arms)) or '(none)'} "
            "(hint: pass --rig with one of these names)",
            file=sys.stderr,
        )
        raise SystemExit(3)
    if not arms:
        print(
            "error: no armature in the imported file "
            "(hint: the sampler retargets skeletons; meshes-only files have none)",
            file=sys.stderr,
        )
        raise SystemExit(3)
    return arms[0]


def iter_fcurves(act):
    """Action fcurves across Blender APIs (4.x legacy / 5.x slotted)."""
    try:
        return list(act.fcurves)
    except AttributeError:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        return out


def select_action(obj, wanted):
    """The action to sample: --action NAME, or the one action the file
    carries. A multi-action file WITHOUT --action refuses with the list
    (actionable, never a silent first pick)."""
    actions = {a.name: a for a in bpy.data.actions}  # type: ignore[name-defined]
    if wanted:
        if wanted not in actions:
            print(
                f"error: no action named {wanted!r}; available: "
                f"{', '.join(sorted(actions)) or '(none)'} "
                "(hint: --action takes one of these names)",
                file=sys.stderr,
            )
            raise SystemExit(3)
        act = actions[wanted]
    elif len(actions) == 1:
        act = next(iter(actions.values()))
    else:
        current = obj.animation_data.action if obj.animation_data else None
        if current is not None and len(actions) > 1:
            print(
                f"error: {len(actions)} actions in the file "
                f"({', '.join(sorted(actions))}); pass --action "
                f"(currently active: {current.name!r})",
                file=sys.stderr,
            )
            raise SystemExit(3)
        act = current
        if act is None:
            print(
                "error: no action to sample "
                "(hint: the file carries no animation the importer exposed)",
                file=sys.stderr,
            )
            raise SystemExit(3)
    ad = obj.animation_data_create()
    ad.action = act
    # 5.x slotted actions: an import may leave the slot unset/mismatched;
    # evaluate nothing rather than guess (the DETERM/static guard would
    # catch it, but the fix belongs here, once, explicitly)
    slot = getattr(ad, "action_slot", None)
    slots = list(getattr(act, "slots", []) or [])
    if slots and slot not in slots:
        ad.action_slot = slots[0]
    return act


def mapped_roles(obj, core, bridge):
    """The REAL mapper (no name hardcoding): rig JSON -> map_rig -> roles."""
    rig_data = core.RigData.from_dict(bridge.rig_data_from_armature(obj))
    mapping = core.map_rig(rig_data)
    if "hips" not in mapping.assignments:
        print(
            "error: the mapper could not map 'hips' on this skeleton "
            "(hint: hips is the converter's anchor — resolve the mapping first "
            "with 'rigpose inspect/map', then re-run the sampler)",
            file=sys.stderr,
        )
        raise SystemExit(3)
    roles = {role: a.bone for role, a in sorted(mapping.assignments.items())}
    unmapped = len(rig_data.bones) - len(roles)
    return roles, unmapped, rig_data.fingerprint()


def rest_torso_span(obj, roles):
    """scale_ref: the source REST hips->mid-shoulders span (armature space)."""
    heads = {role: obj.data.bones[bone].head_local for role, bone in roles.items()}
    hips = heads["hips"]
    mid = tuple(
        (heads["upper_arm.L"][i] + heads["upper_arm.R"][i]) / 2.0 for i in range(3)
    )
    span = sum((mid[i] - hips[i]) ** 2 for i in range(3)) ** 0.5
    if span <= 1e-6:
        print(
            f"error: rest torso span measured {span:.3e} m "
            "(hint: check the upper_arm.L/R + hips mapping — a degenerate "
            "span cannot normalize positions)",
            file=sys.stderr,
        )
        raise SystemExit(3)
    return span


def sample_frames(obj, roles, frame_range, stride):
    """Per frame: frame_set -> view_layer.update() -> mapped-role posed heads.

    pb.matrix's TRANSLATION is the posed head in ARMATURE space (the probe's
    lesson); armature space is also what the REST span uses, so the pair is
    convention-consistent and invariant to the object transform."""
    scene = bpy.context.scene  # type: ignore[name-defined]
    start, end = frame_range
    out = {}
    for f in range(start, end + 1, stride):
        scene.frame_set(f)
        bpy.context.view_layer.update()  # type: ignore[name-defined]
        positions = {}
        for role, bone in roles.items():
            p = obj.pose.bones[bone].matrix.to_translation()
            positions[role] = [round(p[i], ROUND_DIGITS) for i in range(3)]
        out[f] = positions
    scene.frame_set(start)
    bpy.context.view_layer.update()  # type: ignore[name-defined]
    return out


def motion_extent(samples):
    """Largest per-role per-axis range across frames (the frozen-motion
    symptom check; a REAL idle clip can legitimately be small — warn only)."""
    extent = 0.0
    for role in next(iter(samples.values())):
        for i in range(3):
            coords = [p[role][i] for p in samples.values() if role in p]
            if coords:
                extent = max(extent, max(coords) - min(coords))
    return extent


def main():
    model, out, opts = _parse_args(
        sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    )
    if not os.path.isfile(model):
        print(f"error: no such file: {model}", file=sys.stderr)
        return 66
    tag = opts["tag"] or os.path.splitext(model)[1].lstrip(".").upper() or "CLIP"

    core_src = os.environ.get(
        "RM_CORE_SRC",
        str(Path(__file__).resolve().parent.parent / "core" / "src"),
    )
    addon_dir = os.environ.get(
        "RM_ADDON_DIR", str(Path(__file__).resolve().parent.parent / "addon")
    )
    sys.path.insert(0, core_src)
    sys.path.insert(0, addon_dir)
    import riggermortis as core  # noqa: E402
    from riggermortis_addon import bpy_bridge  # noqa: E402

    import_model(model)
    obj = find_armature(opts["rig"])
    roles, unmapped, fingerprint = mapped_roles(obj, core, bpy_bridge)
    act = select_action(obj, opts["action"])
    span = rest_torso_span(obj, roles)
    fr = act.frame_range
    start, end = int(round(fr[0])), int(round(fr[1]))
    if end < start:
        print(
            f"error: action {act.name!r} frame range is empty ({fr})",
            file=sys.stderr,
        )
        return 3
    stride = int(opts["stride"])
    fps = opts["fps"] if opts["fps"] else (
        bpy.context.scene.render.fps  # type: ignore[name-defined]
        / (bpy.context.scene.render.fps_base or 1.0)  # type: ignore[name-defined]
    )

    samples = sample_frames(obj, roles, (start, end), stride)
    twin = sample_frames(obj, roles, (start, end), stride)
    determ = samples == twin

    notes = [
        f"sampler: {os.path.splitext(model)[1].lower()} via builtin importer, "
        f"action={act.name!r} frames {start}..{end} stride {stride}",
    ]
    if os.path.splitext(model)[1].lower() == ".bvh":
        notes.append("imported with axis_forward='Y', axis_up='Z' (measured contract)")
    extent = motion_extent(samples)
    if extent < STATIC_EXTENT_M:
        notes.append(
            f"WARNING: sampled motion extent {extent:.3e} m — all frames one "
            "static pose (the orphaned-fcurve symptom; check that the action "
            "actually drives this armature)"
        )
    clip = {
        "format": 1,
        "fps": float(fps),
        "scale_ref": round(span, ROUND_DIGITS),
        "frames": [
            {"frame": f, "positions": samples[f]} for f in sorted(samples)
        ],
        "source": "blender-import",
        "source_fingerprint": fingerprint,
        "notes": notes,
    }
    out_path = Path(out)
    out_path.write_text(
        json.dumps(clip, indent=1, sort_keys=True), encoding="utf-8"
    )
    static_warn = " WARN_STATIC" if extent < STATIC_EXTENT_M else ""
    print(
        f"RM_MOTION SAMPLE {tag}: ok=True roles={len(roles)} unmapped_bones={unmapped} "
        f"frames={len(samples)} range={start}..{end} stride={stride} "
        f"fps={fps:g} scale_ref={span:.6f} action={act.name!r} "
        f"extent={extent:.4f}m{static_warn}"
    )
    print(f"RM_MOTION DETERM {tag}: {'PASS' if determ else 'FAIL'} byte_identical={determ}")
    print(f"RM_MOTION WRITE {tag}: {out_path} ({out_path.stat().st_size} bytes)")
    return 0 if determ else 1


if __name__ == "__main__":
    import bpy  # type: ignore[name-defined]

    sys.exit(main())
