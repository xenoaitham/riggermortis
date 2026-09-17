# SESSION 10 — Phase 3 push: P3-5 session manager (+ P2-8a, then P3-6 if fast)

## Project (30-second context)

**riggermortis** — local, free, rig-agnostic posing & animation engine:
(1) Blender add-on, (2) MCP server so AI agents drive Blender. Drop a rigged
model + reference image → pose applied. Drop a video → animation, retargeted,
foot-slide-cleaned. Photos AND anime art. Toon renders, manga pages. No cloud,
no accounts, no uploads, ever.

- Repo: `/home/potato/osint/riggermortis` — LIVE ON GITHUB:
  https://github.com/xenoaitham/riggermortis (public, MIT, branch `main`).
  **CI IS GREEN** (latest: 60d4fb2 — tests 3.11+3.13, blender-gate incl. the
  export round-trip, media-guard all PASS).
- Phases 0, 1, 2 ALL COMPLETE. Phase 2 closed honestly (D-015): the real-clip
  gate is recorded NOT-met-with-real-clips (NEEDS-HUMAN stands); the media is
  the labeled SYNTHETIC walk × 3 rigs (`make walk-gifs`), per-rig WALKRIGS
  block in docs/BENCHMARKS.md (lock 21x/12x/21x vs the published ≥5× gate).
- Phase 3: P3-1..P3-4 DONE — stdio JSON-RPC server v0.2.0, 5+1 tool schemas
  (golden-pinned), inspect_rig + policy_status + policy_check live, P3-3
  refusals byte-exact vs `Refusal.to_dict()`, **P3-4 progress streaming**
  (`notifications/progress`, token-gated, `animate_from_video` LIVE for its
  canonical half — rig-space bake honestly `not_implemented`; capability
  flag true). Remaining: P3-5 session manager, P3-6 example configs,
  P3-7 E2E agent demo (needs P3-5), P3-8 registry prep.
- Cleanup pipeline order (documented): `load_action →
  condition_action(hip_stabilize=…) → detect_contacts → lock_feet →
  bake(contacts=) → export via `make export-verify``. The CERTIFIED lock
  composition runs WITHOUT the 1€ pass (`min_cutoff=None`) — keep media and
  gates on it (test_pipeline_condition_detect_lock_still_gates).

## STEP 0 — Session protocol (do this first, always)

1. Read, in order: `STATE/NEXT.md` (authoritative for S10 + env facts),
   `STATE/TASKS.md`, `STATE/PROGRESS.md` (S9 entries),
   `STATE/DECISIONS.md` (esp. D-008 no-prior-tuning, D-013 lock v1 scope,
   D-014 CI pin, **D-015 Phase-2 close + glTF tail finding**),
   `STATE/CONVENTIONS.md`, `STATE/SESSIONS.md`.
2. Register yourself in `STATE/SESSIONS.md` as Session 10.
3. Claim tasks in `STATE/TASKS.md` by ticking + tagging [S10] before working.
4. Append timestamped PROGRESS lines per meaningful unit (real UTC via
   `date -u`).
5. Verify baseline: `cd core && python3 -m pytest tests` (expect **241
   passed**) and `make lint PY=python3` from repo root (clean; the lint list
   now includes xtask/walk_media.py, xtask/assemble_walk.py, xtask/walk_docs.py).

## Environment facts (verified through S9)

- **Blender 5.1.0 at `/home/potato/blender-5.1.0-linux-x64/` — the REAL
  install.** All gates PASS on it. CI deliberately keeps apt 4.0.2
  **plus `python3-numpy`** (D-014; do not "fix" the pin silently).
- **Blender 5.x API change:** `Action.fcurves` is GONE (slotted actions) —
  probe BOTH APIs (`xtask/export_clip.sh` pattern).
- **S9 bake lessons (do not reintroduce):**
  - The 2-bone lock solve takes lengths from **head-to-head rest
    distances**, NOT `Bone.length` (glTF tails can be ~100× garbage —
    D-015).
  - `lock_at` carries a **LIST** of (foot, interval) per frame —
    double-support frames pin BOTH feet.
  - The bone proxy composes vertices through `armature.matrix_world`
    (imported rigs carry object scale; Xbot imports at 0.01).
  - Render staging forces **FLAT shading + an explicit background world**
    (glTF imports can carry a black world; sun/STUDIO silhouettes at some
    angles).
  - Drift metrics are **WORLD units** (armature-local units are
    incomparable across rigs).
