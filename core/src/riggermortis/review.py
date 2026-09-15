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

from dataclasses import dataclass

from .canonical_pose import CanonicalPose
from .fk_apply import PRIMARY_CHILD

#: Confidence below which a joint/flip is flagged for human review.
#: Mirrors the mapper's ambiguity bar (CONVENTIONS.md).
CONFIDENCE_BAR = 0.55

KIND_ORDER = {"flip": 0, "confidence": 1, "note": 2}


@dataclass(frozen=True)
class ReviewItem:
    """One thing a human should look at before trusting the pose."""

    role: str  # canonical role (or flip key like "forearm.L") or "" for notes
    kind: str  # "flip" | "confidence" | "note"
    message: str
    severity: float  # 0..1, higher = more urgent; sorts first

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "kind": self.kind,
            "message": self.message,
            "severity": round(self.severity, 4),
        }


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
