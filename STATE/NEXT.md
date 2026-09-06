# NEXT SESSION SHOULD …

1. **P1-2 — DWPose ONNX wrapper** (the engine start of Phase 1). The model
   manager (P1-1) is done: `rigpose models download|verify|list` works against
   the real pinned manifest. Next:
   - `core/src/riggermortis/inference/dwpose.py`: lazy-import `onnxruntime` +
     `numpy` (CORE_MISSING_HINT-style error pointing at
     `pip install riggermortis-core[inference]`); run the two-stage pipeline
     (yolox_l detector → dw-ll_ucoco_384, 133 keypoints), CPU first.
   - accept: <2 s CPU per image; test with a tiny synthetic raster (no real
     model download in tests — mock the session objects).
   - models are stored via `riggermortis.inference.models.model_path()`;
     never auto-download.
2. **P1-4 — keypoints → canonical pose solve** (2D→3D lift, symmetry,
   smoothing, elbow/knee flip disambiguation; accept: flip test on 20 poses).
3. **P1-5 — FK apply engine** (canonical pose → any mapped rig, rest-offset
   aware, undo-friendly; accept: same pose on 3 rigs).
4. Optional prep for P1-3 (multi-figure detection data model) if the wrapper
   lands early.

Also worth 10 minutes:
- Add a CI badge + the real-rig gate table link to README once publishing
  (NEEDS-HUMAN) unblocks.
- `rigpose models download all` currently serializes; parallel downloads are
  unnecessary (two models, rare event) — leave as-is unless P1-2 wants it.

Blocked / deferred:
- Mixamo real export (Adobe login) — P0-15 recorded the gap honestly;
  synthetic Mixamo fixture covers the naming traps.
- Publishing (GitHub repo, PyPI, Blender Extensions) — NEEDS-HUMAN accounts.
- Session 2's CI yml has NOT run yet (no remote); first push will be its
  first run — expect Blender-gate tuning (apt package name / runtime deps).
