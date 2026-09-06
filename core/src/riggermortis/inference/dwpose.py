"""DWPose ONNX wrapper: person detection + 133-keypoint whole-body estimation.

A faithful re-implementation of the official DWPose ONNX demo
(IDEA-Research/DWPose, branch ``onnx``, ``ControlNet-v1-1-nightly/annotator/
dwpose/{onnxdet,onnxpose}.py``) with two deviations, both documented:

- cv2 is replaced by pure numpy: the 3-point affine matrix is solved directly
  and the crop is sampled by inverse-mapped bilinear interpolation (constant
  border, like the cv2.warpAffine defaults the demo relies on). Numbers match
  the demo.
- Image input is RGB (the demo's cv2.imread yields BGR); RGB is converted to
  BGR once at the boundary so every downstream computation matches the demo
  exactly, including the ImageNet-style mean/std (which the demo applies to
  the BGR channels of the pinned weights).

LOCAL OR NOTHING: nothing here ever downloads. Both models must already be
verified in the local store (checksum-pinned by :mod:`.models`); a missing
model raises an actionable error pointing at ``rigpose models download``.
numpy/onnxruntime are imported lazily inside functions, never at module
import, and only via the ``[inference]`` extra.

Determinism: onnxruntime CPU ExecutionProvider with a fixed thread count set
through SessionOptions; every decode step is plain numpy (exact arithmetic).
Same input + same settings = same output.
"""
from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import InferenceError
from . import models
from .poses import KEYPOINT_COUNT, Detection, Figure

DET_MODEL = "dwpose-yolox-l"
POSE_MODEL = "dwpose-ll-ucoco-384"

DET_SIZE = (640, 640)  # letterboxed detector input (h, w)
POSE_SIZE = (288, 384)  # (w, h) pose model input
SIMCC_SPLIT_RATIO = 2.0
BBOX_PADDING = 1.25
NMS_THR = 0.45
DET_SCORE_THR = 0.1  # inner NMS pre-filter
DET_SCORE_MIN = 0.3  # final detector confidence cut
PERSON_CLASS = 0

# ImageNet mean/std exactly as the official demo applies them (BGR channel
# order, values 0..255).
POSE_MEAN = (123.675, 116.28, 103.53)
POSE_STD = (58.395, 57.12, 57.375)

_INFERENCE_HINT = "pip install riggermortis-core[inference]"


def _import_numpy() -> Any:
    try:
        np_mod = importlib.import_module("numpy")
    except ImportError as exc:
        raise InferenceError(
            "DWPose inference needs numpy, which is not installed",
            hint=_INFERENCE_HINT,
        ) from exc
    if np_mod is None:
        raise InferenceError("numpy import returned no module", hint=_INFERENCE_HINT)
    return np_mod


def _import_onnxruntime() -> Any:
    try:
        ort_mod = importlib.import_module("onnxruntime")
    except ImportError as exc:
        raise InferenceError(
            "DWPose inference needs onnxruntime, which is not installed",
            hint=_INFERENCE_HINT,
        ) from exc
    if ort_mod is None:
        raise InferenceError("onnxruntime import returned no module", hint=_INFERENCE_HINT)
    return ort_mod


# -- sessions ------------------------------------------------------------------

@dataclass
class Sessions:
    """Loaded ONNX sessions (detector, pose). Tests may substitute fakes."""

    det: Any
    pose: Any


_SESSIONS_CACHE: dict[tuple[tuple[str, ...], str], Sessions] = {}


def load_sessions(
    *, providers: list[str] | None = None, root: Path | None = None
) -> Sessions:
    """Verify both pinned models and build (cached) onnxruntime sessions.

    CPU providers by default; pass e.g. ``["CUDAExecutionProvider",
    "CPUExecutionProvider"]`` to opt in to GPU — never initialized silently.
    """
    provider_key = tuple(providers) if providers else ("CPUExecutionProvider",)
    cache_key = (provider_key, str(root) if root else "")
    if cache_key in _SESSIONS_CACHE:
        return _SESSIONS_CACHE[cache_key]

    models.verify_model(DET_MODEL, root)
    models.verify_model(POSE_MODEL, root)

    ort = _import_onnxruntime()
    options = ort.SessionOptions()
    threads = max(1, min(4, os.cpu_count() or 1))
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = threads

    try:
        det = ort.InferenceSession(
            str(models.model_path(DET_MODEL, root)),
            sess_options=options,
            providers=list(provider_key),
        )
        pose = ort.InferenceSession(
            str(models.model_path(POSE_MODEL, root)),
            sess_options=options,
            providers=list(provider_key),
        )
    except Exception as exc:  # onnxruntime raises bare subclasses on bad files
        raise InferenceError(
            f"onnxruntime failed to load the pinned DWPose models: {exc}",
            hint=(
                "the store was checksum-verified, so this is an onnxruntime/"
                "platform issue; re-run: rigpose models verify all"
            ),
        ) from exc

    sessions = Sessions(det=det, pose=pose)
    _SESSIONS_CACHE[cache_key] = sessions
    return sessions


