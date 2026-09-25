"""Pose data model: detection results shared by the wrapper, solver, and UI.

Stdlib-only by design — the canonical-pose solver (P1-4) and the figure
selection model (P1-3) import this without numpy/onnxruntime being installed.

The 133-keypoint layout is COCO-WholeBody, exactly as emitted by the pinned
``dw-ll_ucoco_384.onnx`` (verified against the official DWPose ONNX demo,
branch ``onnx`` of IDEA-Research/DWPose: the demo derives ``neck`` as the mean
of body indices 5 and 6, which pins the COCO body order; 17 body + 6 foot +
68 face + 21 + 21 hand = 133). The wrapper asserts the emitted tensor shapes
against this count at load time.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KEYPOINT_COUNT = 133

# -- COCO-WholeBody body indices (COCO-17 order) -----------------------------
NOSE = 0
EYE_L = 1
EYE_R = 2
EAR_L = 3
EAR_R = 4
SHOULDER_L = 5
SHOULDER_R = 6
ELBOW_L = 7
ELBOW_R = 8
WRIST_L = 9
WRIST_R = 10
HIP_L = 11
HIP_R = 12
KNEE_L = 13
KNEE_R = 14
ANKLE_L = 15
ANKLE_R = 16

#: The 17 COCO body keypoints (indices 0..16) — the live-mode miss floor reads
#: their mean confidence (core/live.py); face/hand keypoints are noisier and
#: not load-bearing for the solve.
BODY_KEYPOINT_COUNT = 17

# -- feet (6) -----------------------------------------------------------------
BIG_TOE_L = 17
SMALL_TOE_L = 18
HEEL_L = 19
BIG_TOE_R = 20
SMALL_TOE_R = 21
HEEL_R = 22

# -- face (68), hands (21 + 21) ------------------------------------------------
FACE_START = 23
FACE_END = 91  # exclusive
HAND_L_START = 91
HAND_L_END = 112  # exclusive
HAND_R_START = 112
HAND_R_END = 133  # exclusive

if FACE_END - FACE_START + HAND_L_END - HAND_L_START + HAND_R_END - HAND_R_START + 23 != KEYPOINT_COUNT:
    raise AssertionError("COCO-WholeBody partition does not sum to 133 keypoints")

# -- COCO-WholeBody face layout (P8-4, docs/FACE.md) -----------------------------
#: 68 face keypoints at absolute indices FACE_START..FACE_END-1; the
#: face-relative indices below (0..67) follow the standard 68-point facial
#: landmark convention as DWPose's wholebody model emits it. Consumers use
#: :func:`face_kp_index` — never re-typed literals.
#:
#: SIDE MAP (MEASURED, S29 probe — docs/FACE.md amendment A4): DWPose's
#: band A (brow 17..21 / eye 36..41) sits at IMAGE LEFT = the subject's
#: RIGHT for a camera-facing face (18/18 real faces measured). The ``.L``
#: params read BAND B; the declared subject-left guess was flipped by
#: measurement, exactly the one-line-constant fix the design planned.
FACE_EYE: dict[str, tuple[int, int]] = {"L": (42, 48), "R": (36, 42)}  # 6 pts
FACE_BROW: dict[str, tuple[int, int]] = {"L": (22, 27), "R": (17, 22)}  # 5 pts
FACE_EYE_CORNERS: dict[str, tuple[int, int]] = {"L": (42, 45), "R": (36, 39)}  # outer, inner
FACE_LOWER_LID: dict[str, tuple[int, int]] = {"L": (46, 48), "R": (40, 42)}  # 2 pts
FACE_WING: dict[str, int] = {"L": 35, "R": 31}  # nose wings
FACE_CORNER: dict[str, int] = {"L": 54, "R": 48}  # mouth corners
FACE_MOUTH_UP = 51  # outer upper-lip center
FACE_MOUTH_LOW = 57  # outer lower-lip center
FACE_NOSE_BOTTOM = 33
FACE_IOD_CORNERS = (36, 39, 42, 45)  # outer+inner per eye — the IOD anchor

if FACE_END - FACE_START != 68:
    raise AssertionError("face partition must hold 68 keypoints")


def face_kp_index(side: str, region: str, i: int = 0) -> int:
    """Absolute keypoint index of one face point (docs/FACE.md layout).

    Loud on unknown names — a typo cannot silently read the wrong keypoint
    (the :func:`hand_kp_index` precedent).
    """
    bands = {"eye": FACE_EYE, "brow": FACE_BROW, "lower_lid": FACE_LOWER_LID}
    if side not in ("L", "R"):
        raise ValueError(f"unknown side {side!r} (known: L, R)")
    if region == "corner":
        return FACE_START + FACE_CORNER[side]
    if region == "wing":
        return FACE_START + FACE_WING[side]
    if region == "nose_bottom":
        return FACE_START + FACE_NOSE_BOTTOM
    if region not in bands:
        raise ValueError(
            f"unknown region {region!r} "
            "(known: eye, brow, lower_lid, corner, wing, nose_bottom)"
        )
    lo, hi = bands[region][side]
    if not 0 <= i < hi - lo:
        raise ValueError(f"{region}.{side}[{i}] out of range (band {lo}..{hi - 1})")
    return FACE_START + lo + i

# -- COCO-WholeBody hand layout (P8-3, docs/FINGERS.md) -------------------------
#: One hand carries 21 keypoints: index 0 = wrist, then 5 fingers x 4 joints
#: (mcp/pip/dip/tip) in the fixed thumb->pinky order. Consumers use
#: :func:`hand_kp_index` — never re-typed literals.
HAND_KP_COUNT = 21
FINGER_ORDER: tuple[str, ...] = ("thumb", "index", "middle", "ring", "pinky")
FINGER_JOINTS: tuple[str, ...] = ("mcp", "pip", "dip", "tip")


def hand_kp_index(hand: str, finger: str, joint: str) -> int:
    """Keypoint index of one hand joint (``hand`` is ``hand.L``/``hand.R``).

    Loud on unknown names: the known values are listed in the error, so a
    typo cannot silently read the wrong keypoint.
    """
    if hand == "hand.L":
        base = HAND_L_START
    elif hand == "hand.R":
        base = HAND_R_START
    else:
        raise ValueError(f"unknown hand {hand!r} (known: hand.L, hand.R)")
    if finger not in FINGER_ORDER:
        raise ValueError(f"unknown finger {finger!r} (known: {', '.join(FINGER_ORDER)})")
    if joint not in FINGER_JOINTS:
        raise ValueError(f"unknown joint {joint!r} (known: {', '.join(FINGER_JOINTS)})")
    return base + 1 + 4 * FINGER_ORDER.index(finger) + FINGER_JOINTS.index(joint)


@dataclass
class Figure:
    """One detected person: bbox, detector score, 133 keypoints + confidences.

    ``keypoints`` are (x, y) pixel coordinates in the source image;
    ``confidences`` are estimator scores in [0, 1] (0 = no response).
    """

    index: int
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    score: float
    keypoints: list[tuple[float, float]]
    confidences: list[float]
    label: str = ""  # stable figure label, set by the selection layer (P1-3)

    def __post_init__(self) -> None:
        if len(self.keypoints) != KEYPOINT_COUNT or len(self.confidences) != KEYPOINT_COUNT:
            raise ValueError(
                f"figure expects {KEYPOINT_COUNT} keypoints/confidences, "
                f"got {len(self.keypoints)}/{len(self.confidences)}"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "bbox": [round(v, 2) for v in self.bbox],
            "score": round(self.score, 4),
            "label": self.label,
            "keypoints": [[round(x, 2), round(y, 2)] for x, y in self.keypoints],
            "confidences": [round(c, 4) for c in self.confidences],
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> Figure:
        return Figure(
            index=int(d["index"]),  # type: ignore[arg-type]
            bbox=(float(d["bbox"][0]), float(d["bbox"][1]), float(d["bbox"][2]), float(d["bbox"][3])),  # type: ignore[index]
            score=float(d["score"]),  # type: ignore[arg-type]
            keypoints=[(float(kp[0]), float(kp[1])) for kp in d["keypoints"]],  # type: ignore[union-attr,index]
            confidences=[float(c) for c in d["confidences"]],  # type: ignore[union-attr]
            label=str(d.get("label", "")),
        )


@dataclass
class Detection:
    """All figures found in one image, in deterministic order."""

    width: int
    height: int
    figures: list[Figure] = field(default_factory=list)

    def sorted_figures(self) -> list[Figure]:
        """Deterministic figure order: score desc, then leftmost, then topmost."""
        return sorted(
            self.figures,
            key=lambda f: (-f.score, f.bbox[0], f.bbox[1], f.index),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "width": self.width,
            "height": self.height,
            "figures": [f.to_dict() for f in self.sorted_figures()],
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> Detection:
        return Detection(
            width=int(d["width"]),  # type: ignore[arg-type]
            height=int(d["height"]),  # type: ignore[arg-type]
            figures=[Figure.from_dict(fd) for fd in d["figures"]],  # type: ignore[union-attr]
        )
