"""P8-9 review-UX contract tests: the per-defect fix affordances, the defect
review items, the additive `fix` tag byte-identity, and the D-011 dual-
estimator interface. Pure stdlib; the fixture classes are the established
ones (the coupling wrap scene, hand-constructed HandPose/FacePose ledgers).

Bars pinned here (docs/REVIEW_UX.md):
- affordances are PURE (input never mutated) and loud (actionable refusals);
- authored corrections carry confidence 1.0 + a provenance note, and clear
  the ledger entry they answer;
- ReviewItem.fix is omitted from to_dict when empty (pre-P8-9 bytes hold);
- review_items is untouched: hands/face/pins never leak into its output;
- the estimator interface: default-only registry byte-identical, keyed
  fallback order on the no-person probe, honest no-person terminal.
"""
from __future__ import annotations

import json

import pytest  # noqa: E402

from riggermortis.canonical import mirror_role  # noqa: E402
from riggermortis.canonical_pose import CanonicalPose, rest_skeleton  # noqa: E402
from riggermortis.coupling import Placement, couple_scene  # noqa: E402
from riggermortis.errors import RiggermortisError  # noqa: E402
from riggermortis.face import FACE_PARAMS, FacePose  # noqa: E402
from riggermortis.fingers import FingerChain, HandPose  # noqa: E402
from riggermortis.inference.estimator import (  # noqa: E402
    DEFAULT_ESTIMATOR,
    ESTIMATOR_FIELD,
    select_estimator,
    with_estimator_entry,
)
from riggermortis.payload import FORMAT, build_pose_payload  # noqa: E402
from riggermortis.review import (  # noqa: E402
    author_finger,
    confirm_pin,
    face_defects,
    finger_defects,
    flip_figure,
    retarget_pin,
    review_items,
    scene_defects,
    trim_face,
)
from riggermortis.scene import ContactPin, SceneFigure, ScenePose  # noqa: E402
from riggermortis.types import BoneData, RigData  # noqa: E402

_FLIP_KEYS = ("forearm.L", "forearm.R", "lower_leg.L", "lower_leg.R")


def _stand() -> CanonicalPose:
    rest = rest_skeleton(1.0 / 0.55)
    return CanonicalPose(
        positions={r: v[0] for r, v in sorted(rest.items())},
        flips={k: -1 for k in _FLIP_KEYS},
        confidence=1.0,
        reliable=True,
        scale=1.0,
        anchor="hips",
    )


def _pose_with_ledgers() -> CanonicalPose:
    """A stand pose carrying one skipped finger + one gated face param."""
    return CanonicalPose(
        positions=_stand().positions,
        flips=dict(_stand().flips),
        confidence=0.9,
        reliable=True,
        scale=1.0,
        anchor="hips",
        hands={
            "hand.L": HandPose(
                fingers={
                    "index": FingerChain(
                        joints={j: (0.1, 0.0, 0.4) for j in
                                ("mcp", "pip", "dip", "tip")},
                        confidence=0.8,
                    )
                },
                skipped={"ring": "confidence 0.31 below floor 0.55"},
                wrist_conf=0.7,
            )
        },
        face=FacePose(
            params={"smile.L": 0.42},
            skipped={"cheek.L": "confidence 0.10 below floor 0.55"},
            iod_conf=0.9,
        ),
    )


def _scene(pins: list[ContactPin]) -> ScenePose:
    return ScenePose(
        name="duet",
        figures=[SceneFigure("A", _stand()), SceneFigure("B", _stand())],
        pins=pins,
    )


def _rig() -> RigData:
    rig = RigData(name="rux-test-rig")
    rest = rest_skeleton(1.0 / 0.55)
    rig.bones["hips"] = BoneData(name="hips", head=rest["hips"][0],
                                 tail=rest["spine"][0], parent="root")
    return rig


# -- author_finger ---------------------------------------------------------------


def test_author_finger_rescues_a_skipped_finger():
    pose = _pose_with_ledgers()
    fixed = author_finger(pose, "hand.L", "ring", (0.0, 0.0, -1.0))
    chain = fixed.hands["hand.L"].fingers["ring"]
    assert "ring" not in fixed.hands["hand.L"].skipped
    assert chain.confidence == 1.0
    # straight chain along -Z at the canonical segment lengths
    zs = [chain.joints[j][2] for j in ("mcp", "pip", "dip", "tip")]
    assert all(zs[i] > zs[i + 1] for i in range(3))  # descending along -Z
    assert any("hand.L.ring: authored in review" in n for n in fixed.notes)
    # PURE: the input pose's ledger is untouched
    assert "ring" in pose.hands["hand.L"].skipped
    assert "ring" not in pose.hands["hand.L"].fingers


