"""P1-4 tests: canonical pose solve (pure stdlib — runs everywhere)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from poses_fixtures import POSES, PoseFixture, project_fixture  # noqa: E402
from riggermortis.canonical import mirror_role  # noqa: E402
from riggermortis.canonical_pose import (  # noqa: E402
    CanonicalPose,
    observations_from_keypoints,
    solve_pose,
)

# -- observation mapping ---------------------------------------------------------


def test_observations_reject_wrong_count() -> None:
    with pytest.raises(ValueError, match="133"):
        observations_from_keypoints([(0.0, 0.0)] * 5, [0.5] * 5)


def test_observations_midpoints_take_min_conf() -> None:
    kps = [(0.0, 0.0)] * 133
    conf = [0.0] * 133
    kps[5], conf[5] = (10.0, 10.0), 0.9  # shoulder.L -> upper_arm.L
    kps[6], conf[6] = (30.0, 10.0), 0.5
    kps[11], conf[11] = (20.0, 100.0), 0.8
    kps[12], conf[12] = (20.0, 120.0), 0.1
    kps[7], conf[7] = (5.0, 50.0), 0.7  # elbow.L -> forearm.L
    obs = observations_from_keypoints(kps, conf)
    assert obs["neck"] == ((20.0, 10.0), 0.5)
    assert obs["hips"] == ((20.0, 110.0), 0.1)
    assert obs["upper_arm.L"] == ((10.0, 10.0), 0.9)
    assert obs["forearm.L"] == ((5.0, 50.0), 0.7)
    assert "hand.L" not in obs  # wrist keypoint not set in this probe
    assert "toe.L" not in obs  # toes need both sources usable


# -- the 20-pose flip accept (>= 18/20) ---------------------------------------------


def _solve_fixture(fx: PoseFixture) -> CanonicalPose:
    return solve_pose(project_fixture(fx))


def test_flip_accept_20_poses() -> None:
    results = []
    for fx in POSES:
        pose = _solve_fixture(fx)
        wrong = [
            limb
            for limb, gt in fx.gt_flips.items()
            if gt is not None and pose.flips[limb] != gt
        ]
        results.append((fx.name, sorted(wrong)))
    solved = [name for name, wrong in results if not wrong]
    failed = [f"{name}: {wrong}" for name, wrong in results if wrong]
    assert len(solved) >= 18, f"flip accept failed ({len(solved)}/20): {failed}"


def test_flip_report_is_honest_per_pose() -> None:
    """Every pose reports its per-pose outcome so failures are visible."""
    for fx in POSES:
        pose = _solve_fixture(fx)
        wrong = [limb for limb, gt in fx.gt_flips.items() if gt is not None and pose.flips[limb] != gt]
        print(f"{fx.name}: flips={pose.flips} wrong={wrong} conf={pose.confidence}")


def test_known_easy_poses_solve_cleanly() -> None:
    by_name = {fx.name: fx for fx in POSES}
    for name in ("arms_down_relaxed", "kneel", "reach_forward", "crouch"):
        pose = _solve_fixture(by_name[name])
        for limb, gt in by_name[name].gt_flips.items():
            if gt is not None:
                assert pose.flips[limb] == gt, f"{name}/{limb}: {pose.flips} vs gt {gt}"


# -- solver properties ---------------------------------------------------------------


def test_solver_determinism() -> None:
    fx = POSES[3]  # arms_crossed
    a = _solve_fixture(fx).to_dict()
    b = _solve_fixture(fx).to_dict()
    assert a == b


def test_mirror_symmetry() -> None:
    """Mirroring the world (x -> -x, roles keep identity) mirrors positions
    exactly and leaves every depth decision unchanged."""
    fx = next(p for p in POSES if p.name == "wave_right")
    obs = project_fixture(fx, scale=200.0, center=(500.0, 700.0))

    def mirror(o: dict) -> dict:
        return {role: ((1000.0 - u, v), c) for role, ((u, v), c) in o.items()}

    a = _solve_fixture(fx).to_dict()
    b = solve_pose(mirror(obs)).to_dict()
    for role, pos in a["positions"].items():
        assert b["positions"][role][0] == pytest.approx(-pos[0], abs=1e-6), role
        assert b["positions"][role][2] == pytest.approx(pos[2], abs=1e-6), role
        assert b["positions"][role][1] == pytest.approx(pos[1], abs=1e-6), role
    assert b["flips"] == a["flips"]


def test_positions_recover_ground_truth() -> None:
    """Observed roles land within projection tolerance of the fixture GT."""
    fx = next(p for p in POSES if p.name == "arms_down_relaxed")
    pose = _solve_fixture(fx)
    scale = 200.0
    for role in ("upper_arm.L", "forearm.R", "lower_leg.L", "foot.R", "hips", "neck"):
        gx, gy, gz = fx.positions[role]
        px, py, pz = pose.positions[role]
        assert px == pytest.approx(gx, abs=2.5 / scale), f"{role} x"
        assert pz == pytest.approx(gz, abs=2.5 / scale), f"{role} z"
        # Depth is prior-driven, not observed: only bound it plausibly.
        assert abs(py - gy) < 0.75, f"{role} y"


def test_degenerate_low_confidence_reports_not_crashes() -> None:
    kps = [(100.0, 100.0)] * 133
    conf = [0.01] * 133
    obs = observations_from_keypoints(kps, conf)
    pose = solve_pose(obs)
    assert pose.reliable is False
    assert pose.confidence == 0.0
    assert "rest-pose fallback" in " ".join(pose.notes)


def test_partial_observations_degrade_gracefully() -> None:
    """Only torso + legs visible (arms out of frame): still solves legs."""
    fx = next(p for p in POSES if p.name == "kneel")
    obs = project_fixture(fx)
    legs_only = {
        r: o for r, o in obs.items()
        if r in ("hips", "neck", "upper_leg.L", "upper_leg.R", "lower_leg.L", "lower_leg.R", "foot.L", "foot.R")
    }
    pose = solve_pose(legs_only)
    for limb in ("forearm.L", "forearm.R"):
        assert pose.flips[limb] == -1  # unobserved: forward default, conf 0
        assert pose.joint_confidence[limb] == 0.0
    assert pose.flips["lower_leg.L"] == 1  # kneel shanks point backward
    assert pose.flips["lower_leg.R"] == 1


# -- flip materiality (D-010): straight limbs auto-pass, ambiguity stays review ------


def _arm_obs(hand: tuple[float, float], forearm: tuple[float, float], conf: float = 0.9) -> dict:
    """Minimal observation set: torso anchors + a left arm chain with given geometry.

    Scale is 1000 px/canonical-unit (neck->hips span 450 px = 0.45 units), so the
    forearm's canonical distal length is 280 px.
    """
    return {
        "neck": ((0.0, 0.0), 0.9),
        "hips": ((0.0, 450.0), 0.9),
        "upper_arm.L": ((-60.0, 100.0), conf),
        "forearm.L": (forearm, conf),
        "hand.L": (hand, conf),
    }


def test_straight_limb_flip_is_immaterial_not_uncertain() -> None:
    """A dead-straight arm renders identically under both flips -> auto-pass (D-010)."""
    pose = solve_pose(_arm_obs(forearm=(-100.0, 350.0), hand=(-102.0, 660.0)))
    assert pose.joint_confidence["forearm.L"] == 1.0
    assert any("immaterial" in n for n in pose.notes)


def test_bent_flip_resolves_confidently_and_never_masquerades_immaterial() -> None:
    """Bent limbs with observed distals resolve via the priors (margin is a ratio,
    so it is evidence-confidence independent): conf stays >= review bar and the
    immaterial note is reserved for straight limbs (D-010)."""
    # Forearm chord ~150 px (clearly bent vs 280 px bone), weak observation conf.
    pose = solve_pose(_arm_obs(forearm=(-100.0, 350.0), hand=(-230.0, 430.0), conf=0.3))
    assert pose.joint_confidence["forearm.L"] >= 0.55
    assert not any(n.startswith("forearm.L") and "immaterial" in n for n in pose.notes)
    # Strong evidence: same confident resolution.
    pose2 = solve_pose(_arm_obs(forearm=(-100.0, 350.0), hand=(-220.0, 420.0)))
    assert pose2.joint_confidence["forearm.L"] >= 0.55
    assert pose2.flips["forearm.L"] == pose.flips["forearm.L"]


def test_confidence_is_bounded_and_honest() -> None:
    for fx in POSES[:5]:
        pose = _solve_fixture(fx)
        assert 0.0 <= pose.confidence <= 1.0
        assert isinstance(pose.reliable, bool)
        if fx.name != "t_pose":  # t-pose has no usable flip evidence
            assert pose.confidence > 0.3


def test_scale_recovers_projection_scale() -> None:
    fx = POSES[0]
    obs = project_fixture(fx, scale=333.0, center=(250.0, 900.0))
    pose = solve_pose(obs)
    assert pose.scale == pytest.approx(333.0, rel=0.02)


# -- payload round-trip + mirror (P1-6 / D-009) ---------------------------------------


def test_from_dict_round_trips_to_dict() -> None:
    fx = next(p for p in POSES if p.name == "arms_down_relaxed")
    pose = _solve_fixture(fx)
    rt = CanonicalPose.from_dict(pose.to_dict())
    assert rt.positions == pose.positions
    assert rt.flips == pose.flips
    assert rt.confidence == pose.confidence
    assert rt.reliable == pose.reliable
    assert rt.scale == pose.scale
    assert rt.anchor == pose.anchor
    assert rt.notes == pose.notes
    assert rt.joint_confidence == pose.joint_confidence


def test_mirrored_swaps_sides_and_negates_x() -> None:
    fx = next(p for p in POSES if p.name == "arms_down_relaxed")
    pose = _solve_fixture(fx)
    mirror = pose.mirrored()

    assert set(mirror.positions) == set(pose.positions)
    for role, pos in pose.positions.items():
        mx, my, mz = mirror.positions[mirror_role(role)]
        assert mx == pytest.approx(-pos[0])
        assert (my, mz) == (pos[1], pos[2])
    assert mirror.positions["upper_arm.L"][0] == pytest.approx(-pose.positions["upper_arm.R"][0])
    assert mirror.positions["upper_arm.R"][0] == pytest.approx(-pose.positions["upper_arm.L"][0])

    # Flip values move with their side key; depth semantics are unchanged.
    assert mirror.flips["forearm.L"] == pose.flips["forearm.R"]
    assert mirror.flips["forearm.R"] == pose.flips["forearm.L"]
    assert mirror.flips["lower_leg.L"] == pose.flips["lower_leg.R"]
    assert mirror.joint_confidence["forearm.L"] == pose.joint_confidence["forearm.R"]
    assert mirror.confidence == pose.confidence and mirror.notes == pose.notes

    # Involution: mirroring twice restores the original.
    twice = mirror.mirrored()
    assert twice.positions == pose.positions and twice.flips == pose.flips


def test_mirrored_pose_applies_within_tolerance() -> None:
    """The add-on mirror toggle path: mirrored pose still satisfies FK."""
    from riggermortis.canonical import ALL_ROLES, CANONICAL, rest_skeleton
    from riggermortis.fk_apply import apply_canonical_pose, verify_application
    from riggermortis.mapper import RigMapping, RoleAssignment
    from riggermortis.types import BoneData, RigData

    skeleton = rest_skeleton(1.7)
    bones = {
        role: BoneData(role, head, tail, CANONICAL[role].parent)
        for role, (head, tail) in sorted(skeleton.items())
    }
    rig = RigData(name="canonical_rest", bones=bones, source="synthetic")
    mapping = RigMapping(
        rig_name=rig.name,
        fingerprint=rig.fingerprint(),
        assignments={
            role: RoleAssignment(role=role, bone=role, confidence=1.0, side="C")
            for role in ALL_ROLES
            if role in rig.bones
        },
    )
    fx = next(p for p in POSES if p.name == "reach_forward")
    pose = _solve_fixture(fx)
    mirrored = pose.mirrored()
    app = apply_canonical_pose(rig, mapping, mirrored)
    errors = verify_application(rig, app, mirrored)
    assert errors and max(errors.values()) <= 1e-6


# -- review overlay data model (P1-7) ------------------------------------------------


def test_review_items_flag_low_flip_margins_and_weak_joints() -> None:
    from riggermortis.review import review_items

    fx = next(p for p in POSES if p.name == "arms_down_relaxed")
    pose = _solve_fixture(fx)
    # Pin every confidence high except the two we want flagged, so the test
    # asserts exactly what it forces (not fixture-specific solver margins).
    pose.joint_confidence = {k: 0.95 for k in pose.joint_confidence}
    pose.joint_confidence["forearm.L"] = 0.1
    pose.joint_confidence["upper_arm.L"] = 0.3
    pose.notes = ["hips unobserved; anchored at neck"]
    items = review_items(pose)

    flips = [i for i in items if i.kind == "flip"]
    confs = [i for i in items if i.kind == "confidence"]
    notes = [i for i in items if i.kind == "note"]
    assert [i.role for i in flips] == ["forearm.L"]
    assert {i.role for i in confs} == {"upper_arm.L"}
    assert len(notes) == 1
    # Severity sort: the weakest item first; notes sink to the end.
    assert items[0].kind == "flip"
    assert items[-1].kind == "note"
    assert all(i.to_dict()["severity"] is not None for i in items)


def test_review_items_empty_for_clean_strong_pose() -> None:
    from riggermortis.review import review_items

    fx = next(p for p in POSES if p.name == "arms_down_relaxed")
    pose = _solve_fixture(fx)
    pose.joint_confidence = {k: 0.9 for k in pose.joint_confidence}
    pose.notes = []
    assert review_items(pose) == []


def test_skeleton_segments_follow_fk_chains_and_are_deterministic() -> None:
    from riggermortis.review import skeleton_segments

    fx = next(p for p in POSES if p.name == "arms_down_relaxed")
    pose = _solve_fixture(fx)
    segments = skeleton_segments(pose)
    assert segments == skeleton_segments(pose)  # deterministic
    assert ("hips", "spine") in segments
    assert ("upper_arm.L", "forearm.L") in segments
    assert ("lower_leg.R", "foot.R") in segments
    # Parents come from the FK chain map only — no invented segments.
    for parent, child in segments:
        assert child.endswith((".L", ".R")) or parent in ("hips", "spine", "chest", "neck")


# -- review interactivity (P1-11 / D-008 rescue): toggle + pick -----------------------


def test_toggled_flip_moves_distal_joint_and_marks_verified() -> None:
    from riggermortis.review import review_items

    fx = next(p for p in POSES if p.name == "kneel")  # shanks clearly bent backward
    pose = _solve_fixture(fx)
    y_knee = pose.positions["lower_leg.L"][1]
    y_foot = pose.positions["foot.L"][1]
    assert y_foot != y_knee

    toggled = pose.toggled("lower_leg.L")
    assert toggled is not pose
    assert toggled.positions["foot.L"][1] == pytest.approx(2 * y_knee - y_foot)
    assert toggled.flips["lower_leg.L"] == -pose.flips["lower_leg.L"]
    assert toggled.joint_confidence["lower_leg.L"] == 1.0  # human-verified
    assert any("manually toggled" in n for n in toggled.notes)
    assert "lower_leg.L" not in [i.role for i in review_items(toggled)
                                 if i.kind == "flip"]
    # untouched roles stay put; the original pose is never mutated
    assert pose.positions["foot.L"][1] == y_foot
    assert toggled.positions["hips"] == pose.positions["hips"]
    # toe rides the foot rigidly when present
    if "toe.L" in pose.positions and "toe.L" in toggled.positions:
        assert toggled.positions["toe.L"][1] == pytest.approx(
            pose.positions["toe.L"][1] + (toggled.positions["foot.L"][1] - y_foot)
        )


def test_toggled_is_idempotent_and_mirror_safe() -> None:
    fx = next(p for p in POSES if p.name == "kneel")
    pose = _solve_fixture(fx)
    once = pose.toggled("lower_leg.L")
    twice = once.toggled("lower_leg.L")
    assert twice.positions.keys() == pose.positions.keys()
    for role in pose.positions:
        assert twice.positions[role] == pytest.approx(pose.positions[role], abs=1e-9), role
    assert twice.flips["lower_leg.L"] == pose.flips["lower_leg.L"]
    # mirror never touches y, so toggling commutes with mirroring — but the
    # key mirrors with the limb: toggling lower_leg.L pre-mirror == toggling
    # lower_leg.R post-mirror.
    a = pose.toggled("lower_leg.L").mirrored()
    b = pose.mirrored().toggled("lower_leg.R")
    assert a.positions["foot.R"] == pytest.approx(b.positions["foot.R"])
    # unknown key / distal absent from the pose: harmless no-op
    assert pose.toggled("nope.X") is pose
    import dataclasses

    no_hands = dataclasses.replace(
        pose, positions={r: p for r, p in pose.positions.items() if r != "hand.L"}
    )
    assert no_hands.toggled("forearm.L") is no_hands


def test_pick_joint_ray_cast_and_determinism() -> None:
    from riggermortis.review import joint_points, pick_joint

    fx = next(p for p in POSES if p.name == "arms_down_relaxed")
    pose = _solve_fixture(fx)
    origin = (0.0, 0.0, 0.0)
    scale = 2.0
    points = joint_points(pose, origin=origin, scale=scale)

    target = "hand.L" if "hand.L" in points else "forearm.L"
    p = points[target]
    # camera at +y looking down -y straight at the joint
    role = pick_joint(points, (p[0], p[1] + 10.0, p[2]), (0.0, -1.0, 0.0), radius=0.5)
    assert role == target

    # a ray passing between two joints picks the closer one, deterministically
    a, b = points["hips"], points["neck"]
    mid = tuple((a[i] + b[i]) / 2 for i in range(3))
    role_mid = pick_joint(points, (mid[0], mid[1] + 5.0, mid[2]), (0.0, -1.0, 0.0), radius=1.0)
    assert role_mid in ("hips", "neck", "spine", "chest", "upper_leg.L", "upper_leg.R")
    assert pick_joint(points, (mid[0], mid[1] + 5.0, mid[2]), (0.0, -1.0, 0.0), radius=1.0) == role_mid

    # miss -> None; everything behind the camera -> None; zero radius/direction -> None
    assert pick_joint(points, (p[0] + 100.0, p[1] + 10.0, p[2]), (0.0, -1.0, 0.0), radius=0.5) is None
    below_all = (0.0, min(pt[1] for pt in points.values()) - 50.0, 0.0)
    assert pick_joint(points, below_all, (0.0, -1.0, 0.0), radius=0.5) is None
    assert pick_joint(points, (p[0], p[1] + 1.0, p[2]), (0.0, -1.0, 0.0), radius=0.0) is None
    assert pick_joint(points, (p[0], p[1] + 1.0, p[2]), (0.0, 0.0, 0.0), radius=0.5) is None
