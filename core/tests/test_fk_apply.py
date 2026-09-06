"""P1-5 tests: FK apply engine (pure stdlib — runs everywhere).

The 3-rig accept runs against the real extracted rigs in ``out/real_rigs``
(git-ignored); if they are absent the test skips with the regeneration
command. The canonical-rest synthetic rig always runs and doubles as the
T-pose passthrough (identity) test.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from poses_fixtures import POSES  # noqa: E402
from riggermortis.canonical import ALL_ROLES, CANONICAL, rest_skeleton  # noqa: E402
from riggermortis.canonical_pose import CanonicalPose  # noqa: E402
from riggermortis.fk_apply import (  # noqa: E402
    apply_canonical_pose,
    q_from_to,
    q_rotate,
    q_to_axis_angle,
    verify_application,
)
from riggermortis.mapper import RigMapping, RoleAssignment  # noqa: E402
from riggermortis.types import BoneData, RigData  # noqa: E402

ANGLE_TOL_RAD = math.radians(0.5)  # stated tolerance: 0.5 degrees

#: Roles every core-complete rig must rotate for any full-body pose.
MUST_APPLY = frozenset(
    ["hips", "spine", "chest", "neck"]
    + [f"{b}.{s}" for b in ("upper_arm", "forearm", "upper_leg", "lower_leg") for s in "LR"]
)


def _identity_mapping(rig: RigData) -> RigMapping:
    """Map every canonical-named bone to its role (synthetic rest rig)."""
    assignments = {
        role: RoleAssignment(role=role, bone=role, confidence=1.0, side="C")
        for role in ALL_ROLES
        if role in rig.bones
    }
    return RigMapping(rig_name=rig.name, fingerprint=rig.fingerprint(), assignments=assignments)


def _canonical_rest_rig() -> RigData:
    """A rig whose rest pose IS the canonical rest skeleton (identity case)."""
    rest = rest_skeleton(1.7)
    bones = {}
    for role, (head, tail) in sorted(rest.items()):
        bones[role] = BoneData(
            name=role, head=head, tail=tail, parent=CANONICAL[role].parent
        )
    return RigData(name="canonical_rest", bones=bones, source="synthetic")


def _pose_from_fixture_positions(positions: dict) -> CanonicalPose:
    return CanonicalPose(
        positions=dict(positions),
        flips={},
        confidence=0.9,
        reliable=True,
        scale=200.0,
        anchor="hips",
    )


# -- quaternion math ---------------------------------------------------------------


def test_q_from_to_known_pairs() -> None:
    q = q_from_to((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    axis, angle = q_to_axis_angle(q)
    assert axis == pytest.approx((0.0, -1.0, 0.0), abs=1e-9)
    assert angle == pytest.approx(math.pi / 2.0, abs=1e-9)
    assert q_rotate(q, (1.0, 0.0, 0.0)) == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)


def test_q_from_to_antiparallel_deterministic() -> None:
    q = q_from_to((0.0, 0.0, 1.0), (0.0, 0.0, -1.0))
    assert q_rotate(q, (0.0, 0.0, 1.0)) == pytest.approx((0.0, 0.0, -1.0), abs=1e-9)
    q2 = q_from_to((0.0, 0.0, 1.0), (0.0, 0.0, -1.0))
    assert q == q2  # deterministic axis pick


def test_q_from_to_parallel_is_identity() -> None:
    assert q_from_to((0.0, 1.0, 0.0), (0.0, 1.0, 0.0)) == (1.0, 0.0, 0.0, 0.0)


# -- engine ------------------------------------------------------------------------


def test_tpose_passthrough_is_identity() -> None:
    rig = _canonical_rest_rig()
    mapping = _identity_mapping(rig)
    rest = rest_skeleton(1.7)
    pose = _pose_from_fixture_positions({r: v[0] for r, v in rest.items()})
    app = apply_canonical_pose(rig, mapping, pose)
    assert app.rotations, "rest rig must still produce rotations"
    for rot in app.rotations:
        assert rot.angle_rad == pytest.approx(0.0, abs=1e-9), rot.bone
    errors = verify_application(rig, app, pose)
    assert all(e <= 1e-9 for e in errors.values())


def test_known_rest_target_rotation() -> None:
    rig = RigData(
        name="one_bone",
        bones={"upper_arm.L": BoneData("upper_arm.L", (0, 0, 0), (1, 0, 0), None)},
    )
    mapping = _identity_mapping(rig)
    pose = _pose_from_fixture_positions(
        {"upper_arm.L": (0, 0, 0), "forearm.L": (0, 0, 1)}
    )
    app = apply_canonical_pose(rig, mapping, pose)
    assert len(app.rotations) == 1
    rot = app.rotations[0]
    assert rot.axis == pytest.approx((0.0, -1.0, 0.0), abs=1e-9)
    assert rot.angle_rad == pytest.approx(math.pi / 2.0, abs=1e-9)


def test_parent_space_composition() -> None:
    """Child local rotation must compensate the parent's applied rotation."""
    # Parent: +X -> +Y (90 deg about Z). Child rest +X must land on +Z.
    rig = RigData(
        name="chain",
        bones={
            "parent": BoneData("parent", (0, 0, 0), (1, 0, 0), None),
            "child": BoneData("child", (1, 0, 0), (2, 0, 0), "parent"),
        },
    )
    # Fake roles: 'spine' -> parent, 'chest' -> child; targets from pose.
    mapping = RigMapping(
        rig_name="chain",
        fingerprint=rig.fingerprint(),
        assignments={
            "spine": RoleAssignment("spine", "parent", 1.0, "C"),
            "chest": RoleAssignment("chest", "child", 1.0, "C"),
        },
    )
    pose = _pose_from_fixture_positions(
        {"spine": (0, 0, 0), "chest": (0, 1, 0), "neck": (0, 1, 1), "head": (0, 1, 2)}
    )
    app = apply_canonical_pose(rig, mapping, pose)
    errors = verify_application(rig, app, pose)
    assert errors["spine"] <= 1e-9
    assert errors["chest"] <= 1e-9
    # Ordered top-down: parent first.
    assert [r.bone for r in app.rotations] == ["parent", "child"]


