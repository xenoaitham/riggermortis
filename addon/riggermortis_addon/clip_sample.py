"""Motion-clip sampler library (P6-2, promoted from xtask/sample_clip.py).

The import/sample loop that turns an imported Mixamo/BVH/FBX clip into the
format-1 motion-clip JSON core ``MotionClip`` consumes — ONE copy of the
loop, owned by the add-on package (the D-016 lockstep lesson: two textual
copies drift); ``xtask/sample_clip.py`` is the thin caller (shell glue
spawns Blender, D-009) and the future ``retarget_clip`` session action
calls this module directly (docs/MOTION_LIBRARY.md § Future).

Builtin importers ONLY. The BVH axis flags are the MEASURED contract
(docs/MOTION_LIBRARY.md § Probe answers) — do not 'fix' them: exporter-
written files are already Blender-world; the defaults land a 90 deg
rotation and ``'-Y'`` lands a vertical MIRROR. Sampling is per frame
``frame_set`` -> ``view_layer.update()`` -> every mapped role's
``pb.matrix.to_translation()`` head (ARMATURE space; the posed-head lesson
— multiplying head_local by pb.matrix double-applies rest). Positions are
never re-derived here and rotation modes are never touched (forcing
QUATERNION orphans the importer's euler fcurves and silently freezes the
motion).

Library discipline: ``bpy`` is imported INSIDE the functions (the add-on
convention, bake.py's pattern) so the module imports cleanly outside
Blender and the pure parts are conftest-shim testable. Errors raise
``ValueError`` with an actionable ``(hint: ...)`` — the caller prints and
maps to exit codes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROUND_DIGITS = 6  # sub-micrometer on meter-scale rigs; stable bytes
STATIC_EXTENT_M = 1e-5  # below this the "motion" is one pose (warn, don't fail)


def import_model(path: str) -> Any:
    """Import a clip file with Blender's BUILTIN importers."""
    import bpy

    ext = os.path.splitext(path)[1].lower()
    if ext == ".bvh":
        return bpy.ops.import_anim.bvh(
            filepath=path, axis_forward="Y", axis_up="Z"
        )
    if ext == ".fbx":
        return bpy.ops.import_scene.fbx(filepath=path)
    if ext in (".glb", ".gltf", ".vrm"):
        return bpy.ops.import_scene.gltf(filepath=path)
    raise ValueError(
        f"unsupported import type {ext!r} "
        "(hint: supported: .bvh .fbx .glb .gltf .vrm)"
    )


def find_armature(rig_filter: str | None) -> Any:
    """The imported armature: ``--rig`` name filter, else the only one."""
    import bpy

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if rig_filter:
        for o in arms:
            if o.name == rig_filter:
                return o
        raise ValueError(
            f"no armature named {rig_filter!r}; available: "
            f"{', '.join(sorted(o.name for o in arms)) or '(none)'} "
            "(hint: pass --rig with one of these names)"
        )
    if not arms:
        raise ValueError(
            "no armature in the imported file "
            "(hint: the sampler retargets skeletons; meshes-only files have none)"
        )
    return arms[0]


def iter_fcurves(act: Any) -> list[Any]:
    """Action fcurves across Blender APIs (4.x legacy / 5.x slotted)."""
    try:
        return list(act.fcurves)
    except AttributeError:
        out: list[Any] = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        return out


def select_action(obj: Any, wanted: str | None) -> Any:
    """The action to sample: an explicit name, or the one action the file
    carries. A multi-action file WITHOUT a name refuses with the list
    (actionable, never a silent first pick)."""
    import bpy

    actions = {a.name: a for a in bpy.data.actions}
    if wanted:
        if wanted not in actions:
            raise ValueError(
                f"no action named {wanted!r}; available: "
                f"{', '.join(sorted(actions)) or '(none)'} "
                "(hint: --action takes one of these names)"
            )
        act = actions[wanted]
    elif len(actions) == 1:
        act = next(iter(actions.values()))
    else:
        current = obj.animation_data.action if obj.animation_data else None
        if current is not None and len(actions) > 1:
            raise ValueError(
                f"{len(actions)} actions in the file "
                f"({', '.join(sorted(actions))}); pass --action "
                f"(currently active: {current.name!r})"
            )
        act = current
        if act is None:
            raise ValueError(
                "no action to sample "
                "(hint: the file carries no animation the importer exposed)"
            )
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


def mapped_roles(obj: Any, core: Any, bridge: Any) -> tuple[dict[str, str], int, str]:
    """The REAL mapper (no name hardcoding): rig JSON -> map_rig -> roles.

    Returns ``(roles, unmapped_bone_count, source_fingerprint)``; refuses
    when hips is unmapped (the converter's anchor)."""
    rig_data = core.RigData.from_dict(bridge.rig_data_from_armature(obj))
    mapping = core.map_rig(rig_data)
    if "hips" not in mapping.assignments:
        raise ValueError(
            "the mapper could not map 'hips' on this skeleton "
            "(hint: hips is the converter's anchor — resolve the mapping "
            "first with 'rigpose inspect/map', then re-run the sampler)"
        )
    roles = {role: a.bone for role, a in sorted(mapping.assignments.items())}
    unmapped = len(rig_data.bones) - len(roles)
    return roles, unmapped, rig_data.fingerprint()