def test_author_finger_direction_fix_keeps_the_existing_mcp():
    pose = _pose_with_ledgers()
    mcp_before = pose.hands["hand.L"].fingers["index"].joints["mcp"]
    fixed = author_finger(pose, "hand.L", "index", (1.0, 0.0, 0.0))
    chain = fixed.hands["hand.L"].fingers["index"]
    assert chain.joints["mcp"] == mcp_before  # a direction fix, not a re-anchor
    assert chain.confidence == 1.0
    # xs advance along +X at canonical lengths, y/z untouched
    assert chain.joints["tip"][0] > chain.joints["mcp"][0]


def test_author_finger_refuses_loudly():
    pose = _pose_with_ledgers()
    with pytest.raises(RiggermortisError):
        author_finger(pose, "hand.C", "index", (1, 0, 0))
    with pytest.raises(RiggermortisError):
        author_finger(pose, "hand.L", "claw", (1, 0, 0))
    with pytest.raises(RiggermortisError):
        author_finger(pose, "hand.L", "index", (0, 0, 0))
    bare = CanonicalPose(  # genuinely hand-less: nothing to anchor the rescue
        positions={"hips": (0.0, 0.0, 0.0), "spine": (0.0, 0.0, 0.09)},
        flips={}, confidence=0.9, reliable=True, scale=1.0, anchor="hips",
    )
    with pytest.raises(RiggermortisError):
        author_finger(bare, "hand.L", "ring", (1, 0, 0))


# -- trim_face -------------------------------------------------------------------


def test_trim_face_authors_a_gated_param_and_clears_the_ledger():
    pose = _pose_with_ledgers()
    trimmed = trim_face(pose, "cheek.L", 0.8)
    assert trimmed.face.params["cheek.L"] == 0.8
    assert "cheek.L" not in trimmed.face.skipped
    assert any("solver gate had skipped it" in n for n in trimmed.notes)
    assert pose.face.params == {"smile.L": 0.42}  # PURE


def test_trim_face_overrides_a_solved_value_with_provenance():
    pose = _pose_with_ledgers()
    trimmed = trim_face(pose, "smile.L", 0.1)
    assert trimmed.face.params["smile.L"] == 0.1
    assert any("solved 0.4200" in n for n in trimmed.notes)


def test_trim_face_clamps_and_refuses_unknown_params():
    pose = _pose_with_ledgers()
    assert trim_face(pose, "jaw.open", 5.0).face.params["jaw.open"] == 1.0
    assert trim_face(pose, "jaw.open", -1.0).face.params["jaw.open"] == 0.0
    with pytest.raises(RiggermortisError):
        trim_face(pose, "smile.C", 0.5)
    assert len(FACE_PARAMS) == 10  # the D-022 namespace is unchanged


# -- flip_figure / retarget_pin / confirm_pin -------------------------------------


def test_flip_figure_mirrors_one_figure_and_rides_its_pins():
    # ASYMMETRIC pose (a mirrored symmetric stand equals itself — the side
    # swap and the x negation cancel), so the flip is observable:
    posed = _stand()
    posed.positions["hand.L"] = (0.5, -0.1, 1.6)  # only the left hand raised
    scene = ScenePose(
        name="duet",
        figures=[SceneFigure("A", posed), SceneFigure("B", _stand())],
        pins=[ContactPin(figure_a="A", role_a="hand.L",
                         figure_b="B", role_b="chest")],
    )
    flipped = flip_figure(scene, "A")
    fig = next(f for f in flipped.figures if f.label == "A")
    assert fig.pose.positions["hand.R"] == (-0.5, -0.1, 1.6)  # raised, mirrored
    orig_r = scene.figures[0].pose.positions["hand.R"]
    assert fig.pose.positions["hand.L"] == (-orig_r[0], orig_r[1], orig_r[2])
    # the pin rode the flip: A's endpoint re-anchored to the mirrored role
    pin = flipped.pins[0]
    assert pin.role_a == mirror_role("hand.L") == "hand.R"
    assert pin.role_b == "chest"  # B untouched
    assert next(f for f in flipped.figures if f.label == "B").pose \
        == scene.figures[1].pose
    with pytest.raises(RiggermortisError):
        flip_figure(scene, "C")


