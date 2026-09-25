"""Finger chains (P8-3): the additive hand namespace + the per-hand solve.

Design of record: docs/FINGERS.md § As-built design (S28); the DECISIONS
entry for the namespace is D-021, written when this module landed. The
frozen 22-role canonical core is untouched: fingers live in a SEPARATE
topology (``FINGER_PARENT``) and ride ``CanonicalPose.hands`` — consumers
that ignore fingers work byte-identically.

The solve reads ONLY observed keypoints (never guesses): per finger, all
four chain keypoints must clear ``FINGER_CONF_FLOOR`` (the CONVENTIONS
ambiguity bar, reused — the coupling enforcement floor precedent,
declared untuned); below it the finger is SKIPPED and LEDGERED with its
verbatim confidences. Depth magnitude comes from the canonical segment
lengths (``FINGER_SEGMENT_LENGTHS`` — declared D-008 priors, measured 2D
lengths publish next to them, never fitted); depth SIGN is the declared
FORWARD-CURL rule (Δy = −|Δy|, the elbow-forward prior one level down —
the probe showed a flatten-prior enumeration un-curls gripped hands).
Curling away from canonical forward is the documented single-view miss
class; clenched hands are occlusion fixtures (gated-skip, Annex A.1).

Pure stdlib (math only), deterministic everywhere (sorted keys, fixed
tie-breaks). A hand whose wrist is unusable solves to NO entry — an
absent hand reads as clean; a wrong finger would read as broken.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .canonical_pose import CanonicalPose, Vec3
from .errors import RiggermortisError
from .inference.poses import (
    FINGER_JOINTS,
    FINGER_ORDER,
    KEYPOINT_COUNT,
    WRIST_L,
    WRIST_R,
    hand_kp_index,
)

#: The additive finger namespace (D-021): ``hand.<SIDE>.finger.<name>.<joint>``.
#: 2 sides x 5 fingers x 4 joints = 40 roles — separate from ALL_ROLES; the
#: mapper never assigns them (they bind via preset ``hands`` mappings only).
FINGER_SIDES: tuple[str, ...] = ("L", "R")

#: Depth for the per-finger solve.
FINGER_CONF_FLOOR = 0.55  # the CONVENTIONS ambiguity bar, reused; untuned
#: Canonical segment lengths in hip-height units (declared untuned D-008
#: priors; the hand role spans 0.11 — segments share what remains).
_SEG_LENGTHS = (0.030, 0.022, 0.016)
FINGER_SEGMENT_LENGTHS: dict[str, tuple[float, float, float]] = {
    "thumb": (0.032, 0.026, 0.020),
    "index": _SEG_LENGTHS,
    "middle": _SEG_LENGTHS,
    "ring": _SEG_LENGTHS,
    "pinky": _SEG_LENGTHS,
}
#: Segment chains as (parent joint, child joint) pairs per finger — the three
#: articulated segments the apply path orients.
FINGER_SEGMENT_CHAIN: tuple[tuple[str, str], ...] = (
    ("mcp", "pip"),
    ("pip", "dip"),
    ("dip", "tip"),
)

_HANDS = ("hand.L", "hand.R")


def finger_roles() -> tuple[str, ...]:
    """Every finger role, deterministic (side, finger, joint order)."""
    out: list[str] = []
    for side in FINGER_SIDES:
        for finger in FINGER_ORDER:
            for joint in FINGER_JOINTS:
                out.append(f"hand.{side}.finger.{finger}.{joint}")
    return tuple(out)


def is_finger_role(role: str) -> bool:
    """True for D-021 namespace roles (never true for the 22 core roles)."""
    if not role.startswith("hand.") or ".finger." not in role:
        return False
    parts = role.split(".")
    return (
        len(parts) == 5
        and parts[1] in FINGER_SIDES
        and parts[3] in FINGER_ORDER
        and parts[4] in FINGER_JOINTS
    )


def finger_parent(role: str) -> str | None:
    """FK parent of a finger role (``hand.L`` for chain roots; None for
    non-finger roles) — the additive topology table."""
    if not is_finger_role(role):
        return None
    _prefix, side, _finger_lit, finger, joint = role.split(".")
    if joint == "mcp":
        return f"hand.{side}"
    idx = FINGER_JOINTS.index(joint)
    return f"hand.{side}.finger.{finger}.{FINGER_JOINTS[idx - 1]}"


# -- result model -----------------------------------------------------------------

@dataclass
class FingerChain:
    """One solved finger: its 4 observed joints + the chain's confidence
    (the MINIMUM of the four keypoint confidences — the chain is only as
    strong as its weakest joint)."""

    joints: dict[str, Vec3]
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {
            "joints": {j: list(self.joints[j]) for j in FINGER_JOINTS},
            "confidence": round(self.confidence, 4),
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> FingerChain:
        if not isinstance(d, dict) or "joints" not in d:
            raise RiggermortisError(
                "finger chain is malformed (no joints object)",
                hint="expected {'joints': {'mcp': [x,y,z], ...}, 'confidence': c}",
            )
        raw = d["joints"]
        if not isinstance(raw, dict) or set(raw) != set(FINGER_JOINTS):
            raise RiggermortisError(
                f"finger chain joints must be exactly {', '.join(FINGER_JOINTS)}",
                hint=f"got {sorted(raw) if isinstance(raw, dict) else raw!r}",
            )
        joints: dict[str, Vec3] = {}
        for j in FINGER_JOINTS:
            p = raw[j]
            if not isinstance(p, (list, tuple)) or len(p) != 3:
                raise RiggermortisError(
                    f"finger joint {j!r} must be [x, y, z]",
                    hint="canonical units, same space as the body roles",
                )
            joints[j] = (float(p[0]), float(p[1]), float(p[2]))
        return FingerChain(joints=joints, confidence=float(d.get("confidence", 0.0)))  # type: ignore[arg-type]

    def mirrored(self) -> FingerChain:
        """X-negated geometry copy (depth untouched — a mirror never flips
        front/back, the body pose's mirrored() semantics)."""
        return FingerChain(
            joints={j: (-p[0], p[1], p[2]) for j, p in self.joints.items()},
            confidence=self.confidence,
        )


@dataclass
class HandPose:
    """One solved hand: solved fingers, the LOUD skip ledger, wrist strength."""

    fingers: dict[str, FingerChain] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    wrist_conf: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "fingers": {f: self.fingers[f].to_dict() for f in sorted(self.fingers)},
            "skipped": {f: self.skipped[f] for f in sorted(self.skipped)},
            "wrist_conf": round(self.wrist_conf, 4),
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> HandPose:
        if not isinstance(d, dict):
            raise RiggermortisError(
                "hand pose must be a JSON object",
                hint="expected {'fingers': {...}, 'skipped': {...}, 'wrist_conf': c}",
            )
        raw_fingers = d.get("fingers", {})
        if not isinstance(raw_fingers, dict):
            raise RiggermortisError(
                "hand 'fingers' must be an object keyed by finger name",
                hint=f"known fingers: {', '.join(FINGER_ORDER)}",
            )
        unknown = sorted(set(raw_fingers) - set(FINGER_ORDER))
        if unknown:
            raise RiggermortisError(
                f"unknown finger name(s): {', '.join(unknown)}",
                hint=f"known fingers: {', '.join(FINGER_ORDER)}",
            )
        fingers = {f: FingerChain.from_dict(raw_fingers[f]) for f in sorted(raw_fingers)}
        raw_skipped = d.get("skipped", {})
        if not isinstance(raw_skipped, dict):
            raise RiggermortisError(
                "hand 'skipped' must be an object keyed by finger name",
                hint="each value is the verbatim below-floor reason",
            )
        skipped = {str(k): str(v) for k, v in raw_skipped.items()}
        return HandPose(
            fingers=fingers,
            skipped=skipped,
            wrist_conf=float(d.get("wrist_conf", 0.0)),  # type: ignore[arg-type]
        )


# -- the solve ---------------------------------------------------------------------

def _plane_anchor(
    pose: CanonicalPose, kps: list[tuple[float, float]]
) -> tuple[float, float, float] | None:
    """The body solve's anchor pixels + scale (hips midpoint, neck fallback),
    rebuilt exactly as observations_from_keypoints builds them."""
    from .inference.poses import HIP_L, HIP_R, SHOULDER_L, SHOULDER_R

    if len(kps) != KEYPOINT_COUNT:
        raise RiggermortisError(
            f"hand solve expects {KEYPOINT_COUNT} keypoints, got {len(kps)}",
            hint="solve_hands consumes the same detection the body solve did",
        )
    hips = ((kps[HIP_L][0] + kps[HIP_R][0]) / 2.0, (kps[HIP_L][1] + kps[HIP_R][1]) / 2.0)
    neck = (
        (kps[SHOULDER_L][0] + kps[SHOULDER_R][0]) / 2.0,
        (kps[SHOULDER_L][1] + kps[SHOULDER_R][1]) / 2.0,
    )
    if pose.anchor == "hips":
        return hips[0], hips[1], pose.scale
    if pose.anchor == "neck":
        return neck[0], neck[1], pose.scale
    return None


def solve_hand(
    hand: str,
    kps: list[tuple[float, float]],
    confs: list[float],
    pose: CanonicalPose,
    ax: float,
    ay: float,
    scale: float,
) -> HandPose | None:
    """Solve one hand's finger chains. Returns None when the wrist anchor is
    unusable (the whole hand is skipped — an absent hand reads as clean)."""
    if hand not in _HANDS:
        raise RiggermortisError(
            f"unknown hand {hand!r}",
            hint="hands are keyed hand.L / hand.R (the D-021 namespace)",
        )
    w_idx = WRIST_L if hand == "hand.L" else WRIST_R
    if confs[w_idx] < FINGER_CONF_FLOOR:
        return None
    if hand not in pose.positions:
        return None
    y_wrist = pose.positions[hand][1]
    fingers: dict[str, FingerChain] = {}
    skipped: dict[str, str] = {}
    for finger in FINGER_ORDER:
        idxs = [hand_kp_index(hand, finger, j) for j in FINGER_JOINTS]
        cs = [confs[i] for i in idxs]
        if any(c < FINGER_CONF_FLOOR for c in cs):
            skipped[finger] = (
                "confidence " + "/".join(f"{c:.2f}" for c in cs)
                + f" below floor {FINGER_CONF_FLOOR}"
            )
            continue
        plane = [
            ((kps[i][0] - ax) / scale, (ay - kps[i][1]) / scale) for i in idxs
        ]
        lengths = FINGER_SEGMENT_LENGTHS[finger]
        joints: dict[str, Vec3] = {"mcp": (plane[0][0], y_wrist, plane[0][1])}
        y = y_wrist
        for k, jname in enumerate(("pip", "dip", "tip")):
            inplane = math.hypot(
                plane[k + 1][0] - plane[k][0], plane[k + 1][1] - plane[k][1]
            )
            length = lengths[k]
            depth = math.sqrt(max(length * length - inplane * inplane, 0.0))
            y -= depth  # the declared FORWARD-CURL sign (module docstring)
            joints[jname] = (plane[k + 1][0], y, plane[k + 1][1])
        fingers[finger] = FingerChain(joints=joints, confidence=min(cs))
    return HandPose(fingers=fingers, skipped=skipped, wrist_conf=confs[w_idx])


def solve_hands(
    kps: list[tuple[float, float]], confs: list[float], pose: CanonicalPose
) -> dict[str, HandPose]:
    """Solve both hands of one detected figure against its solved body pose.

    Returns ``{"hand.L": HandPose, "hand.R": HandPose}`` — a hand with an
    unusable wrist has NO entry (absent reads as clean, never guessed).
    Deterministic: same inputs, same output, byte-for-byte.
    """
    anchor = _plane_anchor(pose, kps)
    if anchor is None:
        return {}
    ax, ay, scale = anchor
    out: dict[str, HandPose] = {}
    for hand in _HANDS:
        solved = solve_hand(hand, kps, confs, pose, ax, ay, scale)
        if solved is not None:
            out[hand] = solved
    return out
