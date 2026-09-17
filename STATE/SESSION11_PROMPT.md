# Session 11 prompt (riggermortis)

## Project (30-second context)

riggermortis — local, free, rig-agnostic posing & animation engine: (1) Blender add-on, (2) MCP server so AI agents drive Blender. Drop a rigged model + reference image → pose applied. Drop a video → animation, retargeted, foot-slide-cleaned. Photos AND anime art. Toon renders, manga pages. No cloud, no accounts, no uploads, ever.

Repo: `/home/potato/osint/riggermortis` — LIVE ON GITHUB: https://github.com/xenoaitham/riggermortis (public, MIT, branch main). CI IS GREEN (latest: **e40df64** — tests 3.11+3.13, blender-gate incl. export round-trip **and the new session-verify E2E**, media-guard all PASS).

Phases 0, 1, 2 ALL COMPLETE (closed honestly: D-011 / D-015, real-clip half still NEEDS-HUMAN). Phase 3: P3-1..P3-6 DONE — stdio JSON-RPC server v0.3.0, 9 tool schemas (golden-pinned), refusals byte-exact, progress streaming, AND **P3-5 session bridge live**: `mcp/session_bridge.py` (SessionHub queue + honest ledger, 127.0.0.1-only transport, token-required hello, poll claims one-shot, stale-on-disconnect never re-sent) + 3 live tools (`session_status` / `enqueue_action` / `action_result`) + add-on client (`addon/riggermortis_addon/session.py` — background thread never touches bpy; main-thread pump executes through the REAL D-009 apply path; N-panel "Agent session (MCP)"). Server starts the bridge ONLY with both `--session-port` AND `--session-token`. P2-8a also DONE: add-on tail normalization with the CORRECTED rule (**D-016**: absurd-ratio 10x + co-located-child skip; sane max ~5.1x vs glTF garbage ≥ ~76x, measured; `addon/tails.py` and `xtask/walk_media.py` in LOCKSTEP). WALKRIGS now: metarig 21.7x / seedsan 12.0x / xbot 21.1x (all ≥5x PASS). P3-6 DONE: `mcp/README.md` walkthrough + `mcp/examples/` configs.

Remaining in Phase 3: **P3-7 E2E agent demo (the launch GIF)** and P3-8 registry prep.

Cleanup pipeline order (documented): load_action → condition_action(hip_stabilize=…) → detect_contacts → lock_feet → bake(contacts=) → export via `make export-verify`. The CERTIFIED lock composition runs WITHOUT the 1€ pass (min_cutoff=None) — keep media and gates on it.

## STEP 0 — Session protocol (do this first, always)

Read, in order: STATE/NEXT.md (authoritative for S11 + env facts), STATE/TASKS.md, STATE/PROGRESS.md (S10 entries), STATE/DECISIONS.md (esp. D-008 no-prior-tuning, D-013 lock v1 scope, D-014 CI pin, D-015 Phase-2 close + glTF tail finding, **D-016 tail-rule amendment**), STATE/CONVENTIONS.md, STATE/SESSIONS.md.

Register yourself in STATE/SESSIONS.md as **Session 11**.

Claim tasks in STATE/TASKS.md by ticking + tagging [S11] before working.

