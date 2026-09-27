"""P8-6 spine gate (run INSIDE Blender, headless) — the RM_SPINE rows.

The sibling of scene_gate/couple_gate/finger_gate/face_gate/camera_gate
(the Mimosa new-file rule). Rows:

1. SPINE-ARCH  — the benchmark through the CORE arch pass + the REAL addon
                 apply on the engine fixture rig: the monotone distribution
                 (neutral < bow < arched), sign correctness, declared-
                 family recovery (<= 0.002 canon), the neutral flat no-op
                 byte-identity, and the 0.5 deg apply re-eval family.
2. SPINE-FLIPS — D-008's 18/20 flip accept through solve -> arch -> roll;
                 every flips dict byte-equal to the plain solve.
3. SPINE-ROLL  — the roll fixture through the REAL apply, BOTH paths:
                 the plain payload (uncorrected) vs the roll-carrying
                 payload (corrected): direction fidelity (worst fk error
                 <= 0.5 deg) in both, the applied Blender bone-frame twist
                 about the (unchanged) direction == the solved correction
                 (within 0.5 deg), and the artifact number published.
4. SPINE-STRAIGHT — a straight-arm payload produces NO roll entries and
                 the addon apply output rotations BYTE-IDENTICAL with and
                 without the roll pass (the structural no-op).
5. SPINE-TWIN  — twin arch+roll solves byte-identical (to_dict + applied
                 bone matrices).

Usage: blender -b --python xtask/spine_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR.
Prints RM_SPINE lines; exit 0 only if every row PASSes.
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.environ["RM_CORE_SRC"])
sys.path.insert(0, os.environ["RM_ADDON_DIR"])
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "tests"
    ),
)

import bpy  # noqa: E402
import riggermortis as core  # noqa: E402
from riggermortis.canonical_pose import solve_pose  # noqa: E402
from riggermortis_addon import pose_apply  # noqa: E402

OK = True


def check(label: str, ok: bool, detail: str = "") -> None:
    global OK
    if not ok:
        OK = False
    print(f"RM_SPINE {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def build_rig(name: str):
    """Canonical-layout rig with role props (TWO-PASS: create every bone,
    then wire parents — the S27 fixture law; the camera_gate recipe)."""
    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.mode_set(mode="EDIT")
    bones = obj.data.edit_bones
    bones.remove(bones[0])
    created: dict = {}

    def add(bn, parent, head, tail):
        b = bones.new(bn)
        b.head, b.tail = head, tail
        created[bn] = b

    add("pelvis", None, (0, 0, 0.98), (0, 0, 1.06))
    add("spine", "pelvis", (0, 0, 1.06), (0, 0, 1.22))
    add("spine.001", "spine", (0, 0, 1.22), (0, 0, 1.40))
    add("neck", "spine.001", (0, 0, 1.40), (0, 0, 1.50))
    add("head", "neck", (0, 0, 1.50), (0, 0, 1.70))
    add("shoulder.L", "spine.001", (0.03, 0, 1.44), (0.14, 0, 1.46))
    add("upper_arm.L", "shoulder.L", (0.16, 0, 1.45), (0.46, 0, 1.45))
    add("forearm.L", "upper_arm.L", (0.46, 0, 1.45), (0.72, 0, 1.45))
    add("hand.L", "forearm.L", (0.72, 0, 1.45), (0.82, 0, 1.45))
    add("shoulder.R", "spine.001", (-0.03, 0, 1.44), (-0.14, 0, 1.46))
    add("upper_arm.R", "shoulder.R", (-0.16, 0, 1.45), (-0.46, 0, 1.45))
    add("forearm.R", "upper_arm.R", (-0.46, 0, 1.45), (-0.72, 0, 1.45))
    add("hand.R", "forearm.R", (-0.72, 0, 1.45), (-0.82, 0, 1.45))
    add("thigh.L", "pelvis", (0.09, 0, 0.98), (0.09, 0, 0.52))
    add("shin.L", "thigh.L", (0.09, 0, 0.52), (0.09, 0, 0.10))
    add("foot.L", "shin.L", (0.09, 0, 0.10), (0.09, -0.14, 0.02))
    add("thigh.R", "pelvis", (-0.09, 0, 0.98), (-0.09, 0, 0.52))
    add("shin.R", "thigh.R", (-0.09, 0, 0.52), (-0.09, 0, 0.10))
    add("foot.R", "shin.R", (-0.09, 0, 0.10), (-0.09, -0.14, 0.02))
    for bn, par in (
        ("spine", "pelvis"), ("spine.001", "spine"), ("neck", "spine.001"),
        ("head", "neck"),
        ("shoulder.L", "spine.001"), ("upper_arm.L", "shoulder.L"),
        ("forearm.L", "upper_arm.L"), ("hand.L", "forearm.L"),
        ("shoulder.R", "spine.001"), ("upper_arm.R", "shoulder.R"),
        ("forearm.R", "upper_arm.R"), ("hand.R", "forearm.R"),
        ("thigh.L", "pelvis"), ("shin.L", "thigh.L"), ("foot.L", "shin.L"),
        ("thigh.R", "pelvis"), ("shin.R", "thigh.R"), ("foot.R", "shin.R"),
    ):
        created[bn].parent = created[par]
    bpy.ops.object.mode_set(mode="OBJECT")
    role_of = {
        "pelvis": "hips", "spine": "spine", "spine.001": "chest", "neck": "neck",
        "head": "head",
        "shoulder.L": "shoulder.L", "upper_arm.L": "upper_arm.L",
        "forearm.L": "forearm.L", "hand.L": "hand.L",
        "shoulder.R": "shoulder.R", "upper_arm.R": "upper_arm.R",
        "forearm.R": "forearm.R", "hand.R": "hand.R",
        "thigh.L": "upper_leg.L", "shin.L": "lower_leg.L", "foot.L": "foot.L",
        "thigh.R": "upper_leg.R", "shin.R": "lower_leg.R", "foot.R": "foot.R",
    }
    for bone, role in sorted(role_of.items()):
        obj[f"rm_role_{role}"] = bone
    return obj


# -- fixture payloads (core-side, the probe's recipes) --------------------------------

_SCALE = 200.0
_CENTER = (500.0, 700.0)


def _proj_obs(positions, conf=0.95):
    obs = {}

    def proj(p):
        return ((_CENTER[0] + _SCALE * p[0], _CENTER[1] - _SCALE * p[2]), conf)

    for role in (
        "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
        "hand.L", "hand.R", "upper_leg.L", "upper_leg.R",
        "lower_leg.L", "lower_leg.R", "foot.L", "foot.R", "head",
    ):
        if role in positions:
            obs[role] = proj(positions[role])
    sl, sr = positions["upper_arm.L"], positions["upper_arm.R"]
    neck2d = ((sl[0] + sr[0]) / 2.0, (sl[2] + sr[2]) / 2.0)
    obs["neck"] = ((_CENTER[0] + _SCALE * neck2d[0], _CENTER[1] - _SCALE * neck2d[1]), conf)
    hl, hr = positions["upper_leg.L"], positions["upper_leg.R"]
    hips2d = ((hl[0] + hr[0]) / 2.0, (hl[2] + hr[2]) / 2.0)
    obs["hips"] = ((_CENTER[0] + _SCALE * hips2d[0], _CENTER[1] - _SCALE * hips2d[1]), conf)
    return obs


def model_curve_positions(phi_deg: float):
    """A torso authored ON the declared arch family (docs/SPINE.md A1)."""
    from riggermortis.canonical_pose import TORSO_SPAN

    phi = math.radians(phi_deg)
    chord = TORSO_SPAN
    ndx, ndz = math.sin(phi), math.cos(phi)
    ga = phi * 2.0
    tx0, tz0 = chord * math.sin(ga), chord * math.cos(ga)
    tx1, tz1 = chord * ndx, chord * ndz
    t_spine, t_chest = 0.09 / chord, 0.26 / chord

    def hermite(t):
        t2, t3 = t * t, t * t * t
        h10 = t3 - 2 * t2 + t
        h01, h11 = -2 * t3 + 3 * t2, t3 - t2
        return (h10 * tx0 + h11 * tx1, h01 * chord + h10 * tz0 + h11 * tz1)

    positions = {
        "hips": (0.0, 0.0, 0.0),
        "root": (0.0, 0.0, 0.0),
        "spine": (*hermite(t_spine)[:1], 0.0, hermite(t_spine)[1]),
        "chest": (*hermite(t_chest)[:1], 0.0, hermite(t_chest)[1]),
        "neck": (0.0, 0.0, chord),
        "head": (0.11 * ndx, 0.0, chord + 0.11 * ndz),
        "upper_leg.L": (0.08, 0.0, 0.0),
        "upper_leg.R": (-0.08, 0.0, 0.0),
    }
    for side, sx in (("L", 1.0), ("R", -1.0)):
        sh = (0.13 * sx, 0.0, chord)
        positions[f"upper_arm.{side}"] = sh
        el = (sh[0] + 0.32 * 0.1 * sx, sh[1] - 0.32 * 0.2, sh[2] - 0.32 * 0.97)
        positions[f"forearm.{side}"] = el
        positions[f"hand.{side}"] = (
            el[0] + 0.28 * 0.35 * sx, el[1] - 0.28 * 0.35, el[2] - 0.28 * 0.87,
        )
        hip = positions[f"upper_leg.{side}"]
        positions[f"lower_leg.{side}"] = (hip[0], hip[1], hip[2] - 0.50)
        positions[f"foot.{side}"] = (hip[0], hip[1], hip[2] - 0.97)
        positions[f"toe.{side}"] = (hip[0], hip[1] - 0.12, hip[2] - 0.97)
    return positions


def bent_arm_positions():
    from riggermortis.fk_apply import v_norm

    positions = {
        "hips": (0.0, 0.0, 0.0),
        "root": (0.0, 0.0, 0.0),
        "spine": (0.0, 0.0, 0.09),
        "chest": (0.0, 0.0, 0.26),
        "neck": (0.0, 0.0, 0.45),
        "head": (0.0, -0.016, 0.557),
        "upper_leg.L": (0.08, 0.0, 0.0),
        "upper_leg.R": (-0.08, 0.0, 0.0),
    }
    ul = v_norm((0.2, 0.0, -0.98))
    fl = v_norm((0.1, -0.9, -0.43))
    positions["upper_arm.L"] = (0.13, 0.0, 0.45)
    positions["forearm.L"] = tuple(  # type: ignore[assignment]
        positions["upper_arm.L"][i] + 0.32 * ul[i] for i in range(3)
    )
    positions["hand.L"] = tuple(  # type: ignore[assignment]
        positions["forearm.L"][i] + 0.28 * fl[i] for i in range(3)
    )
    ur = v_norm((-0.1, 0.0, -1.0))
    positions["upper_arm.R"] = (-0.13, 0.0, 0.45)
    positions["forearm.R"] = tuple(  # type: ignore[assignment]
        positions["upper_arm.R"][i] + 0.32 * ur[i] for i in range(3)
    )
    positions["hand.R"] = tuple(  # type: ignore[assignment]
        positions["forearm.R"][i] + 0.28 * ur[i] for i in range(3)
    )
    for side in ("L", "R"):
        hip = positions[f"upper_leg.{side}"]
        positions[f"lower_leg.{side}"] = (hip[0], hip[1], hip[2] - 0.50)
        positions[f"foot.{side}"] = (hip[0], hip[1], hip[2] - 0.97)
        positions[f"toe.{side}"] = (hip[0], hip[1] - 0.12, hip[2] - 0.97)
    return positions


def payload_for(pose_dict: dict, name: str) -> dict:
    """A detector-shaped v3 payload wrapping a pose dict."""
    return {
        "format": 3,
        "name": name,
        "image": {"path": "synthetic", "width": 640, "height": 960},
        "figures": [
            {"label": "A", "bbox": [0.0, 0.0, 640.0, 960.0], "score": 0.99,
             "pose": pose_dict}
        ],
        "pins": [],
    }


def chord_deviation(positions, role):
    hx, _hy, hz = positions["hips"]
    nx, _ny, nz = positions["neck"]
    cx, cz = nx - hx, nz - hz
    ln = math.hypot(cx, cz)
    px, _py, pz = positions[role]
    return ((px - hx) * cz - (pz - hz) * cx) / ln


def bone_twist_about_direction(cols_a, cols_b):
    """The signed angle about the (shared) bone direction between two
    pose bones' frames, given (x_col, y_col) axis tuples captured AFTER a
    view_layer.update() (the stale-matrix lesson)."""
    xa, ya = cols_a
    xb, yb = cols_b
    dirv = tuple((a + b) / 2.0 for a, b in zip(ya[:3], yb[:3], strict=True))
    ln = math.sqrt(sum(v * v for v in dirv))
    if ln <= 1e-12:
        return 0.0
    dirv = tuple(v / ln for v in dirv)
    cross = (
        xa[1] * xb[2] - xa[2] * xb[1],
        xa[2] * xb[0] - xa[0] * xb[2],
        xa[0] * xb[1] - xa[1] * xb[0],
    )
    return math.atan2(
        sum(a * b for a, b in zip(dirv, cross, strict=True)),
        sum(a * b for a, b in zip(xa[:3], xb[:3], strict=True)),
    )


def main() -> int:
    fresh_scene()

    # 1. SPINE-ARCH — the benchmark bars through the REAL apply.
    rig = build_rig("rig_arch")
    order = [("neutral", 0.0), ("bow_L", 18.0), ("arched", 30.0)]
    devs, mono_ok, rec_ok, apply_worst = [], True, True, 0.0
    signed = {}
    for name, deg in order:
        gt = model_curve_positions(deg)
        flat = solve_pose(_proj_obs(gt))
        arch, rep = core.solve_spine_arch(flat)
        if rep.applied != (deg != 0.0):
            mono_ok = False
        if deg != 0.0:
            devs.append(abs(chord_deviation(arch.positions, "chest")))
            signed[name] = chord_deviation(arch.positions, "chest")
            for role in ("spine", "chest"):
                d = math.dist(arch.positions[role], gt[role])
                if d > 0.002:
                    rec_ok = False
        payload = payload_for(arch.to_dict(), f"arch_{name}")
        report = pose_apply.apply_payload(rig, payload, figure="A")
        if not report.get("applied") or float(report.get("worst_deg", 99.0)) > 0.5:
            mono_ok = False
        apply_worst = max(apply_worst, float(report.get("worst_deg", 0.0)))
    for a, b in zip(devs, devs[1:], strict=False):
        if not b > a:
            mono_ok = False
    flat_n = solve_pose(_proj_obs(model_curve_positions(0.0)))
    arch_n, rep_n = core.solve_spine_arch(flat_n)
    noop_ok = arch_n.to_dict() == flat_n.to_dict() and not rep_n.applied
    sign_ok = signed.get("bow_L", 0.0) > 0.0
    check(
        "SPINE-ARCH",
        mono_ok and sign_ok and rec_ok and noop_ok and apply_worst <= 0.5,
        f"[SYNTHETIC, prior-consistent GT; measured on synthetic prior-"
        f"consistent ground truth; real-detector noise is not in these "
        f"numbers; the Annex A.1 re-validation trigger applies when real "
        f"labeled fixtures enter the workflow] chest deviation from chord "
        f"{' < '.join(f'{d:.4f}' for d in devs)} (monotone {mono_ok}, bow_L "
        f"sign + {sign_ok}), declared-family recovery <= 0.002 canon "
        f"({rec_ok}), neutral flat no-op byte-identical ({noop_ok}), REAL "
        f"addon apply worst {apply_worst:.4f} deg (bar 0.5)",
    )

    # 2. SPINE-FLIPS — D-008's 18/20 accept unchanged through the passes.
    from poses_fixtures import POSES, project_fixture

    accept = 0
    flips_equal = True
    for fx in POSES:
        plain = solve_pose(project_fixture(fx))
        arch, _rep = core.solve_spine_arch(plain)
        rolled, _roll_rep = core.solve_arm_roll(arch)
        if rolled.flips != plain.flips:
            flips_equal = False
        wrong = [
            limb
            for limb, gt_flip in fx.gt_flips.items()
            if gt_flip is not None and rolled.flips[limb] != gt_flip
        ]
        if not wrong:
            accept += 1
    check(
        "SPINE-FLIPS",
        accept >= 18 and flips_equal,
        f"D-008 flip accept {accept}/20 (bar >= 18) through arch+roll; every "
        f"flips dict byte-equal to the plain solve ({flips_equal})",
    )

    # 3. SPINE-ROLL — the fixture through the REAL apply, both paths.
    bent = solve_pose(_proj_obs(bent_arm_positions()))
    rolled, roll_rep = core.solve_arm_roll(bent)
    rho = rolled.roll["forearm.L"].twist_rad
    fresh_scene()
    rig_plain = build_rig("rig_plain")
    rep_plain = pose_apply.apply_payload(
        rig_plain, payload_for(bent.to_dict(), "bent_plain"), figure="A"
    )
    bpy.context.view_layer.update()  # the stale-matrix lesson
    cols_plain = (
        tuple(bpy.data.objects["rig_plain"].pose.bones["forearm.L"].matrix.col[0]),
        tuple(bpy.data.objects["rig_plain"].pose.bones["forearm.L"].matrix.col[1]),
    )
    fresh_scene()
    rig_rolled = build_rig("rig_rolled")
    rep_rolled = pose_apply.apply_payload(
        rig_rolled, payload_for(rolled.to_dict(), "bent_rolled"), figure="A"
    )
    bpy.context.view_layer.update()
    cols_rolled = (
        tuple(bpy.data.objects["rig_rolled"].pose.bones["forearm.L"].matrix.col[0]),
        tuple(bpy.data.objects["rig_rolled"].pose.bones["forearm.L"].matrix.col[1]),
    )
    twist_measured = bone_twist_about_direction(cols_plain, cols_rolled)
    uncorrected = abs(math.degrees(rho))
    measured = abs(math.degrees(twist_measured))
    check(
        "SPINE-ROLL",
        float(rep_rolled.get("worst_deg", 99.0)) <= 0.5
        and float(rep_plain.get("worst_deg", 99.0)) <= 0.5
        and abs(measured - uncorrected) <= 0.5,
        f"frame-continuity fixture through the REAL addon apply: uncorrected "
        f"forearm twist {uncorrected:.2f} deg (the artifact, published), "
        f"Blender-measured applied twist {measured:.2f} deg in magnitude "
        f"(== the solved correction; the SIGN is a Blender bone-frame "
        f"convention, the signed twist lives core-side, bar 0.5), direction "
        f"fidelity both paths worst "
        f"{max(float(rep_plain.get('worst_deg', 0.0)), float(rep_rolled.get('worst_deg', 0.0))):.4f} deg "
        f"(bar 0.5); entry forearm.L conf {roll_rep.entries['forearm.L'].confidence}",
    )

    # 4. SPINE-STRAIGHT — no entries; the addon apply rotations byte-equal.
    from poses_fixtures import POSES as _POSES

    straight = solve_pose(project_fixture(_POSES[0]))  # t_pose
    out, rep_s = core.solve_arm_roll(straight)
    fresh_scene()
    rig_s1 = build_rig("rig_s1")
    pose_apply.apply_payload(
        rig_s1, payload_for(straight.to_dict(), "straight_plain"), figure="A"
    )
    rot_a = json.dumps(
        {
            pb.name: [list(pb.rotation_axis_angle), pb.rotation_mode]
            for pb in bpy.data.objects["rig_s1"].pose.bones
        },
        sort_keys=True,
    )
    fresh_scene()
    rig_s2 = build_rig("rig_s2")
    pose_apply.apply_payload(
        rig_s2, payload_for(out.to_dict(), "straight_rolled"), figure="A"
    )
    rot_b = json.dumps(
        {
            pb.name: [list(pb.rotation_axis_angle), pb.rotation_mode]
            for pb in bpy.data.objects["rig_s2"].pose.bones
        },
        sort_keys=True,
    )
    check(
        "SPINE-STRAIGHT",
        rep_s.entries == {} and rot_a == rot_b,
        f"straight arms (t_pose): no roll entries ({rep_s.entries == {}}), "
        f"addon apply rotations byte-identical with and without the roll "
        f"pass ({rot_a == rot_b}) — the structural no-op",
    )

    # 5. SPINE-TWIN — twin arch+roll solves byte-identical.
    gt = model_curve_positions(30.0)
    arch_a, rep_a2 = core.solve_spine_arch(solve_pose(_proj_obs(gt)))
    roll_a, _rr = core.solve_arm_roll(arch_a)
    arch_b, rep_b2 = core.solve_spine_arch(solve_pose(_proj_obs(gt)))
    roll_b, _rb = core.solve_arm_roll(arch_b)
    fresh_scene()
    rig_t1 = build_rig("rig_t1")
    pose_apply.apply_payload(rig_t1, payload_for(roll_a.to_dict(), "twin"), figure="A")
    # plain-float tuples ONLY: mathutils rich-compare through nested
    # containers is flaky in 5.1 (wrong False + a segfault, both observed)
    mats_a = {
        pb.name: tuple(tuple(float(v) for v in row) for row in pb.matrix_basis)
        for pb in bpy.data.objects["rig_t1"].pose.bones
    }
    fresh_scene()
    rig_t2 = build_rig("rig_t2")
    pose_apply.apply_payload(rig_t2, payload_for(roll_b.to_dict(), "twin"), figure="A")
    mats_b = {
        pb.name: tuple(tuple(float(v) for v in row) for row in pb.matrix_basis)
        for pb in bpy.data.objects["rig_t2"].pose.bones
    }
    diff_bones = [k for k in mats_a if mats_a[k] != mats_b.get(k)]
    check(
        "SPINE-TWIN",
        roll_a.to_dict() == roll_b.to_dict() and rep_a2 == rep_b2 and mats_a == mats_b,
        f"twin arch+roll solves byte-identical (to_dict {roll_a.to_dict() == roll_b.to_dict()}, "
        f"report {rep_a2 == rep_b2}, {len(mats_a)} applied bone matrices "
        f"{mats_a == mats_b}; differing: {diff_bones[:3]})",
    )

    passed = OK
    print(f"RM_SPINE GATE: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
