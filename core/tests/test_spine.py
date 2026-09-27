"""P8-6 contract tests: the spine arch + arm roll (docs/SPINE.md, D-023).

The bars pinned here (Annex A.1 P8-6): the benchmark monotone distribution
+ the FK 0.5° family + D-008's 18/20 flip accept unchanged + the roll
fixture corrects to bar + straight arms BIT-IDENTICAL + the additive
roll namespace byte-identity (omit-when-empty, the hands/face contract).
"""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(__file__))

import pytest  # noqa: E402

from poses_fixtures import POSES, project_fixture  # noqa: E402
from riggermortis.canonical import PRIMARY_CHILD, rest_skeleton  # noqa: E402
from riggermortis.canonical_pose import TORSO_SPAN, CanonicalPose, solve_pose  # noqa: E402
from riggermortis.fk_apply import (  # noqa: E402
    apply_canonical_pose,
    verify_application,
)
from riggermortis.mapper import RigMapping, RoleAssignment  # noqa: E402
from riggermortis.spine import (  # noqa: E402
    ARCH_ENVELOPE_RAD,
    ARCH_MISALIGN_FLOOR_RAD,
    ROLL_ROLES,
    RollEntry,
    is_roll_role,
    roll_correction,
    solve_arm_roll,
    solve_spine_arch,
    validate_roll_map,
)
from riggermortis.types import BoneData, RigData  # noqa: E402

Vec3 = tuple[float, float, float]

_SCALE = 200.0
_CENTER = (500.0, 700.0)


# -- fixtures (the probe's engine-built recipes) --------------------------------------

def _proj_obs(positions: dict[str, Vec3], conf: float = 0.95) -> dict:
    obs: dict = {}

    def proj(p: Vec3) -> tuple[tuple[float, float], float]:
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


