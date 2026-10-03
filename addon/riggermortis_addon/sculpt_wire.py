"""P9-3 sculpt wiring — the add-on apply half (docs/WIRING.md).

ONE shared module for the operator (``rm.apply_sculpt``) and the session
executor (the ``sculpt`` action): proportion + volume applied at the rest
state, BEFORE any pose/animation drives the rig. The two sculpt mechanisms
are the S36/S37 apply functions UNCHANGED (``auto_sculpt.py`` /
``volume.py``); this module owns the WIRING only:

- reference ratios from the pose payload (proportions) and the sculpt
  solve artifact (volume — written by ``rigpose solve-sculpt``, the D-009
  pattern: the segmentation model never enters Blender);
- base ratios from the rig itself — REST bone heads for the proportion
  half (``bone.matrix_local``, invariant under both sculpts by
  construction), and a STAGED REST-SNAPSHOT exact-alpha measurement for
  the volume half (pose transforms + shape-key values saved and cleared,
  a level-frontal WORKBENCH frame rendered, measured with the core's
  S37-certified ``region_widths``, then EVERY touched setting restored).
  Measuring the current sculpted/posed state instead would compose
  factors — the S36 sequential-sculpt failure class; the staged rest
  snapshot is what makes ``factor = ref / base`` absolute-target on
  every re-apply.

Declared limits: DRIVEN shape keys are not staged (a driver overrides the
staged value at evaluation time — the report carries a loud note; the
certified numbers are undriven-key numbers). The volume camera fit is the
declared frontal class (CAM_FIT_TORSO x the rig's world torso span, lens
35 — the S37 fixture class ratio); an oblique reference view is outside
the measured class. ``bpy`` is imported inside functions (the add-on
convention) so the module imports cleanly outside Blender.

Capability lines are the P8-4 verbatim pattern: a missing payload, a
missing solve artifact, or a starved rig is refused LOUD and touches
nothing. Every result lands on editable targets (the artist exit).
"""
from __future__ import annotations

import math
import os
import tempfile
from typing import Any

from . import bpy_bridge, pose_apply

CAPABILITY_NO_PAYLOAD = (
    "sculpt: no payload — proportions not applied "
    "(hint: rigpose pose <image> <rig.json> --out payload.json)"
)
CAPABILITY_NO_SCULPT = (
    "volume: no sculpt solve — volume not applied "
    "(hint: rigpose solve-sculpt <image> <payload.json> --out sculpt.json)"
)

#: The declared frontal camera fit (the S37 fixture class: 2.5 m camera
#: distance for a 0.44 m torso span — the ratio, applied to any rig).
CAM_FIT_TORSO = 2.5 / 0.44
CAM_LENS = 35.0
RES_X, RES_Y = 640, 960
#: Anchor-row guards: the measurement refuses when an anchor leaves the
#: frame (a clamped anchor would silently measure the wrong row).
MEASURE_EPS = 1e-9


def _import_core() -> Any:
    return bpy_bridge.import_core()


def _role_to_bone(arm_obj: Any) -> dict[str, str]:
    return {
        k[len("rm_role_") :]: str(arm_obj[k])
        for k in sorted(arm_obj.keys())
        if k.startswith("rm_role_")
    }


def _rest_heads_world(arm_obj: Any, role_to_bone: dict[str, str]) -> dict[str, Any]:

    heads: dict[str, Any] = {}
    for role, bone_name in sorted(role_to_bone.items()):
        bone = arm_obj.data.bones.get(bone_name)
        if bone is not None:
            heads[role] = arm_obj.matrix_world @ bone.matrix_local.to_translation()
    return heads


def _resolve_deformed_mesh(arm_obj: Any) -> Any | None:
    """The rig's armature-deformed mesh (the S37 apply's target); the
    caller reports the loud capability line when None."""
    import bpy

    for mesh in bpy.data.objects:
        if mesh.type != "MESH":
            continue
        for mod in mesh.modifiers:
            if mod.type == "ARMATURE" and mod.object == arm_obj:
                return mesh
    return None