# -- image loading (RGB in, BGR out like the demo) ------------------------------

def _load_bgr(image: Any, np_mod: Any) -> Any:
    """Accept an image path or an HxWx3 RGB array; return HxWx3 uint8 BGR."""
    if isinstance(image, (str, os.PathLike, Path)):
        try:
            from PIL import Image
        except ImportError as exc:
            raise InferenceError(
                f"cannot open image {image}: pillow is not installed",
                hint="pip install pillow (or pass an RGB numpy array instead)",
            ) from exc
        rgb = Image.open(Path(image)).convert("RGB")
        arr = np_mod.asarray(rgb)
    else:
        arr = np_mod.asarray(image)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise InferenceError(
            f"expected an HxWx3 RGB image, got shape {tuple(arr.shape)}",
            hint="pass a path to an image file or an RGB array",
        )
    bgr = arr[..., ::-1]
    return np_mod.ascontiguousarray(bgr.astype("uint8"))


# -- detector (onnxdet.py, verbatim math) ---------------------------------------

def _resize_uint8(img: Any, ratio: float, np_mod: Any) -> Any:
    """Bilinear resize to (h*ratio, w*ratio), like cv2.INTER_LINEAR here."""
    out_h = int(img.shape[0] * ratio)
    out_w = int(img.shape[1] * ratio)
    ys = np_mod.linspace(0, img.shape[0] - 1, out_h)
    xs = np_mod.linspace(0, img.shape[1] - 1, out_w)
    y0 = np_mod.floor(ys).astype(int)
    x0 = np_mod.floor(xs).astype(int)
    y1 = np_mod.minimum(y0 + 1, img.shape[0] - 1)
    x1 = np_mod.minimum(x0 + 1, img.shape[1] - 1)
    wy = (ys - y0)[:, None, None]
    wx = (xs - x0)[None, :, None]
    img_f = img.astype(np_mod.float32)
    top = img_f[np_mod.ix_(y0, x0)] * (1 - wx) + img_f[np_mod.ix_(y0, x1)] * wx
    bot = img_f[np_mod.ix_(y1, x0)] * (1 - wx) + img_f[np_mod.ix_(y1, x1)] * wx
    out = top * (1 - wy) + bot * wy
    return np_mod.clip(out, 0, 255).astype(np_mod.uint8)


def _letterbox(img: Any, np_mod: Any) -> tuple[Any, float]:
    """Demo preprocess: letterbox into DET_SIZE with pad 114, uint8 -> f32."""
    padded = np_mod.ones((DET_SIZE[0], DET_SIZE[1], 3), dtype=np_mod.uint8) * 114
    ratio = min(DET_SIZE[0] / img.shape[0], DET_SIZE[1] / img.shape[1])
    resized = _resize_uint8(img, ratio, np_mod)
    padded[: int(img.shape[0] * ratio), : int(img.shape[1] * ratio)] = resized
    padded = padded.transpose(2, 0, 1)
    return np_mod.ascontiguousarray(padded.astype(np_mod.float32)), ratio


