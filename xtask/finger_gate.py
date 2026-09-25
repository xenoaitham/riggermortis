"""P8-3 finger gate probe (run INSIDE Blender, headless) — the RM_FINGER
rows. couple_gate.py's sibling for the fingers rock (the same house shape:
real add-on machinery, grep-pinned lines, exit 0 only if all PASS).

Fixtures are ENGINE-BUILT (Annex A.3 — no external sourcing). The hand
benchmarks are SYNTHETIC parametric GT hands (prior-consistent curls; the
declared forward-curl rule solves them exactly — a GT curl away from
canonical forward is the documented single-view miss class, D-008's
elbow analog, and clenched hands are occlusion fixtures, never direction
fixtures). The apply rows drive the REAL add-on apply path
(pose_apply.apply_pose_object) on engine-built fixture rigs with finger
chain bones, through the FULL preset contract (fingerprint-gated
``hands`` bindings via resolve_hands).

Rows:
1. FINGER-BENCH      — the 20-pose hand benchmark class: per-SEGMENT
                       direction error vs GT; median <= 20 deg, p90 <= 35
                       deg on VISIBLE fingers (Annex A.1).
2. FINGER-GATE-OCCL  — occlusion fixtures (hand-behind-back: no hand
                       entry; below-floor: 5/5 ledgered skips) — 100%
                       gated-skip, zero guessed fingers.
3. FINGER-APPLY      — metarig-class fixture + preset hands bindings:
                       live finger-bone FK within the 0.5 deg family.
4. FINGER-MIXAMO     — Mixamo-class fixture (mixamorig names, 0.01
                       object scale): same bar through the same preset
                       contract.
5. FINGER-NOTARGET   — a pose with hands + a rig without bindings: the
                       loud capability line, never a silent no-op.
6. FINGER-TWIN       — two bound applies byte-identical.

Usage: blender -b --python xtask/finger_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR.
Prints RM_FINGER lines; exit 0 only if every row PASSes.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.environ["RM_CORE_SRC"])
sys.path.insert(0, os.environ["RM_ADDON_DIR"])

import bpy  # noqa: E402
import riggermortis as core  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402
from riggermortis.canonical import CANONICAL, PRIMARY_CHILD, rest_skeleton  # noqa: E402
from riggermortis.inference.poses import (  # noqa: E402
    HAND_L_END,
    HAND_L_START,
    KEYPOINT_COUNT,
    WRIST_L,
    hand_kp_index,
)
from riggermortis_addon import bpy_bridge, pose_apply  # noqa: E402

TOL_DEG = 0.5
AX, AY, SCALE = 320.0, 240.0, 400.0
FINGERS = ("thumb", "index", "middle", "ring", "pinky")
JOINTS = ("mcp", "pip", "dip", "tip")
OK = True


def check(label: str, ok: bool, detail: str = "") -> None:
    global OK
    if not ok:
        OK = False
    print(f"RM_FINGER {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


# -- synthetic GT hands (the probe's generator, gate-owned copy) ------------------

SEGMENTS = dict(core.FINGER_SEGMENT_LENGTHS)


def _project(p3):
    return (AX + p3[0] * SCALE, AY - p3[2] * SCALE)


def _gt_chain(base, splay_deg, curls_deg, lengths, mcp):
    def rot_y(v, deg):
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        return (v[0] * c - v[2] * s, v[1], v[0] * s + v[2] * c)

    def curl(v, deg):
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        return (v[0] * c, -(v[0] * s) + v[1] * c, v[2])

    d = rot_y(base, splay_deg)
    joints = {"mcp": mcp}
    prev = mcp
    for k, name in enumerate(("pip", "dip", "tip")):
        d = curl(d, curls_deg[k])
        prev = tuple(prev[i] + d[i] * lengths[k] for i in range(3))
        joints[name] = prev
    return joints


def _gt_hand(splays, curls, wrist):
    gt = {}
    kps = [(0.0, 0.0)] * KEYPOINT_COUNT
    confs = [0.0] * KEYPOINT_COUNT
    kps[WRIST_L] = _project(wrist)
    confs[WRIST_L] = 0.95
    for f in FINGERS:
        mcp = (wrist[0] + 0.02, wrist[1], wrist[2] + 0.01 * FINGERS.index(f))
        gj = _gt_chain((1.0, 0.0, 0.0), splays[f], curls[f], SEGMENTS[f], mcp)
        gt[f] = gj
        for jname in JOINTS:
            idx = hand_kp_index("hand.L", f, jname)
            kps[idx] = _project(gj[jname])
            confs[idx] = 0.9
    return gt, kps, confs


def _segment_dirs(joints):
    out = []
    for a, b in (("mcp", "pip"), ("pip", "dip"), ("dip", "tip")):
        d = tuple(joints[b][i] - joints[a][i] for i in range(3))
        n = math.sqrt(sum(c * c for c in d))
        out.append(tuple(c / n for c in d))
    return out


# -- the 20-pose benchmark class (named SYNTHETIC fixtures) ------------------------

def _benchmark_set():
    zeros = {f: 0.0 for f in FINGERS}
    zc = {f: (0.0, 0.0, 0.0) for f in FINGERS}
    soft = (12.0, 15.0, 10.0)
    mid = (30.0, 35.0, 25.0)
    hard = (55.0, 60.0, 45.0)
    thumb_mid = (15.0, 18.0, 12.0)
    poses = {
        "flat": ({f: 0.0 for f in FINGERS}, zc),
        "spread": ({"thumb": -40.0, "index": -15.0, "middle": 0.0, "ring": 15.0, "pinky": 32.0}, zc),
        "spread_wide": ({"thumb": -60.0, "index": -25.0, "middle": 0.0, "ring": 25.0, "pinky": 50.0}, zc),
        "relax": ({"thumb": -10.0, "index": -4.0, "middle": 0.0, "ring": 4.0, "pinky": 10.0}, zc),
        "V": ({"thumb": -35.0, "index": -18.0, "middle": 18.0, "ring": 0.0, "pinky": 0.0}, zc),
        "fan": ({"thumb": -25.0, "index": -12.0, "middle": -4.0, "ring": 8.0, "pinky": 20.0}, zc),
        "thumb_out": ({"thumb": -70.0, "index": -6.0, "middle": 0.0, "ring": 6.0, "pinky": 12.0}, zc),
        "curl_soft": ({f: -4.0 for f in FINGERS}, {f: soft for f in FINGERS}),
        "curl_mid": ({f: -4.0 for f in FINGERS}, {f: mid for f in FINGERS}),
        "curl_full": ({f: -4.0 for f in FINGERS}, {f: hard for f in FINGERS}),
        "grip": ({"thumb": -15.0, "index": -5.0, "middle": 0.0, "ring": 5.0, "pinky": 10.0},
                 {f: (40.0, 45.0, 35.0) for f in FINGERS}),
        "hook": (zeros, {f: (50.0, 5.0, 5.0) for f in FINGERS}),
        "claw_soft": (zeros, {f: (25.0, 10.0, 10.0) for f in FINGERS}),
        "point_index": ({"thumb": -10.0, "index": 0.0, "middle": 10.0, "ring": 14.0, "pinky": 18.0},
                        {"thumb": thumb_mid, "index": zc["index"], "middle": mid, "ring": mid, "pinky": mid}),
        "point_pinky": ({"thumb": -10.0, "index": 14.0, "middle": 10.0, "ring": 5.0, "pinky": 0.0},
                        {"thumb": thumb_mid, "index": mid, "middle": mid, "ring": mid, "pinky": zc["pinky"]}),
        "tripod": ({"thumb": -20.0, "index": -8.0, "middle": -2.0, "ring": 8.0, "pinky": 16.0},
                   {"thumb": (25.0, 28.0, 20.0), "index": (35.0, 40.0, 30.0),
                    "middle": (35.0, 40.0, 30.0), "ring": mid, "pinky": mid}),
        "cup": ({"thumb": -30.0, "index": -12.0, "middle": 0.0, "ring": 12.0, "pinky": 24.0},
                {f: (18.0, 20.0, 15.0) for f in FINGERS}),
        "pinch_open": ({"thumb": -45.0, "index": -25.0, "middle": 5.0, "ring": 10.0, "pinky": 16.0},
                       {"thumb": (20.0, 22.0, 15.0), "index": (25.0, 28.0, 20.0),
                        "middle": mid, "ring": mid, "pinky": mid}),
        "pinch_closed": ({"thumb": -50.0, "index": -30.0, "middle": 5.0, "ring": 10.0, "pinky": 16.0},
                         {"thumb": (35.0, 38.0, 28.0), "index": (40.0, 44.0, 34.0),
                          "middle": mid, "ring": mid, "pinky": mid}),
        "splay_curl": ({"thumb": -35.0, "index": -10.0, "middle": 0.0, "ring": 10.0, "pinky": 20.0},
                       {"thumb": thumb_mid, "index": soft, "middle": mid, "ring": (40.0, 44.0, 34.0), "pinky": hard}),
    }
    assert len(poses) == 20, f"benchmark class must hold 20 poses, has {len(poses)}"
    return poses


# -- the engine-built fixture rigs --------------------------------------------------

REST = rest_skeleton(1.0 / 0.55)


def _body_tail(role):
    child = PRIMARY_CHILD.get(role)
    if child is None:
        head = Vector(REST[role][0])
        if role.startswith("hand"):
            return tuple(head + Vector((0.11 * (1 if role.endswith(".L") else -1), 0, 0)))
        if role.startswith("toe"):
            return tuple(head + Vector((0.0, -0.12, 0.0)))
        if role == "head":
            return tuple(head + Vector((0.0, 0.0, 0.21)))
        return tuple(head + Vector((0.0, 0.0, 0.05)))
    return tuple(REST[child][0])


def build_fixture_rig(name, *, mixamo=False, scale=1.0, fingers=True):
    """Canonical body chain + per-hand finger chains (fingers=False builds a
    bare body rig — the no-target class). TWO-PASS build (create every
    bone, then wire parents; a missing parent REFUSES) — the S9/S27
    real-Blender-gate lesson. mixamo=True renames the left arm chain to
    mixamorig names (a real Mixamo export's naming class)."""
    body_roles = [r for r in sorted(REST) if r != "root"]
    hand_chain = {f"{f}{i}": (f, i) for f in FINGERS for i in (1, 2, 3)}
    rename = {}
    if mixamo:
        rename = {
            "upper_arm.L": "mixamorig:LeftArm",
            "forearm.L": "mixamorig:LeftForeArm",
            "hand.L": "mixamorig:LeftHand",
        }
        for f in FINGERS:
            cap = {"thumb": "Thumb", "index": "Index", "middle": "Middle",
                   "ring": "Ring", "pinky": "Pinky"}[f]
            for i in (1, 2, 3):
                rename[f"L_{f}{i}"] = f"mixamorig:LeftHand{cap}{i}"

    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.mode_set(mode="EDIT")
    bones = obj.data.edit_bones
    bones.remove(bones[0])

    def bone_name(key):
        return rename.get(key, key)

    def finger_head(f, i):
        base = Vector(REST["hand.L"][1])
        fi = FINGERS.index(f)
        if mixamo:
            base = Vector(REST["hand.L"][1])
        return tuple(base + Vector((0.0, -0.02 * (2 - fi), (fi - 2) * 0.012))
                     if i == 1 else Vector((0.0, 0.0, 0.0)))

    # pass 1: geometry for every bone
    for role in body_roles:
        b = bones.new(bone_name(role))
        b.head = tuple(REST[role][0])
        b.tail = _body_tail(role)
    hand_tail = Vector(REST["hand.L"][1])
    if fingers:
        for key, (f, i) in sorted(hand_chain.items()):
            b = bones.new(bone_name(f"L_{key}"))
            length = SEGMENTS[f][i - 1]
            fi = FINGERS.index(f)
            base = hand_tail + Vector((-0.01, -0.02 * (2 - fi), (fi - 2) * 0.012))
            if i > 1:
                prev_key = f"L_{f}{i - 1}"
                prev = bones[bone_name(prev_key)]
                base = Vector(prev.tail)
            b.head = tuple(base)
            b.tail = tuple(base + Vector((length, 0.0, 0.0)))

    # pass 2: parenting (every bone exists now; a missing parent REFUSES)
    for role in body_roles:
        parent = CANONICAL[role].parent
        if not parent or parent == "root":
            continue
        if parent not in body_roles:
            raise RuntimeError(f"fixture rig {name!r}: parent {parent!r} missing for {role!r}")
        bones[bone_name(role)].parent = bones[bone_name(parent)]
    if fingers:
        for key, (f, i) in sorted(hand_chain.items()):
            if i == 1:
                parent = "hand.L"
            else:
                parent = f"L_{f}{i - 1}"
            parent_bone = bone_name(parent)
            if parent_bone not in bones:
                raise RuntimeError(f"fixture rig {name!r}: parent {parent_bone!r} missing for {key!r}")
            bones[bone_name(f"L_{key}")].parent = bones[parent_bone]
    bpy.ops.object.mode_set(mode="OBJECT")

    obj.scale = (scale, scale, scale)
    for role in body_roles:
        obj[f"rm_role_{role}"] = bone_name(role)
    finger_bones = (
        {bone_name(f"L_{f}{i}"): (f, i) for f in FINGERS for i in (1, 2, 3)}
        if fingers else {}
    )
    return obj, finger_bones


def _finger_bindings(finger_bones):
    """D-021 segment roles -> this rig's finger bones (mcp->bone1,
    pip->bone2, dip->bone3 per finger)."""
    rev = {v: k for k, v in finger_bones.items()}
    out = {}
    for f in FINGERS:
        for role_j, i in (("mcp", 1), ("pip", 2), ("dip", 3)):
            out[f"hand.L.finger.{f}.{role_j}"] = rev[(f, i)]
    return out


def _stand_pose_with_hands(curls=None, splays=None):
    """Rest-stance body pose + hand.L chains solved through the REAL
    solve_hands (synthetic prior-consistent GT kps at the rest wrist)."""
    pose_dict = {
        "positions": {r: list(v[0]) for r, v in sorted(REST.items())},
        "flips": {},
        "confidence": 1.0,
        "reliable": True,
        "scale": SCALE,
        "anchor": "hips",
        "notes": [],
        "joint_confidence": {},
    }
    pose = core.CanonicalPose.from_dict(pose_dict)
    wrist = pose.positions["hand.L"]
    curls = curls or {f: (15.0, 18.0, 12.0) for f in FINGERS}
    splays = splays or {f: -6.0 * (i - 2) for i, f in enumerate(FINGERS)}
    gt, kps, confs = _gt_hand(splays, curls, wrist)
    # anchor consistency: write the hips-midpoint PIXELS the solver's
    # _plane_anchor reconstructs from the kp array (HIP_L/HIP_R sources)
    hips3 = tuple(
        (REST["upper_leg.L"][0][i] + REST["upper_leg.R"][0][i]) / 2.0 for i in range(3)
    )
    kps[11] = _project(hips3)  # HIP_L (midpoint source)
    kps[12] = _project(hips3)  # HIP_R
    confs[11] = confs[12] = 0.95
    pose.hands = core.solve_hands(kps, confs, pose)
    return pose, gt


def _all_quats():
    out = {}
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        for pb in obj.pose.bones:
            q = Quaternion(pb.rotation_axis_angle[1:4], pb.rotation_axis_angle[0])
            out[f"{obj.name}/{pb.name}"] = tuple(round(v, 9) for v in q)
    return out


def _live_finger_fk_deg(obj, pose, finger_map):
    bpy.context.view_layer.update()  # place, UPDATE, then measure (S26 lesson)
    worst, worst_role = 0.0, ""
    for role in sorted(finger_map):
        target = core.bone_target_direction(pose, role)
        pb = obj.pose.bones.get(finger_map[role])
        if target is None or pb is None:
            return 999.0, role
        d = pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))
        d.normalize()
        dot = max(-1.0, min(1.0, d.dot(Vector(target))))
        deg = math.degrees(math.acos(dot))
        if deg > worst:
            worst, worst_role = deg, role
    return worst, worst_role