def test_retarget_pin_becomes_authored_with_provenance():
    scene = _scene([ContactPin(figure_a="A", role_a="hips",
                               figure_b="B", role_b="hand.R")])
    retargeted = retarget_pin(scene, 0, "a", "hand.L")
    pin = retargeted.pins[0]
    assert (pin.figure_a, pin.role_a) == ("A", "hand.L")
    assert pin.origin == "authored" and pin.confidence == 1.0
    assert "hips->hand.L retargeted in review" in pin.note


def test_retarget_and_confirm_refuse_bad_indexes_and_endpoints():
    scene = _scene([ContactPin(figure_a="A", role_a="hips",
                               figure_b="B", role_b="hand.R")])
    with pytest.raises(RiggermortisError):
        retarget_pin(scene, 99, "b", "hand.R")
    with pytest.raises(RiggermortisError):
        retarget_pin(scene, 0, "c", "hand.R")
    with pytest.raises(RiggermortisError):
        confirm_pin(scene, -1)


def test_confirm_pin_suggested_to_authored():
    scene = _scene([ContactPin(figure_a="A", role_a="hand.L",
                               figure_b="B", role_b="hand.R",
                               origin="suggested", confidence=0.6)])
    confirmed = confirm_pin(scene, 0)
    pin = confirmed.pins[0]
    assert pin.origin == "authored" and pin.confidence == 1.0
    assert "confirmed in review" in pin.note


# -- the defect review items -------------------------------------------------------


def test_finger_defects_list_the_ledger_and_the_weak_wrist():
    pose = _pose_with_ledgers()
    items = finger_defects(pose)
    fix_tags = [i.fix for i in items]
    assert "finger_fix:hand.L.ring" in fix_tags
    weak = [i for i in items if i.role == "hand.L" and i.kind == "confidence"]
    assert len(weak) == 1  # wrist_conf 0.7 < 0.75, fingers solved
    assert all(i.to_dict()["fix"] for i in items if i.kind == "defect")


def test_face_defects_list_the_gated_params():
    items = face_defects(_pose_with_ledgers())
    assert [i.fix for i in items] == ["face_trim:cheek.L"]
    assert face_defects(_stand()) == []
    assert face_defects(_pose_with_ledgers())[0].to_dict()["fix"]


def test_scene_defects_flag_unclosable_and_suggested_pins():
    scene = _scene([
        ContactPin(figure_a="A", role_a="hand.R", figure_b="B", role_b="chest"),
        ContactPin(figure_a="A", role_a="hand.L", figure_b="B", role_b="spine",
                   origin="suggested", confidence=0.5),
    ])
    coupled, report = couple_scene(
        scene, {"A": Placement(), "B": Placement(t=(0.0, -3.0, 0.0))})
    items = scene_defects(scene, report)
    retargets = [i for i in items if i.fix and i.fix.startswith("pin_retarget:")]
    confirms = [i for i in items if i.fix and i.fix.startswith("pin_confirm:")]
    assert len(confirms) == 1 and confirms[0].fix == "pin_confirm:1"
    # the far-apart wrap scene cannot close both pins: the over-bar rows are
    # loud defect items with their index
    assert all(int(i.fix.split(":")[1]) in (0, 1) for i in retargets)
    assert scene_defects(_scene([])) == []


def test_clean_inputs_produce_zero_new_items():
    pose = _stand()
    assert finger_defects(pose) == []
    assert face_defects(pose) == []
    assert scene_defects(_scene([])) == []
    # review_items is untouched: the namespace defects never leak into it
    assert all(i.kind in ("flip", "confidence", "note")
               for i in review_items(_pose_with_ledgers()))


# -- byte identity ------------------------------------------------------------------


def test_review_item_fix_tag_omitted_when_empty():
    from riggermortis.review import ReviewItem

    plain = ReviewItem(role="forearm.L", kind="flip", message="m", severity=0.5)
    assert "fix" not in plain.to_dict()
    assert json.loads(json.dumps(plain.to_dict())) == plain.to_dict()
    fixed = ReviewItem(role="r", kind="defect", message="m", severity=1.0,
                       fix="face_trim:smile.L")
    assert fixed.to_dict()["fix"] == "face_trim:smile.L"


