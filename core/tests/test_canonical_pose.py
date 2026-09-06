"""P1-4 tests: canonical pose solve (pure stdlib — runs everywhere)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from poses_fixtures import POSES, PoseFixture, project_fixture  # noqa: E402
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
    kps[5], conf[5] = (10.0, 10.0), 0.9
    kps[6], conf[6] = (30.0, 10.0), 0.5
    kps[11], conf[11] = (20.0, 100.0), 0.8
    kps[12], conf[12] = (20.0, 120.0), 0.1
    kps[7], conf[7] = (5.0, 50.0), 0.7
    obs = observations_from_keypoints(kps, conf)
    assert obs["neck"] == ((20.0, 10.0), 0.5)
    assert obs["hips"] == ((20.0, 110.0), 0.1)
    assert obs["upper_arm.L"] == ((5.0, 50.0), 0.7)
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