def test_zero_length_bone_reported() -> None:
    rig = RigData(
        name="degenerate",
        bones={
            "spine": BoneData("spine", (0, 0, 0), (0, 0, 1), None),
            "chest": BoneData("chest", (0, 0, 1), (0, 0, 1), "spine"),
        },
    )
    mapping = _identity_mapping(rig)
    pose = _pose_from_fixture_positions(
        {"spine": (0, 0, 0), "chest": (0, 0, 1), "neck": (0, 0, 2), "head": (0, 0, 3)}
    )
    app = apply_canonical_pose(rig, mapping, pose)
    assert any("zero-length" in s for s in app.skipped)


def test_low_confidence_pose_notes_but_applies() -> None:
    rig = _canonical_rest_rig()
    mapping = _identity_mapping(rig)
    pose = CanonicalPose(
        positions={r: v[0] for r, v in rest_skeleton(1.7).items()},
        flips={}, confidence=0.2, reliable=False, scale=1.0, anchor="hips",
    )
    app = apply_canonical_pose(rig, mapping, pose)
    assert any("confidence" in n for n in app.notes)


# -- the 3-rig accept ---------------------------------------------------------------


def _real_rig_paths() -> list[Path]:
    base = Path(__file__).resolve().parents[2] / "out" / "real_rigs"
    return sorted(base.glob("*.rig.json"))


@pytest.mark.parametrize("rig_path", _real_rig_paths(), ids=lambda p: p.stem)
def test_same_pose_on_real_rigs_within_tolerance(rig_path: Path) -> None:
    from riggermortis.io import load_rig
    from riggermortis.mapper import map_rig

    rig = load_rig(rig_path)
    mapping = map_rig(rig)
    assert not mapping.core_missing(), f"{rig.name}: mapper must be core-complete"
    fixture = next(p for p in POSES if p.name == "arms_down_relaxed")
    pose = _pose_from_fixture_positions(fixture.positions)
    app = apply_canonical_pose(rig, mapping, pose)
    applied = {r.role for r in app.rotations}
    missing = MUST_APPLY - applied
    assert not missing, f"{rig.name}: core roles not applied: {sorted(missing)}"
    errors = verify_application(rig, app, pose)
    worst_role, worst = max(errors.items(), key=lambda kv: kv[1])
    assert worst <= ANGLE_TOL_RAD, (
        f"{rig.name}: {worst_role} off by {math.degrees(worst):.4f} deg"
    )


def test_ordering_is_depth_then_name() -> None:
    rig = _canonical_rest_rig()
    mapping = _identity_mapping(rig)
    fixture = next(p for p in POSES if p.name == "kneel")
    pose = _pose_from_fixture_positions(fixture.positions)
    app = apply_canonical_pose(rig, mapping, pose)
    keys = [(r.depth, r.bone) for r in app.rotations]
    assert keys == sorted(keys)
    assert app.to_dict()["rotations"] == app.to_dict()["rotations"]  # stable payload
