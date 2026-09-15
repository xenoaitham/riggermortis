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
from dataclasses import dataclass

from .canonical import PRIMARY_CHILD
from .canonical_pose import CanonicalPose

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