def measure_volume_base_ratios(arm_obj: Any, mesh_obj: Any) -> tuple[dict[str, float], list[str]]:
    """The staged rest-snapshot measurement (WIRING.md): the rig's own
    region ratios from its exact-alpha silhouette at the REST state.

    Saves + clears every pose-bone transform, saves + zeroes every
    shape-key value, stages the WORKBENCH render recipe + a fitted
    frontal camera, renders one frame to a temp file, measures with the
    core's certified ``region_widths`` (anchors = the mapped roles' REST
    heads projected through the staged camera), then restores everything.
    Returns (ratios, notes); raises ``AutoSculptError`` on a starved
    measurement (anchors outside the frame, collapsed torso)."""
    import bpy  # noqa: PLC0415
    from bpy_extras.object_utils import world_to_camera_view  # noqa: PLC0415
    from mathutils import Euler, Matrix, Vector  # noqa: PLC0415

    core = _import_core()
    from riggermortis.sculpt import anchor_points_px, region_widths  # noqa: PLC0415

    role_to_bone = _role_to_bone(arm_obj)
    notes: list[str] = []
    missing = sorted(
        r for r in ("hips", "neck", "upper_leg.L", "upper_leg.R")
        if r not in role_to_bone or role_to_bone[r] not in arm_obj.data.bones
    )
    if missing:
        raise core.AutoSculptError(
            "volume anchors need the mapped hips/neck/upper_leg roles "
            f"(missing: {', '.join(missing)})",
            hint="run Inspect & Map so the rig's roles are assigned",
        )

    # -- stage: the rest snapshot ------------------------------------------
    saved_basis = {pb.name: pb.matrix_basis.copy() for pb in arm_obj.pose.bones}
    for pb in arm_obj.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    # an ASSIGNED ACTION overrides matrix_basis at evaluation (fcurves win),
    # so the snapshot mutes it too — a re-sculpt on an animated rig must
    # measure the rest, never the current frame (the staged restore puts it
    # back untouched; the 5.x slotted-action fields ride along)
    anim = getattr(arm_obj, "animation_data", None)
    saved_action = getattr(anim, "action", None) if anim is not None else None
    saved_slot = getattr(anim, "action_slot", None) if anim is not None else None
    if anim is not None and saved_action is not None:
        anim.action = None
    saved_values: dict[str, tuple[float, bool]] = {}
    if mesh_obj.data.shape_keys is not None:
        drivers = (
            mesh_obj.data.shape_keys.animation_data.drivers
            if mesh_obj.data.shape_keys.animation_data else []
        )
        driven_paths = {fc.data_path for fc in drivers}
        for kb in mesh_obj.data.shape_keys.key_blocks:
            driven = any(
                kb.name in path and path.endswith(".value") for path in driven_paths
            )
            saved_values[kb.name] = (kb.value, driven)
            kb.value = 0.0
            if driven:
                notes.append(
                    f"volume: shape key {kb.name!r} is DRIVEN — the staged "
                    "zero does not hold at evaluation (declared limit); "
                    "the base measurement may include its warp"
                )

    scene = bpy.context.scene
    saved_render = (
        scene.render.engine,
        scene.render.film_transparent,
        scene.render.resolution_x,
        scene.render.resolution_y,
        scene.render.resolution_percentage,
        scene.render.filepath,
        scene.render.image_settings.file_format,
        scene.render.image_settings.color_mode,
        scene.display.shading.light,
        scene.display.shading.color_type,
        scene.camera,
    )

    # world-space anchors from the REST heads (the snapshot state)
    heads = _rest_heads_world(arm_obj, role_to_bone)
    hips_w, neck_w = heads["hips"], heads["neck"]
    span_w = float((Vector(neck_w) - Vector(hips_w)).length)
    if span_w <= 1e-9:
        _restore(
            arm_obj, mesh_obj, saved_basis, saved_values, scene, saved_render,
            anim, saved_action, saved_slot,
        )
        raise core.AutoSculptError(
            "the rig's torso ruler collapsed — volume not applied",
            hint="check the mapped hips/neck roles",
        )

    cam_data = bpy.data.cameras.new("rm_sculpt_cam")
    cam_data.lens = CAM_LENS
    cam = bpy.data.objects.new("rm_sculpt_cam", cam_data)
    scene.collection.objects.link(cam)
    center = (Vector(hips_w) + Vector(neck_w)) / 2.0
    cam.location = (center.x, center.y - CAM_FIT_TORSO * span_w, center.z)
    cam.rotation_euler = Euler((math.pi / 2.0, 0.0, 0.0), "XYZ")  # the fixture recipe
    scene.camera = cam

    out_dir = tempfile.mkdtemp(prefix="rm_sculpt_base_")
    out_path = os.path.join(out_dir, "base.png")  # noqa: PTH118 — staged temp

    try:
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.film_transparent = True
        scene.render.resolution_x = RES_X
        scene.render.resolution_y = RES_Y
        scene.render.resolution_percentage = 100
        scene.render.filepath = out_path
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"
        bpy.ops.render.render(write_still=True)

        # mask from pixels (BOTTOM-UP storage; the measurement wants
        # top-down rows, the project_px convention)
        import numpy as np  # noqa: PLC0415

        img = bpy.data.images.load(out_path)  # noqa: PTH118 — staged temp
        raw = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(raw)
        bpy.data.images.remove(img)
        alpha = raw.reshape(-1, 4)[:, 3].reshape(RES_Y, RES_X) > 0.5
        mask = alpha[::-1]

        def project(p_world: Any) -> tuple[float, float]:
            v = world_to_camera_view(scene, cam, Vector(p_world))
            return (v.x * RES_X, (1.0 - v.y) * RES_Y)

        anchors_px, torso_px = anchor_points_px({
            "hips": tuple(project(hips_w)),
            "neck": tuple(project(neck_w)),
            "upper_leg.L": tuple(project(heads["upper_leg.L"])),
            "upper_leg.R": tuple(project(heads["upper_leg.R"])),
        })
        k = core.MEDIAN_HALF_BAND  # the median band's reach guards the rows
        for name, (ax, ay) in sorted(anchors_px.items()):
            if not (k <= ay <= RES_Y - 1 - k and 0 <= ax < RES_X):
                raise core.AutoSculptError(
                    f"volume anchor {name!r} projected outside the staged "
                    "frame",
                    hint="the rig does not fit the declared frontal class "
                         "at this framing — check the rig's placement",
                )
        ratios = region_widths(mask, anchors_px, torso_px)
    finally:
        _restore(
            arm_obj, mesh_obj, saved_basis, saved_values, scene, saved_render,
            anim, saved_action, saved_slot,
        )
        import contextlib  # noqa: PLC0415

        with contextlib.suppress(OSError):
            bpy.data.objects.remove(cam)
        with contextlib.suppress(OSError):
            os.remove(out_path)
            os.rmdir(out_dir)
    return ratios, notes