def rest_torso_span(obj: Any, roles: dict[str, str]) -> float:
    """scale_ref: the source REST hips->mid-shoulders span (armature space)."""
    heads = {role: obj.data.bones[bone].head_local for role, bone in roles.items()}
    hips = heads["hips"]
    mid = tuple(
        (heads["upper_arm.L"][i] + heads["upper_arm.R"][i]) / 2.0 for i in range(3)
    )
    span = sum((mid[i] - hips[i]) ** 2 for i in range(3)) ** 0.5
    if span <= 1e-6:
        raise ValueError(
            f"rest torso span measured {span:.3e} m "
            "(hint: check the upper_arm.L/R + hips mapping — a degenerate "
            "span cannot normalize positions)"
        )
    return span


def sample_frames(
    obj: Any, roles: dict[str, str], frame_range: tuple[int, int], stride: int
) -> dict[int, dict[str, list[float]]]:
    """Per frame: frame_set -> view_layer.update() -> mapped-role posed heads.

    pb.matrix's TRANSLATION is the posed head in ARMATURE space (the probe's
    lesson); armature space is also what the REST span uses, so the pair is
    convention-consistent and invariant to the object transform."""
    import bpy

    scene = bpy.context.scene
    start, end = frame_range
    out: dict[int, dict[str, list[float]]] = {}
    for f in range(start, end + 1, stride):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        positions: dict[str, list[float]] = {}
        for role, bone in roles.items():
            p = obj.pose.bones[bone].matrix.to_translation()
            positions[role] = [round(p[i], ROUND_DIGITS) for i in range(3)]
        out[f] = positions
    scene.frame_set(start)
    bpy.context.view_layer.update()
    return out


def motion_extent(samples: dict[int, dict[str, list[float]]]) -> float:
    """Largest per-role per-axis range across frames (the frozen-motion
    symptom check; a REAL idle clip can legitimately be small — warn only)."""
    extent = 0.0
    for role in next(iter(samples.values())):
        for i in range(3):
            coords = [p[role][i] for p in samples.values() if role in p]
            if coords:
                extent = max(extent, max(coords) - min(coords))
    return extent


def build_clip(
    samples: dict[int, dict[str, list[float]]],
    *,
    fps: float,
    scale_ref: float,
    fingerprint: str,
    notes: list[str],
) -> dict[str, Any]:
    """The format-1 clip JSON dict (frames sorted, positions rounded —
    stable bytes; core ``MotionClip.from_dict`` validates the shape)."""
    return {
        "format": 1,
        "fps": float(fps),
        "scale_ref": round(scale_ref, ROUND_DIGITS),
        "frames": [
            {"frame": f, "positions": samples[f]} for f in sorted(samples)
        ],
        "source": "blender-import",
        "source_fingerprint": fingerprint,
        "notes": list(notes),
    }


def sample_clip(
    model: str,
    out: str,
    core: Any,
    bridge: Any,
    *,
    action: str | None = None,
    rig: str | None = None,
    stride: int = 1,
    fps: float | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """The whole sampler minus argv parsing and exit codes: import -> map ->
    sample (plus a DETERM twin pass that must agree byte-for-byte) -> write
    the clip JSON. Returns the report dict (``lines`` are the exact
    ``RM_MOTION`` lines the gate greps, byte-identical to the pre-refactor
    script). ``determ=False`` is a FAIL: the caller exits nonzero."""
    if not os.path.isfile(model):
        raise ValueError(f"no such file: {model}")
    tag = tag or os.path.splitext(model)[1].lstrip(".").upper() or "CLIP"

    import_model(model)
    obj = find_armature(rig)
    roles, unmapped, fingerprint = mapped_roles(obj, core, bridge)
    act = select_action(obj, action)
    span = rest_torso_span(obj, roles)
    fr = act.frame_range
    start, end = int(round(fr[0])), int(round(fr[1]))
    if end < start:
        raise ValueError(f"action {act.name!r} frame range is empty ({fr})")

    if fps is None:
        import bpy

        fps = bpy.context.scene.render.fps / (bpy.context.scene.render.fps_base or 1.0)

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
    clip = build_clip(
        samples,
        fps=fps,
        scale_ref=span,
        fingerprint=fingerprint,
        notes=notes,
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(clip, indent=1, sort_keys=True), encoding="utf-8"
    )
    static_warn = " WARN_STATIC" if extent < STATIC_EXTENT_M else ""
    lines = [
        f"RM_MOTION SAMPLE {tag}: ok=True roles={len(roles)} unmapped_bones={unmapped} "
        f"frames={len(samples)} range={start}..{end} stride={stride} "
        f"fps={fps:g} scale_ref={span:.6f} action={act.name!r} "
        f"extent={extent:.4f}m{static_warn}",
        f"RM_MOTION DETERM {tag}: {'PASS' if determ else 'FAIL'} byte_identical={determ}",
        f"RM_MOTION WRITE {tag}: {out_path} ({out_path.stat().st_size} bytes)",
    ]
    return {"lines": lines, "determ": determ, "out_path": str(out_path)}
