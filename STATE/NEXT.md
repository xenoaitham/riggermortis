# NEXT SESSION SHOULD …

1. **P1-6 — add-on pose UX** (the user-visible BOOM): image picker in the
   N-panel, run `rigpose detect` via the established edge pattern (D-004:
   inference runs outside Blender; the add-on consumes the JSON payload),
   FigureBoard selection (P1-3 API is ready), then solve + FK and apply the
   rotation payload via bpy pose bones (`rotation_mode` AXIS_ANGLE).
   media: UI screenshot + first posed-rig render.
2. **P1-7 — review overlay**: ghost canonical skeleton over the image
   (canonical.rest_skeleton renderer already exists), per-joint confidence
   heat from `CanonicalPose.joint_confidence`, manual flip toggles (the two
   documented solver misses are the exact case it must rescue).
3. **P1-9 — 20-image benchmark harness** (10 photo / 10 anime): usable-rate
   metric per the Phase 1 gate; its anime number decides P1-8 (fallback
   estimator plan). The engine chain is proven end-to-end (S3 smoke);
   the harness mostly wraps `detect -> FigureBoard -> solve_pose -> FK`.
4. If the benchmark says DWPose holds ≥90% on the photo set: start P1-10
   (BOOM GIF via `xtask/render_demos.py --demo boom`).

Watch out for:
- Keep `rigpose detect` outside the network-audit test's command list (it
  lazy-imports numpy/onnxruntime; CI has neither).
- The two flip misses (D-008) are REPORTED via notes/confidence — do not
  "fix" them by tuning priors against the fixture set (that's overfitting);
  the review UI is the remedy.
- Blender-side pose application needs rotation_mode handling per pose bone
  and an undo push — verify headlessly via the established sentinel pattern.

Blocked / deferred (unchanged):
- Mixamo real export (Adobe login) — NEEDS-HUMAN.
- Publishing (GitHub repo, PyPI, Blender Extensions) — NEEDS-HUMAN; CI yml
  still has never run (first push will be its first run).