def _restore(
    arm_obj: Any,
    mesh_obj: Any,
    saved_basis: dict[str, Any],
    saved_values: dict[str, tuple[float, bool]],
    scene: Any,
    saved_render: tuple,
    anim: Any = None,
    saved_action: Any = None,
    saved_slot: Any = None,
) -> None:
    """Restore EVERYTHING the snapshot staged (the turntable discipline)."""
    import bpy  # noqa: PLC0415

    for pb in arm_obj.pose.bones:
        if pb.name in saved_basis:
            pb.matrix_basis = saved_basis[pb.name]
    if anim is not None and saved_action is not None:
        anim.action = saved_action
        if saved_slot is not None:
            import contextlib as _contextlib  # noqa: PLC0415

            with _contextlib.suppress(Exception):
                anim.action_slot = saved_slot
    if mesh_obj.data.shape_keys is not None:
        for kb in mesh_obj.data.shape_keys.key_blocks:
            if kb.name in saved_values:
                kb.value = saved_values[kb.name][0]
    (
        engine, film, res_x, res_y, pct, filepath, fmt, color_mode,
        shade_light, shade_color, cam,
    ) = saved_render
    scene.render.engine = engine
    scene.render.film_transparent = film
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = pct
    scene.render.filepath = filepath
    scene.render.image_settings.file_format = fmt
    scene.render.image_settings.color_mode = color_mode
    scene.display.shading.light = shade_light
    scene.display.shading.color_type = shade_color
    scene.camera = cam
    bpy.context.view_layer.update()


