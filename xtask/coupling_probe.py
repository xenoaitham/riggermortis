"""P8-2 capability probe: the coupling-solve unknowns, answered by DOING.

The coupling solve is PURE CORE (canonical positions in, positions out; the
apply path derives rotations from positions, so nothing here touches bpy and
there is no Blender unknown in the solver itself — the real-rig apply is the
GATE's job). Design of record: docs/SCENES.md § Contact coupling. Every
constant below is pre-declared there (D-008 style: order-of-magnitude
choices, never fixture-fitted).

Rows (engine-built fixtures per Annex A.3 — no external sourcing):

1. BUILD      — the hold-from-behind-class fixture: two figures, placements
                measured-class (t only), both authored pins start inside the
                movable chains' reach annulus.
2. CONVERGE   — both pins close within the Annex A.1 bar (residual < 2%
                torso span) through the declared iterative redistribution.
3. NONCHAIN   — roles outside the pinned limbs' chains keep byte-identical
                positions (the movable-chain table's blast radius: no torso
                swing for hand pins), and through the REAL
                apply_canonical_pose their derived rotations are
                byte-identical (to_dict equality) while the pinned chain
                roles move.
4. CONFLICT   — two authored pins competing for ONE hand: the damped
                authored-order compromise, both residuals reported, the
                over-bar pins flagged unclosable, twin run byte-identical.
5. DETERM     — two independent CONVERGE solves are byte-identical (pure
                function of scene + placements).
6. NOENFORCE  — a suggested pin and a below-floor authored pin move nothing
                (positions byte-identical) and report their reasons.
7. REACH      — an unreachable pin (target beyond chain reach) stays loud:
                unclosable flagged, no crash, the chain straightens toward
                the target (the endpoint gets closer, the residual reports
                the truth).

Prints RM_COUPLE lines; exit 0 only if every row PASSes.
Usage: /home/potato/miniconda3/bin/python3 xtask/coupling_probe.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

CORE_SRC = Path(
    os.environ.get(
        "RM_CORE_SRC",
        Path(__file__).resolve().parent.parent / "core" / "src",
    )
)
sys.path.insert(0, str(CORE_SRC))

from riggermortis.canonical import PRIMARY_CHILD, children_of, rest_skeleton  # noqa: E402
from riggermortis.canonical_pose import TORSO_SPAN, CanonicalPose  # noqa: E402
from riggermortis.fk_apply import apply_canonical_pose  # noqa: E402
from riggermortis.mapper import RigMapping, RoleAssignment  # noqa: E402
from riggermortis.types import BoneData, RigData  # noqa: E402

# -- pre-declared constants (docs/SCENES.md § Contact coupling) -------------------

MAX_ITERS = 32
EARLY_EXIT_FRAC = 2e-4  # three orders under the 0.02 bar
ENFORCE_CONF_FLOOR = 0.55  # the CONVENTIONS ambiguity bar, reused
BAR_FRAC = 0.02  # Annex A.1: residual < 2% torso span

FLIP_KEYS = ("forearm.L", "forearm.R", "lower_leg.L", "lower_leg.R")

OK: list[bool] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    OK.append(ok)
    print(f"RM_COUPLE {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")


# -- tiny vec helpers (the probe is the recipe; core lifts these) -----------------

def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a: Vec3, k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot3(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a: Vec3) -> float:
    return math.sqrt(dot3(a, a))


def unit(a: Vec3) -> Vec3:
    n = norm(a)
    return (0.0, 0.0, 0.0) if n <= 1e-12 else (a[0] / n, a[1] / n, a[2] / n)


def q_axis_angle(axis: Vec3, angle: float):
    s = math.sin(angle / 2.0)
    return (math.cos(angle / 2.0), axis[0] * s, axis[1] * s, axis[2] * s)


def q_rotate(q, v: Vec3) -> Vec3:
    w, x, y, z = q
    uvx, uvy, uvz = 2.0 * (y * v[2] - z * v[1]), 2.0 * (z * v[0] - x * v[2]), 2.0 * (x * v[1] - y * v[0])
    return (
        v[0] + w * uvx + (y * uvz - z * uvy),
        v[1] + w * uvy + (z * uvx - x * uvz),
        v[2] + w * uvz + (x * uvy - y * uvx),
    )


Vec3 = tuple[float, float, float]

# -- fixture builders --------------------------------------------------------------


def stand_pose(hip_conf: float = 1.0) -> CanonicalPose:
    """Canonical-unit rest stance (T-pose), hips anchored, unit torso span."""
    rest = rest_skeleton(1.0 / 0.55)  # hip height 1.0 -> TORSO_SPAN == 0.45
    return CanonicalPose(
        positions={r: v[0] for r, v in sorted(rest.items())},
        flips={k: -1 for k in FLIP_KEYS},
        confidence=1.0,
        reliable=True,
        scale=1.0,
        anchor="hips",
        notes=[],
        joint_confidence={"hand.R": hip_conf},
    )


class Placement:
    """(R, t, s): scene_p = t + s * R * canonical_p."""

    def __init__(self, t: Vec3 = (0.0, 0.0, 0.0), quat=(1.0, 0.0, 0.0, 0.0), s: float = 1.0):
        self.t = t
        self.quat = quat
        self.s = s

    def place(self, p: Vec3) -> Vec3:
        return add(self.t, scale(q_rotate(self.quat, p), self.s))

    def unplace(self, p: Vec3) -> Vec3:
        return q_rotate((self.quat[0], -self.quat[1], -self.quat[2], -self.quat[3]),
                        scale(sub(p, self.t), 1.0 / self.s))


def subtree_of(positions: dict[str, Vec3], joint: str) -> list[str]:
    out, stack = [], [joint]
    while stack:
        r = stack.pop()
        for c in children_of(r):
            if c in positions:
                out.append(c)
                stack.append(c)
    return sorted(out)  # keyed


def movable_joints(role: str, positions: dict[str, Vec3]) -> list[str]:
    """The declared v1 movable-chain table (docs/SCENES.md), root->leaf."""
    base, _, side = role.partition(".")
    if side:
        if base in ("hand", "forearm"):
            chain = [f"upper_arm.{side}", f"forearm.{side}"]
        elif base in ("lower_leg", "foot", "toe"):
            chain = [f"upper_leg.{side}", f"lower_leg.{side}"]
        else:
            chain = []
    elif role == "chest":
        chain = ["spine"]
    elif role in ("neck", "head"):
        chain = ["spine", "chest"]
    else:
        chain = []
    return [j for j in chain if j in positions]


def carry(positions: dict[str, Vec3], endpoint: str, target: Vec3, joints: list[str]) -> None:
    """One redistribution pass: root->leaf, each joint takes 1/n of the
    currently-needed carry angle about its own position (recomputed after
    every joint — bends the chain instead of swinging it rigidly)."""
    n = max(len(joints), 1)
    for j in joints:  # keyed root->leaf
        cur = positions[endpoint]
        piv = positions[j]
        u, v = sub(cur, piv), sub(target, piv)
        if norm(u) < 1e-12 or norm(v) < 1e-12:
            continue
        nu, nv = unit(u), unit(v)
        angle = math.acos(max(-1.0, min(1.0, dot3(nu, nv))))
        if angle < 1e-9:
            continue
        axis = cross(nu, nv)
        if norm(axis) < 1e-9:
            continue  # collinear: already pointing at (or away from) the target
        q = q_axis_angle(unit(axis), angle / n)
        for d in subtree_of(positions, j):
            positions[d] = add(piv, q_rotate(q, sub(positions[d], piv)))


def joint_conf(pose: CanonicalPose, role: str) -> float:
    return float(pose.joint_confidence.get(role, pose.confidence))


def solve(figures: dict[str, CanonicalPose], placements: dict[str, Placement],
          pins: list[dict]) -> tuple[dict[str, CanonicalPose], list[dict]]:
    """The declared solve: authored-order damped redistribution. Returns
    (coupled poses by label, per-pin report rows in authored order)."""
    pos = {lab: dict(p.positions) for lab, p in figures.items()}
    chains = {
        (lab, role): movable_joints(role, pos[lab])
        for pin in pins
        for lab, role in ((pin["figure_a"], pin["role_a"]), (pin["figure_b"], pin["role_b"]))
    }
    rows: list[dict] = []
    enforceable = []
    for pin in pins:
        ca, cb = joint_conf(figures[pin["figure_a"]], pin["role_a"]), \
            joint_conf(figures[pin["figure_b"]], pin["role_b"])
        ma, mb = bool(chains[(pin["figure_a"], pin["role_a"])]), bool(chains[(pin["figure_b"], pin["role_b"])])
        enforced, reason = True, ""
        if pin["origin"] != "authored":
            enforced, reason = False, "suggested pin (never auto-enforced)"
        elif float(pin["confidence"]) < ENFORCE_CONF_FLOOR:
            enforced, reason = False, f"pin confidence below floor {ENFORCE_CONF_FLOOR}"
        elif not ma and not mb:
            enforced, reason = False, "both endpoints immovable (girdle/anchor-rigid)"
        row = {**pin, "enforced": enforced, "reason": reason, "iterations": 0}
        rows.append(row)
        if enforced:
            if not ma:
                row["wa"], row["wb"] = 0.0, 1.0
            elif not mb:
                row["wa"], row["wb"] = 1.0, 0.0
            else:
                da, db = 1.0 - ca, 1.0 - cb
                if da + db < 1e-12:
                    row["wa"], row["wb"] = 0.5, 0.5
                else:
                    row["wa"], row["wb"] = da / (da + db), db / (da + db)
            enforceable.append(row)

    for it in range(MAX_ITERS):
        done = True
        for row in enforceable:  # AUTHORED order (the precedence rule)
            fa, fb = row["figure_a"], row["figure_b"]
            pa, pb = pos[fa][row["role_a"]], pos[fb][row["role_b"]]
            sa, sb = placements[fa], placements[fb]
            gap = sub(sa.place(pa), sb.place(pb))
            span = figure_span(figures[fa], sa) + figure_span(figures[fb], sb)
            if norm(gap) / (0.5 * span) < EARLY_EXIT_FRAC:
                continue
            done = False
            row["iterations"] = it + 1
            if row["wa"] > 0.0:
                target = sa.unplace(sub(sa.place(pa), scale(gap, row["wa"])))
                carry(pos[fa], row["role_a"], target, chains[(fa, row["role_a"])])
            if row["wb"] > 0.0:
                target = sb.unplace(add(sb.place(pb), scale(gap, row["wb"])))
                carry(pos[fb], row["role_b"], target, chains[(fb, row["role_b"])])
        if done:
            break

    for row in rows:  # residuals for EVERY pin (enforced or not) — loud
        fa, fb = row["figure_a"], row["figure_b"]
        sa, sb = placements[fa], placements[fb]
        resid = norm(sub(sa.place(pos[fa][row["role_a"]]), sb.place(pos[fb][row["role_b"]])))
        span = 0.5 * (figure_span(figures[fa], sa) + figure_span(figures[fb], sb))
        row["residual"] = resid
        row["residual_frac"] = resid / span
        row["closed"] = row["residual_frac"] < BAR_FRAC
    coupled = {lab: CanonicalPose(
        positions=p, flips=dict(figures[lab].flips), confidence=figures[lab].confidence,
        reliable=figures[lab].reliable, scale=figures[lab].scale,
        anchor=figures[lab].anchor, notes=list(figures[lab].notes),
        joint_confidence=dict(figures[lab].joint_confidence),
    ) for lab, p in pos.items()}
    return coupled, rows


def figure_span(pose: CanonicalPose, pl: Placement) -> float:
    if "hips" in pose.positions and "neck" in pose.positions:
        return pl.s * norm(sub(pose.positions["neck"], pose.positions["hips"]))
    return pl.s * TORSO_SPAN


# -- the synthetic identity rig (exercises the REAL apply path) --------------------


def identity_rig() -> tuple[RigData, RigMapping]:
    rest = rest_skeleton(1.0 / 0.55)
    rig = RigData(name="couple-probe-rig")
    for role, (head, _tail) in sorted(rest.items()):
        child = PRIMARY_CHILD.get(role)
        if child is None:
            continue
        parent_role = {"upper_arm": "shoulder", "forearm": "upper_arm",
                       "lower_leg": "upper_leg", "foot": "lower_leg",
                       "toe": "foot"}.get(role.partition(".")[0])
        if parent_role and role.partition(".")[1]:
            parent_role = f"{parent_role}.{role.partition('.')[2]}"
        elif role == "shoulder.L" or role == "shoulder.R":
            parent_role = "chest"
        rig.bones[role] = BoneData(name=role, head=head, tail=rest[child][0],
                                   parent=parent_role)
    mapping = RigMapping(rig_name=rig.name, fingerprint=rig.fingerprint())
    for role in sorted(rig.bones):
        side = role.rpartition(".")[2] or "C"
        mapping.assignments[role] = RoleAssignment(
            role=role, bone=role, confidence=1.0, side=side)
    return rig, mapping


def pose_dict_rotations(rig: RigData, mapping: RigMapping, pose: CanonicalPose) -> dict:
    return apply_canonical_pose(rig, mapping, pose).to_dict()


# -- rows ---------------------------------------------------------------------------


def main() -> int:
    figures = {"A": stand_pose(), "B": stand_pose()}
    placements = {"A": Placement(), "B": Placement(t=(0.0, -0.32, 0.0))}
    pins = [
        {"figure_a": "A", "role_a": "hand.R", "figure_b": "B", "role_b": "chest",
         "origin": "authored", "confidence": 1.0},
        {"figure_a": "A", "role_a": "hand.L", "figure_b": "B", "role_b": "spine",
         "origin": "authored", "confidence": 1.0},
    ]

    # BUILD — each pinned target starts inside its chain's reach annulus:
    # pivot (upper_arm head, the fixed base) to target, vs the chain length.
    a0, b0 = figures["A"].positions, figures["B"].positions
    d1 = norm(sub(placements["B"].place(b0["chest"]), placements["A"].place(a0["upper_arm.R"])))
    d2 = norm(sub(placements["B"].place(b0["spine"]), placements["A"].place(a0["upper_arm.L"])))
    reach = 0.32 + 0.28
    check("BUILD", 0.04 < d1 < reach and 0.04 < d2 < reach,
          f"pivot->target {d1:.4f}/{d2:.4f} reach {reach:.2f}")

    # CONVERGE
    coupled, rows = solve(figures, placements, pins)
    fr = [r["residual_frac"] for r in rows]
    check("CONVERGE", all(r["closed"] for r in rows) and all(r["enforced"] for r in rows),
          f"fracs {fr[0]:.6f}/{fr[1]:.6f} bar {BAR_FRAC} iters {rows[0]['iterations']}")

    # NONCHAIN — positions + through-the-real-apply rotations
    moved_a = {"upper_arm.R", "forearm.R", "hand.R", "upper_arm.L", "forearm.L", "hand.L"}
    pos_same_a = all(coupled["A"].positions[r] == a0[r] for r in a0
                     if r not in moved_a and r not in ("hips", "root"))
    torso_fixed = all(coupled["A"].positions[r] == a0[r]
                      for r in ("spine", "chest", "neck", "head"))
    b_rides = {"spine", "chest", "neck", "head", "shoulder.L", "shoulder.R",
               "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R", "hand.L", "hand.R"}
    b_fixed = all(coupled["B"].positions[r] == b0[r] for r in b0 if r not in b_rides)
    rig, mapping = identity_rig()
    rot0 = pose_dict_rotations(rig, mapping, figures["A"])
    rot1 = pose_dict_rotations(rig, mapping, coupled["A"])
    rot0_by = {r["bone"]: r for r in rot0["rotations"]}
    rot1_by = {r["bone"]: r for r in rot1["rotations"]}
    chain = {"upper_arm.R", "forearm.R", "upper_arm.L", "forearm.L"}
    nonchain_byte = all(rot0_by[b] == rot1_by[b] for b in rot0_by if b not in chain)
    chain_moved = any(rot0_by[b] != rot1_by[b] for b in chain)
    check("NONCHAIN", pos_same_a and torso_fixed and b_fixed and nonchain_byte and chain_moved,
          f"A non-chain positions byte-equal={pos_same_a} torso fixed={torso_fixed} "
          f"B anchored positions byte-equal={b_fixed} "
          f"non-chain rotations byte-equal={nonchain_byte} chain moved={chain_moved}")

    # CONFLICT — one hand, two targets (chest vs spine, 0.17 apart)
    conflict_pins = [
        {"figure_a": "A", "role_a": "hand.R", "figure_b": "B", "role_b": "chest",
         "origin": "authored", "confidence": 1.0},
        {"figure_a": "A", "role_a": "hand.R", "figure_b": "B", "role_b": "spine",
         "origin": "authored", "confidence": 1.0},
    ]
    c_coupled, c_rows = solve(figures, placements, conflict_pins)
    _, c_rows_again = solve(figures, placements, conflict_pins)
    twin = json.dumps([r["residual"] for r in c_rows]) == json.dumps([r["residual"] for r in c_rows_again])
    both_reported = all(r["residual"] >= 0.0 for r in c_rows)
    unclosable = [r for r in c_rows if not r["closed"]]
    improved = all(r["residual_frac"] < 1.0 for r in c_rows)
    finite = all(math.isfinite(p[0]) for lab in c_coupled for p in c_coupled[lab].positions.values())
    check("CONFLICT", twin and both_reported and len(unclosable) >= 1 and improved and finite,
          f"residuals {c_rows[0]['residual']:.4f}/{c_rows[1]['residual']:.4f} "
          f"unclosable {len(unclosable)} twin={twin}")

    # DETERM
    s1, r1 = solve(figures, placements, pins)
    s2, r2 = solve(figures, placements, pins)
    j1 = json.dumps({lab: p.to_dict() for lab, p in s1.items()}, sort_keys=True)
    j2 = json.dumps({lab: p.to_dict() for lab, p in s2.items()}, sort_keys=True)
    check("DETERM", j1 == j2 and json.dumps(r1) == json.dumps(r2), "twin solves byte-identical")

    # NOENFORCE — suggested + below-floor authored move nothing
    ne_pins = [
        {"figure_a": "A", "role_a": "hand.R", "figure_b": "B", "role_b": "chest",
         "origin": "suggested", "confidence": 0.9},
        {"figure_a": "A", "role_a": "hand.L", "figure_b": "B", "role_b": "spine",
         "origin": "authored", "confidence": 0.4},
    ]
    ne_coupled, ne_rows = solve(figures, placements, ne_pins)
    untouched = all(ne_coupled[lab].positions == figures[lab].positions for lab in figures)
    reasons_ok = ("suggested" in ne_rows[0]["reason"]
                  and str(ENFORCE_CONF_FLOOR) in ne_rows[1]["reason"])
    check("NOENFORCE", untouched and reasons_ok
          and not any(r["enforced"] for r in ne_rows),
          f"positions untouched={untouched} reasons reported={reasons_ok}")

    # REACH — target beyond the chain's reach: loud, no crash, chain straightens
    far = {"A": Placement(), "B": Placement(t=(0.0, -3.0, 0.0))}
    r_coupled, r_rows = solve(figures, far, pins[:1])
    hand_before = norm(sub(far["B"].place(b0["chest"]), far["A"].place(a0["hand.R"])))
    hand_after = r_rows[0]["residual"]
    check("REACH", (not r_rows[0]["closed"]) and hand_after < hand_before
          and all(math.isfinite(p[0]) for p in r_coupled["A"].positions.values()),
          f"residual {hand_after:.4f} < start {hand_before:.4f}, closed={r_rows[0]['closed']}")

    passed = all(OK)
    print(f"RM_COUPLE PROBE: {'OK' if passed else 'FAILED'} ({sum(OK)}/{len(OK)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