Append timestamped PROGRESS lines per meaningful unit (**real UTC via `date -u`** — S10 had to re-stamp invented times; don't repeat that).

Verify baseline: `cd core && python3 -m pytest tests` (expect **261 passed**) and `make lint PY=python3` from repo root (clean; the lint list now includes `mcp/riggermortis_mcp.py`, `mcp/session_bridge.py`, `xtask/session_probe.py` — there is a **root `ruff.toml`** since S10: core standard E,F,W,I,UP,B with E402/E501 ignored repo-wide, core keeps its own pyproject config).

## Environment facts (verified through S10)

- Blender 5.1.0 at `/home/potato/blender-5.1.0-linux-x64/` — the REAL install. All gates PASS on it. CI deliberately keeps apt 4.0.2 (D-014); the session-verify gate now runs in CI on 4.0.2 (was stable twice on 5.1.0 — if it flakes in CI, fix timing budgets, never fake results).
- Gates need the right env or they 127 on PATH: `BLENDER=/home/potato/blender-5.1.0-linux-x64/blender`, `RIGPOSE=/home/potato/miniconda3/bin/rigpose`, `PY=/home/potato/miniconda3/bin/python3` (blender-verify uses RIGPOSE; system python3 has no pytest — conda BASE is the project env).
- S10 facts (do not reintroduce): **`pose_bone.matrix` is ARMATURE-space** — world needs `matrix_world` (the metarig's identity transform hid this for 9 sessions). **glTF/VRM imports BAKE a skin pose into `matrix_basis`** (66/67 non-identity on Xbot) — evaluated-vs-rest is only meaningful calibrated against sane rigs, never absolute. **Blender's Python sockets have no `__dict__`** — never stash attributes on a socket object (the session client carries its readline handle on itself). Tail repair runs BEFORE posing (posing first invalidates stored rotations when rest frames change).
- D-016 rule is LOCKED: don't loosen the pose gate's calibrated sane-band bars (Xbot fixed lift ∈ [0.15, 0.40] m; raw > 1.0 m and > 3x fixed) without re-measuring the certified rigs. Metarig noop must stay 0.
- Session bridge contract: action kinds `inspect_scene` / `apply_pose` live, `bake_action` declared → honest `not_implemented` through the full round trip. Dispatched actions are never silently re-sent; idempotency is the enqueuer's concern. Token lives on WindowManager (session-only, never saved to disk).
- Every push runs CI — keep it green. CI installs the LATEST ruff.
- media-guard pins 6 files: docs/media/{boom.gif, ui_screenshot.png, walk_lock_metarig.gif, walk_lock_seedsan.gif, walk_lock_xbot.gif, walk_3rigs.gif}. Extending the allowlist = deliberate, documented Makefile change in the same commit as the media. `make walk-gifs` regenerates walk media (needs LOCAL rigs — not a CI target).
- Headless realities: workbench renders fine; gpu/GPUOffScreen reports SKIPPED honestly in background; armature bones don't render (bone-proxy pattern in render_demos.py); render staging forces FLAT shading + explicit background world; windowed Blender is flaky (~1-in-4) — best-effort, never fake media (S10 attempt missed; the genuine S5 capture stays).
- Payload format 2 everywhere; core/payload.py is the single contract; actions load ONLY through it (D-009). Local assets (git-ignored): out/real_rigs/ (metarig.blend, rigify_generated.blend, Seed-san.vrm, Xbot.glb — all with .rig.json), out/payloads/, out/benchmark/images/{photo,anime}/, out/video_smoke/, out/p28/.
- Network-audit test must stay green; `--gpu` = CUDA opt-in only. The loopback transport is opt-in; default stdio opens zero sockets (audit-tested, with positive control).
- MCP server: mcp/riggermortis_mcp.py (v0.3.0) + mcp/session_bridge.py; tests in core/tests/test_mcp_server.py + test_mcp_session.py.
- Mimosa commit hook: compatibility-basis note on every commit/push is NORMAL (never claim project-wide safety from it). If a finding BLOCKS: verify it's real, fix inline, re-scan focused (`mcp__plugin_mimosa_mimosa__security_scan_start`, focusFiles), commit again. S10 note: it once false-positived "SQL injection" on an f-string status message in the bpy add-on — restructuring the edit into smaller candidates cleared it; use Write/Edit for .py files, never bash heredocs/sed. S10's focused scan on the new session/tails code: 0 findings, sealed.
- PATH can go stale mid-session (box crash symptom): conda BASE is the project env — see above.

## Work order (claim in this sequence; stop cleanly wherever you run out)

### A. P3-7 — E2E agent demo run (the Phase-3 gate; P3-5 unblocked it)

Design the action set FIRST in mcp/DESIGN.md (extend the session-bridge section):

1. Implement the declared **`bake_action`** session action — params keyed on a video job_dir: the add-on's REAL `bake.bake_action(contacts=...)` path over `core.load_action(job_dir)` → certified composition (stabilize → detect → lock, min_cutoff=None). This closes `animate_from_video`'s honestly-`not_implemented` rig-space half through the loopback. Gate: extend `xtask/session_verify.sh` (it's the harness) — bake a real fixture job in headless Blender through the queue and verify the baked action's frames re-evaluate ≤0.5° (the existing RM_BAKE instrument pattern).
2. Add a **`render_turntable`** action reusing `xtask/render_demos.py` staging (bone-proxy + FLAT shading + explicit world; compose through `matrix_world` — S9/S10 lessons).
3. Then the demo itself: a real agent conversation (stdio JSON-RPC over the server's stdin/stdout — the shell-glue pattern from session_verify.sh is the client) driving a live Blender: inspect → pose → animate (job) → render turntable — collected via action_result. Media: the **agent-driven turntable GIF** = pipeline-generated only, committed under docs/media/ WITH the media-guard allowlist extension in the same commit; honest labels (what was real-time vs scripted; the agent transcript cited in docs).

Accept: every claim cites a test or the gate; DESIGN.md updated; no fabricated root motion; walk-in-place stays the baseline.

### B. P3-8 — MCP registry listing prep (if A lands)

Manifest metadata + honest capability list citing the golden schema (9 tools, statuses), docs/PUBLISHING.md addition; no registry submission (account-bound, LO).

### C. If A+B land green

Open Phase 4 (P4-1 toon shader presets on EEVEE — banded shading + rim; presets as data files).

Cheap wins while gates run: windowed UI screenshot attempt (best-effort ~1-in-4; replaces docs/media/ui_screenshot.png in place ONLY if genuine); `docs/EXPORT.md`/BENCHMARKS cross-checks against current numbers.

## Non-negotiable rules (locked, from mission + CONVENTIONS)

- QUALITY ABOVE ALL. Anything 80% done is 0% shipped. Fix feel before features.
- LOCAL OR NOTHING. Zero outbound in default use; network-audit test stays green. The loopback socket is opt-in and binds 127.0.0.1 ONLY.
- Rig-agnostic or fake. Ambiguity reported (skipped/notes/confidence), never swallowed.
- Honest claims. No "perfect animation"; every claim cites a test, number, or GIF. Synthetic stays labeled synthetic (D-015); no fabricated root motion; walk-in-place is the accepted baseline.
- Deterministic ops: keyed sorts; same input = same output (tested).
- NO `subprocess` string in any .py (spawn lives in shell glue / user shell / agent). No sockets in core (D-003).
- Core dependency-free except lazy [inference].
- Conventions: Python ≥3.10-compat, Z-up / facing −Y / character-left = +X, canonical roles frozen API, refusal codes public API, ruff + pytest green before commits (CI runs on every push), STATE logs append-only, timestamps REAL via `date -u`.
- Errors are actionable (`message (hint: ...)`) — never trace dumps.
- Do NOT tune solve priors or contact thresholds against fixtures (D-008); do not loosen benchmark thresholds to move numbers (D-010..016).
- 18+ module stays default-OFF, core-enforced, nothing explicit committed (P6-4/P6-5 shape) — Phase 6 scope.

## End of session (non-negotiable)

Tick claimed tasks in STATE/TASKS.md (completed vs partially-done with what remains).
Append PROGRESS lines (real UTC via `date -u`).
Top of STATE/NEXT.md: "NEXT SESSION SHOULD:" — write it for Session 12 (likely P3-8 finish / Phase 4 opening if P3-7 closes Phase 3).
Update STATE/SESSIONS.md row.
Commit + push (routine commits authorized; CI runs — keep it green). If a Mimosa finding blocks: verify it's real, fix inline, re-scan focused, commit again.

## Known blockers (parked — do not burn time on them)

- PyPI upload + Blender Extensions upload — account-bound (LO); docs/PUBLISHING.md has the one-command runbooks.
- Windowed Blender GL stability on this box — best-effort only; never fake media to compensate.
- P1-8a fallback estimator — parked (D-011/D-012), needs a licensing-clean candidate; park unless LO raises it.
- CI Blender bump — DECIDED (D-014: keep apt 4.0.2 + python3-numpy); only revisit per its trigger.
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md has the criteria: single person, full body, side-ish view, ≥3 s, steady fps, named license or LO-owned with a provenance statement). The WALKRIGS/FOOTLOCK/HIPSTAB instruments re-run unchanged on a real clip when one lands.