def model_curve_fixture(phi_deg: float) -> dict[str, Vec3]:
    """A torso authored ON the declared arch family (docs/SPINE.md A1)."""
    phi = math.radians(phi_deg)
    chord = TORSO_SPAN
    ndx, ndz = math.sin(phi), math.cos(phi)
    ga = phi * 2.0
    tx0, tz0 = chord * math.sin(ga), chord * math.cos(ga)
    tx1, tz1 = chord * ndx, chord * ndz
    t_spine, t_chest = 0.09 / chord, 0.26 / chord

    def hermite(t: float) -> tuple[float, float]:
        t2, t3 = t * t, t * t * t
        h10 = t3 - 2 * t2 + t
        h01, h11 = -2 * t3 + 3 * t2, t3 - t2
        return (h10 * tx0 + h11 * tx1, h01 * chord + h10 * tz0 + h11 * tz1)

    positions: dict[str, Vec3] = {
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


def bent_arm_positions() -> dict[str, Vec3]:
    """The roll fixture: LEFT arm bent in a non-trivial orientation."""
    from riggermortis.fk_apply import v_norm

    positions: dict[str, Vec3] = {
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


def identity_rig() -> tuple[RigData, RigMapping]:
    rest = rest_skeleton(1.0 / 0.55)
    rig = RigData(name="spine-test-rig")
    parent_of: dict[str, str | None] = {
        "spine": "hips", "chest": "spine", "neck": "chest", "head": "neck",
        "hips": None,
    }
    for base in ("upper_arm", "forearm", "hand"):
        parent = {"upper_arm": "shoulder", "forearm": "upper_arm", "hand": "forearm"}[base]
        for side in ("L", "R"):
            parent_of[f"{base}.{side}"] = f"{parent}.{side}"
    for side in ("L", "R"):
        parent_of[f"shoulder.{side}"] = "chest"
        parent_of[f"upper_leg.{side}"] = "hips"
        parent_of[f"lower_leg.{side}"] = f"upper_leg.{side}"
        parent_of[f"foot.{side}"] = f"lower_leg.{side}"
    for role, (head, _tail) in sorted(rest.items()):
        child = PRIMARY_CHILD.get(role)
        if child is None:
            continue
        rig.bones[role] = BoneData(
            name=role, head=head, tail=rest[child][0], parent=parent_of.get(role)
        )
    mapping = RigMapping(rig_name=rig.name, fingerprint=rig.fingerprint())
    for role in sorted(rig.bones):
        side = role.rpartition(".")[2] or "C"
        mapping.assignments[role] = RoleAssignment(
            role=role, bone=role, confidence=1.0, side=side
        )
    return rig, mapping


def chord_deviation(positions: dict[str, Vec3], role: str) -> float:
    hx, _hy, hz = positions["hips"]
    nx, _ny, nz = positions["neck"]
    cx, cz = nx - hx, nz - hz
    ln = math.hypot(cx, cz)
    px, _py, pz = positions[role]
    return ((px - hx) * cz - (pz - hz) * cx) / ln


# -- the arch: benchmark bars ----------------------------------------------------------

@pytest.mark.parametrize("name,deg", [("neutral", 0.0), ("bow_L", 18.0), ("bow_R", -18.0), ("arched", 30.0)])
def test_arch_benchmark_class(name: str, deg: float) -> None:
    gt = model_curve_fixture(deg)
    flat = solve_pose(_proj_obs(gt))
    arch, rep = solve_spine_arch(flat)
    assert rep.applied == (deg != 0.0), rep.reason
    if deg == 0.0:
        assert "below the 5 deg floor" in rep.reason
        assert arch.to_dict() == flat.to_dict()  # the flat byte no-op
        return
    assert rep.misalign_deg is not None
    assert abs(rep.misalign_deg - deg) < 0.5  # the observable recovered
    # declared-family recovery: the chain inverts to the authored curve
    for role in ("spine", "chest"):
        assert math.dist(arch.positions[role], gt[role]) <= 0.002


def test_arch_benchmark_monotone_distribution() -> None:
    devs = {}
    for name, deg in (("neutral", 0.0), ("bow_L", 18.0), ("arched", 30.0)):
        arch, _rep = solve_spine_arch(solve_pose(_proj_obs(model_curve_fixture(deg))))
        devs[name] = abs(chord_deviation(arch.positions, "chest"))
    assert devs["neutral"] == 0.0
    assert devs["bow_L"] < devs["arched"]  # strictly monotone


def test_arch_benchmark_signs() -> None:
    left, _ = solve_spine_arch(solve_pose(_proj_obs(model_curve_fixture(18.0))))
    right, _ = solve_spine_arch(solve_pose(_proj_obs(model_curve_fixture(-18.0))))
    assert chord_deviation(left.positions, "chest") > 0.0
    assert chord_deviation(right.positions, "chest") < 0.0


def test_arch_does_not_disturb_other_roles() -> None:
    flat = solve_pose(_proj_obs(model_curve_fixture(30.0)))
    arch, _rep = solve_spine_arch(flat)
    for role, p in flat.positions.items():
        if role not in ("spine", "chest"):
            assert arch.positions[role] == p
    assert all(p[1] == 0.0 for r, p in arch.positions.items() if r in ("spine", "chest"))


# -- the arch: guards, honesty, round-trip ---------------------------------------------

def test_arch_guards_report_verbatim_and_change_nothing() -> None:
    pose = solve_pose(_proj_obs(model_curve_fixture(30.0)))
    # head unobserved: drop the head confidence -> skip, no bytes changed
    starved = replace(pose, joint_confidence={**pose.joint_confidence, "head": 0.3})
    out, rep = solve_spine_arch(starved)
    assert not rep.applied and "below floor" in rep.reason
    assert out.to_dict() == starved.to_dict()
    # envelope breach: a nose 70 deg past the chord is out of the class
    extreme = _proj_obs(model_curve_fixture(70.0))
    out2, rep2 = solve_spine_arch(solve_pose(extreme))
    assert not rep2.applied and "envelope" in rep2.reason
    assert "not representable" in rep2.reason
    assert abs(rep2.misalign_deg) > math.degrees(ARCH_ENVELOPE_RAD) - 1e-6
    assert out2.to_dict() == solve_pose(extreme).to_dict()


def test_arch_below_floor_is_flat_byte_identical() -> None:
    pose = solve_pose(_proj_obs(model_curve_fixture(2.0)))  # under the 5 deg floor
    out, rep = solve_spine_arch(pose)
    assert not rep.applied
    assert "flat" in rep.reason
    assert out.to_dict() == pose.to_dict()
    assert abs(math.degrees(ARCH_MISALIGN_FLOOR_RAD) - 5.0) < 1e-9


def test_arch_round_trip_through_payload_matches_in_process() -> None:
    pose = solve_pose(_proj_obs(model_curve_fixture(30.0)))
    arch_fresh, rep_fresh = solve_spine_arch(pose)
    rt = CanonicalPose.from_dict(json.loads(json.dumps(pose.to_dict())))
    arch_rt, rep_rt = solve_spine_arch(rt)
    assert arch_rt.to_dict() == arch_fresh.to_dict()
    assert rep_rt.applied and rep_rt.misalign_deg == rep_fresh.misalign_deg


def test_arch_mirror_composes() -> None:
    pose = solve_pose(_proj_obs(model_curve_fixture(18.0)))
    arch, _rep = solve_spine_arch(pose)
    # mirroring an arch-applied pose == arching the mirrored pose (the arch
    # is x-symmetric math over positions; the applied arch NOTE carries the
    # sign, so positions/flips are the compared contract here)
    a = arch.mirrored()
    b, rep_b = solve_spine_arch(pose.mirrored())
    assert rep_b.applied
    assert a.positions == b.positions
    assert a.flips == b.flips


# -- the roll: namespace + bars ----------------------------------------------------------

def test_roll_namespace_omit_when_empty_byte_identity() -> None:
    pose = solve_pose(_proj_obs(model_curve_fixture(30.0)))
    assert pose.roll == {}
    d = pose.to_dict()
    assert "roll" not in d  # omitted when empty — the D-023 contract
    bare = CanonicalPose.from_dict(json.loads(json.dumps(d)))
    assert bare.roll == {}
    assert bare.to_dict() == d


def test_roll_bent_arm_entries_and_straight_arm_noop() -> None:
    bent = solve_pose(_proj_obs(bent_arm_positions()))
    applied, rep = solve_arm_roll(bent)
    assert set(rep.entries) == {"forearm.L"}  # R is straight -> no entry
    entry = rep.entries["forearm.L"]
    assert abs(entry.twist_rad) > math.radians(5.0)  # the artifact, made numeric
    assert entry.confidence <= 0.75  # the geometry-only cap
    assert applied.roll["forearm.L"].twist_rad == entry.twist_rad
    assert any("twist" in r for r in applied.notes)
    # the straight side reports verbatim, changes nothing
    assert any("below the 15 deg floor" in r for r in rep.rows)
    # a STRAIGHT-arm fixture produces NO entries and NO bytes change
    # (t_pose: distal continues proximal exactly — bend 0.0 deg)
    straight = solve_pose(project_fixture(POSES[0]))
    out, rep2 = solve_arm_roll(straight)
    assert rep2.entries == {}
    assert out.to_dict() == straight.to_dict()


def test_roll_correction_closed_form_sign() -> None:
    from riggermortis.canonical import CANONICAL
    from riggermortis.fk_apply import (
        q_conj,
        q_from_to,
        q_mul,
        q_rotate,
        v_norm,
    )

    pos = bent_arm_positions()
    u = v_norm(tuple(pos["forearm.L"][i] - pos["upper_arm.L"][i] for i in range(3)))
    f = v_norm(tuple(pos["hand.L"][i] - pos["forearm.L"][i] for i in range(3)))
    rho = roll_correction(u, f, CANONICAL["upper_arm.L"].direction, CANONICAL["forearm.L"].direction)
    # the corrected frame EQUALS the frame-continuous chain (the declared
    # convention the fixture embodies): the twist residual vanishes
    q_u = q_from_to(CANONICAL["upper_arm.L"].direction, u)
    q_f = q_from_to(CANONICAL["forearm.L"].direction, f)
    hinge = q_from_to(CANONICAL["forearm.L"].direction, q_rotate(q_conj(q_u), f))
    q_c = q_mul(q_u, hinge)
    corrected = q_mul(_twist(f, rho), q_f)
    hinge_axis = q_rotate(corrected, (0.0, 0.0, -1.0))
    expected_axis = q_rotate(q_c, (0.0, 0.0, -1.0))
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(hinge_axis, expected_axis, strict=True))))
    assert math.degrees(math.acos(dot)) <= 0.5


