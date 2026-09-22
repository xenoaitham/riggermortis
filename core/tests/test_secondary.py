"""Secondary motion (P6-1): ChainSpec validation + spring-chain simulation.

Determinism and behavior only — never trajectory values (D-008): the
constants are order-of-magnitude defaults declared untuned, so the tests
assert follow/lag/settle/inertness/determinism, not specific directions.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from riggermortis.action import action_from_poses
from riggermortis.canonical import rest_skeleton
from riggermortis.canonical_pose import CanonicalPose
from riggermortis.errors import SecondaryError
from riggermortis.linalg import v_add, v_len, v_norm, v_sub
from riggermortis.secondary import (
    ChainSpec,
    SecondaryTrack,
    simulate_secondary,
)

_ADDON_DIR = Path(__file__).resolve().parents[2] / "addon" / "riggermortis_addon"
FPS = 30.0


def _positions(shift: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> dict:
    """Full 21-role rest pose, rigidly translated by ``shift``."""
    rest = rest_skeleton(1.7)
    return {
        role: v_add(head, shift) for role, (head, _tail) in rest.items()
    }


def _pose(positions: dict | None = None) -> CanonicalPose:
    full = _positions()
    if positions:
        full.update(positions)
    return CanonicalPose(
        positions=full,
        flips={},
        confidence=0.9,
        reliable=True,
        scale=94.5,
        anchor="hips",
    )


def _tail_spec(**kw) -> ChainSpec:
    base = dict(
        name="tail",
        anchor_role="hips",
        links=4,
        rest_direction=(0.0, -0.35, -1.0),
    )
    base.update(kw)
    return ChainSpec.from_dict(base)


def _hair_spec(**kw) -> ChainSpec:
    base = dict(
        name="hair",
        anchor_role="head",
        links=3,
        rest_direction=(0.0, -0.5, -1.0),
    )
    base.update(kw)
    return ChainSpec.from_dict(base)


def _pitched_positions(deg: float) -> dict:
    """Head pitched forward by ``deg`` about the neck (head-anchored chains)."""
    rest = rest_skeleton(1.7)
    positions = {role: head for role, (head, _t) in rest.items()}
    neck = positions["neck"]
    head = positions["head"]
    d = v_sub(head, neck)
    a = math.radians(deg)
    # rotate d forward (toward -Y) about X
    dn = v_norm(
        (d[0], d[1] * math.cos(a) - d[2] * math.sin(a), d[1] * math.sin(a) + d[2] * math.cos(a))
    )
    positions["head"] = v_add(neck, dn)
    return positions


# --- ChainSpec validation -----------------------------------------------------


def test_spec_round_trip() -> None:
    d = {
        "format": 1,
        "name": "tail",
        "anchor_role": "hips",
        "links": 4,
        "rest_direction": [0.0, -0.35, -1.0],
        "freq_hz": 2.0,
        "damping_ratio": 0.4,
    }
    spec = ChainSpec.from_dict(d)
    assert ChainSpec.from_dict(spec.to_dict()) == spec
    assert all(abs(v_len(r) - 1.0) < 1e-12 for r in spec.rest_directions)


def test_spec_per_link_directions_round_trip() -> None:
    spec = _tail_spec(
        rest_directions=[(0.0, -0.35, -1.0), (0.0, 0.0, -1.0), (0.0, 0.0, -1.0), (0.0, 0.2, -1.0)]
    )
    assert ChainSpec.from_dict(spec.to_dict()) == spec
    assert len(spec.to_dict()["rest_directions"]) == 4


def test_spec_unknown_field_refused() -> None:
    with pytest.raises(SecondaryError) as exc:
        ChainSpec.from_dict({"name": "x", "anchor_role": "hips", "links": 2, "stiffness": 5})
    assert "stiffness" in str(exc.value)
    assert exc.value.hint is not None and "freq_hz" in exc.value.hint


def test_spec_root_anchor_refused_with_hint() -> None:
    with pytest.raises(SecondaryError) as exc:
        ChainSpec.from_dict({"name": "x", "anchor_role": "root", "links": 2})
    assert "parent" in str(exc.value) and exc.value.hint is not None


def test_spec_unknown_role_refused() -> None:
    with pytest.raises(SecondaryError):
        ChainSpec.from_dict({"name": "x", "anchor_role": "hair_back", "links": 2})


def test_spec_links_band_refused() -> None:
    for bad in (0, 17, 2.5, True):
        with pytest.raises(SecondaryError):
            ChainSpec.from_dict({"name": "x", "anchor_role": "hips", "links": bad})


def test_spec_bands_refused_and_zero_damping() -> None:
    for bad in ({"freq_hz": 100.0}, {"freq_hz": 0.05}, {"damping_ratio": 9.0},
                {"freq_hz": "fast"}, {"damping_ratio": 0.0}):
        with pytest.raises(SecondaryError):
            ChainSpec.from_dict(
                {"name": "x", "anchor_role": "hips", "links": 2, **bad}
            )


def test_spec_zero_direction_refused_and_non_unit_normalized() -> None:
    with pytest.raises(SecondaryError):
        ChainSpec.from_dict(
            {"name": "x", "anchor_role": "hips", "links": 2, "rest_direction": [0, 0, 0]}
        )
    spec = ChainSpec.from_dict(
        {"name": "x", "anchor_role": "hips", "links": 2, "rest_direction": [0.0, 0.0, -5.0]}
    )
    assert spec.rest_directions[0] == (0.0, 0.0, -1.0)


def test_spec_wrong_direction_count_refused() -> None:
    with pytest.raises(SecondaryError) as exc:
        ChainSpec.from_dict(
            {
                "name": "x",
                "anchor_role": "hips",
                "links": 4,
                "rest_directions": [(0.0, 0.0, -1.0)] * 3,
            }
        )
    assert "4" in str(exc.value)


# --- simulation ---------------------------------------------------------------


def test_determinism_and_sorted_track_keys() -> None:
    frames = [
        (i, _pose(positions=_pitched_positions(20.0 * math.sin(0.5 * i))))
        for i in range(30)
    ]
    action = action_from_poses(frames)
    chains = [_hair_spec(), _tail_spec()]
    tracks_a, _rep_a = simulate_secondary(action, chains, fps=FPS)
    tracks_b, rep_b = simulate_secondary(action, chains, fps=FPS)
    assert list(tracks_a) == sorted(tracks_a) == ["hair", "tail"]
    assert tracks_a == tracks_b
    assert rep_b.substeps_per_frame == 8  # ceil((1/30)/(1/240))
    assert rep_b.chains == ["hair", "tail"]


def test_input_action_never_mutated() -> None:
    frames = [(i, _pose()) for i in range(5)]
    action = action_from_poses(frames)
    before = json.dumps(
        [af.pose.to_dict() for af in action.frames], sort_keys=True
    )
    contacts_id = id(action.contacts)
    simulate_secondary(action, [_tail_spec()], fps=FPS)
    after = json.dumps([af.pose.to_dict() for af in action.frames], sort_keys=True)
    assert before == after
    assert id(action.contacts) == contacts_id
    assert action.notes == []


def test_translation_inertness_pinned_contract() -> None:
    """Direction-only v1: a pure translation of the pose moves nothing —
    the chain stays exactly at rest (pinned contract, not an accident)."""
    frames = [
        (i, _pose(positions={
            role: v_add(p, (0.02 * i, 0.0, 0.0))
            for role, p in _positions().items()
        }))
        for i in range(10)
    ]
    action = action_from_poses(frames)
    tracks, rep = simulate_secondary(action, [_tail_spec()], fps=FPS)
    track = tracks["tail"]
    assert rep.max_dev_deg["tail"] == pytest.approx(0.0, abs=1e-9)
    # every frame identical: translation moved the anchor, not the chain
    assert track.directions == (track.directions[0],) * len(track.directions)


def test_rotation_step_follows_then_settles() -> None:
    """Head pitches at frame 10 and holds: the chain lags (behavior bar),
    then the untuned damping settles it within the 1 s hold (D-008)."""
    frames = [
        (i, _pose(positions=_pitched_positions(30.0 if i >= 10 else 0.0)))
        for i in range(40)
    ]
    action = action_from_poses(frames)
    tracks, rep = simulate_secondary(action, [_hair_spec()], fps=FPS)
    assert rep.max_dev_deg["hair"] > 5.0  # real follow-through happened
    assert rep.end_res_deg["hair"] < 2.0  # and it settled after the hold
    track = tracks["hair"]
    assert track.frames == tuple(range(40))
    assert all(len(d) == 3 for d in track.directions)


def test_directions_unit_and_bounded() -> None:
    frames = [
        (i, _pose(positions=_pitched_positions(60.0 * math.sin(1.3 * i))))
        for i in range(60)
    ]
    action = action_from_poses(frames)
    tracks, rep = simulate_secondary(action, [_tail_spec(freq_hz=15.0)], fps=FPS)
    for frame_dirs in tracks["tail"].directions:
        for d in frame_dirs:
            assert abs(v_len(d) - 1.0) < 1e-9
            assert all(math.isfinite(c) for c in d)
    assert 0.0 <= rep.max_dev_deg["tail"] <= 180.0


def test_single_frame_action_starts_at_rest() -> None:
    action = action_from_poses([(0, _pose())])
    tracks, rep = simulate_secondary(action, [_tail_spec()], fps=FPS)
    track = tracks["tail"]
    assert track.frames == (0,)
    # at rest = zero deviation from the instantaneous rest targets (the
    # published behavior metric; deeper links' world dirs are chain
    # kinematics, not a formula)
    assert rep.end_res_deg["tail"] == pytest.approx(0.0, abs=1e-9)
    assert rep.max_dev_deg["tail"] == pytest.approx(0.0, abs=1e-9)
    assert all(abs(v_len(d) - 1.0) < 1e-12 for d in track.directions[0])


def test_empty_action_yields_empty_tracks_with_note() -> None:
    action = action_from_poses([])
    tracks, rep = simulate_secondary(action, [_tail_spec()], fps=FPS)
    assert tracks == {}
    assert any("empty action" in n for n in rep.notes)


def test_unorientable_frame_holds_and_reports() -> None:
    """A frame missing the anchor's parent cannot orient the chain: it is
    reported (once) and the chain holds — never interpolated, never fatal."""
    good = [(i, _pose()) for i in range(3)]
    broken = _pose()
    broken_positions = dict(broken.positions)
    del broken_positions["root"]
    del broken_positions["spine"]  # the hips→spine fallback dies with it
    broken = CanonicalPose(
        positions=broken_positions,
        flips={},
        confidence=0.9,
        reliable=True,
        scale=94.5,
        anchor="hips",
    )
    frames = good + [(3, broken), (4, _pose())]
    action = action_from_poses(frames)
    tracks, rep = simulate_secondary(action, [_tail_spec()], fps=FPS)
    track = tracks["tail"]
    assert set(track.frames) == {0, 1, 2, 3, 4}  # held frames still record
    assert any(
        "1 frame(s) could not orient" in n and "held" in n for n in rep.notes
    )


def test_duplicate_chain_names_refused() -> None:
    action = action_from_poses([(0, _pose())])
    with pytest.raises(SecondaryError) as exc:
        simulate_secondary(action, [_tail_spec(), _tail_spec(name="tail")], fps=FPS)
    assert "duplicate" in str(exc.value)


def test_fps_validation() -> None:
    action = action_from_poses([(0, _pose())])
    for bad in (0.0, -30.0):
        with pytest.raises(SecondaryError):
            simulate_secondary(action, [_tail_spec()], fps=bad)


def test_demo_tail_data_file_validates() -> None:
    raw = json.loads(
        (_ADDON_DIR / "presets" / "secondary" / "demo_tail.json").read_text(
            encoding="utf-8"
        )
    )
    spec = ChainSpec.from_dict(raw)
    assert spec.name == "tail" and spec.links == 4
    assert spec.anchor_role == "hips"


def test_track_type_shape() -> None:
    action = action_from_poses([(0, _pose()), (1, _pose())])
    tracks, _ = simulate_secondary(action, [_tail_spec()], fps=FPS)
    track = tracks["tail"]
    assert isinstance(track, SecondaryTrack)
    assert track.anchor_role == "hips"
    assert track.frames == (0, 1)
    assert len(track.directions) == 2
