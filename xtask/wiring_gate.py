"""P9-3 wiring gate (run INSIDE Blender, headless) — the RM_WIRE rows, the
volume_gate sibling (the Mimosa new-file rule). The wiring of record is
docs/WIRING.md: proportion + volume applied ONCE at the rest state, BEFORE
animation drives the rig, through the ONE shared addon path
(riggermortis_addon.sculpt_wire.apply_sculpt — the operator AND the session
action run it):

1. WIRE-FIXTURE  — both rig classes build (the S37 probe's builders, ONE
                   fixture copy — the motion_fixture rule).
2. WIRE-MEASURE  — the wiring's staged rest-snapshot measurement on the
                   PRISTINE fixtures reproduces the S37 pipeline's
                   exact-alpha instrument (per-band relative tolerance
                   2e-2 — same instrument, different plumbing; declared).
3. WIRE-SOLVE    — authored reference ratios -> factors -> the volume
                   apply: factors land exact and every pose bone is
                   byte-identical through the key warp (the invariance
                   contract).
4. WIRE-FLOW     — THE animation-order proof: sculpt -> a REAL 5-frame
                   action through the add-on bake path -> (a) shape-key
                   values + pose locations byte-identical pre/post,
                   (b) frame-one band width drift <= 1e-05 m, (c) FK
                   re-eval worst <= 0.5 deg at every frame, (d) the
                   action's fcurves carry rotation channels only
                   (per-frame soft tissue OUT, structural).
5. WIRE-RESCULPT — re-apply at the sculpt frame AFTER the animation: the
                   staged rest snapshot mutes the action, the factors
                   re-solve identically, key values re-land
                   BYTE-IDENTICAL, the proportion target re-lands within
                   its bar, and the action stays assigned and untouched.
6. WIRE-OPS      — the REAL operator (bpy.ops.rm.apply_sculpt, the addon
                   enabled the checkbox way) lands the direct path's
                   state exactly; {'FINISHED'} on success (the S34
                   operator classes).
7. WIRE-SESSION  — the session executor's `sculpt` action lands the same
                   state through the same shared function.
8. WIRE-NOTARGET — the loud refusals verbatim (no mesh / starved roles).
9. WIRE-DETERM   — twin wiring runs byte-identical.

SCENE LAW (the S37 lesson, earned twice here): every render-adjacent case
runs in a FRESH scene containing exactly ITS fixture — two classes share
one world position, and a sculpted neighbour silently poisons the next
case's render-based base measurement (the first draft's WIRE-SOLVE read
1.15/0.9987 exactly this way).

Rows print as `RM_WIRE ...: PASS|FAIL <detail>`; the final
`RM_WIRE GATE: PASS` is the crash-proof contract (grep-tested both
shapes; no `: FAIL` row may exist on a green run). Model-free by
construction (the u2net-dependent product solve is the CLI's
solve-sculpt; its math is contract-tested in core). Usage:

    blender -b --python xtask/wiring_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR (required).
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

_core_src = os.environ.get("RM_CORE_SRC")
_addon_dir = os.environ.get("RM_ADDON_DIR")
if not _core_src or not _addon_dir:
    raise SystemExit("RM_CORE_SRC and RM_ADDON_DIR are required")
for _p in (_core_src, _addon_dir, os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import auto_sculpt_probe as probe9  # noqa: E402
import bpy  # noqa: E402
import mathutils  # noqa: E402
import riggermortis as core  # noqa: E402
import volume_common as vc  # noqa: E402
import volume_gate as vgate  # noqa: E402
import volume_probe as vprobe  # noqa: E402
from riggermortis_addon import (  # noqa: E402
    bake as addon_bake,
)
from riggermortis_addon import (
    pose_apply,
)
from riggermortis_addon import (
    sculpt_wire as wire,
)
from riggermortis_addon import (
    session as addon_session,
)

OK = True

# The scratch dir — a module-level literal (the volume_common shape; the
# out/ tree is gitignored, nothing commits).
SCRATCH = Path(__file__).resolve().parents[1] / "out" / "wiring_gate"
P_PAYLOAD = str(SCRATCH / "payload.json")
P_SOLVE = str(SCRATCH / "sculpt.json")
P_RENDER = str(SCRATCH / "direct_alpha.png")

BANDS = tuple(core.BAND_PARAMS)
MEASURE_TOL = 2e-2  # declared: WIRE-MEASURE's relative per-band tolerance
DRIFT_BAR = 1e-5  # the S36 GATE-COMPOSE family
FK_BAR_DEG = 0.5  # the certified FK family
AUTHORED = 1.15  # the gate's authored volume reference delta


def check(label: str, ok: bool, detail: str = "") -> bool:
    global OK
    if not ok:
        OK = False
    print(f"RM_WIRE {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def pose_location_bytes(arm_obj) -> dict[str, tuple]:
    return {
        pb.name: tuple(pb.location)
        for pb in sorted(arm_obj.pose.bones, key=lambda b: b.name)
    }


def shape_key_values(mesh_obj) -> dict[str, float]:
    if mesh_obj is None or mesh_obj.data.shape_keys is None:
        return {}
    return {kb.name: kb.value for kb in mesh_obj.data.shape_keys.key_blocks}


def heavy_positions() -> dict[str, tuple[float, float, float]]:
    """The declared GT reference family (the S36 heavy class made concrete:
    shoulders +25%, hips +20%, torso + limbs unchanged)."""
    pos = dict(probe9.BASE_JOINTS)
    for side in ("L", "R"):
        x, y, z = pos[f"upper_arm.{side}"]
        pos[f"upper_arm.{side}"] = (x * 1.25, y, z)
        x, y, z = pos[f"upper_leg.{side}"]
        pos[f"upper_leg.{side}"] = (x * 1.20, y, z)
    return pos


def gt_payload() -> dict:
    """A contract-valid payload dict (v1 shape; the wiring reads it through
    the REAL payload contract)."""
    positions = heavy_positions()
    pose = core.CanonicalPose(
        positions=positions,
        flips={},
        confidence=1.0,
        reliable=True,
        scale=100.0,
        anchor="hips",
        joint_confidence={r: 0.95 for r in positions},
    )
    return {
        "format": 1,
        "figure": {"label": "figure 1", "index": 0, "score": 1.0, "bbox": []},
        "pose": pose.to_dict(),
    }


def gt_solve(volume_ratios: dict[str, float]) -> dict:
    """The sculpt solve artifact dict (format 1; authored volume ratios,
    the proportion ratios measured from the GT payload positions)."""
    ratios = core.measure_proportion_ratios(heavy_positions())
    return core.SculptSolve(
        figure="figure 1",
        reference_image="gate://heavy",
        image_size=(vc.RES_X, vc.RES_Y),
        reference_ratios=ratios,
        volume_ratios=volume_ratios,
    ).to_dict()


def swing_pose(theta_deg: float) -> core.CanonicalPose:
    """A real arm-swing frame (the left forearm raised about the elbow; the
    certified FK consumes positions)."""
    pos = dict(probe9.BASE_JOINTS)
    t = math.radians(theta_deg)
    top_forearm = probe9.BASE_JOINTS["upper_arm.L"]
    top_hand = probe9.BASE_JOINTS["forearm.L"]
    len_forearm = math.dist(probe9.BASE_JOINTS["forearm.L"], top_forearm)
    len_hand = math.dist(probe9.BASE_JOINTS["hand.L"], top_hand)
    pos["forearm.L"] = (
        top_forearm[0] + len_forearm * math.sin(t),
        top_forearm[1],
        top_forearm[2] - len_forearm * math.cos(t),
    )
    pos["hand.L"] = (
        top_hand[0] + len_hand * math.sin(t),
        top_hand[1],
        top_hand[2] - len_hand * math.cos(t),
    )
    return core.CanonicalPose(
        positions=pos,
        flips={},
        confidence=1.0,
        reliable=True,
        scale=100.0,
        anchor="hips",
        joint_confidence={r: 0.95 for r in pos},
    )


def reeval(obj, mapping, frames) -> tuple[int, float]:
    """Independent fcurve re-evaluation (the RM_BAKE recipe): mapped-role
    bone world directions vs the canonical targets. The bake's default
    frame_offset 1 maps source frame f to Blender frame f+1 — the re-eval
    reads the SAME mapping (the first draft read one frame early and
    measured exactly the 20-deg frame spacing)."""
    worst, checked = 0.0, 0
    for af in frames:
        bpy.context.scene.frame_set(af.frame + 1)
        bpy.context.view_layer.update()
        for role, assignment in sorted(mapping.assignments.items()):
            target = core.bone_target_direction(af.pose, role)
            if target is None:
                continue
            pb = obj.pose.bones.get(assignment.bone)
            if pb is None:
                continue
            d = (pb.matrix.to_3x3() @ mathutils.Vector((0.0, 1.0, 0.0))).normalized()
            checked += 1
            worst = max(worst, math.degrees(d.angle(mathutils.Vector(target).normalized())))
    return checked, worst


def action_fcurves(arm_obj):
    anim = getattr(arm_obj, "animation_data", None)
    if anim is None or anim.action is None:
        return []
    try:  # the 5.x slotted-action API, with the legacy fallback
        return list(anim.action.layers[0].strips[0].channelbags[0].fcurves)
    except (AttributeError, IndexError):
        return list(anim.action.fcurves)


def direct_alpha_ratios(fx: dict) -> dict[str, float]:
    """The S37 pipeline's own instrument: render the pristine fixture with
    the pipeline camera recipe, measure the exact alpha with the core's
    region_widths (the model-free measurement the certified rows rode)."""
    import numpy as np

    scene, cam = vprobe.setup_scene_and_render(P_RENDER)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(P_RENDER)
    raw = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(raw)
    bpy.data.images.remove(img)
    mask = (raw.reshape(-1, 4)[:, 3].reshape(vc.RES_Y, vc.RES_X) > 0.5)[::-1]
    anchors_px = {
        name: vprobe.project_px(scene, cam, p)
        for name, p in vprobe.anchors_world(fx).items()
    }
    return vc.region_widths(mask, vc.anchors_px_of(anchors_px), vc.torso_px_of(anchors_px))


def gate_solve(staged: dict[str, float]) -> core.SculptSolve:
    """The gate's solve artifact: authored reference ratios = the measured
    base x the authored delta (so the solved factors must land EXACT)."""
    return core.SculptSolve.from_dict(
        gt_solve({p: staged[p] * AUTHORED for p in BANDS})
    )


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)

    # ---- WIRE-FIXTURE + WIRE-MEASURE (fresh scene per class — the scene law)
    fixture_ok = True
    measure_ok = True
    notes: list[str] = []
    staged_ratios: dict[bool, dict[str, float]] = {}
    for mixamo in (False, True):
        tag = "mixamo" if mixamo else "metarig"
        fresh_scene()
        fx = vprobe.build_volume_fixture(f"wire_{tag}_base", mixamo=mixamo)
        fixture_ok &= fx["mesh"] is not None and fx["n_weighted"] > 0
        staged, _n = wire.measure_volume_base_ratios(fx["arm"], fx["mesh"])
        staged_ratios[mixamo] = staged
        direct = direct_alpha_ratios(fx)
        worst_rel = 0.0
        for param in BANDS:
            denom = max(abs(direct[param]), 1e-9)
            worst_rel = max(worst_rel, abs(staged[param] - direct[param]) / denom)
        measure_ok &= worst_rel <= MEASURE_TOL
        notes.append(f"{tag}: worst rel {worst_rel:.4f} (bar {MEASURE_TOL})")
    check(
        "WIRE-FIXTURE", fixture_ok,
        "both classes build (the S37 builders, ONE fixture copy)",
    )
    check("WIRE-MEASURE", measure_ok, "; ".join(notes))

    # ---- WIRE-SOLVE (factors -> values, joints invariant) -------------------
    solve_ok = True
    notes = []
    for mixamo in (False, True):
        tag = "mixamo" if mixamo else "metarig"
        fresh_scene()
        fx = vprobe.build_volume_fixture(f"wire_{tag}_solve", mixamo=mixamo)
        solve = gate_solve(staged_ratios[mixamo])
        joints_before = pose_location_bytes(fx["arm"])
        rep = wire.apply_sculpt(fx["arm"], payload=None, solve=solve, proportions=False)
        vol = rep["volume"]
        factors_exact = (
            vol is not None and vol["applied"]
            and all(abs(vol["factors"][p] - AUTHORED) < 1e-6 for p in BANDS)
        )
        joints_after = pose_location_bytes(fx["arm"])
        invariant = joints_before == joints_after
        solve_ok &= factors_exact and invariant
        notes.append(
            f"{tag}: factors exact={factors_exact} joints invariant={invariant} "
            f"applied={vol is not None and vol['applied']}"
        )
    check("WIRE-SOLVE", solve_ok, "; ".join(notes))

    # ---- WIRE-FLOW + WIRE-RESCULPT (THE animation-order proof) --------------
    flow_ok = True
    notes = []
    for mixamo in (False, True):
        tag = "mixamo" if mixamo else "metarig"
        fresh_scene()
        fx = vprobe.build_volume_fixture(f"wire_{tag}_flow", mixamo=mixamo)
        arm, mesh = fx["arm"], fx["mesh"]
        payload = gt_payload()
        solve = gate_solve(staged_ratios[mixamo])
        rep1 = wire.apply_sculpt(arm, payload=payload, solve=solve)
        applied = (
            rep1["proportions"] is not None and rep1["proportions"]["applied"]
            and rep1["volume"] is not None and rep1["volume"]["applied"]
        )
        keys_pre = shape_key_values(mesh)
        locs_pre = pose_location_bytes(arm)
        bpy.context.view_layer.update()
        ext_pre = {p: vgate.band_extent(fx, p) for p in BANDS}

        # the REAL bake path: 5 frames of a real arm swing; the default
        # frame_offset 1 keeps the sculpt at Blender frame one
        poses = [swing_pose(t) for t in (0.0, 20.0, 40.0, 60.0, 80.0)]
        action = core.action_from_poses(list(enumerate(poses)))
        baked = addon_bake.bake_action(arm, action.frames, core, name=f"rm_wire_{tag}")

        keys_post = shape_key_values(mesh)
        locs_post = pose_location_bytes(arm)
        sculpt_survives = keys_pre == keys_post and locs_pre == locs_post

        fcurves = action_fcurves(arm)
        rotations_only = bool(fcurves) and all(
            fc.data_path.endswith("rotation_axis_angle") for fc in fcurves
        )

        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        ext_f1 = {p: vgate.band_extent(fx, p) for p in BANDS}
        worst_drift = max(abs(ext_f1[p] - ext_pre[p]) for p in BANDS)

        mapping = pose_apply.mapping_from_props(arm, core)
        checked, worst_fk = reeval(arm, mapping, action.frames)

        ok_row = (
            applied and sculpt_survives and rotations_only
            and worst_drift <= DRIFT_BAR
            and baked["worst_deg"] <= FK_BAR_DEG
            and worst_fk <= FK_BAR_DEG
        )
        flow_ok &= ok_row
        notes.append(
            f"{tag}: applied={applied} sculpt survives={sculpt_survives} "
            f"rot-only fcurves={rotations_only} "
            f"frame1 drift={worst_drift:.2e} (bar {DRIFT_BAR}) "
            f"bake worst={baked['worst_deg']:.4f} reeval worst={worst_fk:.4f} "
            f"deg ({checked} checks; bars {FK_BAR_DEG})"
        )

        # ---- WIRE-RESCULPT: re-apply AT THE SCULPT FRAME after the
        # animation (the artist exit). The solve's locations may differ
        # from the first apply's BY DESIGN only if the frame's rotations
        # differ from rest — at frame one the swing is at rest, so the
        # honest checks are: values byte-identical, the proportion target
        # re-landed within its bar, and the action intact.
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        anim = getattr(arm, "animation_data", None)
        action_before = getattr(anim, "action", None)
        rep2 = wire.apply_sculpt(arm, payload=payload, solve=solve)
        values_identical = rep1["volume"]["values"] == rep2["volume"]["values"]
        resculpt_ok = (
            rep2["proportions"] is not None and rep2["proportions"]["applied"]
            and rep2["proportions"]["within_bar"]
            and rep2["volume"] is not None and rep2["volume"]["applied"]
            and values_identical
            and action_before is not None
            and getattr(anim, "action", None) is action_before
        )
        check(
            "WIRE-RESCULPT",
            resculpt_ok,
            f"{tag}: values byte-identical={values_identical} "
            f"target re-landed={rep2['proportions']['within_bar']} "
            f"(worst {rep2['proportions']['worst_frac']:.6f}) "
            f"action intact={getattr(anim, 'action', None) is action_before}",
        )
        flow_ok &= resculpt_ok
    check("WIRE-FLOW", flow_ok, "; ".join(notes))

    # ---- WIRE-OPS + WIRE-SESSION (the user-facing surfaces; one fixture per
    # scene — the scene law: a sculpted neighbour poisons the next render)
    Path(P_PAYLOAD).write_text(json.dumps(gt_payload(), sort_keys=True), encoding="utf-8")
    Path(P_SOLVE).write_text(
        json.dumps(gt_solve({p: staged_ratios[False][p] * AUTHORED for p in BANDS}),
                   sort_keys=True),
        encoding="utf-8",
    )
    solve_file = core.SculptSolve.from_dict(
        json.loads(Path(P_SOLVE).read_text(encoding="utf-8"))
    )

    # the DIRECT path (the shared function, the reference bytes; own scene)
    fresh_scene()
    fx_dir = vprobe.build_volume_fixture("wire_dir", mixamo=False)
    wire.apply_sculpt(fx_dir["arm"], payload=gt_payload(), solve=solve_file)
    direct_keys = shape_key_values(fx_dir["mesh"])
    direct_locs = pose_location_bytes(fx_dir["arm"])

    # the REAL operator (the addon enabled the checkbox way; own scene)
    fresh_scene()
    import addon_utils

    addon_utils.enable("riggermortis_addon", default_set=False, persistent=False)
    fx_ops = vprobe.build_volume_fixture("wire_ops", mixamo=False)
    scene = bpy.context.scene
    scene.rm_settings.payload_path = P_PAYLOAD
    scene.rm_settings.sculpt_path = P_SOLVE
    bpy.context.view_layer.objects.active = fx_ops["arm"]
    result = bpy.ops.rm.apply_sculpt()
    ops_keys = shape_key_values(fx_ops["mesh"])
    ops_locs = pose_location_bytes(fx_ops["arm"])
    ops_ok = (
        set(result) == {"FINISHED"}
        and ops_keys == direct_keys and ops_locs == direct_locs
    )
    check(
        "WIRE-OPS", ops_ok,
        f"result={sorted(result)} keys byte-identical={ops_keys == direct_keys} "
        f"locations byte-identical={ops_locs == direct_locs}",
    )

    # the session executor (the agent path; own scene)
    fresh_scene()
    fx_ses = vprobe.build_volume_fixture("wire_ses", mixamo=False)
    ses = addon_session.execute_action({
        "kind": "sculpt",
        "params": {
            "payload_path": P_PAYLOAD,
            "sculpt_path": P_SOLVE,
            "armature_name": fx_ses["arm"].name,
        },
    })
    ses_keys = shape_key_values(fx_ses["mesh"])
    ses_locs = pose_location_bytes(fx_ses["arm"])
    ses_ok = (
        ses["ok"] is True and ses["report"]["armature"] == fx_ses["arm"].name
        and ses_keys == direct_keys and ses_locs == direct_locs
    )
    check(
        "WIRE-SESSION", ses_ok,
        f"ok={ses['ok']} keys byte-identical={ses_keys == direct_keys} "
        f"locations byte-identical={ses_locs == direct_locs}",
    )

    # ---- WIRE-NOTARGET (the loud refusals, verbatim; no renders fire) -------
    fresh_scene()
    fx_nomesh = vprobe.build_volume_fixture("wire_nomesh", mixamo=False, with_mesh=False)
    rep_nm = wire.apply_sculpt(
        fx_nomesh["arm"], payload=gt_payload(),
        solve=core.SculptSolve.from_dict(gt_solve({p: 1.0 for p in BANDS})),
    )
    no_mesh = (
        rep_nm["volume"] is not None and not rep_nm["volume"]["applied"]
        and core.CAPABILITY_NO_MESH in rep_nm["volume"]["capability_lines"]
    )
    fx_starved = vprobe.build_volume_fixture("wire_starved", mixamo=False)
    del fx_starved["arm"]["rm_role_lower_leg.L"]
    rep_st = wire.apply_sculpt(fx_starved["arm"], payload=gt_payload(), solve=None)
    starved_line = wire.CAPABILITY_NO_SCULPT in rep_st["capability_lines"]
    prop_lines = (
        rep_st["proportions"] is not None
        and rep_st["proportions"]["capability_lines"]
        and "lower_leg.L" in rep_st["proportions"]["capability_lines"][0]
    )
    check(
        "WIRE-NOTARGET", no_mesh and starved_line and prop_lines,
        f"no-mesh line={no_mesh} no-solve line={starved_line} "
        f"starved proportion line={prop_lines}",
    )

    # ---- WIRE-DETERM (twin wiring runs byte-identical; fresh scene each) ----
    twins = []
    for name in ("wire_twin1", "wire_twin2"):
        fresh_scene()
        fxd = vprobe.build_volume_fixture(name, mixamo=False)
        stagedd = wire.measure_volume_base_ratios(fxd["arm"], fxd["mesh"])[0]
        repd = wire.apply_sculpt(fxd["arm"], payload=gt_payload(), solve=gate_solve(stagedd))
        twins.append((
            repd["proportions"]["factors"],
            repd["volume"]["factors"],
            repd["volume"]["values"],
            pose_location_bytes(fxd["arm"]),
            shape_key_values(fxd["mesh"]),
        ))
    identical = twins[0] == twins[1]
    check(
        "WIRE-DETERM", identical,
        "twin wiring runs byte-identical (factors, values, locations, keys)",
    )

    # ---- verdict --------------------------------------------------------------
    check("WIRE", OK, "the wiring rows above are the contract")
    check("GATE", OK, "the wiring gate's rows above are the contract")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