def _yolox_decode(predictions: Any, np_mod: Any) -> Any:
    """Demo demo_postprocess: grid/stride decode for strides 8/16/32."""
    strides = [8, 16, 32]
    grids = []
    expanded_strides = []
    hsizes = [DET_SIZE[0] // s for s in strides]
    wsizes = [DET_SIZE[1] // s for s in strides]
    for hsize, wsize, stride in zip(hsizes, wsizes, strides, strict=False):
        xv, yv = np_mod.meshgrid(np_mod.arange(wsize), np_mod.arange(hsize))
        grid = np_mod.stack((xv, yv), 2).reshape(1, -1, 2)
        grids.append(grid)
        expanded_strides.append(np_mod.full((*grid.shape[:2], 1), stride))
    grids = np_mod.concatenate(grids, 1)
    strides_arr = np_mod.concatenate(expanded_strides, 1)
    outputs = predictions.copy()
    outputs[..., :2] = (outputs[..., :2] + grids) * strides_arr
    outputs[..., 2:4] = np_mod.exp(outputs[..., 2:4]) * strides_arr
    return outputs


def _nms(boxes: Any, scores: Any, thr: float, np_mod: Any) -> list[int]:
    """Demo single-class NMS (numpy), verbatim."""
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np_mod.maximum(x1[i], x1[order[1:]])
        yy1 = np_mod.maximum(y1[i], y1[order[1:]])
        xx2 = np_mod.minimum(x2[i], x2[order[1:]])
        yy2 = np_mod.minimum(y2[i], y2[order[1:]])
        w = np_mod.maximum(0.0, xx2 - xx1 + 1)
        h = np_mod.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np_mod.where(ovr <= thr)[0]
        order = order[inds + 1]
    return keep


def _multiclass_nms(boxes: Any, scores: Any, np_mod: Any) -> Any | None:
    """Demo multiclass NMS with the demo thresholds (0.45 / 0.1)."""
    final_dets = []
    num_classes = scores.shape[1]
    for cls_ind in range(num_classes):
        cls_scores = scores[:, cls_ind]
        valid = cls_scores > DET_SCORE_THR
        if valid.sum() == 0:
            continue
        valid_scores = cls_scores[valid]
        valid_boxes = boxes[valid]
        keep = _nms(valid_boxes, valid_scores, NMS_THR, np_mod)
        if keep:
            cls_inds = np_mod.ones((len(keep), 1)) * cls_ind
            dets = np_mod.concatenate(
                [valid_boxes[keep], valid_scores[keep, None], cls_inds], 1
            )
            final_dets.append(dets)
    if not final_dets:
        return None
    return np_mod.concatenate(final_dets, 0)


def _detect(session: Any, bgr: Any, np_mod: Any) -> tuple[Any, Any]:
    """Run the detector; return (boxes (N,4) xyxy, scores (N,)) pixel coords."""
    img, ratio = _letterbox(bgr, np_mod)
    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: img[None, :, :, :]})
    predictions = _yolox_decode(output[0], np_mod)[0]

    boxes = predictions[:, :4]
    scores = predictions[:, 4:5] * predictions[:, 5:]

    boxes_xyxy = np_mod.ones_like(boxes)
    boxes_xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2.0
    boxes_xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2.0
    boxes_xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2.0
    boxes_xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2.0
    boxes_xyxy /= ratio
    dets = _multiclass_nms(boxes_xyxy, scores, np_mod)
    if dets is None:
        empty = np_mod.zeros((0, 4), dtype=np_mod.float32)
        return empty, np_mod.zeros((0,), dtype=np_mod.float32)
    final_boxes, final_scores, final_cls = dets[:, :4], dets[:, 4], dets[:, 5]
    keep = (final_scores > DET_SCORE_MIN) & (final_cls == PERSON_CLASS)
    return final_boxes[keep], final_scores[keep]


# -- pose stage (onnxpose.py, verbatim math; cv2 affine replaced) ---------------

def _bbox_to_center_scale(bbox: Any, np_mod: Any) -> tuple[Any, Any]:
    """Demo bbox_xyxy2cs with padding 1.25 (degenerate boxes clamped to 1px)."""
    x1, y1, x2, y2 = (float(v) for v in bbox)
    center = np_mod.array([(x1 + x2) * 0.5, (y1 + y2) * 0.5], dtype=np_mod.float64)
    scale = np_mod.array(
        [max(1.0, x2 - x1) * BBOX_PADDING, max(1.0, y2 - y1) * BBOX_PADDING],
        dtype=np_mod.float64,
    )
    return center, scale


def _fix_aspect_ratio(scale: Any, aspect_ratio: float, np_mod: Any) -> Any:
    """Demo _fix_aspect_ratio: extend (w, h) to the model's w/h ratio."""
    w, h = float(scale[0]), float(scale[1])
    if w > h * aspect_ratio:
        return np_mod.array([w, w / aspect_ratio], dtype=np_mod.float64)
    return np_mod.array([h * aspect_ratio, h], dtype=np_mod.float64)


def _third_point(a: Any, b: Any, np_mod: Any) -> Any:
    """Demo _get_3rd_point: rotate a-b by 90 degrees about b."""
    direction = a - b
    return b + np_mod.array([-direction[1], direction[0]])