def _apply_proportion_half(arm_obj: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Payload positions -> reference ratios -> the S36 apply (UNCHANGED).
    Raises ``ValueError``/``AutoSculptError`` on malformed inputs; a
    starved rig is refused by the report (the capability lines)."""
    core = _import_core()
    from riggermortis.auto_sculpt import (  # noqa: PLC0415
        build_proportion_target,
        measure_proportion_ratios,
    )

    from . import auto_sculpt as addon_auto_sculpt  # noqa: PLC0415

    pose_dict = pose_apply.payload_module().pose_for_figure(payload, None)
    raw = pose_dict.get("positions")
    if not isinstance(raw, dict) or not raw:
        raise ValueError(
            "the payload's figure carries no solved positions "
            "(hint: regenerate with: rigpose pose <image> <rig.json> --out payload.json)"
        )
    ref_positions = {str(r): (float(p[0]), float(p[1]), float(p[2])) for r, p in raw.items()}
    ref_ratios = measure_proportion_ratios(ref_positions)

    role_to_bone = _role_to_bone(arm_obj)
    heads = _rest_heads_world(arm_obj, role_to_bone)
    base = {r: (float(v.x), float(v.y), float(v.z)) for r, v in sorted(heads.items())}
    lines = core.sculpt_capability_lines(set(base))
    if lines:
        return {
            "applied": False,
            "capability_lines": lines,
            "factors": {},
            "adjusted": [],
            "notes": ["refused loud — nothing applied"],
        }
    base_ratios = measure_proportion_ratios(base)
    target, factors, adjusted = build_proportion_target(base, ref_ratios, base_ratios)
    obj_scale = float(arm_obj.scale.x) if abs(float(arm_obj.scale.x)) > 1e-9 else 0.0
    if obj_scale == 0.0:
        raise ValueError(
            "the rig's object scale collapsed — proportions not applied "
            "(hint: check the armature's transform; the response solve "
            "needs a sane uniform scale)"
        )
    space_scale = 1.0 / obj_scale
    rep = addon_auto_sculpt.apply_proportion_sculpt(arm_obj, target, base, space_scale)
    return {
        "applied": bool(rep.get("applied")),
        "capability_lines": list(rep.get("capability_lines", [])),
        "factors": {k: round(v, 6) for k, v in sorted(factors.items())},
        "adjusted": list(adjusted),
        "worst_frac": rep.get("worst_frac"),
        "within_bar": rep.get("within_bar"),
        "notes": list(rep.get("notes", [])),
    }


def _apply_volume_half(arm_obj: Any, solve: Any) -> dict[str, Any]:
    """Solve artifact + the staged base measurement -> factors -> the S37
    apply (UNCHANGED). Raises on starved measurements; the clamp notes
    land in the report (loud)."""

    core = _import_core()
    from . import volume as addon_volume  # noqa: PLC0415

    mesh_obj = _resolve_deformed_mesh(arm_obj)
    if mesh_obj is None:
        return {
            "applied": False,
            "capability_lines": list(core.volume_capability_lines(False)),
            "factors": {},
            "notes": ["refused loud — nothing applied"],
        }
    base_ratios, notes = measure_volume_base_ratios(arm_obj, mesh_obj)
    factors = core.solve_factors(solve.volume_ratios, base_ratios)
    clamp_notes = [
        "volume: clamped loudly at " + p for p in core.clamp_note_params(factors)
    ]
    role_to_bone = _role_to_bone(arm_obj)
    rep = addon_volume.apply_volume_sculpt(arm_obj, mesh_obj, factors, role_to_bone)
    return {
        "applied": bool(rep.get("applied")),
        "capability_lines": list(rep.get("capability_lines", [])),
        "factors": {k: round(v, 6) for k, v in sorted(factors.items())},
        "values": {k: float(v) for k, v in sorted(rep.get("values", {}).items())},
        "keys": list(rep.get("keys", [])),
        "notes": notes + list(rep.get("notes", [])) + clamp_notes,
    }


def apply_sculpt(
    arm_obj: Any,
    payload: dict[str, Any] | None = None,
    solve: Any | None = None,
    proportions: bool = True,
    volume: bool = True,
) -> dict[str, Any]:
    """Apply the static sculpt (proportions + volume) to the rig — the
    operator and the session action's shared path. The halves are
    independent; a missing input for a half reports the loud capability
    line and the other half still applies. Raises ``ValueError`` on
    malformed inputs (actionable, per the operator contract)."""
    if arm_obj is None or arm_obj.type != "ARMATURE":
        raise ValueError("apply_sculpt needs an armature (got none)")
    report: dict[str, Any] = {
        "proportions": None,
        "volume": None,
        "capability_lines": [],
        "notes": [],
    }
    if payload is not None and solve is not None:
        # the solve records the figure label it measured; the payload apply
        # uses the payload's SELECTED figure — a mismatch is loud, never silent
        try:
            selected = pose_apply.payload_module().entry_for_label(payload, None)
            if str(selected.get("label", "")) != solve.figure:
                report["notes"].append(
                    f"sculpt: the solve measured {solve.figure!r} but the "
                    f"payload's selected figure is "
                    f"{str(selected.get('label', ''))!r} — applied anyway "
                    "(declared: the halves ride their own selections)"
                )
        except Exception:  # noqa: BLE001 — the note is best-effort
            pass
    if proportions:
        if payload is None:
            report["capability_lines"].append(CAPABILITY_NO_PAYLOAD)
        else:
            report["proportions"] = _apply_proportion_half(arm_obj, payload)
            report["capability_lines"].extend(report["proportions"]["capability_lines"])
            report["notes"].extend(
                f"proportions: {n}" for n in report["proportions"]["notes"]
            )
    if volume:
        if solve is None:
            report["capability_lines"].append(CAPABILITY_NO_SCULPT)
        else:
            report["volume"] = _apply_volume_half(arm_obj, solve)
            report["capability_lines"].extend(report["volume"]["capability_lines"])
            report["notes"].extend(f"volume: {n}" for n in report["volume"]["notes"])
    return report


def report_lines(report: dict[str, Any]) -> list[str]:
    """The panel-friendly summary lines (loud, never swallowed)."""
    lines: list[str] = []
    prop = report.get("proportions")
    if prop is not None and prop.get("applied"):
        worst = prop.get("worst_frac")
        lines.append(
            f"proportions applied: {len(prop.get('adjusted', []))} ruler(s)"
            + ("" if worst is None else f", worst {worst:.4f} (bar 0.05)")
        )
    vol = report.get("volume")
    if vol is not None and vol.get("applied"):
        lines.append(
            f"volume applied: {len(vol.get('keys', []))} key(s), factors "
            + " ".join(f"{k}={v:.3f}" for k, v in sorted(vol.get("factors", {}).items()))
        )
    lines.extend(report.get("capability_lines", []))
    lines.extend(report.get("notes", []))
    return lines
