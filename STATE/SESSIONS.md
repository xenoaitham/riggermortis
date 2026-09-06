# Sessions

| Session | Date | Scope | Outcome |
|---|---|---|---|
| 1 | 2026-09-06 | Prior-art research + name checks; repo scaffold; Phase 0 core (canonical skeleton, mapper v1, presets, policy, CLI, bridge); add-on skeleton; 49 tests; Blender gate PASS | Phase 0 ~90%: synthetic gate green, real-rig gate (P0-15) + CI (P0-16) open |
| 2 | 2026-09-06 | P0-15 real-rig gate (Rigify metarig + generated, VRM sample, edge import script, mapper fixes); P0-16 CI + network-audit test; P0-17 review data model | **Phase 0 COMPLETE**: P0-15 gate passed (metarig 0 corrections, generated 706-bone rig 22/22, Seed-san VRM 0 corrections; Mixamo NEEDS-HUMAN honestly recorded; mapper v2 → D-007), CI skeleton + audit-hook network test (84 tests), review API (`propose_reassignment`, `ambiguity_rank`, CLI `--set`), P1-1 model manager done early (real pinned sha256s, live download verified). Gate: ruff + 84/84 + blender-verify PASS |
| 3 | 2026-09-06 | P1-2 DWPose ONNX wrapper → P1-4 canonical pose solve → P1-5 FK apply engine (+ P1-3 figures) | **Phase 1 engine COMPLETE**: P1-2 wrapper 0.85 s (budget <2 s), demo-faithful numpy (no cv2), `rigpose detect` CLI; P1-4 pure-stdlib 2.5D lift, 20-pose flip accept 18/20 (2 documented misses → D-008); P1-5 FK apply, 3 real rigs at 0.0000° (tol 0.5°); P1-3 FigureBoard; end-to-end smoke detect→solve→FK on real metarig green. 128/128 tests, ruff clean |
