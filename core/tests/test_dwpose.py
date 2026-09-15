"""P1-2 tests: DWPose wrapper math, data model, and error paths.

The ONNX sessions are always faked (tiny tensors, no downloads, no real
runtime). Decode-math tests need numpy; CI installs ``core[dev]`` only, so
those tests skip with an explicit reason. The numpy-free tests (data model,
error paths) run everywhere.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from riggermortis.errors import InferenceError
from riggermortis.inference import dwpose
from riggermortis.inference.poses import KEYPOINT_COUNT, Detection, Figure

NP_SKIP_REASON = "decode math needs numpy ([inference] extra); CI installs core[dev] only"


# -- fake sessions --------------------------------------------------------------


class _FakeIO:
    def __init__(self, name: str, shape: list) -> None:
        self.name = name
        self.shape = shape


class _FakeDetSession:
    """Emits YOLOX-style raw predictions decoding to known boxes.

    ``specs``: list of (cx, cy, w, h, score) in ORIGINAL image pixels; the
    fake converts them into the 640-letterbox space itself.
    """

    def __init__(self, specs: list[tuple[float, float, float, float, float]], orig_size: tuple[int, int]) -> None:
        self.specs = specs
        self.orig_size = orig_size
        self.io = _FakeIO("images", [1, 3, 640, 640])

    def get_inputs(self) -> list[_FakeIO]:
        return [self.io]

    def get_outputs(self) -> list[_FakeIO]:
        return [_FakeIO("output", None)]

    def run(self, _outs, feeds):  # type: ignore[no-untyped-def]
        import numpy as np

        ratio = min(640 / self.orig_size[1], 640 / self.orig_size[0])
        out = np.zeros((1, 8400, 85), dtype=np.float32)
        for i, (cx, cy, w, h, score) in enumerate(self.specs):
            anchor = 1000 + i * 700  # any stride-8 anchor; keep specs apart
            gx, gy = anchor % 80, (anchor // 80) % 80
            out[0, anchor, 0] = (cx * ratio) / 8.0 - gx
            out[0, anchor, 1] = (cy * ratio) / 8.0 - gy
            out[0, anchor, 2] = math.log((w * ratio) / 8.0)
            out[0, anchor, 3] = math.log((h * ratio) / 8.0)
            out[0, anchor, 4] = score  # obj (already sigmoided by the export)
            out[0, anchor, 5] = 1.0  # person class
        return [out]


class _FakePoseSession:
    """Emits SimCC tensors placing each joint at a known ORIGINAL image spot.

    Built from the documented rescale contract (kp_orig = kp_crop/model_size *
    scale + center - scale/2 with crop bins = kp_crop * split_ratio), which is
    the exact formula the wrapper must invert. The crop geometry is taken from
    the detector's boxes — the same boxes the wrapper crops with.
    """

    POSE_MODEL_SHAPE = [1, 3, 384, 288]  # (N, C, H, W) -> w=288, h=384

    def __init__(
        self,
        keypoints: list[list[tuple[float, float]]],
        bboxes: list[tuple[float, float, float, float]],
    ) -> None:
        # One keypoint list + detector box per expected detection.
        self.keypoints = keypoints
        self.bboxes = bboxes
        self.io = _FakeIO("input", self.POSE_MODEL_SHAPE)

    def get_inputs(self) -> list[_FakeIO]:
        return [self.io]

    def get_outputs(self) -> list[_FakeIO]:
        return [_FakeIO("simcc_x", None), _FakeIO("simcc_y", None)]

    def run(self, _outs, feeds):  # type: ignore[no-untyped-def]
        import numpy as np

        if feeds["input"].shape[0] != 1:
            raise AssertionError("wrapper must run the pose model per person")
        person = self.keypoints[self._call_index]
        bbox = self.bboxes[self._call_index]
        self._call_index += 1
        return self._simcc(person, bbox, np)

    _call_index = 0

    def _simcc(self, kps_orig, bbox, np):  # type: ignore[no-untyped-def]
        w_model, h_model = 288, 384
        cx, cy = (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0
        sw, sh = (bbox[2] - bbox[0]) * 1.25, (bbox[3] - bbox[1]) * 1.25
        if sw > sh * (w_model / h_model):
            sh = sw / (w_model / h_model)
        else:
            sw = sh * (w_model / h_model)
        simcc_x = np.zeros((1, KEYPOINT_COUNT, w_model * 2), dtype=np.float32)
        simcc_y = np.zeros((1, KEYPOINT_COUNT, h_model * 2), dtype=np.float32)
        for j, (x, y) in enumerate(kps_orig):
            crop_x = (x - cx + sw / 2.0) / sw * w_model
            crop_y = (y - cy + sh / 2.0) / sh * h_model
            bin_x, bin_y = int(round(crop_x * 2)), int(round(crop_y * 2))
            if 0 <= bin_x < w_model * 2 and 0 <= bin_y < h_model * 2:
                simcc_x[0, j, bin_x] = 0.9
                simcc_y[0, j, bin_y] = 0.8
        return [simcc_x, simcc_y]


def _person_keypoints(center: tuple[float, float], scale_px: float) -> list[tuple[float, float]]:
    """A crude standing figure (body joints only; rest left at the center)."""
    cx, cy = center
    pts: list[tuple[float, float]] = []
    body = {
        0: (0.0, -1.6), 5: (-0.5, -1.0), 6: (0.5, -1.0), 7: (-0.7, -0.3), 8: (0.7, -0.3),
        9: (-0.8, 0.4), 10: (0.8, 0.4), 11: (-0.3, 0.6), 12: (0.3, 0.6),
        13: (-0.35, 1.5), 14: (0.35, 1.5), 15: (-0.35, 2.4), 16: (0.35, 2.4),
    }
    for idx in range(KEYPOINT_COUNT):
        dx, dy = body.get(idx, (0.0, -1.2))
        pts.append((cx + dx * scale_px, cy + dy * scale_px))
    return pts


# -- numpy-free: data model -------------------------------------------------------


def test_figure_rejects_wrong_keypoint_count() -> None:
    with pytest.raises(ValueError, match="133"):
        Figure(index=0, bbox=(0, 0, 1, 1), score=0.9, keypoints=[(0.0, 0.0)] * 3,
               confidences=[0.5] * 3)


def test_detection_roundtrip_and_ordering() -> None:
    figs = [
        Figure(index=0, bbox=(100, 0, 200, 300), score=0.8, keypoints=[(1.0, 2.0)] * KEYPOINT_COUNT,
               confidences=[0.5] * KEYPOINT_COUNT),
        Figure(index=1, bbox=(10, 0, 90, 300), score=0.9, keypoints=[(3.0, 4.0)] * KEYPOINT_COUNT,
               confidences=[0.6] * KEYPOINT_COUNT),
        Figure(index=2, bbox=(50, 5, 95, 300), score=0.9, keypoints=[(5.0, 6.0)] * KEYPOINT_COUNT,
               confidences=[0.4] * KEYPOINT_COUNT),
    ]
    det = Detection(width=320, height=300, figures=figs)
    ordered = det.sorted_figures()
    # score desc, then leftmost: figure 1 and 2 tie at 0.9; leftmost x=10 wins.
    assert [f.index for f in ordered] == [1, 2, 0]
    rt = Detection.from_dict(det.to_dict())
    assert rt.width == 320 and len(rt.figures) == 3
    assert rt.sorted_figures()[0].keypoints[0] == (3.0, 4.0)


def test_missing_extra_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "numpy", None)
    with pytest.raises(InferenceError, match="riggermortis-core\\[inference\\]"):
        dwpose.detect_keypoints(object())


def test_missing_onnxruntime_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Stub the on-disk model check: without it, environments without downloaded
    # models (CI) fail on "not downloaded" BEFORE reaching the import gate.
    monkeypatch.setattr(dwpose.models, "verify_model", lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    with pytest.raises(InferenceError, match="onnxruntime"):
        dwpose.load_sessions(root=tmp_path)


def test_missing_model_error(tmp_path: Path) -> None:
    with pytest.raises(InferenceError, match="not downloaded") as excinfo:
        dwpose.load_sessions(root=tmp_path)
    assert "rigpose models download" in str(excinfo.value)


# -- numpy tests: decode + geometry math ------------------------------------------


def test_simcc_decode_known_peaks() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    simcc_x = np.zeros((1, KEYPOINT_COUNT, 576), dtype=np.float32)
    simcc_y = np.zeros((1, KEYPOINT_COUNT, 768), dtype=np.float32)
    simcc_x[0, 0, 100] = 0.9  # joint 0 -> x=50 crop px, val 0.9
    simcc_y[0, 0, 200] = 0.7
    simcc_x[0, 1, 10] = 0.5  # val = max(0.5, 0.3)
    simcc_y[0, 1, 6] = 0.3
    kps, scores = dwpose._simcc_decode(simcc_x, simcc_y, np)
    assert kps.shape == (1, KEYPOINT_COUNT, 2)
    assert kps[0, 0, 0] == pytest.approx(50.0)
    assert kps[0, 0, 1] == pytest.approx(100.0)
    assert scores[0, 0] == pytest.approx(0.9)
    assert kps[0, 1, 0] == pytest.approx(5.0)
    assert scores[0, 1] == pytest.approx(0.5)
    # Dead joint: all-zero SimCC -> invalid bin, zero confidence.
    assert scores[0, 2] == pytest.approx(0.0)


def test_simcc_decode_rejects_wrong_layout() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    with pytest.raises(InferenceError, match="133"):
        dwpose._simcc_decode(np.zeros((1, 17, 576), dtype=np.float32),
                             np.zeros((1, 17, 768), dtype=np.float32), np)


def test_affine_and_warp_matrix() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    src = np.array([[10.0, 20.0], [10.0, -30.0], [60.0, 20.0]])
    dst = np.array([[0.0, 0.0], [0.0, -50.0], [50.0, 0.0]])
    mat = dwpose._affine_from_points(src, dst, np)
    assert np.allclose(mat @ np.append(src[0], 1.0), dst[0])
    assert np.allclose(mat @ np.append(src[2], 1.0), dst[2])
    # The demo's crop matrix: center lands at (w/2, h/2).
    center, scale = dwpose._bbox_to_center_scale((0.0, 0.0, 200.0, 400.0), np)
    scale = dwpose._fix_aspect_ratio(scale, 288 / 384, np)
    mat = dwpose._warp_matrix(center, scale, dwpose.POSE_SIZE, np)
    assert np.allclose(mat @ np.append(center, 1.0), [144.0, 192.0])


def test_bbox_center_scale_matches_demo() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    center, scale = dwpose._bbox_to_center_scale((10.0, 20.0, 110.0, 220.0), np)
    assert center.tolist() == [60.0, 120.0]
    assert scale.tolist() == [100.0 * 1.25, 200.0 * 1.25]
    fixed = dwpose._fix_aspect_ratio(scale, 0.75, np)
    # w=125, h=250 -> h dominates: (250*0.75, 250)
    assert fixed.tolist() == pytest.approx([187.5, 250.0])


def test_warp_bilinear_identity_and_bruteforce() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    rng = np.random.default_rng(42)
    img = rng.integers(0, 255, size=(40, 50, 3)).astype(np.uint8)

    ident = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    out = dwpose._warp_bilinear(img, ident, (50, 40), np)
    assert np.array_equal(out.astype(np.uint8), img)

    # Arbitrary affine vs a brute-force reference loop of the same definition.
    mat = np.array([[0.9, 0.1, 3.0], [-0.05, 1.1, -2.0]])
    out = dwpose._warp_bilinear(img, mat, (60, 45), np)
    mat_inv = np.linalg.inv(np.vstack([mat, [0.0, 0.0, 1.0]]))
    ref = np.zeros((45, 60, 3), dtype=np.float32)
    for y in range(45):
        for x in range(60):
            sx, sy, _ = mat_inv @ np.array([x, y, 1.0])
            if 0 <= sx <= 49 and 0 <= sy <= 39:
                x0, y0 = int(math.floor(sx)), int(math.floor(sy))
                x1, y1 = min(x0 + 1, 49), min(y0 + 1, 39)
                wx, wy = sx - x0, sy - y0
                top = img[y0, x0] * (1 - wx) + img[y0, x1] * wx
                bot = img[y1, x0] * (1 - wx) + img[y1, x1] * wx
                ref[y, x] = top * (1 - wy) + bot * wy
    assert np.allclose(out, ref, atol=1e-3)


def test_nms_suppression() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    boxes = np.array(
        [[0.0, 0.0, 100.0, 100.0], [10.0, 10.0, 110.0, 110.0], [300.0, 300.0, 400.0, 400.0]],
        dtype=np.float32,
    )
    scores = np.array([0.9, 0.8, 0.5], dtype=np.float32)
    keep = dwpose._nms(boxes, scores, 0.45, np)
    assert keep == [0, 2]  # box 1 overlaps box 0 by IoU ~0.68 -> suppressed


def test_yolox_decode_grid_math() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    preds = np.zeros((1, 8400, 85), dtype=np.float32)
    anchor = 163  # stride 8: y = 163 // 80 = 2, x = 163 % 80 = 3
    cx, cy, w, h = 100.0, 200.0, 80.0, 160.0
    preds[0, anchor, 0] = cx / 8.0 - 3.0
    preds[0, anchor, 1] = cy / 8.0 - 2.0
    preds[0, anchor, 2] = math.log(w / 8.0)
    preds[0, anchor, 3] = math.log(h / 8.0)
    preds[0, anchor, 4] = 0.9
    preds[0, anchor, 5] = 1.0
    decoded = dwpose._yolox_decode(preds, np)
    assert decoded[0, anchor, 0] == pytest.approx(cx)
    assert decoded[0, anchor, 1] == pytest.approx(cy)
    assert decoded[0, anchor, 2] == pytest.approx(w)
    assert decoded[0, anchor, 3] == pytest.approx(h)


# -- numpy tests: end-to-end through faked sessions --------------------------------


def _fake_sessions(
    specs: list[tuple[float, float, float, float, float]],
    orig_size: tuple[int, int],
    kp_sets: list[list[tuple[float, float]]] | None = None,
) -> tuple[_FakeDetSession, _FakePoseSession]:
    det = _FakeDetSession(specs, orig_size)
    bboxes = [(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2) for cx, cy, w, h, _s in specs]
    if kp_sets is None:
        kp_sets = []
        for cx, cy, w, h, _s in specs:
            kp_sets.append(_person_keypoints((cx, cy), min(w, h) / 5.0))
    pose = _FakePoseSession(kp_sets, bboxes)
    return det, pose


def test_detect_keypoints_end_to_end_fakes() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    det, pose = _fake_sessions(
        [(160.0, 320.0, 120.0, 300.0, 0.95)], (320, 640)
    )
    sessions = dwpose.Sessions(det=det, pose=pose)
    image = np.zeros((640, 320, 3), dtype=np.uint8)
    detection = dwpose.detect_keypoints(image, sessions=sessions)
    assert detection.width == 320 and detection.height == 640
    assert len(detection.figures) == 1
    fig = detection.figures[0]
    assert fig.score == pytest.approx(0.95)
    # Key round-trip: original pixels -> SimCC bins -> rescaled original pixels
    # (within the 0.5-crop-px SimCC quantization scaled into image space).
    # Detector box for (cx=160, cy=320, w=120, h=300), aspect-fixed to 0.75.
    sw, sh = 120.0 * 1.25, 300.0 * 1.25  # 150 x 375 -> h dominates
    sw = sh * (288 / 384)  # 281.25
    tol_x, tol_y = sw / 288.0, sh / 384.0
    expected = _person_keypoints((160.0, 320.0), 24.0)
    for j, (ex, ey) in enumerate(expected):
        assert fig.keypoints[j][0] == pytest.approx(ex, abs=tol_x + 1e-3)
        assert fig.keypoints[j][1] == pytest.approx(ey, abs=tol_y + 1e-3)
    assert all(0.0 <= c <= 1.0 for c in fig.confidences)
    assert fig.confidences[0] == pytest.approx(0.9)


def test_detect_keypoints_two_figures_and_low_score_cut() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    det, pose = _fake_sessions(
        [
            (160.0, 320.0, 120.0, 300.0, 0.95),
            (480.0, 320.0, 120.0, 300.0, 0.91),
            (480.0, 320.0, 120.0, 300.0, 0.2),  # below DET_SCORE_MIN -> dropped
        ],
        (640, 640),
        kp_sets=[
            _person_keypoints((160.0, 320.0), 24.0),
            _person_keypoints((480.0, 320.0), 24.0),
            _person_keypoints((480.0, 320.0), 24.0),
        ],
    )
    sessions = dwpose.Sessions(det=det, pose=pose)
    image = np.zeros((640, 640, 3), dtype=np.uint8)
    detection = dwpose.detect_keypoints(image, sessions=sessions)
    assert len(detection.figures) == 2
    # Deterministic order: score desc (0.95 first).
    assert detection.figures[0].score > detection.figures[1].score
    # Each pose run got its own crop: figure 0's wrist sits left of figure 1's.
    assert detection.figures[0].keypoints[9][0] < detection.figures[1].keypoints[9][0]


def test_detect_keypoints_determinism() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    image = np.zeros((640, 320, 3), dtype=np.uint8)
    runs = []
    for _ in range(2):
        det, pose = _fake_sessions([(160.0, 320.0, 120.0, 300.0, 0.95)], (320, 640))
        detection = dwpose.detect_keypoints(image, sessions=dwpose.Sessions(det=det, pose=pose))
        runs.append(detection.to_dict())
    assert runs[0] == runs[1]


def test_detect_no_person() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)
    det = _FakeDetSession([], (320, 640))
    pose = _FakePoseSession([], [])
    image = np.zeros((640, 320, 3), dtype=np.uint8)
    detection = dwpose.detect_keypoints(image, sessions=dwpose.Sessions(det=det, pose=pose))
    assert detection.figures == []
    assert detection.to_dict()["figures"] == []


def test_simcc_shape_gate() -> None:
    np = pytest.importorskip("numpy", reason=NP_SKIP_REASON)

    class _BadPose(_FakePoseSession):
        def run(self, _outs, feeds):  # type: ignore[no-untyped-def]
            return [np.zeros((1, KEYPOINT_COUNT, 100), dtype=np.float32),
                    np.zeros((1, KEYPOINT_COUNT, 100), dtype=np.float32)]

    det, _ = _fake_sessions([(160.0, 320.0, 120.0, 300.0, 0.95)], (320, 640))
    with pytest.raises(InferenceError, match="SimCC"):
        dwpose.detect_keypoints(
            np.zeros((640, 320, 3), dtype=np.uint8),
            sessions=dwpose.Sessions(det=det, pose=_BadPose([], [])),
        )
