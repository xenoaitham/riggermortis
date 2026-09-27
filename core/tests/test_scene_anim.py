"""Scene-animation contract tests (P8-8): the identity assignment, the swap
alarm, overrides, the per-frame placements + coupling composition, the S32
tracks per character, and the loader (docs/SCENE_ANIMATION.md)."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis.canonical_pose import CanonicalPose, rest_skeleton  # noqa: E402
from riggermortis.coupling import BAR_FRAC  # noqa: E402
from riggermortis.errors import RiggermortisError, SceneError  # noqa: E402
from riggermortis.root_motion import SOURCE_VIDEO  # noqa: E402
from riggermortis.scene import ContactPin  # noqa: E402
from riggermortis.scene_anim import (  # noqa: E402
    ALARM_ABS,
    MIN_COMMON_ROLES,
    SCALE_WEIGHT,
    StreamFigure,
    StreamFrame,
    assign_stream,
    attach_tracks,
    couple_scene_action,
    load_scene_frames,
    placements_for,
    scene_pose_of,
    scene_reference,
    track_for_character,
)
from riggermortis.video import load_state  # noqa: E402

FLIPS = ("forearm.L", "forearm.R", "lower_leg.L", "lower_leg.R")


def _pose(scale: float = 50.0, arm_up: bool = True) -> CanonicalPose:
    rest = rest_skeleton(1.0 / 0.55)  # hip height 1.0 -> TORSO_SPAN 0.45
    positions = {r: (v[0][0], v[0][1], v[0][2])
                 for r, v in sorted(rest.items())}
    ua = positions["upper_arm.L"]
    if arm_up:  # the distinct shape: left arm raised
        positions["forearm.L"] = (ua[0] + 0.18, ua[1], ua[2] + 0.30)
        positions["hand.L"] = (ua[0] + 0.28, ua[1], ua[2] + 0.50)
    return CanonicalPose(
        positions=positions,
        flips={k: -1 for k in FLIPS},
        confidence=1.0,
        reliable=True,
        scale=scale,
        anchor="hips",
        notes=[],
        joint_confidence={},
    )


def _fig(label: str, pose: CanonicalPose,
         center: tuple[float, float] | None = (0.0, 0.0)) -> StreamFigure:
    return StreamFigure(label=label, pose=pose, bbox_center=center)


def _stream(n: int = 5, poses: dict[int, tuple[CanonicalPose, CanonicalPose]]
            | None = None) -> list[StreamFrame]:
    """A tiny two-figure stream: 'figure 1'/'figure 2', distinct shapes and
    scales (A up/50.0 on the left, B down/62.5 on the right)."""
    out = []
    for f in range(1, n + 1):
        pa, pb = (poses or {}).get(f) or (_pose(), _pose(62.5, arm_up=False))
        out.append(StreamFrame(
            frame=f,
            figures=(_fig("figure 1", pa, (250.0, 240.0)),
                     _fig("figure 2", pb, (295.0, 240.0))),
        ))
    return out


# -- the cost ---------------------------------------------------------------------


def test_pose_cost_identical_is_zero():
    p = _pose()
    assert pose_cost_value(p, p) == 0.0


def test_pose_cost_symmetric():
    a, b = _pose(), _pose(62.5, arm_up=False)
    assert pose_cost_value(a, b) == pytest.approx(pose_cost_value(b, a))


def test_pose_cost_scale_term_is_the_log_ratio():
    a, b = _pose(), _pose(62.5, arm_up=False)
    common = sorted(set(a.positions) & set(b.positions))
    mean_dist = sum(math.dist(a.positions[r], b.positions[r])
                    for r in common) / len(common)
    want = mean_dist + SCALE_WEIGHT * abs(math.log(62.5 / 50.0))
    assert pose_cost_value(a, b) == pytest.approx(want)


def test_pose_cost_uncomparable_below_floor():
    tiny = CanonicalPose(
        positions={k: _pose().positions[k] for k in ("hips", "spine",
                                                     "chest")},
        flips={}, confidence=1.0, reliable=True, scale=50.0,
        anchor="hips")
    assert pose_cost_value(tiny, _pose()) is None


def pose_cost_value(a, b):
    from riggermortis.scene_anim import pose_cost
    return pose_cost(a, b)


# -- the assignment ----------------------------------------------------------------


def test_hungarian_known_optimum():
    # row0->col1 (1) + row1->col0 (2) + row2->col2 (2) = 5, strictly optimal
    cost = [[4.0, 1.0, 3.0], [2.0, 0.0, 5.0], [3.0, 2.0, 2.0]]
    from riggermortis.scene_anim import hungarian
    assert hungarian(cost) == [1, 0, 2]


def test_hungarian_rectangular_and_deterministic():
    from riggermortis.scene_anim import hungarian
    cost = [[1.0, 2.0, 3.0], [2.0, 1.0, 3.0]]
    out = hungarian(cost)
    assert len(out) == 2 and out[0] != out[1]
    assert hungarian(cost) == out  # twins


def test_assign_seed_is_keyed_sorted_order():
    action, report = assign_stream(_stream(1), characters=("B", "A"))
    # sorted roster ["A", "B"] x sorted labels ["figure 1", "figure 2"]
    assert action.frames[0].assignment == {"A": "figure 1",
                                           "B": "figure 2"}
    assert not report.alarms and not action.failed


def test_assign_follows_identity_through_a_label_swap():
    # frames 1-2: 'figure 1' carries A's data; frame 3 (the authored
    # event): the labels permute — the WHOLE data stream swaps (shape AND
    # scale, what a real detector glitch carries) — the assignment must
    # FOLLOW the data
    a_data, b_data = _pose(), _pose(62.5, arm_up=False)
    swapped = {3: (b_data, a_data), 4: (b_data, a_data)}
    stream = _stream(4, {1: (a_data, b_data), 2: (a_data, b_data),
                         **swapped})
    action, _report = assign_stream(stream, characters=("A", "B"))
    assert action.frames[2].assignment == {"A": "figure 2",
                                           "B": "figure 1"}
    assert scene_pose_of(action.frames[2], "A") is a_data
    assert scene_pose_of(action.frames[2], "B") is b_data


def test_assign_missing_character_fails_the_frame():
    stream = _stream(3)
    hole = StreamFrame(frame=2, figures=(stream[1].figures[0],))
    action, report = assign_stream(
        [stream[0], hole, stream[2]], characters=("A", "B"))
    assert action.failed == [2]
    assert [af.frame for af in action.frames] == [1, 3]
    assert any("missing" in n for n in report.notes)


def test_assign_extra_figure_is_reported_not_silent():
    stream = _stream(2)
    crowded = StreamFrame(
        frame=2,
        figures=(*stream[1].figures, _fig("figure 3", _pose(), (500.0, 240.0))))
    action, report = assign_stream([stream[0], crowded],
                                   characters=("A", "B"))
    assert report.extras[2] == ["figure 3"]
    assert set(action.frames[1].assignment.values()) == {"figure 1",
                                                         "figure 2"}


def test_assign_empty_stream_refuses_loud():
    with pytest.raises(SceneError, match="empty"):
        assign_stream([], characters=("A", "B"))


def test_assign_uncomparable_pairing_refuses():
    tiny = CanonicalPose(
        positions={k: _pose().positions[k] for k in ("hips", "spine",
                                                     "chest")},
        flips={}, confidence=1.0, reliable=True, scale=50.0,
        anchor="hips")
    stream = _stream(2)
    sparse = StreamFrame(
        frame=2,
        figures=(_fig("figure 1", tiny, (250.0, 240.0)),
                 _fig("figure 2", _pose(62.5, arm_up=False),
                      (295.0, 240.0))))
    with pytest.raises(SceneError, match="uncomparable"):
        assign_stream([stream[0], sparse], characters=("A", "B"))


def test_min_common_roles_is_six():
    assert MIN_COMMON_ROLES == 6


# -- the swap alarm -----------------------------------------------------------------


def test_evidence_alarm_fires_on_the_swap_frame():
    a_data, b_data = _pose(), _pose(62.5, arm_up=False)
    poses = {1: (a_data, b_data), 2: (a_data, b_data),
             3: (b_data, a_data), 4: (b_data, a_data)}
    action, report = assign_stream(_stream(4, poses), characters=("A", "B"))
    evidence = [a for a in report.alarms if a.kind == "evidence"]
    assert [a.frame for a in evidence] == [3]
    assert any(a.kind == "flip" and a.frame == 3 for a in report.alarms)


def test_no_alarm_on_smooth_frames():
    _action, report = assign_stream(_stream(5), characters=("A", "B"))
    assert not [a for a in report.alarms if a.kind == "evidence"]
    assert all(abs(j[1]) <= ALARM_ABS for j in report.jumps)


# -- overrides (authored wins) -------------------------------------------------------


def test_override_wins_marks_and_reports():
    # after the swap the solve (and the data) put A on 'figure 2'; the
    # artist forces A back to 'figure 1' — the authored word wins and the
    # solve's opinion is recorded
    a_data, b_data = _pose(), _pose(62.5, arm_up=False)
    poses = {1: (a_data, b_data), 2: (b_data, a_data),
             3: (b_data, a_data)}
    action, report = assign_stream(
        _stream(3, poses), characters=("A", "B"),
        overrides={3: {"A": "figure 1"}})
    af = action.frames[2]
    assert af.assignment == {"A": "figure 1", "B": "figure 2"}
    assert af.overridden and 3 in report.overridden_frames
    assert any("override wins" in d for d in report.disagreements)


def test_override_with_absent_label_fails_the_frame():
    stream = _stream(2)
    action, report = assign_stream(
        stream, characters=("A", "B"), overrides={2: {"A": "figure 9"}})
    assert action.failed == [2]
    assert any("absent" in n for n in report.notes)


# -- purity + determinism -------------------------------------------------------------


def test_assign_and_couple_never_mutate_the_stream():
    stream = _stream(3)
    before = {f.frame: {fig.label: dict(fig.pose.positions)
                        for fig in f.figures} for f in stream}
    action, _report = assign_stream(
        stream, characters=("A", "B"),
        pins=(ContactPin(figure_a="A", role_a="hand.L",
                         figure_b="B", role_b="hand.R"),))
    couple_scene_action(action, stream)
    after = {f.frame: {fig.label: dict(fig.pose.positions)
                       for fig in f.figures} for f in stream}
    assert before == after


def test_determ_twins_are_identical():
    a1, r1 = assign_stream(_stream(4), characters=("A", "B"))
    a2, r2 = assign_stream(_stream(4), characters=("A", "B"))
    assert a1 == a2 and r1 == r2


# -- placements + the per-frame scene pass -------------------------------------------


def test_placements_are_in_plane_measured():
    stream = _stream(1)
    ref = scene_reference(stream, {1: {"A": "figure 1", "B": "figure 2"}})
    origin, unit = ref
    assert origin == (250.0, 240.0)  # the anchor = min-label char's center
    assert unit == 50.0  # the anchor character's scale
    pl = placements_for({"A": "figure 1", "B": "figure 2"},
                        list(stream[0].figures), ref)
    assert pl["A"].t == (0.0, 0.0, 0.0)  # A is the anchor
    assert pl["A"].s == pytest.approx(1.0)
    # B keeps its real separation: 45 px right of the anchor at U=50
    assert pl["B"].t == pytest.approx((0.9, 0.0, 0.0))
    assert pl["B"].t[1] == 0.0  # depth stays exactly zero
    assert pl["B"].s == pytest.approx(62.5 / 50.0)


def test_scene_reference_refuses_without_bboxes():
    stream = [StreamFrame(frame=1,
                          figures=(_fig("figure 1", _pose(), None),
                                   _fig("figure 2", _pose(62.5,
                                                        arm_up=False), None)))]
    with pytest.raises(SceneError, match="reference"):
        scene_reference(stream, {1: {"A": "figure 1", "B": "figure 2"}})


def test_per_frame_coupling_closes_within_the_bar():
    pin = ContactPin(figure_a="A", role_a="hand.L",
                     figure_b="B", role_b="hand.R",
                     origin="authored", confidence=1.0)
    stream = _stream(3)
    action, _report = assign_stream(stream, characters=("A", "B"),
                                    pins=(pin,))
    coupled = couple_scene_action(action, stream)
    assert len(coupled) == 3
    for _frame, _scene, c_report in coupled:
        row = c_report.rows[0]
        assert row.enforced
        assert row.closed and row.residual_frac < BAR_FRAC


def test_zero_pins_pass_through_byte_identically():
    stream = _stream(2)
    action, _report = assign_stream(stream, characters=("A", "B"))
    coupled = couple_scene_action(action, stream)
    for af, (_f, scene, c_report) in zip(action.frames, coupled, strict=True):
        assert [f.to_dict() for f in scene.figures] \
            == [f.to_dict() for f in af.scene.figures]
        assert c_report.notes == ["no enforceable pins: scene passed "
                                  "through unchanged"]


# -- the S32 tracks, per character -----------------------------------------------------


def test_track_for_character_is_approximate_in_plane():
    stream = _stream(5)
    action, _report = assign_stream(stream, characters=("A", "B"))
    assignment_of = {af.frame: af.assignment for af in action.frames}
    t = track_for_character(stream, assignment_of, "A")
    assert t is not None and t.source == SOURCE_VIDEO
    assert all(v[1] == 0.0 for v in t.translations.values())
    assert any("APPROXIMATE" in n for n in t.notes)


def test_track_returns_none_on_missing_bbox():
    stream = [StreamFrame(frame=1,
                          figures=(_fig("figure 1", _pose(), None),
                                   _fig("figure 2", _pose(62.5,
                                                        arm_up=False), None)))]
    action, _report = assign_stream(stream, characters=("A", "B"))
    assignment_of = {af.frame: af.assignment for af in action.frames}
    assert track_for_character(stream, assignment_of, "A") is None


def test_attach_tracks_keeps_track_free_characters_loud():
    stream = [StreamFrame(frame=1,
                          figures=(_fig("figure 1", _pose(), None),
                                   _fig("figure 2", _pose(62.5,
                                                        arm_up=False),
                                        (295.0, 240.0))))]
    action, _report = assign_stream(stream, characters=("A", "B"))
    attached = attach_tracks(action, stream)
    assert set(attached.tracks) == {"B"}
    assert any("no drift track" in n and "'A'" in n
               for n in attached.notes)


def test_actions_view_decomposes_for_the_certified_bake():
    stream = _stream(3)
    pin = ContactPin(figure_a="A", role_a="hand.L",
                     figure_b="B", role_b="hand.R")
    action, _report = assign_stream(stream, characters=("A", "B"),
                                    pins=(pin,))
    action = attach_tracks(action, stream)
    view = action.actions_view()
    assert set(view) == {"A", "B"}
    for ch, ca in view.items():
        assert [af.frame for af in ca.frames] == [1, 2, 3]
        assert all(af.pose is scene_pose_of(saf, ch)
                   for af, saf in zip(ca.frames, action.frames, strict=True))
        assert ca.root_track is action.tracks[ch]
    assert view["A"].frames[0].pose is not view["B"].frames[0].pose


# -- the loader (the real P2-1 container) ------------------------------------------------


def _write_job(tmp: Path, stream: list[StreamFrame]) -> Path:
    job = tmp / "job"
    job.mkdir()
    done = {}
    for sf in stream:
        entries = [{
            "label": fig.label,
            "index": i,
            "score": 0.9,
            "bbox": [fig.bbox_center[0] - 35, fig.bbox_center[1] - 90,
                     fig.bbox_center[0] + 35, fig.bbox_center[1] + 90]
            if fig.bbox_center else [],
            "pose": fig.pose.to_dict(),
            "rotations": [],
            "skipped": [],
            "notes": [],
        } for i, fig in enumerate(sf.figures)]
        rel = f"frame_{sf.frame:06d}.json"
        (job / rel).write_text(json.dumps({
            "format": 3,
            "image": {"path": "x.png", "width": 640, "height": 480},
            "figures": entries,
        }, sort_keys=True), encoding="utf-8")
        done[sf.frame] = rel
    (job / "job.json").write_text(json.dumps({
        "format": 1, "source": "t", "rig": "t", "stride": 1,
        "frames": sorted(done.values()),
        "done": {str(k): v for k, v in done.items()},
        "notes": [],
    }), encoding="utf-8")
    return job


def test_load_scene_frames_round_trip(tmp_path):
    stream = _stream(3)
    job = _write_job(tmp_path, stream)
    loaded = load_scene_frames(job)
    assert [sf.frame for sf in loaded] == [1, 2, 3]
    for sf_in, sf_out in zip(stream, loaded, strict=True):
        assert [f.label for f in sf_out.figures] \
            == [f.label for f in sf_in.figures]
        assert sf_out.figures[0].bbox_center == (250.0, 240.0)
        assert sf_out.figures[0].pose.to_dict() \
            == sf_in.figures[0].pose.to_dict()


def test_load_scene_frames_missing_state_refuses(tmp_path):
    with pytest.raises(RiggermortisError, match="no video job state"):
        load_scene_frames(tmp_path)


def test_load_state_recovered_by_the_loader(tmp_path):
    job = _write_job(tmp_path, _stream(2))
    assert load_state(job) is not None