def _affine_from_points(src: Any, dst: Any, np_mod: Any) -> Any:
    """Solve the 2x3 affine mapping three src points onto three dst points.

    Equivalent to cv2.getAffineTransform(src, dst).
    """
    coeffs = np_mod.column_stack([src, np_mod.ones(len(src))])  # 3x3
    mat = np_mod.zeros((2, 3), dtype=np_mod.float64)
    mat[0] = np_mod.linalg.solve(coeffs, dst[:, 0])
    mat[1] = np_mod.linalg.solve(coeffs, dst[:, 1])
    return mat


def _warp_matrix(center: Any, scale: Any, out_size: tuple[int, int], np_mod: Any) -> Any:
    """Demo get_warp_matrix with rot=0 (dst = model crop space)."""
    out_w, out_h = out_size
    src = np_mod.zeros((3, 2), dtype=np_mod.float64)
    src[0] = center
    src[1] = center + np_mod.array([0.0, -scale[0] * 0.5])
    src[2] = _third_point(src[0], src[1], np_mod)
    dst = np_mod.zeros((3, 2), dtype=np_mod.float64)
    dst[0] = [out_w * 0.5, out_h * 0.5]
    dst[1] = [out_w * 0.5, out_h * 0.5 - out_w * 0.5]
    dst[2] = _third_point(dst[0], dst[1], np_mod)
    return _affine_from_points(src, dst, np_mod)


def _warp_bilinear(img: Any, mat: Any, out_size: tuple[int, int], np_mod: Any) -> Any:
    """The demo's cv2.warpAffine(img, mat, size, INTER_LINEAR) without cv2.

    Inverse mapping: dst(x, y) = src(M^-1 . (x, y, 1)), bilinear, constant 0
    border — the cv2 defaults the demo relies on.
    """
    out_w, out_h = out_size
    mat_inv = np_mod.linalg.inv(np_mod.vstack([mat, [0.0, 0.0, 1.0]]))
    xs = np_mod.arange(out_w, dtype=np_mod.float64)
    ys = np_mod.arange(out_h, dtype=np_mod.float64)
    grid_x, grid_y = np_mod.meshgrid(xs, ys)
    ones = np_mod.ones_like(grid_x)
    coords = np_mod.stack([grid_x, grid_y, ones], axis=0).reshape(3, -1)
    src_pts = mat_inv @ coords
    sx = src_pts[0].reshape(out_h, out_w)
    sy = src_pts[1].reshape(out_h, out_w)

    h, w = img.shape[:2]
    inside = (sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1)
    sx_c = np_mod.clip(sx, 0, w - 1)
    sy_c = np_mod.clip(sy, 0, h - 1)
    x0 = np_mod.floor(sx_c).astype(int)
    y0 = np_mod.floor(sy_c).astype(int)
    x1 = np_mod.minimum(x0 + 1, w - 1)
    y1 = np_mod.minimum(y0 + 1, h - 1)
    wx = (sx_c - x0)[..., None]
    wy = (sy_c - y0)[..., None]
    img_f = img.astype(np_mod.float32)
    top = img_f[y0, x0] * (1 - wx) + img_f[y0, x1] * wx
    bot = img_f[y1, x0] * (1 - wx) + img_f[y1, x1] * wx
    out = top * (1 - wy) + bot * wy
    return out * inside[..., None]


def _preprocess_pose(
    img: Any, bbox: Any, model_size: tuple[int, int], np_mod: Any
) -> tuple[Any, Any, Any]:
    """Demo preprocess for one person: center/scale, affine crop, normalize."""
    center, scale = _bbox_to_center_scale(bbox, np_mod)
    aspect = model_size[0] / model_size[1]
    scale = _fix_aspect_ratio(scale, aspect, np_mod)
    mat = _warp_matrix(center, scale, model_size, np_mod)
    crop = _warp_bilinear(img, mat, model_size, np_mod)
    crop = (crop - np_mod.array(POSE_MEAN, dtype=np_mod.float32)) / np_mod.array(
        POSE_STD, dtype=np_mod.float32
    )
    return crop.transpose(2, 0, 1), center, scale