def _twist(axis: Vec3, angle: float) -> tuple[float, float, float, float]:
    from riggermortis.fk_apply import q_from_axis_angle

    return q_from_axis_angle(axis, angle)


def test_roll_fk_apply_directions_exact_and_entries_only() -> None:
    rig, mapping = identity_rig()
    bent = solve_pose(_proj_obs(bent_arm_positions()))
    applied, _rep = solve_arm_roll(bent)
    # with entries: direction errors stay in the 0.5 deg family
    app = apply_canonical_pose(rig, mapping, applied)
    errs = verify_application(rig, app, applied)
    assert max(errs.values()) <= math.radians(0.5)
    # the ENTRY role's rotation differs from the minimal path; all others
    # are byte-equal
    plain = apply_canonical_pose(rig, mapping, bent)
    plain_by_bone = {r.bone: r for r in plain.rotations}
    diff_bones = {r.bone for r in app.rotations
                  if r.bone in plain_by_bone
                  and (r.axis, r.angle_rad) != (plain_by_bone[r.bone].axis, plain_by_bone[r.bone].angle_rad)}
    assert diff_bones == {"forearm.L"}
    # straight pose: NO entries -> apply rotations byte-equal (the no-op proof)
    straight = solve_pose(project_fixture(POSES[0]))
    a = apply_canonical_pose(rig, mapping, straight)
    out, _rep2 = solve_arm_roll(straight)
    b = apply_canonical_pose(rig, mapping, out)
    assert a.to_dict() == b.to_dict()


