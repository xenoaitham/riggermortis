"""P9-1 auto-sculpt gate (run INSIDE Blender, headless) — the RM_ASCULPT
GATE rows, the sibling of scene_gate/couple_gate/.../review_ux_gate (the
Mimosa new-file rule). The SELECTED mechanism (docs/AUTO_SCULPT.md § Probe
answers: armature_scale_correctives, pose-translation delivery) through the
REAL addon apply path:

1. GATE-SCALE    — the addon apply on BOTH rig classes x the 3 reference
                   classes: per-joint worst frac vs the Annex A.1 5% bar.
2. GATE-FOLLOW   — the skinned mesh follows through real LBS (the follow
                   instrument at the probe-earned threshold).
3. GATE-COMPOSE  — sculpt, then a REAL payload pose through pose_apply:
                   FK direction family <= 0.5 deg AND the sculpted girdle
                   width SURVIVES the pose (locations are rigid offsets;
                   the apply writes rotations only).
4. GATE-NOTARGET — a rig missing mapped roles: the loud capability line
                   verbatim, nothing applied.
5. GATE-UNTOUCHED — a zero-delta target writes NO pose locations and the
                   pose state stays byte-identical (the no-op contract).
6. GATE-TWIN     — twin sculpt runs byte-identical (pose locations).

Fixtures are the PROBE's builders (ONE copy — the motion_fixture rule):
engine-built canonical-class + mixamorig-class armatures with skinned
meshes, deterministic nearest-bone weights. Rows print as
`RM_ASCULPT GATE-...: PASS|FAIL <detail>`; the final `RM_ASCULPT GATE:
PASS` is the crash-proof contract. Usage:

    blender -b --python xtask/auto_sculpt_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR (required).
"""
from __future__ import annotations

import math
import os
import sys

_core_src = os.environ.get("RM_CORE_SRC")
_addon_dir = os.environ.get("RM_ADDON_DIR")
if not _core_src or not _addon_dir:
    raise SystemExit("RM_CORE_SRC and RM_ADDON_DIR are required")
