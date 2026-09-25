"""P8-4 face gate probe (run INSIDE Blender, headless) — the RM_FACE rows.
finger_gate.py's sibling for the facials rock (the same house shape: real
add-on machinery, engine-built fixtures, grep-pinned lines, exit 0 only if
all PASS).

Fixtures are ENGINE-BUILT (Annex A.3 — no external sourcing). The
benchmark is SYNTHETIC prior-consistent GT faces (docs/FACE.md; the probe
earned the constants — the measured side map maps .L to band B). The
apply rows drive the REAL add-on apply path (pose_apply.apply_pose_object)
on engine-built fixture rigs with facial bones AND convention shape keys,
through the FULL preset contract (fingerprint-gated ``face_bones`` via
resolve_face).

Rows:
1. FACE-BENCH        — the 10-expression benchmark (neutral + 9): per-param
                       monotonicity (violations <= 1 of 9 steps, MONO_TOL
                       0.05) AND reach >= 0.5 at the max-GT state (docs/
                       FACE.md amendment A3) — the Annex A.1 9/10 bar.
2. FACE-GATE-OCCL    — conf-0 face -> no entry; below-floor params ->
                       100% ledgered skips with verbatim reasons; a
                       neutral face -> 0 params, 10/10 below-threshold
                       ledgered. Zero guessed params.
3. FACE-BONE-APPLY   — metarig-class fixture + preset face_bones through
                       the REAL addon path: applied world rotation vs the
                       declared FACE_BONE_PLAN axis-angle within the
                       0.5 deg family, 5/5 facial bones keyed.
4. FACE-SHAPE-APPLY  — convention shape keys (name == param) on a mesh
                       deformed by the armature: applied value vs intended
                       param <= 0.1 normalized (exact here), and the mesh
                       actually displaces (evaluated vertex moves).
5. FACE-NOTARGET     — a pose with a solved face + a rig with NEITHER
                       class: the loud capability line, never silent.
6. FACE-TWIN         — two bound applies byte-identical (bones + keys).

Usage: blender -b --python xtask/face_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR.
Prints RM_FACE lines; exit 0 only if every row PASSes.
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
    FACE_START,
    KEYPOINT_COUNT,
    face_kp_index,
)
from riggermortis_addon import pose_apply  # noqa: E402

TOL_DEG = 0.5
CX, CY, SCALE = 320.0, 240.0, 400.0
_EYE_W = 0.30
_PRIOR_EYE_H = 0.28 * _EYE_W
_NOSE_Y = 0.45
_MOUTH_Y = _NOSE_Y + 0.40
OK = True


def check(label: str, ok: bool, detail: str = "") -> None:
    global OK
    if not ok:
        OK = False
    print(f"RM_FACE {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


# -- the GT face generator (the probe's recipe, gate-owned copy) -------------------

def gt_face(brow=None, blink=None, jaw=0.0, smile=None, pout=0.0, cheek=None):
    brow, blink, smile, cheek = brow or {}, blink or {}, smile or {}, cheek or {}
    face: list[tuple[float, float] | None] = [None] * 68
    confs = [0.0] * KEYPOINT_COUNT

    def put(rel, x, y, conf=0.9):
        face[rel] = (CX + x * SCALE, CY + y * SCALE)
        confs[FACE_START + rel] = conf

    for side, sgn in (("L", 1.0), ("R", -1.0)):
        cx_eye = 0.5 * sgn
        h = _PRIOR_EYE_H * (1.0 - blink.get(side, 0.0))
        e_lo = 42 if side == "L" else 36  # measured side map: .L = band B
        put(e_lo + 0, cx_eye - 0.15 * sgn, 0.0)
        put(e_lo + 1, cx_eye - 0.075 * sgn, -h / 2.0)
        put(e_lo + 2, cx_eye + 0.075 * sgn, -h / 2.0)
        put(e_lo + 3, cx_eye + 0.15 * sgn, 0.0)
        put(e_lo + 4, cx_eye + 0.075 * sgn, h / 2.0)
        put(e_lo + 5, cx_eye - 0.075 * sgn, h / 2.0)
        b_lo = 22 if side == "L" else 17
        brow_y = -(0.30 + brow.get(side, 0.0) * 0.15)
        for i in range(5):
            put(b_lo + i, cx_eye - 0.15 * sgn + 0.075 * sgn * i, brow_y)
        ll_lo, ll_hi = (46, 48) if side == "L" else (40, 42)
        lid_y = h / 2.0
        put(ll_lo, cx_eye + 0.075 * sgn, lid_y)
        put(ll_hi - 1, cx_eye - 0.075 * sgn, lid_y)
        put(35 if side == "L" else 31, cx_eye,
            lid_y + (0.72 - cheek.get(side, 0.0) * 0.10))
    nose_lift = 0.3 * 0.10 * (cheek.get("L", 0.0) + cheek.get("R", 0.0)) / 2.0
    put(33, 0.0, _NOSE_Y - nose_lift)
    w = 0.83 - pout * 0.25
    c_l_y = _MOUTH_Y - smile.get("L", 0.0) * 0.12
    c_r_y = _MOUTH_Y - smile.get("R", 0.0) * 0.12
    put(54, w / 2.0, c_l_y)  # corner .L = image-right (measured map)
    put(48, -w / 2.0, c_r_y)
    put(51, 0.0, _MOUTH_Y - 0.05)
    put(57, 0.0, _MOUTH_Y - 0.05 + 0.02 + jaw * 0.55)
    for rel in range(17):
        put(rel, -0.6 + 1.2 * rel / 16.0, _MOUTH_Y + 0.45)
    for rel in range(27, 31):
        put(rel, 0.0, 0.10 + 0.10 * (rel - 27))
    for rel in (32, 34):
        put(rel, -0.1 + 0.1 * (rel - 32), _NOSE_Y - nose_lift)
    for rel in range(49, 54):
        if face[rel] is None:
            put(rel, -w / 2.0 + w * (rel - 48) / 6.0, _MOUTH_Y - 0.05)
    for rel in range(55, 60):
        if face[rel] is None:
            put(rel, -w / 2.0 + w * (rel - 54) / 6.0, c_l_y + 0.03)
    for rel in range(60, 68):
        if face[rel] is None:
            put(rel, -0.3 + 0.086 * (rel - 60), _MOUTH_Y + 0.02)
    kps: list[tuple[float, float]] = [(0.0, 0.0)] * KEYPOINT_COUNT
    for rel in range(68):
        assert face[rel] is not None, f"GT face gap at {rel}"
        kps[FACE_START + rel] = face[rel]  # type: ignore[index]
    return kps, confs


def benchmark_state_kwargs() -> dict[str, dict]:
    return {
        "neutral": {},
        "brows_raise": {"brow": {"L": 0.8, "R": 0.8}},
        "brow_raise_L": {"brow": {"L": 0.8}},
        "blink_both": {"blink": {"L": 1.0, "R": 1.0}},
        "blink_L": {"blink": {"L": 1.0}},
        "jaw_open": {"jaw": 1.0},
        "smile": {"smile": {"L": 1.0, "R": 1.0}},
        "smile_L": {"smile": {"L": 1.0}},
        "pout": {"pout": 1.0},
        "cheeks": {"cheek": {"L": 0.7, "R": 0.7}},
    }


def _gt_params(kw: dict) -> dict[str, float]:
    return {
        **{f"brow.raise.{s}": kw.get("brow", {}).get(s, 0.0) for s in ("L", "R")},
        **{f"blink.{s}": kw.get("blink", {}).get(s, 0.0) for s in ("L", "R")},
        **{f"smile.{s}": kw.get("smile", {}).get(s, 0.0) for s in ("L", "R")},
        **{f"cheek.{s}": kw.get("cheek", {}).get(s, 0.0) for s in ("L", "R")},
        "jaw.open": float(kw.get("jaw", 0.0)),
        "pout": float(kw.get("pout", 0.0)),
    }


# -- the engine-built fixture rig + mesh --------------------------------------------

REST = rest_skeleton(1.0 / 0.55)
FACE_BINDINGS = {
    "jaw.open": "jaw",
    "brow.raise.L": "brow.L",
    "brow.raise.R": "brow.R",
    "blink.L": "lid.L",
    "blink.R": "lid.R",
}
SHAPE_KEY_PARAMS = ("jaw.open", "brow.raise.L", "blink.R", "smile.L")


def _body_tail(role):
    child = PRIMARY_CHILD.get(role)
    if child is None:
        head = Vector(REST[role][0])
        return tuple(head + Vector((0.0, 0.0, 0.21 if role == "head" else 0.05)))
    return tuple(REST[child][0])


def build_fixture(name, *, face=True, mesh_keys=True):
    """Body chain (neck/head bound) + facial bones + (optionally) a mesh
    with convention shape keys. TWO-PASS build (create every bone, then
    wire parents; a missing parent REFUSES) — the S9/S27/S28 rule."""
    body_roles = [r for r in sorted(REST) if r != "root"]
    facial = ["jaw", "brow.L", "brow.R", "lid.L", "lid.R"] if face else []
    head_pos = Vector(REST["head"][0])

    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.mode_set(mode="EDIT")
    bones = obj.data.edit_bones
    bones.remove(bones[0])

    # pass 1: geometry for every bone
    for role in body_roles:
        b = bones.new(role)
        b.head = tuple(REST[role][0])
        b.tail = _body_tail(role)
    for fb in facial:
        b = bones.new(fb)
        b.head = tuple(head_pos + Vector((0.02 * facial.index(fb), -0.03, 0.0)))
        b.tail = tuple(head_pos + Vector((0.02 * facial.index(fb), -0.03, 0.08)))

    # pass 2: parenting (every bone exists now; a missing parent REFUSES)
    for role in body_roles:
        parent = CANONICAL[role].parent
        if not parent or parent == "root":
            continue
        if parent not in body_roles:
            raise RuntimeError(f"fixture {name!r}: parent {parent!r} missing for {role!r}")
        bones[role].parent = bones[parent]
    for fb in facial:
        if "head" not in bones:
            raise RuntimeError(f"fixture {name!r}: head missing for {fb!r}")
        bones[fb].parent = bones["head"]
    bpy.ops.object.mode_set(mode="OBJECT")

    for role in body_roles:
        obj[f"rm_role_{role}"] = role

    # the deformed mesh with convention shape keys (name == param) — each
    # key carries a REAL vertex delta so the displacement check has teeth
    mesh_obj = None
    if mesh_keys:
        bpy.ops.mesh.primitive_cube_add(location=(0, -0.3, head_pos.z))
        mesh_obj = bpy.context.object
        mesh_obj.name = f"{name}_skin"
        mod = mesh_obj.modifiers.new("arm", "ARMATURE")
        mod.object = obj
        if face:
            mesh_obj.shape_key_add(name="Basis")
            for i, key in enumerate(SHAPE_KEY_PARAMS):
                kb = mesh_obj.shape_key_add(name=key)
                for v in kb.data:
                    v.co = v.co + Vector((0.0, -0.3 - 0.05 * i, 0.0))
    return obj, mesh_obj


def _stand_pose_with_face(**face_kw):
    """Rest-stance body pose + a solved face from the GT generator."""
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
    kps, confs = gt_face(**face_kw)
    pose.face = core.solve_face(kps, confs)
    return pose


def _intended_face_quats(pose, face_map):
    """The declared world-space rotations (docs/FACE.md plan)."""
    out = {}
    for param, bone in face_map.items():
        if pose.face is None or param not in pose.face.params:
            continue
        axis, max_deg = core.FACE_BONE_PLAN[param]
        out[bone] = (param, Quaternion(Vector(axis), math.radians(max_deg) * pose.face.params[param]))
    return out


def _live_face_report(obj):
    out = {}
    for pb in obj.pose.bones:
        q = Quaternion(pb.rotation_axis_angle[1:4], pb.rotation_axis_angle[0])
        rest = pb.bone.matrix_local.to_quaternion()
        out[pb.name] = (rest @ q @ rest.inverted()).normalized()
    return out


def _quat_angle_deg(a, b):
    d = abs(a.dot(b))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, d))))


def _bound_apply(name, **face_kw):
    obj, mesh_obj = build_fixture(name)
    pose = _stand_pose_with_face(**face_kw)
    rig = core.RigData.from_dict(__import__("riggermortis_addon").bpy_bridge.rig_data_from_armature(obj))
    mapping = pose_apply.mapping_from_props(obj, core)
    if mapping is None:
        raise RuntimeError(f"{name}: fixture produced no mapping")
    preset = core.preset_from_mapping(rig, mapping, face_bones=dict(FACE_BINDINGS))
    face_map = core.resolve_face(preset, rig.fingerprint())
    report = pose_apply.apply_pose_object(obj, pose, core, face_bones=face_map)
    return obj, mesh_obj, pose, face_map, report


def main() -> int:
    global OK

    # 1. FACE-BENCH — monotonicity + reach over the 10-expression class.
    states = benchmark_state_kwargs()
    solved: dict[str, dict[str, float]] = {}
    for name, kw in states.items():
        face = core.solve_face(*gt_face(**kw))
        solved[name] = dict(face.params) if face else {}
    worst_viol, worst_reach = 0, 1.0
    for param in core.FACE_PARAMS:
        gt = {n: _gt_params(kw)[param] for n, kw in states.items()}
        order = sorted(gt, key=lambda n: (gt[n], n))
        seq = [solved[n].get(param, 0.0) for n in order]
        viol = sum(1 for a, b in zip(seq, seq[1:], strict=False) if a - b > 0.05)
        gt_max = max(gt.values())
        reach = 1.0
        if gt_max > 0:
            reach = max(solved[n].get(param, 0.0) for n in gt if gt[n] == gt_max) / gt_max
        if viol > worst_viol or reach < worst_reach:
            worst_viol = max(worst_viol, viol)
            worst_reach = min(worst_reach, reach)
    check(
        "FACE-BENCH",
        worst_viol <= 1 and worst_reach >= 0.5,
        f"worst violations {worst_viol}/9 (bar 1), worst reach {worst_reach:.2f} "
        f"(bar 0.5) over 10 states x {len(core.FACE_PARAMS)} params "
        "[SYNTHETIC, prior-consistent GT]",
    )

    # 2. FACE-GATE-OCCL — zero guessed params, verbatim ledgers.
    kps, confs = gt_face(jaw=0.8)
    no_entry = core.solve_face(kps, [0.0] * KEYPOINT_COUNT)
    confs_p = list(confs)
    for i in range(5):
        confs_p[face_kp_index("R", "brow", i)] = 0.3
    face_p = core.solve_face(kps, confs_p)
    partial_ok = (
        face_p is not None
        and "brow.raise.R" in face_p.skipped
        and "below floor 0.55" in face_p.skipped["brow.raise.R"]
        and "jaw.open" in face_p.params
    )
    face_n = core.solve_face(*gt_face())
    neutral_ok = (
        face_n is not None and len(face_n.params) == 0
        and len(face_n.skipped) == len(core.FACE_PARAMS)
        and all("below activation floor" in r for r in face_n.skipped.values())
    )
    check(
        "FACE-GATE-OCCL",
        no_entry is None and partial_ok and neutral_ok,
        "conf-0 -> no entry; brow.R below-floor ledgered, rest solved; "
        "neutral -> 0 params, all ledgered; zero guessed",
    )

    # 3. FACE-BONE-APPLY — real addon path, declared axis-angle within family.
    # The fixture pose authors ALL five bound classes (blink.L and smile.L
    # included — an unauthored param is LEDGERED, never guessed, so its
    # bone/key would legitimately stay untouched).
    fresh_scene()
    obj, _mesh, pose, face_map, report = _bound_apply(
        "RM_FaceMeta", jaw=0.8, brow={"L": 0.6, "R": 0.2},
        blink={"L": 0.7, "R": 0.9}, smile={"L": 0.5},
    )
    intended = _intended_face_quats(pose, face_map)
    live = _live_face_report(obj)
    worst, worst_bone = 0.0, ""
    for bone, (_param, q) in intended.items():
        deg = _quat_angle_deg(live[bone], q)
        if deg > worst:
            worst, worst_bone = deg, bone
    keyed = len([r for r in report["applied"] if r in set(FACE_BINDINGS.values())])
    check(
        "FACE-BONE-APPLY",
        worst <= TOL_DEG and keyed == len(FACE_BINDINGS),
        f"live face-bone world-rotation worst {worst:.4f} deg ({worst_bone}) "
        f"bar {TOL_DEG}, {keyed}/{len(FACE_BINDINGS)} facial bones keyed",
    )

    # 4. FACE-SHAPE-APPLY — convention keys set to params, mesh displaces.
    applied_keys = report.get("shape_keys_applied", [])
    key_ok = set(SHAPE_KEY_PARAMS) <= set(applied_keys)
    value_err = 0.0
    if _mesh is not None and _mesh.data.shape_keys is not None:
        for key in SHAPE_KEY_PARAMS:
            v = _mesh.data.shape_keys.key_blocks[key].value
            intended_v = pose.face.params.get(key, 0.0) if pose.face else 0.0
            value_err = max(value_err, abs(v - intended_v))
    # displacement: the evaluated mesh must move under the driven keys
    displaced = False
    if _mesh is not None:
        bpy.context.view_layer.update()  # place, UPDATE, then measure (S26)
        deps = bpy.context.evaluated_depsgraph_get()
        ev = _mesh.evaluated_get(deps)
        base = _mesh.data.vertices[0].co
        moved = (ev.to_mesh().vertices[0].co - base).length
        displaced = moved > 0.01
    check(
        "FACE-SHAPE-APPLY",
        key_ok and value_err <= 0.1 and displaced,
        f"keys {len(applied_keys)}/{len(SHAPE_KEY_PARAMS)} applied, value "
        f"delta {value_err:.4f} (bar 0.1), mesh displaced={displaced}",
    )

    # 5. FACE-NOTARGET — bare rig (no bindings, no shape keys): loud line.
    fresh_scene()
    obj_b, mesh_b = build_fixture("RM_FaceBare", face=False, mesh_keys=False)
    pose_b = _stand_pose_with_face(jaw=0.7)
    report_b = pose_apply.apply_pose_object(obj_b, pose_b, core)
    line = [n for n in report_b["notes"] if "no facial targets for this rig" in n]
    check(
        "FACE-NOTARGET",
        len(line) == 1 and f"face: {len(pose_b.face.params)} expression param(s) solved" in line[0],
        "capability line verbatim",
    )

    # 6. FACE-TWIN — two bound applies byte-identical (bones + keys).
    fresh_scene()
    _obj1, m1, _p1, _f1, _r1 = _bound_apply("RM_FaceT1", jaw=0.5, smile={"L": 0.8})
    snap1 = {
        pb.name: tuple(round(v, 9) for v in pb.rotation_axis_angle)
        for pb in bpy.data.objects["RM_FaceT1"].pose.bones
    }
    keys1 = tuple(
        round(m1.data.shape_keys.key_blocks[k].value, 9)
        for k in sorted(SHAPE_KEY_PARAMS)
    ) if m1 is not None else ()
    fresh_scene()
    _obj2, m2, _p2, _f2, _r2 = _bound_apply("RM_FaceT2", jaw=0.5, smile={"L": 0.8})
    snap2 = {
        pb.name: tuple(round(v, 9) for v in pb.rotation_axis_angle)
        for pb in bpy.data.objects["RM_FaceT2"].pose.bones
    }
    keys2 = tuple(
        round(m2.data.shape_keys.key_blocks[k].value, 9)
        for k in sorted(SHAPE_KEY_PARAMS)
    ) if m2 is not None else ()
    check(
        "FACE-TWIN",
        snap1 == snap2 and keys1 == keys2 and len(snap1) > 0,
        f"bones={len(snap1)} keys_identical={keys1 == keys2} identical={snap1 == snap2}",
    )

    print(f"RM_FACE GATE: {'PASS' if OK else 'FAIL'}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