def test_affordances_are_pure_on_the_whole_pose():
    pose = _pose_with_ledgers()
    before = json.dumps(pose.to_dict(), sort_keys=True)
    author_finger(pose, "hand.L", "ring", (0, 0, -1))
    trim_face(pose, "cheek.L", 0.8)
    assert json.dumps(pose.to_dict(), sort_keys=True) == before


# -- the D-011 dual-estimator interface --------------------------------------------


class _Fake:
    def __init__(self, name: str, people: int):
        self.name = name
        self._people = people
        self.calls = 0

    def detect_keypoints(self, image, **kwargs):  # noqa: ANN001, ARG002
        self.calls += 1
        from riggermortis.inference.dwpose import Detection, Figure

        figs = [Figure(index=i, bbox=(0.0, 0.0, 1.0, 1.0), score=0.9,
                       keypoints=[(0.0, 0.0)] * 133,
                       confidences=[0.9] * 133)
                for i in range(self._people)]
        return Detection(width=10, height=10, figures=figs)


def test_select_estimator_default_wins_and_fallback_is_keyed():
    found = _Fake(DEFAULT_ESTIMATOR, 1)
    anime = _Fake("fake-anime", 1)
    name, det = select_estimator(None, {DEFAULT_ESTIMATOR: found,
                                        "fake-anime": anime})
    assert (name, len(det.figures)) == (DEFAULT_ESTIMATOR, 1)
    assert anime.calls == 0  # the fallback never ran
    # no person on the default -> the keyed-order fallback answers
    empty = _Fake(DEFAULT_ESTIMATOR, 0)
    name2, det2 = select_estimator(None, {DEFAULT_ESTIMATOR: empty,
                                          "fake-anime": anime})
    assert name2 == "fake-anime" and len(det2.figures) == 1
    # EVERY fallback missing too -> the honest no-person detection (the last
    # estimator's empty answer — no figures either way, nothing fabricated)
    anime0 = _Fake("fake-anime", 0)
    empty2 = _Fake(DEFAULT_ESTIMATOR, 0)
    name3, det3 = select_estimator(None, {DEFAULT_ESTIMATOR: empty2,
                                          "fake-anime": anime0})
    assert name3 == "fake-anime" and not det3.figures
    assert empty2.calls == 1 and anime0.calls == 1


def test_estimator_provenance_field_is_additive_and_default_free():
    entry = {"label": "figure 1", "pose": {}, "rotations": [],
             "skipped": [], "notes": []}
    assert with_estimator_entry(entry, DEFAULT_ESTIMATOR) is entry
    stamped = with_estimator_entry(entry, "fake-anime")
    assert stamped is not entry and stamped[ESTIMATOR_FIELD] == "fake-anime"
    assert ESTIMATOR_FIELD not in entry


def test_payload_writer_carries_estimator_only_for_non_default():
    rig = _rig()
    meta = {"label": "figure 1", "index": 0, "score": 0.9, "bbox": [0, 0, 1, 1]}
    pose = {"positions": {}, "flips": {}, "confidence": 1.0, "reliable": True,
            "scale": 1.0, "anchor": "hips", "notes": [], "joint_confidence": {}}

    def entries(est=None):  # noqa: ANN001
        e = {"figure": dict(meta), "pose": pose, "rotations": [],
             "skipped": [], "notes": []}
        if est:
            e["estimator"] = est
        return [e]

    plain = build_pose_payload(__import__("pathlib").Path("img"), 1, 1, rig,
                               entries(), "figure 1")
    assert all(ESTIMATOR_FIELD not in f for f in plain["figures"])
    assert plain["format"] == FORMAT
    stamped = build_pose_payload(__import__("pathlib").Path("img"), 1, 1, rig,
                                 entries("fake-anime"), "figure 1")
    assert stamped["figures"][0][ESTIMATOR_FIELD] == "fake-anime"
    # the default NEVER writes the field — byte-identical provenance
    dw = build_pose_payload(__import__("pathlib").Path("img"), 1, 1, rig,
                            entries(DEFAULT_ESTIMATOR), "figure 1")
    assert dw["figures"] == plain["figures"]