- **PATH can go stale mid-session** (box crash symptom): if `python3 -m ruff`
  404s, the project env is conda BASE — use
  `/home/potato/miniconda3/bin/python3` (and
  `RIGPOSE=/home/potato/miniconda3/bin/rigpose` for gate scripts). `git push`
  may fail with a credential error inside the sandbox — the gh helper is
  fine; retry the push unsandboxed.
- **Mimosa commit hook:** blocks on findings; fix the real substance, then
  re-verify with a focused scan (`mcp__plugin_mimosa_mimosa__security_scan_start`,
  `focusFiles`) — a clean sealed scan + inline confinement cleared S9's
  4x-blocked "path-traversal entry" finding (argv-less `main()` + confinement
  inline in main was what the fast hook accepted). The standing
  "partial callgraph / compatibility basis" note is normal — never claim
  project-wide safety from it. No `subprocess` string in any `.py` (use
  Write/Edit for .py files, never bash heredocs).
- Every push runs CI — keep it green. CI installs the LATEST ruff.
- media-guard pins **6 files** now: docs/media/{boom.gif, ui_screenshot.png,
  walk_lock_metarig.gif, walk_lock_seedsan.gif, walk_lock_xbot.gif,
  walk_3rigs.gif}. Extending the allowlist = deliberate, documented Makefile
  change in the same commit as the media. `make walk-gifs` regenerates the
  walk media (needs LOCAL rigs — not a CI target).
- Headless realities: workbench renders fine; `gpu`/GPUOffScreen report
  SKIPPED honestly in background; armature bones don't render (bone-proxy
  pattern in `render_demos.py` — now with optional `bone_names` filter);
  windowed Blender is flaky (~1-in-4) — best-effort, never fake media.
- Payload format 2 everywhere; `core/payload.py` is the single contract;
  actions load ONLY through it (D-009); `load_action` is now a core package
  export. Local assets (git-ignored): `out/real_rigs/` (metarig.blend,
  rigify_generated.blend, Seed-san.vrm, Xbot.glb — all with .rig.json),
  `out/payloads/`, `out/benchmark/images/{photo,anime}/` (10+10),
  `out/video_smoke/` (person.mp4 near-static; mmpose_dance.mp4 = 1 s @ 5 fps
  seed; real walk clip still NEEDS-HUMAN), `out/p28/` (S9 manifests/frames).
- Network-audit test must stay green; `--gpu` = CUDA opt-in only.
- MCP server: `mcp/riggermortis_mcp.py` (v0.2.0), tests in
  `core/tests/test_mcp_server.py` (golden schema + streaming end-to-end with
  a fixture job — `params._meta.progressToken`, silent without one).

## Work order (claim in this sequence; stop cleanly wherever you run out)

### A. P3-5 — Blender session manager (the Phase-3 rock)

1. **DESIGN THE PROTOCOL FIRST in `mcp/DESIGN.md`**: add-on ↔ server loopback
   socket (127.0.0.1 bind ONLY — never external), message shapes, the action
   queue semantics (enqueue/status/result, honest failure ledger), reconnect
   behavior, what happens when Blender is closed. Get the contract right
   before code.
2. Socket code lives in **mcp/ + addon/ ONLY** (D-003: core stays
   process-free AND socket-free). The server transport stays opt-in — the
   default path is still stdio; the **network-audit test must stay green**
   (default use opens zero sockets).
