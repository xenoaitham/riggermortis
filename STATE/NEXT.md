# NEXT SESSION SHOULD …

1. **P2-3 keyframed retarget** (the Phase-2 core rock): canonical per-frame
   payloads (already flowing from `rigpose pose-video`, P2-1) → a Blender
   ACTION on the mapped rig: sample each payload's rotations onto frames,
   root-motion option, wire `smoothing.reduce_keyframes` into the bake so
   actions stay lean. Gate context: dance + fight clips playable on 3 rigs
   (P2-8) needs this first. Extend `xtask/verify_pose_apply.sh` with a
   2-frame action bake check (frame A → frame B, both within 0.5°).
2. **P2-4 foot contact detection** (velocity + height heuristic on canonical
   ankle positions from the job payloads) — the input to the foot-slide gate.
3. If Phase-2 retarget lands early: **P3-3 structured policy refusals through
   MCP** (the refusal shapes are already designed in mcp/DESIGN.md and the
   skeleton answers structured errors — wire `riggermortis.policy` codes in),
   or P3-5's loopback socket bridge.
4. Cheap wins while gates run:
   - anime benchmark set: 3 slots still open (out/benchmark/SOURCES.md has
     the bar; drop LO-owned/CC0 art, rerun `python3 xtask/benchmark_poses.py`,
     re-decide P1-8 at n=10 — the detector no-person rate is the number).
   - windowed Blender screenshot (xtask/ui_screenshot.sh) is flaky ~3-in-4 on
     this box (GL startup/teardown) — the one capture that succeeded is real
     and verified; a second stable capture would be nice for README (P7-1).

Watch out for:
- `make pose-verify` needs local assets (out/real_rigs/*, out/payloads/*,
  out/benchmark/images/*) — all present as of S5; regenerate per
  docs/BENCHMARKS.md reproduce blocks if you switch machines.
- Payload format is **2** everywhere now (core payload.py is the single
  contract: write v2, read v1+v2). The add-on, video jobs, and MCP all go
  through it — don't read payload dicts ad hoc.
- `CanonicalPose.toggled()` is the D-008 rescue primitive; review UI flip
  state lives in the addon's session `manual_flips` (payload files stay
  untouched).
- Windowed Blender under this box's GL segfaults on `space.show_region_ui`
  assignment from Python — do not reintroduce that in ui_screenshot.py.

Blocked / deferred (unchanged):
- Publishing (GitHub repo, PyPI, Blender Extensions) — NEEDS-HUMAN; CI yml
  has still never run (first push will be its first run).
- Mixamo real export (Adobe login) — NEEDS-HUMAN.
- Full Mimosa audit run — queued since S2 for an explicit human ask
  (pre-commit runs on partial-callgraph compatibility; one false-positive
  "SQL injection" on the addon UI file was grep-proven clean in S5).
