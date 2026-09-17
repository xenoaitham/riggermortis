# NEXT SESSION SHOULD …

1. **P3-5 — Blender session manager** (add-on ↔ server loopback socket, action
   queue). DESIGN THE PROTOCOL IN mcp/DESIGN.md FIRST, then implement; socket
   code lives in mcp/ + add-on only (no sockets in core, D-003), 127.0.0.1
   bind ONLY, the network-audit test must stay green (server transports are
   opt-in). This unblocks the P3-7 E2E agent demo (its launch GIF).
2. **P2-8a — add-on tail normalization** (small, from S9's D-015 finding):
   conditional glTF/VRM bone-tail repair at import time in the add-on (same
   deterministic rule as xtask/walk_media.py `_repair_imported_tails`) +
   a Blender probe in the pose-apply gate proving posed children no longer
   ladder on Xbot.glb. Small but real: without it, add-on users posing
   imported rigs hit broken evaluated placement.
3. **P3-6 example agent configs + docs walkthrough** if P3-5 lands fast.
4. Phase 4 opening (toon shaders) if Phase 3's rocks are done.

Watch out for:
- **Blender 5.1.0 at `/home/potato/blender-5.1.0-linux-x64/` is the real
  install**; CI deliberately keeps apt 4.0.2 (D-014). `Action.fcurves` is
  GONE in 5.x (slotted actions) — probe BOTH APIs for action introspection
  (see xtask/export_clip.sh).
- **S9 bake lessons (do not reintroduce):** the 2-bone lock solve takes
  lengths from HEAD-TO-HEAD rest distances, NOT `Bone.length` (glTF tails can
  be ~100x garbage, D-015); `lock_at` carries a LIST of (foot, interval) per
  frame — double-support frames pin BOTH feet; the bone proxy composes
  vertices through `armature.matrix_world` (imported rigs carry object
  scale); render staging forces FLAT shading + an explicit background world
  (glTF imports can carry a black world; sun/STUDIO silhouettes at some
  angles).
- The certified lock composition is stabilize → detect → lock WITHOUT the 1€
  pass (test_pipeline_condition_detect_lock_still_gates runs min_cutoff=None);
  on the synthetic generator, smoothing lags swing-landings into stance
  (phantom slide + unreachable pins). Keep media + gates on the certified
  composition.
- PATH can go stale after a box crash: conda BASE is the project env
  (`~/miniconda3/bin/python`, `RIGPOSE=/home/potato/miniconda3/bin/rigpose`).
- Noqa rule: no stale `# noqa` (RUF100); used ones are fine.
- Windowed Blender GL is flaky on this box (~1-in-4): the UI screenshot
  re-capture stays best-effort, never staged.

Blocked / deferred (unchanged unless noted):
- PyPI + Blender Extensions uploads — account-bound (LO);
  docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- CI Blender bump — DECIDED (D-014).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
  instruments (FOOTLOCK/HIPSTAB/WALKRIGS) re-run unchanged on a real clip.
