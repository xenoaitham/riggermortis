# NEXT SESSION SHOULD …

1. **P1-8 decision is explicitly pending on sourcing** (NEEDS-HUMAN): the
   benchmark harness is done and honest, but only 1 photo + 1 anime image
   exist locally. Source 10+10 licensing-clean images (CC0/OWN collections;
   never commit scraped files), rerun `python3 xtask/benchmark_poses.py`,
   and let the anime number decide the fallback-estimator plan.
2. **P1-11 polish pass** (the known rough edges, all documented in TASKS):
   - review overlay interactivity: joint picking, in-viewport flip toggles,
     image-plane projection onto the reference empty;
   - multi-figure payloads (embed all figures in one payload so the panel can
     switch without re-running the CLI);
   - UI screenshot for the README (needs xvfb or a display — do not fake);
   - BOOM GIF framing polish (pose-centroid camera target).
3. **Then open Phase 2** (video pipeline): P2-1 video reader + per-frame
   detection is the first rock; the payload path (D-009) extends to per-frame
   rotation payloads. Phase 3 (MCP server) can start in parallel per
   mcp/DESIGN.md — the payload contracts are exactly the tool outputs.

Watch out for:
- `verify_pose_apply.sh` + `render_boom.sh` need local assets
  (out/real_rigs/*, out/benchmark/images/*) — regenerate per
  docs/BENCHMARKS.md reproduce blocks before running.
- Blender background mode has NO GPU API (`gpu` module, GPUOffScreen) —
  overlay offscreen checks must stay honestly SKIPPED there; workbench/EEVEE
  renders DO work headlessly on this machine (EGL).
- Keep `rigpose detect` / `rigpose pose` out of the network-audit command
  list (lazy [inference] imports; CI has neither).
- Do NOT tune solve priors against fixtures (D-008) — the review UI is the
  remedy for the two documented miss classes.

Blocked / deferred (unchanged):
- Mixamo real export (Adobe login) — NEEDS-HUMAN.
- Publishing (GitHub repo, PyPI, Blender Extensions) — NEEDS-HUMAN; CI yml
  still has never run (first push will be its first run).
- Benchmark image sourcing (10 photo / 10 anime, licensing-clean) — NEEDS-HUMAN.
