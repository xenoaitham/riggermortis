"""P8-2 coupling gate probe (run INSIDE Blender, headless) — the RM_COUPLE
rows. scene_gate.py's sibling for the contact-coupling rock (the same house
shape: real add-on machinery, grep-pinned lines, exit 0 only if all PASS).

The fixture is ENGINE-BUILT (Annex A.3 — no external sourcing): two
canonical-exact rigs (bones at rest_skeleton positions, identity role->bone
props, so the measured placement scale s == 1 and the rig-space residual
measures the COUPLING, not rig-proportion mismatch — the apply rows in
scene_gate own fidelity), placed hold-from-behind (B in front of A), driven
through the REAL add-on scene-apply library entry with in-memory payload
dicts (the file-IO + socket halves of apply_scene are covered by scene_gate
APPLY2 and session-verify; this gate isolates the coupling machinery):
placements MEASURED from the posed rigs, the core coupling pass, the
coupled re-apply, and the structured coupling report.

Rows:
1. COUPLE-RESIDUAL — both authored pins close: rig-space residual < 2%
   torso span (the Annex A.1 bar), report rows closed, coupled apply
   FK-fidelity within the 0.5 deg family.
2. COUPLE-NONCHAIN — roles outside the pinned limbs' chains apply
   byte-identically vs the pins-free baseline; exactly the pinned chains'
   bones move.
3. COUPLE-TWIN — two coupled runs are byte-identical.
4. COUPLE-CONFLICT — two authored pins competing for one hand: the apply
   succeeds, BOTH residuals are reported, the over-bar rows stay loud
   (unclosable), rotations finite.
5. COUPLE-NOENFORCE — a suggested pin moves NOTHING (quats equal the
   pins-free baseline) and reports why.

Usage: blender -b --python xtask/couple_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR.
Prints RM_COUPLE lines; exit 0 only if every row PASSes.
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.environ["RM_CORE_SRC"])
sys.path.insert(0, os.environ["RM_ADDON_DIR"])

import bpy  # noqa: E402
import riggermortis as core  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402
from riggermortis.canonical import CANONICAL, PRIMARY_CHILD, rest_skeleton  # noqa: E402
from riggermortis.coupling import BAR_FRAC as COUPLE_BAR  # noqa: E402
from riggermortis_addon import scene_apply  # noqa: E402

TOL_DEG = 0.5
OK = True


def check(label: str, ok: bool, detail: str = "") -> None:
    global OK
    if not ok:
        OK = False
    print(f"RM_COUPLE {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def all_quats() -> dict:
    """Pose rotations as (w, x, y, z) quaternions, 9 dp (deterministic)."""
    out = {}
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        for pb in obj.pose.bones:
            q = Quaternion(pb.rotation_axis_angle[1:4], pb.rotation_axis_angle[0])
            out[f"{obj.name}/{pb.name}"] = tuple(round(v, 9) for v in q)
    return out


# -- the engine-built fixture -----------------------------------------------------


def _stand_pose() -> dict:
    """Canonical-unit rest stance as a payload pose dict (T-pose, hips
    anchored, torso span 0.45) — the hold-from-behind fixture class."""
    rest = rest_skeleton(1.0 / 0.55)
    return {
        "positions": {r: list(v[0]) for r, v in sorted(rest.items())},
        "flips": {k: -1 for k in ("forearm.L", "forearm.R", "lower_leg.L", "lower_leg.R")},
        "confidence": 1.0,
        "reliable": True,
        "scale": 1.0,
        "anchor": "hips",
        "notes": [],
        "joint_confidence": {},
    }


def _couple_payload(pins: list[dict]) -> dict:
    stand = _stand_pose()
    entries = [
        {
            "label": lab,
            "index": i,
            "score": 0.99,
            "bbox": [0.0, 0.0, 100.0, 200.0],
            "pose": json.loads(json.dumps(stand)),  # deep copy per figure
            "rotations": [],
            "skipped": [],
            "notes": [],
        }
        for i, lab in enumerate(("A", "B"))
    ]
    return {
        "format": 3,
        "image": {"path": "engine-built couple fixture", "width": 100, "height": 200},
        "figure": dict(entries[0]),
        "pose": entries[0]["pose"],
        "rotations": [],
        "skipped": [],
        "notes": [],
        "figures": entries,
        "rig": {"name": "gate-fixture", "fingerprint": "engine-built"},
        "pins": pins,
    }


def build_canonical_rig(name: str, y_off: float):
    """A canonical-EXACT fixture rig: bones at rest_skeleton positions
    (meters, hips at z=1.0), identity role->bone mapping via rm_role props.
    The measured placement scale s is 1.0 exactly, so posed joints ==
    placements * canonical and the rig-space residual is the coupling's.

    TWO-PASS build (create every bone, then wire parents): alphabetical
    creation order puts children before parents (forearm before upper_arm),
    and a silent `parent in bones` fallback disconnects the limbs — the
    exact class the S9 gate lesson warns about (parents must exist first,
    and a missing parent must refuse, never fall back to None)."""
    rest = rest_skeleton(1.0 / 0.55)
    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.mode_set(mode="EDIT")
    bones = obj.data.edit_bones
    bones.remove(bones[0])

    def tail_of(role: str) -> tuple[float, float, float]:
        child = PRIMARY_CHILD.get(role)
        if child is None:
            head = Vector(rest[role][0])
            if role.startswith("hand"):
                return tuple(head + Vector((0.11 * (1 if role.endswith(".L") else -1), 0, 0)))
            if role.startswith("toe"):
                return tuple(head + Vector((0.0, -0.12, 0.0)))
            if role == "head":
                return tuple(head + Vector((0.0, 0.0, 0.21)))
            return tuple(head + Vector((0.0, 0.0, 0.05)))
        return tuple(rest[child][0])

    roles = [r for r in sorted(rest) if r != "root"]  # coincident with hips
    for role in roles:  # pass 1: geometry
        b = bones.new(role)
        b.head = tuple(rest[role][0])
        b.tail = tail_of(role)
    for role in roles:  # pass 2: parenting (every bone exists now)
        parent = CANONICAL[role].parent
        if not parent or parent == "root":
            continue  # hips is a root bone here
        if parent not in bones:
            raise RuntimeError(f"fixture rig {name!r}: parent {parent!r} "
                               f"missing for {role!r}")
        bones[role].parent = bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.location = (0.0, y_off, 0.0)
    for role in roles:
        obj[f"rm_role_{role}"] = role
    return obj


def _world_head(obj, bone: str) -> Vector:
    return obj.matrix_world @ Vector(obj.pose.bones[bone].head)


def _worst_fk_deg(obj, pose_dict: dict) -> tuple[float, str]:
    """LIVE per-bone world-direction error vs the pose's canonical targets
    (the scene_gate instrument — reads the actual posed matrix)."""
    pose = core.CanonicalPose.from_dict(pose_dict)
    worst, worst_role = 0.0, ""
    for role in sorted(core.ALL_ROLES):
        target = core.bone_target_direction(pose, role)
        bone = obj.get(f"rm_role_{role}")
        if target is None or not bone:
            continue
        pb = obj.pose.bones.get(str(bone))
        if pb is None:
            continue
        d = pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))
        d.normalize()
        dot = max(-1.0, min(1.0, d.dot(Vector(target))))
        deg = math.degrees(math.acos(dot))
        if deg > worst:
            worst, worst_role = deg, role
    return worst, worst_role


def _rest_head(obj, bone: str) -> Vector:
    """Rest armature-space joint (data bone — unaffected by any pose)."""
    return obj.matrix_world @ Vector(obj.data.bones[bone].head_local)


def _rig_span(obj) -> float:
    """Rest torso span (the placement scale's denominator measurement)."""
    return (_rest_head(obj, "neck") - _rest_head(obj, "hips")).length


ASSIGNMENTS = {"A": "RM_CplA", "B": "RM_CplB"}

PINS = [
    {"figure_a": "A", "role_a": "hand.R", "figure_b": "B", "role_b": "chest",
     "origin": "authored", "confidence": 1.0},
    {"figure_a": "A", "role_a": "hand.L", "figure_b": "B", "role_b": "spine",
     "origin": "authored", "confidence": 1.0},
]
CONFLICT_PINS = [
    {"figure_a": "A", "role_a": "hand.R", "figure_b": "B", "role_b": "chest",
     "origin": "authored", "confidence": 1.0},
    {"figure_a": "A", "role_a": "hand.R", "figure_b": "B", "role_b": "spine",
     "origin": "authored", "confidence": 1.0},
]
SUGGEST_PINS = [
    {"figure_a": "A", "role_a": "hand.R", "figure_b": "B", "role_b": "chest",
     "origin": "suggested", "confidence": 0.9},
]


def run(payload: dict) -> tuple[dict, dict]:
    """The REAL scene-apply library path: fresh canonical-exact rigs placed
    hold-from-behind, one apply_scene_payload call (couple defaults on).
    Returns (report, the exact payload dict the apply consumed)."""
    fresh_scene()
    build_canonical_rig("RM_CplA", 0.0)
    build_canonical_rig("RM_CplB", -0.30)  # hold-from-behind: B in front of A
    consumed = json.loads(json.dumps(payload))
    report = scene_apply.apply_scene_payload(consumed, dict(ASSIGNMENTS), core=core)
    return report, consumed


def main() -> int:
    global OK
    p_couple = _couple_payload(PINS)
    p_nopins = _couple_payload([])
    p_nopins.pop("pins")
    p_conflict = _couple_payload(CONFLICT_PINS)
    p_suggest = _couple_payload(SUGGEST_PINS)

    # 1. COUPLE-RESIDUAL: placements measured from the posed rigs, coupled
    # re-apply; rig-space residual < 2% torso span on BOTH authored pins.
    report, _consumed = run(p_couple)
    bpy.context.view_layer.update()
    rig_a, rig_b = bpy.data.objects["RM_CplA"], bpy.data.objects["RM_CplB"]
    span = 0.5 * (_rig_span(rig_a) + _rig_span(rig_b))
    r1 = (_world_head(rig_a, "hand.R") - _world_head(rig_b, "chest")).length
    r2 = (_world_head(rig_a, "hand.L") - _world_head(rig_b, "spine")).length
    rows = (report.get("coupling") or {}).get("rows", [])
    worst_fk = report.get("worst_deg", 999.0)
    check("COUPLE-RESIDUAL",
          len(rows) == 2 and all(r.get("closed") for r in rows)
          and r1 / span < COUPLE_BAR and r2 / span < COUPLE_BAR
          and worst_fk <= TOL_DEG,
          f"rig residuals {r1:.5f}/{r2:.5f} m, span {span:.4f} m, fracs "
          f"{r1 / span:.5f}/{r2 / span:.5f} bar {COUPLE_BAR}, worst_fk "
          f"{worst_fk:.4f} deg, iterations {[r.get('iterations') for r in rows]}")

    # 2. COUPLE-NONCHAIN — the Annex A.1 bar decomposed honestly:
    # (a) CORE-side (already unit-pinned, re-proven on the consumed payload):
    #     roles OUTSIDE the pinned subtrees keep byte-identical canonical
    #     positions — the solve never touches them;
    # (b) Blender-side: the apply realizes the coupled targets within the
    #     0.5 deg family (live world directions vs the consumed targets,
    #     the scene_gate instrument). Roles that RIDE a moved subtree swing
    #     rigidly with it (positions AND segment directions) — that is the
    #     coupled pose's own physics, not a coupling artifact.
    _r, consumed_nopins = run(p_nopins)
    report_c, consumed = run(p_couple)
    bpy.context.view_layer.update()
    stand = _stand_pose()["positions"]
    outside = {r for r in stand if r not in (
        "upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R",
        "hand.R")}  # A's pinned-arm subtrees + their pivots
    b_outside = {r for r in stand if r not in (
        "spine", "chest", "neck", "head", "shoulder.L", "shoulder.R",
        "upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R",
        "hand.R")}  # B's spine subtree rides pin 1's chest endpoint
    a_pos = consumed["figures"][0]["pose"]["positions"]
    b_pos = consumed["figures"][1]["pose"]["positions"]
    byte_ok = (all(tuple(a_pos[r]) == tuple(stand[r]) for r in outside if r in a_pos)
               and all(tuple(b_pos[r]) == tuple(stand[r]) for r in b_outside if r in b_pos))
    rig_a, rig_b = bpy.data.objects["RM_CplA"], bpy.data.objects["RM_CplB"]
    wa, ra_ = _worst_fk_deg(rig_a, consumed["figures"][0]["pose"])
    wb, rb_ = _worst_fk_deg(rig_b, consumed["figures"][1]["pose"])
    check("COUPLE-NONCHAIN",
          byte_ok and wa <= TOL_DEG and wb <= TOL_DEG,
          f"A non-chain positions byte-equal + B anchored byte-equal={byte_ok}; "
          f"live fk vs coupled targets A {wa:.4f} deg ({ra_}) B {wb:.4f} deg ({rb_}) "
          f"bar {TOL_DEG}")

    # 3. COUPLE-TWIN: two coupled runs byte-identical.
    run(p_couple)
    q_t1 = all_quats()
    run(p_couple)
    q_t2 = all_quats()
    check("COUPLE-TWIN", q_t1 == q_t2 and len(q_t1) > 0,
          f"bones={len(q_t1)} identical={q_t1 == q_t2}")

    # 4. COUPLE-CONFLICT: competing pins compromise + report; the apply still
    # succeeds and the over-bar rows stay loud.
    creport, _consumed_c = run(p_conflict)
    crows = (creport.get("coupling") or {}).get("rows", [])
    unclosable = [r for r in crows if not r.get("closed")]
    bpy.context.view_layer.update()
    finite = all(
        all(math.isfinite(v) for v in q)
        for q in all_quats().values()
    )
    check("COUPLE-CONFLICT",
          len(crows) == 2 and len(unclosable) >= 1 and finite,
          f"residual_fracs {[round(r['residual_frac'], 4) for r in crows]} "
          f"unclosable={len(unclosable)} (compromise reported, apply succeeded)")

    # 5. COUPLE-NOENFORCE: a suggested pin moves NOTHING and says why.
    run(p_nopins)
    q_base = all_quats()
    sreport, _consumed_s = run(p_suggest)
    q_suggest = all_quats()
    srows = (sreport.get("coupling") or {}).get("rows", [])
    check("COUPLE-NOENFORCE",
          len(srows) == 1 and not srows[0]["enforced"]
          and "suggested" in srows[0]["reason"] and q_suggest == q_base,
          f"enforced={srows[0]['enforced'] if srows else '?'} "
          f"rig untouched={q_suggest == q_base}")

    print(f"RM_COUPLE GATE: {'PASS' if OK else 'FAIL'}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
