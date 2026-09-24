"""Coupling contract tests (P8-2): enforcement gate, movable chains, the
declared solve (convergence, determinism, purity, conflict, reach), and the
report shape (docs/SCENES.md § Contact coupling)."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis.canonical_pose import TORSO_SPAN, CanonicalPose, rest_skeleton  # noqa: E402
from riggermortis.coupling import (  # noqa: E402
    BAR_FRAC,
    ENFORCE_CONF_FLOOR,
    Placement,
    couple_scene,
    movable_joints,
)
from riggermortis.errors import SceneError  # noqa: E402
from riggermortis.scene import ContactPin, SceneFigure, ScenePose  # noqa: E402

_FLIP_KEYS = ("forearm.L", "forearm.R", "lower_leg.L", "lower_leg.R")


def _stand() -> CanonicalPose:
    """Canonical-unit rest stance (T-pose, hips anchored, torso span 0.45)."""
    rest = rest_skeleton(1.0 / 0.55)  # hip height 1.0 -> TORSO_SPAN == 0.45
    return CanonicalPose(
        positions={r: v[0] for r, v in sorted(rest.items())},
        flips={k: -1 for k in _FLIP_KEYS},
        confidence=1.0,
        reliable=True,
        scale=1.0,
        anchor="hips",
        notes=[],
        joint_confidence={},
    )


def _scene(pins: list[ContactPin], poses: dict[str, CanonicalPose] | None = None) -> ScenePose:
    poses = poses or {"A": _stand(), "B": _stand()}
    return ScenePose(
        name="duet",
        figures=[SceneFigure(label, poses[label]) for label in sorted(poses)],
        pins=pins,
    )


def _wrap_pins(**over_a) -> list[ContactPin]:
    fields = dict(origin="authored", confidence=1.0)
    fields.update(over_a)
    return [
        ContactPin(figure_a="A", role_a="hand.R", figure_b="B", role_b="chest", **fields),
        ContactPin(figure_a="A", role_a="hand.L", figure_b="B", role_b="spine", **fields),
    ]


_WRAP_PLACEMENTS = {"A": Placement(), "B": Placement(t=(0.0, -0.32, 0.0,))}


# -- the movable-chain table ---------------------------------------------------------


def test_movable_chain_table():
    assert movable_joints("hand.R", {"upper_arm.R": (0, 0, 0), "forearm.R": (0, 0, 0)}) == \
        ["upper_arm.R", "forearm.R"]
    # a forearm endpoint lists its own joint too — in _carry it is a no-op
    # (pivot == endpoint position, skipped by the zero-arm guard)
    assert movable_joints("forearm.L", {"upper_arm.L": (0, 0, 0), "forearm.L": (0, 0, 0)}) == \
        ["upper_arm.L", "forearm.L"]
    assert movable_joints("toe.L", {"upper_leg.L": (0, 0, 0)}) == ["upper_leg.L"]
    assert movable_joints("chest", {"spine": (0, 0, 0)}) == ["spine"]
    assert movable_joints("head", {"spine": (0, 0, 0), "chest": (0, 0, 0)}) == ["spine", "chest"]


def test_movable_chain_immovable_endpoints():
    for role in ("upper_arm.R", "shoulder.L", "upper_leg.R", "spine", "hips", "root",
                 "upper_arm.L", "shoulder.R", "upper_leg.L"):
        assert movable_joints(role, {"upper_arm.R": (0, 0, 0)}) == [], role


def test_movable_chain_filters_absent_roles():
    assert movable_joints("hand.R", {}) == []


# -- placements -----------------------------------------------------------------------


def test_placement_round_trip_with_rotation_and_scale():
    from riggermortis.coupling import q_axis_angle

    pl = Placement(quat=q_axis_angle((0.0, 0.0, 1.0), 0.7), t=(3.0, -1.0, 2.0), s=1.7)
    p = (0.3, -0.2, 1.1)
    back = pl.unplace(pl.place(p))
    assert all(abs(a - b) < 1e-12 for a, b in zip(p, back, strict=True))


def test_placement_refuses_degenerate_inputs():
    with pytest.raises(SceneError, match="degenerate"):
        Placement(quat=(0.0, 0.0, 0.0, 0.0))
    with pytest.raises(SceneError, match="positive"):
        Placement(s=0.0)
    with pytest.raises(SceneError, match="finite"):
        Placement(t=(float("nan"), 0.0, 0.0))


# -- the pass: purity, passthrough, convergence, determinism --------------------------


def test_no_pins_passthrough_byte_identical():
    scene = _scene([])
    coupled, report = couple_scene(scene, {})
    assert coupled.to_dict() == scene.to_dict()
    assert report.rows == []
    assert report.notes == ["no enforceable pins: scene passed through unchanged"]


def test_pins_present_but_all_unenforced_passthrough():
    scene = _scene([ContactPin(figure_a="A", role_a="hand.R", figure_b="B",
                               role_b="chest", origin="suggested", confidence=0.9)])
    coupled, report = couple_scene(scene, _WRAP_PLACEMENTS)
    assert coupled.to_dict() == scene.to_dict()
    assert report.rows[0].enforced is False


def test_wrap_fixture_converges_within_bar():
    scene = _scene(_wrap_pins())
    coupled, report = couple_scene(scene, _WRAP_PLACEMENTS)
    assert all(r.enforced for r in report.rows)
    assert all(r.closed for r in report.rows), report.to_dict()
    assert all(r.residual_frac < BAR_FRAC for r in report.rows)
    assert all(0 < r.iterations <= 32 for r in report.rows)


def test_input_scene_never_mutated():
    scene = _scene(_wrap_pins())
    before = json.dumps(scene.to_dict(), sort_keys=True)
    couple_scene(scene, _WRAP_PLACEMENTS)
    assert json.dumps(scene.to_dict(), sort_keys=True) == before


def test_twin_solves_byte_identical():
    scene = _scene(_wrap_pins())
    c1, r1 = couple_scene(scene, _WRAP_PLACEMENTS)
    c2, r2 = couple_scene(scene, _WRAP_PLACEMENTS)
    assert json.dumps(c1.to_dict(), sort_keys=True) == json.dumps(c2.to_dict(), sort_keys=True)
    assert json.dumps(r1.to_dict(), sort_keys=True) == json.dumps(r2.to_dict(), sort_keys=True)


def test_nonchain_roles_untouched_and_torso_fixed():
    scene = _scene(_wrap_pins())
    coupled, report = couple_scene(scene, _WRAP_PLACEMENTS)
    a_in = scene.figures[0].pose.positions if scene.figures[0].label == "A" \
        else scene.figures[1].pose.positions
    a_out = next(f.pose for f in coupled.figures if f.label == "A")
    moved = set(report.moved_roles["A"])
    # only the pinned arms' RIDING roles move: upper_arm heads are the carry
    # pivots (a joint's own position is invariant), forearm/hand ride them;
    # the torso line never swings for hand pins
    assert moved == {"hand.R", "hand.L", "forearm.R", "forearm.L"}
    for role in ("hips", "root", "spine", "chest", "neck", "head",
                 "upper_leg.L", "lower_leg.L", "foot.L", "toe.L",
                 "upper_leg.R", "lower_leg.R", "foot.R", "toe.R"):
        assert a_out.positions[role] == a_in[role], role


# -- the enforcement gate -------------------------------------------------------------


def test_suggested_pin_reason_verbatim():
    scene = _scene([ContactPin(figure_a="A", role_a="hand.R", figure_b="B",
                               role_b="chest", origin="suggested", confidence=0.9)])
    _, report = couple_scene(scene, _WRAP_PLACEMENTS)
    row = report.rows[0]
    assert row.enforced is False
    assert row.reason == "suggested pin (never auto-enforced)"


def test_below_floor_pin_reason_verbatim():
    scene = _scene([ContactPin(figure_a="A", role_a="hand.R", figure_b="B",
                               role_b="chest", confidence=ENFORCE_CONF_FLOOR - 0.01)])
    _, report = couple_scene(scene, _WRAP_PLACEMENTS)
    row = report.rows[0]
    assert row.enforced is False
    assert str(ENFORCE_CONF_FLOOR) in row.reason
    assert "pin confidence" in row.reason


def test_enforcement_gates_on_pin_confidence_not_role_confidence():
    # the probe catch: role joint confidence feeds the WEIGHTS; the PIN's
    # confidence gates enforcement. A high-confidence role must not rescue a
    # low-confidence pin.
    scene = _scene([ContactPin(figure_a="A", role_a="hand.R", figure_b="B",
                               role_b="chest", confidence=0.3)])
    _, report = couple_scene(scene, _WRAP_PLACEMENTS)
    assert report.rows[0].enforced is False


def test_missing_placement_reported_not_raised():
    scene = _scene(_wrap_pins())
    coupled, report = couple_scene(scene, {"A": Placement()})  # B unplaced
    row_b = next(r for r in report.rows if r.figure_b == "B" and r.role_b == "chest"
                 and r.role_a == "hand.R")
    assert row_b.enforced is False
    assert "no placement for figure 'B'" in row_b.reason
    # the other pin still enforces against the placement that exists? No — it
    # also references B. Both report; nothing moved.
    assert all(not r.enforced for r in report.rows)
    assert coupled.to_dict() == scene.to_dict()


def test_immovable_both_ends_reported():
    scene = _scene([ContactPin(figure_a="A", role_a="spine", figure_b="B", role_b="hips")])
    coupled, report = couple_scene(scene, _WRAP_PLACEMENTS)
    row = report.rows[0]
    assert row.enforced is False
    assert "immovable" in row.reason
    assert coupled.to_dict() == scene.to_dict()


# -- conflict, weights, reach, scale --------------------------------------------------


def test_competing_pins_compromise_reported_and_deterministic():
    pins = [
        ContactPin(figure_a="A", role_a="hand.R", figure_b="B", role_b="chest"),
        ContactPin(figure_a="A", role_a="hand.R", figure_b="B", role_b="spine"),
    ]
    scene = _scene(pins)
    c1, r1 = couple_scene(scene, _WRAP_PLACEMENTS)
    c2, r2 = couple_scene(scene, _WRAP_PLACEMENTS)
    assert len(r1.unclosable) >= 1  # two targets 0.17 apart cannot both close
    assert all(r.residual >= 0.0 for r in r1.rows)
    assert all(math.isfinite(p[0]) for f in c1.figures for p in f.pose.positions.values())
    assert json.dumps(r1.to_dict(), sort_keys=True) == json.dumps(r2.to_dict(), sort_keys=True)


def test_confidence_weights_move_the_low_confidence_endpoint_more():
    poses = {"A": _stand(), "B": _stand()}
    poses["A"].joint_confidence["hand.R"] = 0.2   # A's hand barely observed
    poses["B"].joint_confidence["chest"] = 1.0
    pins = [ContactPin(figure_a="A", role_a="hand.R", figure_b="B", role_b="chest")]
    scene = _scene(pins, poses)
    coupled, _ = couple_scene(scene, _WRAP_PLACEMENTS)
    out = {f.label: f.pose for f in coupled.figures}
    moved_a = math.dist(out["A"].positions["hand.R"], poses["A"].positions["hand.R"])
    moved_b = math.dist(out["B"].positions["chest"], poses["B"].positions["chest"])
    assert moved_a > moved_b * 4.0  # w_a ~ 0.89 vs w_b ~ 0.11 (declared rule)


def test_unreachable_pin_stays_loud_and_straightens():
    far = {"A": Placement(), "B": Placement(t=(0.0, -3.0, 0.0))}
    scene = _scene([ContactPin(figure_a="A", role_a="hand.R", figure_b="B", role_b="chest")])
    coupled, report = couple_scene(scene, far)
    row = report.rows[0]
    assert row.closed is False
    assert not report.unclosable == []  # loud
    out = next(f.pose for f in coupled.figures if f.label == "A")
    before = math.dist(_WRAP_PLACEMENTS["B"].unplace(
        far["B"].place(_stand().positions["chest"])), _stand().positions["hand.R"])
    after = row.residual
    assert 0.0 < after < before  # the chain straightened toward the target
    assert all(math.isfinite(v) for p in out.positions.values() for v in p)


def test_scale_invariance_of_the_frac_bar():
    scene = _scene(_wrap_pins())
    _, r1 = couple_scene(scene, _WRAP_PLACEMENTS)
    big = {k: Placement(t=tuple(v * 10.0 for v in p.t), quat=p.quat, s=p.s * 10.0)
           for k, p in _WRAP_PLACEMENTS.items()}
    _, r2 = couple_scene(scene, big)
    for a, b in zip(r1.rows, r2.rows, strict=True):
        assert a.closed == b.closed
        assert abs(a.residual_frac - b.residual_frac) < 1e-9
        assert abs(a.residual * 10.0 - b.residual) < 1e-6


# -- report shape + round-trip --------------------------------------------------------


def test_report_rows_authored_order_and_moved_roles_sorted():
    pins = list(reversed(_wrap_pins()))  # authored order L-pin first
    scene = _scene(pins)
    _, report = couple_scene(scene, _WRAP_PLACEMENTS)
    assert [(r.figure_a, r.role_a) for r in report.rows] == \
        [("A", "hand.L"), ("A", "hand.R")]
    for roles in report.moved_roles.values():
        assert roles == sorted(roles)


def test_coupled_scene_round_trip_byte_stable():
    scene = _scene(_wrap_pins())
    coupled, _ = couple_scene(scene, _WRAP_PLACEMENTS)
    d1 = coupled.to_dict()
    rt = ScenePose.from_dict(json.loads(json.dumps(d1)))
    assert rt.to_dict() == d1


def test_torso_span_constant_is_the_canonical_unit_span():
    # the bar's denominator: stand poses measure exactly TORSO_SPAN
    assert abs(TORSO_SPAN - 0.45) < 1e-12