def _bound_apply(name, mixamo=False, scale=1.0):
    """Build the fixture, gate the preset contract, apply through the REAL
    addon path. Returns (obj, pose, finger_map, report)."""
    obj, finger_bones = build_fixture_rig(name, mixamo=mixamo, scale=scale)
    pose, _gt = _stand_pose_with_hands()
    rig = core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    mapping = pose_apply.mapping_from_props(obj, core)
    if mapping is None:
        raise RuntimeError(f"{name}: fixture produced no mapping")
    preset = core.preset_from_mapping(rig, mapping, hands=_finger_bindings(finger_bones))
    finger_map = core.resolve_hands(preset, rig.fingerprint())
    report = pose_apply.apply_pose_object(obj, pose, core, finger_map=finger_map)
    return obj, pose, finger_map, report


def main() -> int:
    global OK

    # 1. FINGER-BENCH — the 20-pose class: per-segment direction vs GT.
    all_errs = []
    for name in sorted(_benchmark_set()):
        splays, curls = _benchmark_set()[name]
        gt, kps, confs = _gt_hand(splays, curls, (0.5, 0.0, 0.9))
        stub = core.CanonicalPose(
            positions={"hips": (0.0, 0.0, 0.0), "hand.L": (0.5, 0.0, 0.9),
                       "forearm.L": (0.22, 0.0, 0.9)},
            flips={}, confidence=1.0, reliable=True, scale=SCALE,
            anchor="hips", notes=[], joint_confidence={},
        )
        solved = core.solve_hands(kps, confs, stub).get("hand.L")
        if solved is None or len(solved.fingers) != 5:
            check("FINGER-BENCH", False, f"{name}: hand did not solve")
            continue
        for f in FINGERS:
            sd = _segment_dirs(solved.fingers[f].joints)
            gd = _segment_dirs(gt[f])
            for a, b in zip(sd, gd, strict=True):
                dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b, strict=True))))
                all_errs.append(math.degrees(math.acos(dot)))
    all_errs.sort()
    median = all_errs[len(all_errs) // 2]
    p90 = all_errs[min(int(0.9 * len(all_errs)), len(all_errs) - 1)]
    check("FINGER-BENCH", median <= 20.0 and p90 <= 35.0,
          f"median {median:.2f} deg (bar 20) p90 {p90:.2f} deg (bar 35) "
          f"over {len(all_errs)} segments x 20 poses [SYNTHETIC]")

    # 2. FINGER-GATE-OCCL — 100% gated-skip, zero guessed fingers.
    _gt, kps, confs = _gt_hand({f: 0.0 for f in FINGERS},
                               {f: (0.0, 0.0, 0.0) for f in FINGERS}, (0.5, 0.0, 0.9))
    stub = core.CanonicalPose(
        positions={"hips": (0.0, 0.0, 0.0), "hand.L": (0.5, 0.0, 0.9),
                   "forearm.L": (0.22, 0.0, 0.9)},
        flips={}, confidence=1.0, reliable=True, scale=SCALE,
        anchor="hips", notes=[], joint_confidence={},
    )
    behind = list(confs)
    behind[9] = 0.0  # the wrist is a BODY keypoint (index 9): behind the
    for i in range(HAND_L_START, HAND_L_END):
        behind[i] = 0.0  # back nothing responds — wrist below floor = no entry
    no_entry = core.solve_hands(kps, behind, stub)
    below = list(confs)
    for i in range(HAND_L_START + 1, HAND_L_END):
        below[i] = 0.3  # clenched class: finger kps present, all below floor
    hs_below = core.solve_hands(kps, below, stub).get("hand.L")
    ledgered = (
        hs_below is not None and len(hs_below.fingers) == 0
        and len(hs_below.skipped) == 5
        and all("below floor 0.55" in r for r in hs_below.skipped.values())
    )
    check("FINGER-GATE-OCCL",
          no_entry == {} and ledgered,
          f"behind-back: wrist below floor -> no hand entry (absent=clean)="
          f"{no_entry == {}}; below-floor: 0 solved, 5/5 ledgered={ledgered}, "
          f"zero guessed")

    # 3. FINGER-APPLY — metarig-class fixture through the FULL preset path.
    fresh_scene()
    obj, pose, finger_map, report = _bound_apply("RM_FngMeta")
    worst, wrole = _live_finger_fk_deg(obj, pose, finger_map)
    bound_count = len([r for r in report["applied"] if r in set(finger_map.values())])
    check("FINGER-APPLY", worst <= TOL_DEG and bound_count == 15,
          f"live finger FK worst {worst:.4f} deg ({wrole}) bar {TOL_DEG}, "
          f"{bound_count}/15 finger bones keyed")

    # 4. FINGER-MIXAMO — Mixamo-class naming + 0.01 object scale.
    fresh_scene()
    obj_m, pose_m, fmap_m, report_m = _bound_apply("RM_FngMix", mixamo=True, scale=0.01)
    worst_m, wrole_m = _live_finger_fk_deg(obj_m, pose_m, fmap_m)
    bound_m = len([r for r in report_m["applied"] if r in set(fmap_m.values())])
    check("FINGER-MIXAMO", worst_m <= TOL_DEG and bound_m == 15,
          f"live finger FK worst {worst_m:.4f} deg ({wrole_m}) bar {TOL_DEG}, "
          f"{bound_m}/15 finger bones keyed")

    # 5. FINGER-NOTARGET — hands + no bindings: the loud capability line.
    fresh_scene()
    obj_n, _fb = build_fixture_rig("RM_FngBare", fingers=False)
    pose_n, _gt_n = _stand_pose_with_hands()
    report_n = pose_apply.apply_pose_object(obj_n, pose_n, core)
    line = [n for n in report_n["notes"] if "fingers not applied" in n]
    check("FINGER-NOTARGET", len(line) == 1 and "5 finger chain(s) solved" in line[0],
          f"capability line verbatim={len(line) == 1}")

    # 6. FINGER-TWIN — two bound applies byte-identical.
    fresh_scene()
    _bound_apply("RM_FngT1")
    q1 = _all_quats()
    fresh_scene()
    _bound_apply("RM_FngT2")
    q2 = {k.split("/", 1)[1]: v for k, v in _all_quats().items()}
    q1n = {k.split("/", 1)[1]: v for k, v in q1.items()}
    check("FINGER-TWIN", q1n == q2 and len(q1n) > 0,
          f"bones={len(q1n)} identical={q1n == q2}")

    print(f"RM_FINGER GATE: {'PASS' if OK else 'FAIL'}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