def _simcc_decode(simcc_x: Any, simcc_y: Any, np_mod: Any) -> tuple[Any, Any]:
    """Demo decode: per-joint argmax over the SimCC axes (split ratio 2.0)."""
    if simcc_x.ndim != 3 or simcc_y.ndim != 3:
        raise InferenceError(
            f"unexpected SimCC output rank {simcc_x.ndim}/{simcc_y.ndim}",
            hint="the pinned pose model changed — do not use it; report this",
        )
    if simcc_x.shape[1] != KEYPOINT_COUNT or simcc_y.shape[1] != KEYPOINT_COUNT:
        raise InferenceError(
            f"pose model emitted {simcc_x.shape[1]} keypoints, expected {KEYPOINT_COUNT}",
            hint="the pinned model no longer matches the manifest — report this",
        )
    x_locs = np_mod.argmax(simcc_x, axis=-1)
    y_locs = np_mod.argmax(simcc_y, axis=-1)
    locs = np_mod.stack((x_locs, y_locs), axis=-1).astype(np_mod.float32)
    max_val_x = np_mod.amax(simcc_x, axis=-1)
    max_val_y = np_mod.amax(simcc_y, axis=-1)
    vals = np_mod.where(max_val_x > max_val_y, max_val_x, max_val_y)
    locs[vals <= 0.0] = -1.0  # dead joint: demo marks the bin invalid
    locs = locs / SIMCC_SPLIT_RATIO
    return locs, vals


def _estimate(session: Any, bgr: Any, boxes: Any, np_mod: Any) -> tuple[Any, Any]:
    """Run the pose model per detected box; return (N,133,2) kps and (N,133)."""
    shape = session.get_inputs()[0].shape
    if isinstance(shape[2], int) and isinstance(shape[3], int):
        model_size = (int(shape[3]), int(shape[2]))  # (w, h)
    else:
        model_size = POSE_SIZE

    input_name = session.get_inputs()[0].name
    expected_x = int(model_size[0] * SIMCC_SPLIT_RATIO)
    expected_y = int(model_size[1] * SIMCC_SPLIT_RATIO)
    all_kps, all_scores = [], []
    for bbox in boxes:
        crop, center, scale = _preprocess_pose(bgr, bbox, model_size, np_mod)
        outputs = session.run(None, {input_name: crop[None].astype(np_mod.float32)})
        simcc_x, simcc_y = outputs[0], outputs[1]
        # Load-time shape gate: SimCC bins must be model_size * split ratio.
        if simcc_x.shape[-1] != expected_x or simcc_y.shape[-1] != expected_y:
            raise InferenceError(
                f"pose model SimCC shapes {simcc_x.shape}/{simcc_y.shape} do not match "
                f"input size {model_size} (expected last dims {expected_x}/{expected_y})",
                hint="the pinned model changed — verify with: rigpose models verify all",
            )
        kps, scores = _simcc_decode(simcc_x, simcc_y, np_mod)
        kps = kps / np_mod.array(model_size, dtype=np_mod.float32) * scale + (
            center - scale / 2
        )
        all_kps.append(kps[0])
        all_scores.append(scores[0])
    if not all_kps:
        return (
            np_mod.zeros((0, KEYPOINT_COUNT, 2), dtype=np_mod.float32),
            np_mod.zeros((0, KEYPOINT_COUNT), dtype=np_mod.float32),
        )
    return np_mod.stack(all_kps), np_mod.stack(all_scores)


# -- public API -------------------------------------------------------------------

def detect_keypoints(
    image: Any,
    *,
    providers: list[str] | None = None,
    root: Path | None = None,
    sessions: Sessions | None = None,
) -> Detection:
    """Detect people in ``image`` and estimate 133 keypoints per figure.

    ``image`` is a path to an image file or an HxWx3 RGB numpy array.
    ``sessions`` overrides the loaded ONNX sessions (test seam; also lets
    callers reuse sessions across many images). GPU is opt-in via
    ``providers`` — CPU-only unless asked.
    """
    np_mod = _import_numpy()
    bgr = _load_bgr(image, np_mod)
    sess = sessions if sessions is not None else load_sessions(providers=providers, root=root)
    boxes, det_scores = _detect(sess.det, bgr, np_mod)
    kps, scores = _estimate(sess.pose, bgr, boxes, np_mod)

    figures: list[Figure] = []
    for i in range(len(boxes)):
        figures.append(
            Figure(
                index=i,
                bbox=(float(boxes[i][0]), float(boxes[i][1]), float(boxes[i][2]), float(boxes[i][3])),
                score=float(det_scores[i]),
                keypoints=[(float(kps[i][j][0]), float(kps[i][j][1])) for j in range(KEYPOINT_COUNT)],
                confidences=[
                    float(min(1.0, max(0.0, scores[i][j]))) for j in range(KEYPOINT_COUNT)
                ],
            )
        )
    ordered = sorted(figures, key=lambda f: (-f.score, f.bbox[0], f.bbox[1], f.index))
    for new_index, fig in enumerate(ordered):
        fig.index = new_index
    return Detection(width=int(bgr.shape[1]), height=int(bgr.shape[0]), figures=ordered)