def test_roll_namespace_validation_and_mirror() -> None:
    with pytest.raises(ValueError, match="roll key"):
        validate_roll_map({"hips": RollEntry(0.0, 1.0)})
    assert is_roll_role("forearm.L") and is_roll_role("upper_arm.R")
    assert not is_roll_role("hips")
    # the D-023 keys are exactly the declared set
    assert ROLL_ROLES == ("forearm.L", "forearm.R")
    # mirrored: sides swap, twist negates; solve(mirror) == mirror(solve)
    bent = solve_pose(_proj_obs(bent_arm_positions()))
    applied, _ = solve_arm_roll(bent)
    mirrored = applied.mirrored()
    assert set(mirrored.roll) == {"forearm.R"}
    assert mirrored.roll["forearm.R"].twist_rad == -applied.roll["forearm.L"].twist_rad
    solved_mirrored, rep_m = solve_arm_roll(bent.mirrored())
    assert rep_m.entries["forearm.R"].twist_rad == pytest.approx(
        mirrored.roll["forearm.R"].twist_rad, abs=1e-9
    )


def test_roll_round_trip_through_payload() -> None:
    bent = solve_pose(_proj_obs(bent_arm_positions()))
    applied, _ = solve_arm_roll(bent)
    rt = CanonicalPose.from_dict(json.loads(json.dumps(applied.to_dict())))
    assert set(rt.roll) == {"forearm.L"}
    assert rt.roll["forearm.L"].to_dict() == applied.roll["forearm.L"].to_dict()
    d = rt.to_dict()
    assert "roll" in d
    assert d["roll"] == {"forearm.L": applied.roll["forearm.L"].to_dict()}


# -- D-008's 18/20 flip accept unchanged through the passes ------------------------------

def test_flip_accept_18_of_20_unchanged_through_arch_and_roll() -> None:
    accept = 0
    for fx in POSES:
        plain = solve_pose(project_fixture(fx))
        arch, _rep = solve_spine_arch(plain)
        rolled, _roll_rep = solve_arm_roll(arch)
        assert rolled.flips == plain.flips  # byte-equal through both passes
        wrong = [
            limb
            for limb, gt in fx.gt_flips.items()
            if gt is not None and rolled.flips[limb] != gt
        ]
        if not wrong:
            accept += 1
    assert accept >= 18


# -- determinism -------------------------------------------------------------------------

def test_twin_solves_byte_identical() -> None:
    pose_a = solve_pose(_proj_obs(model_curve_fixture(30.0)))
    arch_a, rep_a = solve_spine_arch(pose_a)
    roll_a, _ = solve_arm_roll(arch_a)
    pose_b = solve_pose(_proj_obs(model_curve_fixture(30.0)))
    arch_b, rep_b = solve_spine_arch(pose_b)
    roll_b, _ = solve_arm_roll(arch_b)
    assert arch_a.to_dict() == arch_b.to_dict()
    assert roll_a.to_dict() == roll_b.to_dict()
    assert rep_a == rep_b
