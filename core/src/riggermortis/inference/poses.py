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
