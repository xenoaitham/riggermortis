"""Review overlay data model: what a human should double-check, and the ghost
skeleton segments to draw over a reference (P1-7).

Pure stdlib and deterministic — the add-on's draw handler and the MCP review
tool both consume these functions; the presentation (colors, picking) lives in
the frontends.

The two documented solver miss classes (D-008: deep forward kicks, wrists
held behind the back) are precisely what the review flow must rescue: they
surface as low flip margins / low joint confidence here, never silently.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .canonical import PRIMARY_CHILD
from .canonical_pose import CanonicalPose

#: Confidence below which a joint/flip is flagged for human review.
#: Mirrors the mapper's ambiguity bar (CONVENTIONS.md).
CONFIDENCE_BAR = 0.55

KIND_ORDER = {"flip": 0, "confidence": 1, "note": 2}


@dataclass(frozen=True)
class ReviewItem:
    """One thing a human should look at before trusting the pose.

    ``fix`` (P8-9) names the affordance that answers the item, e.g.
    ``finger_fix:hand.L.ring`` / ``face_trim:smile.L`` / ``pin_retarget:0``
    / ``pin_confirm:1`` — empty for everything the pre-P8-9 surfaces emit,
    and omitted from ``to_dict`` when empty (byte identity)."""

    role: str  # canonical role (or flip key like "forearm.L") or "" for notes
    kind: str  # "flip" | "confidence" | "note" | "defect"
    message: str
    severity: float  # 0..1, higher = more urgent; sorts first
    fix: str = ""

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "role": self.role,
            "kind": self.kind,
            "message": self.message,
            "severity": round(self.severity, 4),
        }
        if self.fix:
            out["fix"] = self.fix
        return out


def review_items(pose: CanonicalPose) -> list[ReviewItem]:
    """Deterministic 'needs review' list for a solved pose (may be empty).

    - every flip whose solved margin confidence is below :data:`CONFIDENCE_BAR`
      (the D-008 miss classes land here);
    - every observed joint with joint_confidence below the bar;
    - every solver note as a low-severity line.
    """
    items: list[ReviewItem] = []
    flip_keys = ("forearm.L", "forearm.R", "lower_leg.L", "lower_leg.R")
    for key in flip_keys:
        conf = pose.joint_confidence.get(key)
        if conf is not None and conf < CONFIDENCE_BAR:
            items.append(
                ReviewItem(
                    role=key,
                    kind="flip",
                    message=f"{key} bend direction uncertain (margin {conf:.2f}) — toggle the flip if wrong",
                    severity=1.0 - conf,
                )
            )
    for role in sorted(pose.joint_confidence):
        if role in flip_keys:
            continue
        conf = pose.joint_confidence[role]
        if conf < CONFIDENCE_BAR:
            items.append(
                ReviewItem(
                    role=role,
                    kind="confidence",
                    message=f"{role} detected weakly ({conf:.2f})",
                    severity=1.0 - conf,
                )
            )
    for note in pose.notes:
        items.append(ReviewItem(role="", kind="note", message=note, severity=0.0))
    items.sort(key=lambda i: (-i.severity, KIND_ORDER[i.kind], i.role, i.message))
    return items


def skeleton_segments(pose: CanonicalPose) -> list[tuple[str, str]]:
    """Ordered (parent role, child role) bone segments present in the pose.

    Follows the same chain definition the FK engine uses (PRIMARY_CHILD), so
    the ghost skeleton shows exactly the bones the pose will drive. Parents
    sort before children; deterministic.
    """
    segments: list[tuple[str, str]] = []
    for role in sorted(pose.positions):
        child = PRIMARY_CHILD.get(role)
        if child is not None and child in pose.positions:
            segments.append((role, child))
    return segments


# -- interactivity (P1-11): joint dots + ray-cast picking -----------------------------


def joint_points(
    pose: CanonicalPose, origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: float = 1.0,
) -> dict[str, tuple[float, float, float]]:
    """World-space joint positions for overlay dots and picking (pure math)."""
    return {
        role: (
            origin[0] + p[0] * scale,
            origin[1] + p[1] * scale,
            origin[2] + p[2] * scale,
        )
        for role, p in sorted(pose.positions.items())
    }


def pick_joint(
    points: dict[str, tuple[float, float, float]],
    ray_origin: tuple[float, float, float],
    ray_direction: tuple[float, float, float],
    radius: float,
) -> str | None:
    """The joint nearest a picking ray within ``radius`` world units, or None.

    Pure ray/point math so the add-on's viewport click and any future MCP
    pick tool share one implementation. Deterministic: ties break by ray
    distance (nearer first), then role name. Joints behind the ray origin
    are never picked.
    """
    n = math.sqrt(sum(c * c for c in ray_direction))
    if n <= 1e-12 or radius <= 0.0:
        return None
    rd = tuple(c / n for c in ray_direction)
    best: tuple[float, float, str] | None = None  # (dist, t, role)
    for role in sorted(points):
        p = points[role]
        rel = (p[0] - ray_origin[0], p[1] - ray_origin[1], p[2] - ray_origin[2])
        t = sum(rel[i] * rd[i] for i in range(3))
        if t <= 0.0:
            continue  # behind the camera
        closest = tuple(ray_origin[i] + t * rd[i] for i in range(3))
        d = math.sqrt(sum((p[i] - closest[i]) ** 2 for i in range(3)))
        if d > radius:
            continue
        if best is None or (d, t, role) < best:
            best = (d, t, role)
    return best[2] if best else None


# -- per-defect fix affordances (P8-9, docs/REVIEW_UX.md) -----------------------------
#
# The other half of the honesty loop: every flagged defect is loud DATA under
# the review model above; these four authored corrections REPLACE flagged data
# with human-authored data at confidence 1.0, keep the provenance note, and
# never mutate their input (the CanonicalPose.toggled pattern). No new solve,
# no new namespace — they ride D-021 (fingers), D-022 (face), P8-1 (pins).


def _with_fields(
    pose: CanonicalPose,
    *,
    notes: list[str],
    hands: dict | None = None,
    face: object | None = None,
) -> CanonicalPose:
    return CanonicalPose(
        positions=pose.positions,
        flips=dict(pose.flips),
        confidence=pose.confidence,
        reliable=pose.reliable,
        scale=pose.scale,
        anchor=pose.anchor,
        notes=notes,
        joint_confidence=dict(pose.joint_confidence),
        hands=pose.hands if hands is None else hands,
        face=pose.face if face is None else face,
        roll=dict(pose.roll),
    )


def author_finger(
    pose: CanonicalPose, hand: str, finger: str, direction: tuple[float, float, float]
) -> CanonicalPose:
    """Click a finger, drag the direction: (re)build one finger chain straight
    along ``direction`` (canonical space; normalized here; zero-length
    refuses). From the chain's existing mcp when the finger already solved
    (a direction fix), else from the hand's wrist head — the rescue of a
    SKIPPED (ledgered) finger: the occlusion class becomes one drag.
    Confidence 1.0 (human-authored); the skip-ledger entry is removed; the
    note keeps provenance. One drag authors DIRECTION, not per-joint curl
    (declared scope, docs/REVIEW_UX.md)."""
    from .errors import RiggermortisError
    from .fingers import FINGER_ORDER, FINGER_SEGMENT_LENGTHS, FingerChain, HandPose

    if hand not in ("hand.L", "hand.R"):
        raise RiggermortisError(
            f"unknown hand {hand!r}",
            hint="hands are 'hand.L' / 'hand.R' (the D-021 namespace)",
        )
    if finger not in FINGER_ORDER:
        raise RiggermortisError(
            f"unknown finger {finger!r}",
            hint=f"known fingers: {', '.join(FINGER_ORDER)}",
        )
    n = math.sqrt(sum(c * c for c in direction))
    if n <= 1e-9:
        raise RiggermortisError(
            "finger direction is a zero vector",
            hint="drag somewhere — the chain is authored along the drag direction",
        )
    unit = (direction[0] / n, direction[1] / n, direction[2] / n)
    existing = pose.hands.get(hand)
    if existing is not None and finger in existing.fingers:
        start = existing.fingers[finger].joints["mcp"]
    else:
        start = pose.positions.get(hand)
        if start is None:
            raise RiggermortisError(
                f"{hand} has no wrist position in this pose",
                hint="author the finger after the body solve placed the hand",
            )
    joints: dict[str, tuple[float, float, float]] = {"mcp": start}
    prev = start
    for name, seg in zip(("pip", "dip", "tip"), FINGER_SEGMENT_LENGTHS[finger],
                         strict=True):
        prev = (
            prev[0] + unit[0] * seg,
            prev[1] + unit[1] * seg,
            prev[2] + unit[2] * seg,
        )
        joints[name] = prev
    fingers = dict(existing.fingers) if existing is not None else {}
    fingers[finger] = FingerChain(joints=joints, confidence=1.0)
    skipped = dict(existing.skipped) if existing is not None else {}
    skipped.pop(finger, None)
    hands = dict(pose.hands)
    hands[hand] = HandPose(
        fingers=fingers,
        skipped=skipped,
        wrist_conf=existing.wrist_conf if existing is not None else 1.0,
    )
    return _with_fields(
        pose,
        notes=[*pose.notes, f"{hand}.{finger}: authored in review (direction fix)"],
        hands=hands,
    )


def trim_face(pose: CanonicalPose, param: str, value: float) -> CanonicalPose:
    """Per-param face trim: author one expression param, overriding the gate.
    The value is clamped to [0, 1]; an unknown param refuses; the D-022
    ledger entry (when any) is replaced by the authored value with the
    provenance note left loud."""
    from .errors import RiggermortisError
    from .face import FACE_PARAMS, FacePose

    if param not in FACE_PARAMS:
        raise RiggermortisError(
            f"unknown face param {param!r}",
            hint=f"known params: {', '.join(FACE_PARAMS)} (the D-022 namespace)",
        )
    clamped = max(0.0, min(1.0, float(value)))
    face = pose.face
    was = face.params.get(param) if face is not None else None
    was_skipped = face is not None and param in face.skipped
    params = dict(face.params) if face is not None else {}
    params[param] = clamped
    skipped = dict(face.skipped) if face is not None else {}
    skipped.pop(param, None)
    if was is not None:
        why = f"; solved {was:.4f})"
    elif was_skipped:
        why = "; solver gate had skipped it)"
    else:
        why = ")"
    new_face = FacePose(
        params=params,
        skipped=skipped,
        iod_conf=face.iod_conf if face is not None else 1.0,
    )
    return _with_fields(
        pose,
        notes=[*pose.notes, f"{param}: authored in review (trim{why}"],
        face=new_face,
    )


def flip_figure(scene, label: str):  # noqa: ANN001 — ScenePose (deferred import)
    """Per-figure flip: mirror one figure in place (labels are identity,
    P8-8); every pin endpoint on that figure re-anchors via mirror_role —
    a flip moves the whole figure, its pin anchors move with it."""
    from .canonical import mirror_role
    from .errors import RiggermortisError
    from .scene import ContactPin, SceneFigure, ScenePose

    if not any(f.label == label for f in scene.figures):
        raise RiggermortisError(
            f"scene {scene.name!r}: no figure {label!r}",
            hint=f"figures: {', '.join(sorted(f.label for f in scene.figures))}",
        )
    figures = [
        SceneFigure(label=f.label, pose=f.pose.mirrored()) if f.label == label else f
        for f in scene.figures
    ]
    pins = [
        ContactPin(
            figure_a=p.figure_a,
            role_a=mirror_role(p.role_a) if p.figure_a == label else p.role_a,
            figure_b=p.figure_b,
            role_b=mirror_role(p.role_b) if p.figure_b == label else p.role_b,
            origin=p.origin,
            confidence=p.confidence,
            note=p.note,
        )
        for p in scene.pins
    ]
    return ScenePose(name=scene.name, figures=figures, pins=pins)


def _edited_pin(scene, pin_index: int, **edits):  # noqa: ANN001
    from .errors import RiggermortisError
    from .scene import ScenePose

    if not 0 <= pin_index < len(scene.pins):
        raise RiggermortisError(
            f"pin index {pin_index} out of range (scene has {len(scene.pins)} pins)",
            hint="indexes are the pins' authored order",
        )
    pins = list(scene.pins)
    pins[pin_index] = replace(scene.pins[pin_index], **edits)
    return ScenePose(name=scene.name, figures=list(scene.figures), pins=pins)


def _pin_note(p: object, suffix: str) -> str:  # noqa: ANN001 — ContactPin
    note = getattr(p, "note", "")
    return (f"{note}; " if note else "") + suffix


def retarget_pin(scene, pin_index: int, endpoint: str, new_role: str):  # noqa: ANN001
    """Pin nudge: re-target one endpoint (``"a"``/``"b"``) of a pin to a
    role on the same figure. The pin becomes AUTHORED at confidence 1.0 —
    a re-target is an authoring act — with the provenance note appended."""
    from .errors import RiggermortisError

    if endpoint not in ("a", "b"):
        raise RiggermortisError(
            f"unknown pin endpoint {endpoint!r}", hint="endpoints are 'a' and 'b'"
        )
    if not 0 <= pin_index < len(scene.pins):
        raise RiggermortisError(
            f"pin index {pin_index} out of range (scene has {len(scene.pins)} pins)",
            hint="indexes are the pins' authored order",
        )
    p = scene.pins[pin_index]
    old = p.role_a if endpoint == "a" else p.role_b
    note = _pin_note(p, f"{old}->{new_role} retargeted in review")
    edits: dict[str, object] = {"origin": "authored", "confidence": 1.0,
                                "note": note}
    if endpoint == "a":
        edits["role_a"] = new_role
    else:
        edits["role_b"] = new_role
    return _edited_pin(scene, pin_index, **edits)


def confirm_pin(scene, pin_index: int):  # noqa: ANN001
    """Confirm a suggested pin into an authored one at confidence 1.0
    (the P8-2 confirm, one call)."""
    from .errors import RiggermortisError

    if not 0 <= pin_index < len(scene.pins):
        raise RiggermortisError(
            f"pin index {pin_index} out of range (scene has {len(scene.pins)} pins)",
            hint="indexes are the pins' authored order",
        )
    note = _pin_note(scene.pins[pin_index], "confirmed in review")
    return _edited_pin(
        scene, pin_index, origin="authored", confidence=1.0, note=note
    )


def _sorted_items(items: list[ReviewItem]) -> list[ReviewItem]:
    return sorted(items, key=lambda i: (-i.severity, i.role, i.fix, i.message))


def finger_defects(pose: CanonicalPose) -> list[ReviewItem]:
    """The D-021 ledger as review items: one per skipped finger (fixable via
    ``author_finger``), plus a low-severity advisory per weak-wrist hand with
    solved fingers. Empty for hands-free poses — ``review_items`` is
    untouched and its output stays byte-identical."""
    out: list[ReviewItem] = []
    for hand in sorted(pose.hands):
        h = pose.hands[hand]
        for finger in sorted(h.skipped):
            out.append(ReviewItem(
                role=f"{hand}.{finger}",
                kind="defect",
                message=f"{hand}.{finger} skipped ({h.skipped[finger]}) — "
                        "click + drag to author",
                severity=1.0,
                fix=f"finger_fix:{hand}.{finger}",
            ))
        if h.fingers and h.wrist_conf < 0.75:
            out.append(ReviewItem(
                role=hand,
                kind="confidence",
                message=f"{hand} wrist weak ({h.wrist_conf:.2f}) — "
                        f"{len(h.fingers)} finger chain(s) solved, verify them",
                severity=max(0.0, 0.75 - h.wrist_conf),
            ))
    return _sorted_items(out)


def face_defects(pose: CanonicalPose) -> list[ReviewItem]:
    """The D-022 ledger as review items: one per gated param (fixable via
    ``trim_face``). Empty for face-free poses."""
    out: list[ReviewItem] = []
    if pose.face is None:
        return out
    for param in sorted(pose.face.skipped):
        out.append(ReviewItem(
            role=param,
            kind="defect",
            message=f"{param} gated ({pose.face.skipped[param]}) — trim to author",
            severity=1.0,
            fix=f"face_trim:{param}",
        ))
    return _sorted_items(out)


def scene_defects(scene, couple_report=None) -> list[ReviewItem]:  # noqa: ANN001
    """Loud pin data as review items: unclosable rows of a P8-2 CoupleReport
    (fixable via ``retarget_pin``) and suggested pins (fixable via
    ``confirm_pin``). Without a report only the suggested-pin items emit."""
    out: list[ReviewItem] = []
    if couple_report is not None:
        for row in couple_report.unclosable:
            for idx, p in enumerate(scene.pins):
                if (p.figure_a, p.role_a, p.figure_b, p.role_b) == (
                    row.figure_a, row.role_a, row.figure_b, row.role_b
                ):
                    out.append(ReviewItem(
                        role=f"{row.figure_a}.{row.role_a}"
                             f"<->{row.figure_b}.{row.role_b}",
                        kind="defect",
                        message=f"pin unclosable "
                                f"({row.reason or 'over-bar residual'}) — "
                                "drag an endpoint to a reachable role",
                        severity=1.0,
                        fix=f"pin_retarget:{idx}",
                    ))
                    break
    for i, p in enumerate(scene.pins):
        if p.origin == "suggested":
            out.append(ReviewItem(
                role=f"{p.figure_a}.{p.role_a}<->{p.figure_b}.{p.role_b}",
                kind="note",
                message=f"suggested pin (conf {p.confidence:.2f}) — "
                        "confirm or ignore",
                severity=0.25,
                fix=f"pin_confirm:{i}",
            ))
    return _sorted_items(out)