for _p in (_core_src, _addon_dir, os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import auto_sculpt_probe as probe  # noqa: E402
import bpy  # noqa: E402
import riggermortis as core  # noqa: E402
from riggermortis_addon import auto_sculpt as addon_sculpt  # noqa: E402
from riggermortis_addon import pose_apply  # noqa: E402

OK = True


def check(label: str, ok: bool, detail: str = "") -> bool:
    global OK
    if not ok:
        OK = False
    print(f"RM_ASCULPT {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _head_world(arm_obj, bone_name: str) -> tuple[float, float, float]:
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = arm_obj.evaluated_get(deps)
    w = ev.matrix_world @ ev.pose.bones[bone_name].matrix.to_translation()
    return (w.x, w.y, w.z)


def _posed_rotations_bytes(arm_obj) -> dict[str, tuple]:
    return {
        pb.name: (tuple(pb.location), tuple(pb.rotation_axis_angle), pb.rotation_mode)
        for pb in sorted(arm_obj.pose.bones, key=lambda b: b.name)
    }


def main() -> int:
    fresh_scene()
    base_ratios = core.measure_proportion_ratios(probe.BASE_JOINTS)

    fixtures = {}
    for mixamo in (False, True):
        tag = "mixamo" if mixamo else "metarig"
        fixtures[mixamo] = probe.build_fixture(f"gate_{tag}_base", mixamo=mixamo)
    check(
        "GATE-FIXTURE",
        all(f["n_weighted"] > 0 for f in fixtures.values()),
        "the probe's builders, ONE fixture copy (the motion_fixture rule)",
    )

    # ---- GATE-SCALE + GATE-FOLLOW (the real addon apply) ------------------
    scale_ok = True
    follow_ok = True
    scale_notes: list[str] = []
    for mixamo in (False, True):
        tag = "mixamo" if mixamo else "metarig"
        base_local = probe.rest_joints(fixtures[mixamo])
        for class_name in sorted(probe.REF_CLASSES):
            deltas = probe.REF_CLASSES[class_name]
            ref = probe.class_ratios(base_ratios, deltas)
            tgt, _f, _a = core.build_proportion_target(base_local, ref, base_ratios)
            rep = addon_sculpt.apply_proportion_sculpt(fixtures[mixamo]["arm"], tgt, base_local, space_scale=fixtures[mixamo]["space_scale"])
            achieved = {}
            arm = fixtures[mixamo]["arm"]
            for role, bone_name in fixtures[mixamo]["role_to_bone"].items():
                t = arm.pose.bones[bone_name].matrix.to_translation()
                achieved[role] = (t.x, t.y, t.z)
            worst, _fr, wrole, within = core.validate_sculpt(achieved, tgt, base_local)
            scale_ok &= rep["applied"] and within
            scale_notes.append(f"{tag}/{class_name}: worst={worst:.4f}@{wrole}")
            if class_name == "heavy":
                follow = addon_sculpt.measure_mesh_follow(fixtures[mixamo]["mesh"], fixtures[mixamo]["space_scale"])
                follow_ok &= follow > 0.5
                scale_notes.append(f"{tag}: follow={follow:.2f}")
    check("GATE-SCALE", scale_ok, "; ".join(scale_notes))
    check("GATE-FOLLOW", follow_ok, "LBS follow-through at the 1e-6 threshold")

    # ---- GATE-COMPOSE (sculpt + a REAL payload pose) -----------------------
    compose_ok = True
    fx = fixtures[False]
    base_local = probe.rest_joints(fx)
    ref = probe.class_ratios(base_ratios, probe.REF_CLASSES["heavy"])
    tgt, _f, _a = core.build_proportion_target(base_local, ref, base_ratios)
    rep_sculpt = addon_sculpt.apply_proportion_sculpt(fx["arm"], tgt, base_local)
    compose_ok &= rep_sculpt["applied"]
    pose_positions = dict(probe.BASE_JOINTS)
    pose_positions["forearm.L"] = (0.30, -0.10, 1.20)
    pose_positions["forearm.R"] = (-0.30, -0.10, 1.20)
    pose_positions["hand.L"] = (0.36, -0.16, 1.10)
    pose_positions["hand.R"] = (-0.36, -0.16, 1.10)
    pose = core.CanonicalPose(
        positions=pose_positions,
        flips={},
        confidence=1.0,
        reliable=True,
        scale=100.0,
        anchor="hips",
        joint_confidence={r: 0.95 for r in pose_positions},
    )
    rep = pose_apply.apply_pose_object(fx["arm"], pose, core)
    compose_ok &= rep["worst_deg"] <= 0.5
    widths = (
        math.dist(_head_world(fx["arm"], fx["role_to_bone"]["upper_arm.L"]), _head_world(fx["arm"], fx["role_to_bone"]["upper_arm.R"])),
        math.dist(tgt["upper_arm.L"], tgt["upper_arm.R"]),
    )
    drift = abs(widths[0] - widths[1])
    # 1e-5 m: an order above the evaluated-matrix read noise (the probe's
    # float32 lesson), ten micrometers — invisible at posing distance
    compose_ok &= drift < 1e-5
    check(
        "GATE-COMPOSE",
        compose_ok,
        f"payload apply worst {rep['worst_deg']:.4f} deg (bar 0.5); sculpted girdle width survives:"
        f" posed {widths[0]:.6f} vs target {widths[1]:.6f} (drift {drift:.2e})",
    )

    # ---- GATE-NOTARGET ------------------------------------------------------
    fxn = probe.build_fixture("gate_notarget", with_mesh=True)
    del fxn["arm"]["rm_role_lower_leg.L"]
    repn = addon_sculpt.apply_proportion_sculpt(fxn["arm"], tgt, base_local)
    loud = (not repn["applied"]) and repn["capability_lines"] and "lower_leg.L" in repn["capability_lines"][0]
    check("GATE-NOTARGET", bool(loud), repn["capability_lines"][0] if repn["capability_lines"] else "NO LINE")
    probe.cleanup_fixtures(fxn)

    # ---- GATE-UNTOUCHED (zero-delta target = structural no-op) --------------
    fxu = probe.build_fixture("gate_untouched", with_mesh=True)
    base_u = probe.rest_joints(fxu)
    before = _posed_rotations_bytes(fxu["arm"])
    repu = addon_sculpt.apply_proportion_sculpt(fxu["arm"], base_u, base_u)
    after = _posed_rotations_bytes(fxu["arm"])
    untouched = (
        repu["applied"]
        and all(loc == (0.0, 0.0, 0.0) for loc in repu["pose_locations"].values())
        and before == after
    )
    check("GATE-UNTOUCHED", untouched, "zero-delta target: no locations written, pose state byte-identical")
    probe.cleanup_fixtures(fxu)

    # ---- GATE-TWIN ----------------------------------------------------------
    twins = []
    for name in ("gate_twin1", "gate_twin2"):
        fxd = probe.build_fixture(name, mixamo=False)
        bl = probe.rest_joints(fxd)
        reft = probe.class_ratios(base_ratios, probe.REF_CLASSES["heavy"])
        td, _fd, _ad = core.build_proportion_target(bl, reft, base_ratios)
        repd = addon_sculpt.apply_proportion_sculpt(fxd["arm"], td, bl)
        twins.append(repd["pose_locations"])
        probe.cleanup_fixtures(fxd)
    identical = twins[0].keys() == twins[1].keys() and all(twins[0][k] == twins[1][k] for k in twins[0])
    check("GATE-TWIN", identical, f"{len(twins[0])} pose bones byte-identical")

    # ---- verdict ------------------------------------------------------------
    check("GATE", OK, "the gate's rows above are the contract")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