3. Implement add-on side (connect to the server, submit/collect actions) +
   server side (loopback transport, queue) + tests like any tool (faked
   socket pairs are fine; a real loopback probe on 127.0.0.1 is better —
   it's still "no external network").
4. Accept: an agent can enqueue an action (e.g. inspect_rig result delivery,
   pose apply request) and collect the structured result through the queue
   while Blender stays interactive; every claim cites a test; DESIGN.md is
   the source of record.
5. Do NOT tune gates or relabel anything (D-008, D-010..015).

### B. P2-8a — add-on tail normalization (small, from S9's D-015 finding)

- Conditional glTF/VRM bone-tail repair in the ADD-ON (same deterministic
  rule as `xtask/walk_media.py::_repair_imported_tails`: chain tails →
  nearest child head within 1%; leaves only when absurdly long; sane rigs
  bit-for-bit untouched), wired so users posing imported rigs don't hit the
  evaluated-placement breakage.
- Add a probe to `xtask/verify_pose_apply.sh` on Xbot.glb proving posed
  children no longer ladder (foot head stays near ground after apply with
  repair on).
- Keep the pose-apply gate's existing numbers byte-identical (metarig must
  be untouched).

### C. If A+B land green

- **P3-6 example agent configs** (Claude Desktop, Cursor) + docs walkthrough
  (5-minute connect), citing the tested server surface only.
- Cheap wins while gates run: windowed UI screenshot attempt on 5.1
  (`xtask/ui_screenshot.sh`, best-effort ~1-in-4, replaces
  `docs/media/ui_screenshot.png` in place if genuine, never staged);
  `docs/EXPORT.md`/BENCHMARKS cross-checks (no doc calls the synthetic
  numbers real).

## Non-negotiable rules (locked, from mission + CONVENTIONS)

1. QUALITY ABOVE ALL. Anything 80% done is 0% shipped. Fix feel before
   features.
2. LOCAL OR NOTHING. Zero outbound in default use; network-audit test stays
   green. The loopback socket is opt-in and binds 127.0.0.1 ONLY.
3. Rig-agnostic or fake. Ambiguity reported (skipped/notes/confidence), never
   swallowed.
4. Honest claims. No "perfect animation"; every claim cites a test, number,
   or GIF. Synthetic stays labeled synthetic (D-015); no fabricated root
   motion; walk-in-place is the accepted baseline.
5. Deterministic ops: keyed sorts; same input = same output (tested).
6. NO `subprocess` string in any Python file. Spawn lives in shell glue /
   user shell / agent. No sockets in core (D-003).
7. Core dependency-free except lazy `[inference]`.
8. Conventions: Python ≥3.10-compat, Z-up / facing −Y / character-left = +X,
   canonical roles frozen API, refusal codes public API, ruff + pytest green
   before commits (CI runs on every push), STATE logs append-only.
9. Errors are actionable (`message (hint: ...)`) — never trace dumps.
10. Do NOT tune solve priors or contact thresholds against fixtures
    (D-008); do not loosen benchmark thresholds to move numbers
    (D-010..015).
11. 18+ module stays default-OFF, core-enforced, nothing explicit committed
    (P6-4/P6-5 shape) — Phase 6 scope.

## End of session (non-optional)

1. Tick claimed tasks in `STATE/TASKS.md` (completed vs partially-done with
   what remains).
2. Append PROGRESS lines (real UTC via `date -u`).
3. Top of `STATE/NEXT.md`: "NEXT SESSION SHOULD:" — write it for Session 11
   (likely P3-6/P3-7 E2E agent demo — its launch GIF needs P3-5 — or Phase 4
   opening if Phase 3's rocks are done).
4. Update `STATE/SESSIONS.md` row.
5. Commit + push (routine commits authorized; CI runs — keep it green). If a
   Mimosa finding blocks: verify it's real, fix inline, re-scan focused,
   commit again (see the S9 recipe under Environment facts).

## Known blockers (parked — do not burn time on them)

- PyPI upload + Blender Extensions upload — account-bound (LO);
  docs/PUBLISHING.md has the one-command runbooks.
- Windowed Blender GL stability on this box — best-effort only; never fake
  media to compensate.
- P1-8a fallback estimator — parked (D-011/D-012), needs a licensing-clean
  candidate; park unless LO raises it.
- CI Blender bump — DECIDED (D-014: keep apt 4.0.2 + python3-numpy); only
  revisit per its trigger.
- P2-8 real walking clip — NEEDS-HUMAN (`out/video_smoke/SOURCES.md` has the
  criteria: single person, full body, side-ish view, ≥3 s, steady fps, named
  license or LO-owned with a provenance statement). The WALKRIGS/FOOTLOCK/
  HIPSTAB instruments re-run unchanged on a real clip when one lands.
