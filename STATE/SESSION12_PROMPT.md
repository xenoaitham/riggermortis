Session 12 prompt (riggermortis)
Project (30-second context)
riggermortis — local, free, rig-agnostic posing & animation engine: (1) Blender add-on, (2) MCP server so AI agents drive Blender. Drop a rigged model + reference image → pose applied. Drop a video → animation, retargeted, foot-slide-cleaned. Photos AND anime art. Toon renders, manga pages. No cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB: https://github.com/xenoaitham/riggermortis (public, MIT, branch main). CI IS GREEN (latest: eaeea95 — tests 3.11+3.13 at 264, blender-gate incl. export round-trip AND the 5-action session gate, media-guard all PASS).

Phases 0–2 closed (honest: D-011/D-015; real-clip half still NEEDS-HUMAN). Phase 3 CLOSED (S11): P3-1..P3-8 all done — stdio JSON-RPC server v0.3.0, 9-tool golden-pinned schema, progress streaming, session bridge (SessionHub queue, 127.0.0.1-only, token hello, poll claims one-shot, stale-on-disconnect), FOUR live action kinds (inspect_scene / apply_pose / bake_action / render_turntable), the extended session gate in CI, and the LAUNCH DEMO committed: make agent-demo = scripted stdio agent drives live headless Blender inspect → pose → animate → bake → turntable; docs/media/agent_turntable.gif (allowlist extended, 7 pinned outputs) + docs/AGENT_DEMO.md + verbatim transcript; SYNTHETIC motion + scripted-agent honesty labeled everywhere. P3-8: mcp/manifest.json pinned to the golden schema by test + docs/PUBLISHING.md registry runbook (submission account-bound). Phase 4 OPENED (S11): P4-1 DONE — toon presets as DATA FILES (addon/riggermortis_addon/presets/{anime,manga,western}.json) + addon/style.py build_toon_material = deterministic EEVEE node graph (banded N·L ColorRamp with double stops per cut = hard cel edges; Layer-Weight rim as black→WHITE mask, rim color lives in RimMix.B so dark ink contours work like bright rims; UNLIT by construction — Emission strength 1, scene-independent) + make style-verify (xtask/style_verify.sh + style_probe.py): three byte-deterministic rebuilds, per-preset graph assertions, ONE REAL EEVEE FRAME PER PRESET rendered headless on the dev box, visually checked (anime 3-band blue + white rim / manga 2-band ink + black contour / western 4-band warm). NOT in ci.yml yet (deliberate, documented in the gate header).

Remaining in Phase 4: P4-2 (Grease Pencil line art), P4-3 (screentones as compositor node groups + style packs as data files), P4-4 (multi-camera panel system), P4-5 (speech bubbles), P4-6 (PDF/EPUB/PNG export), P4-7 (animatic mode), P4-8 (the 6-page manga + 3-style hero).

STEP 0 — Session protocol (do this first, always)
Read, in order: STATE/NEXT.md (authoritative for S12 + env facts), STATE/TASKS.md, STATE/PROGRESS.md (S11 entries), STATE/DECISIONS.md (esp. D-008 no-prior-tuning, D-009 payload-consumer, D-013 lock v1, D-014 CI pin, D-015 Phase-2 close, D-016 tail rule), STATE/CONVENTIONS.md, STATE/SESSIONS.md.

Register yourself in STATE/SESSIONS.md as Session 12.

Claim tasks in STATE/TASKS.md by ticking + tagging [S12] before working.

Append timestamped PROGRESS lines per meaningful unit (real UTC via date -u — the S11 box runs UTC+2 local, so file mtimes lie; trust date -u).

Verify baseline: cd core && python3 -m pytest tests (expect 264 passed) and make lint PY=python3 from repo root (clean; the lint list now includes xtask/walk_job.py, xtask/agent_demo_docs.py, xtask/agent_demo_blender.py, xtask/style_probe.py — root ruff.toml covers addon/ + mcp/ + xtask/ with E,F,W,I,UP,B and E402/E501 ignored repo-wide; core keeps its own pyproject config).

Environment facts (verified through S11)
Blender 5.1.0 at /home/potato/blender-5.1.0-linux-x64/ — the REAL install. All gates PASS on it. CI deliberately keeps apt 4.0.2 (D-014; the S11 libegl1 install does NOT change that decision). Gates need explicit env or they 127 on PATH: BLENDER=/home/potato/blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/miniconda3/bin/python3 (conda BASE is the project env — system python3 has no pytest).
EEVEE RENDERS HEADLESS on the dev box (S11-verified, engine "BLENDER_EEVEE" in 5.1). Workbench renders everywhere. CI now installs libegl1 + libgl1 + libgl1-mesa-dri (the session gate renders in CI since S11); EEVEE-on-CI is still unknown — the style gate's honest SKIPPED path covers it, do not fake pixels.
S11 facts (do not reintroduce):
- ShaderNodeMix sockets: access BY IDENTIFIER via addon/style.py::_socket (Factor_Float / A_Color / B_Color / Result_Color). Name lookup grabs the float socket first; this Blender's bracket lookup does NOT resolve identifiers.
- Material slots: faces render SLOT 0 — clear/rebind slots when swapping the star material (flat-grey-sphere class). Rebuilds must REMOVE-then-create the datablock (create-first suffixes .001; late rename sticks .001 into the report).
- bake_action session executor order is LOCKED: tails repair FIRST (D-016) → core.load_action → certified composition (min_cutoff=None) → detect_contacts → lock_feet → real bake(contacts=) → RM_BAKE re-eval (FK roles bar 0.5°; plant-pin deviation reported separately as reeval_lock_dev_deg — do NOT merge them, locked legs deviate BY DESIGN).
- turntable.py restores everything it stages (camera, world, shading, resolution, hidden objects; worlds removed via bpy.data.worlds, objects via bpy.data.objects) and cycles the baked action PROPORTIONALLY (i * span // frames) for a clean loop.
- The demo + gate consume xtask/walk_job.py's fixture job (SYNTHETIC, generator-cited). Demo media rules: allowlist extensions ONLY in the same commit as the media; honest labels (scripted agent, synthetic motion) travel on the asset.
- animate_from_video's bake field is per-process honest: session_action (enqueue recipe) on bridge-enabled servers, not_implemented on stdio-only. The apply_style MCP tool is still DECLARED (schema v1) — wiring it as a session action is additive + gate-tested when the Phase-4 work justifies it.
- Shell glue: Mimosa intercepts bash writes of ANY source-looking file (even to /tmp) — use Write/Edit; and it blocked the S11 demo script twice on "command injection" until the echo lines became printf '%s' forms and $( ) was hoisted out of [ ] tests. json_field prints Python repr; use the json_value pattern for dicts.
- Mimosa commit hook: compatibility-basis note on every commit/push is NORMAL (never claim project-wide safety). If a finding BLOCKS: verify it's real, fix inline, re-scan focused (mcp__plugin_mimosa_mimosa__security_scan_start, focusFiles), commit again.
Work order (claim in this sequence; stop cleanly wherever you run out)
A. P4-2 — Grease Pencil line art pass (the style system's next rock)
PROBE FIRST (the S11 lesson: verify the Blender capability before designing — EEVEE-headless was a probe win, this one is a real unknown): does Blender 5.1's Grease Pencil (post-GPv3 rewrite) still expose the LineArt modifier/stack, or whatever replaced it, in a scriptable headless path? Write the smallest probe that answers yes/no + the actual API shape. If 5.1 removed scriptable LineArt: STOP, record the finding in DECISIONS (D-017 class), and switch A to the honest fallback (P4-3 screentones next, line art re-scoped as a documented gap — never faked with hand-drawn strokes shipped as pipeline output).
If the probe passes: design in docs FIRST (a short P4-2 section in docs/BENCHMARKS.md or a docs/STYLE.md — line-art parameters as DATA, matching P4-1's preset pattern), then implement: line-art preset data file(s) consumed by a builder in the add-on (addon/style.py or a sibling module), deterministic like build_toon_material, composing OVER the P4-1 materials (banded fill + ink lines = the manga look).
Gate: extend xtask/style_probe.py's harness (same sphere scene or the bone-proxy) — line-art build assertions + one EEVEE/workbench frame per composed style, honest SKIPPED degradation, VISUAL CHECK before claiming anything.
Accept: every claim cites the probe/gate; determinism test (rebuild == report); no fabricated "hand-inked" media.
B. P4-3 — Screentone/halftone compositor node groups; style packs as data files
Compositor node groups (halftone dots/lines) generated from preset data files — same data-file discipline as P4-1; the manga preset's docstring deliberately does NOT fake tones (it awaits this).
Keep the graph deterministic and testable: parameterized dot size/angle/blend; verify via compositor-node assertions + one rendered frame per tone preset if EEVEE/compositor cooperates headless (compositor full-frame in background mode: probe first, honestly SKIPPED if the GPU context refuses).
Accept: preset JSON → node group mapping asserted; visual check; SKIPPED paths honest.
C. If A+B land green — wire style-verify into CI
One deliberate ci.yml commit per the D-014 style: the style gate's graph checks + honest SKIPPED renders should pass on apt 4.0.2 (it now has the libegl1 stack). If apt 4.0.2 chokes on anything, fix timing/deps — never fake results. Also consider wiring the P4-1+P4-2 style pack into the agent demo's turntable (a styled shot) — only if it stays honest and pipeline-generated.
Cheap wins while gates run
apply_style session action: the MCP tool is declared; if Phase 4 now has a real style surface, wiring apply_style(kind, params) → add-on executor is additive (kinds 4→5, golden pin update same-commit, gate extension) — do it only if the style builder API is stable by then.
Windowed UI screenshot attempt (best-effort ~1-in-4; replaces docs/media/ui_screenshot.png in place ONLY if genuine; S10/S11 precedent: misses are fine, never staged).
docs cross-checks: BENCHMARKS.md + AGENT_DEMO.md numbers vs current gates; mcp/README.md walkthrough still matches reality (it gained the bake/turntable lines in S11).
Non-negotiable rules (locked, from mission + CONVENTIONS)
QUALITY ABOVE ALL. Anything 80% done is 0% shipped. Fix feel before features.
LOCAL OR NOTHING. Zero outbound in default use; network-audit test stays green. The loopback socket is opt-in and binds 127.0.0.1 ONLY.
Rig-agnostic or fake. Ambiguity reported (skipped/notes/confidence), never swallowed.
Honest claims. No "perfect animation"; every claim cites a test, number, or GIF. Synthetic stays labeled synthetic (D-015); no fabricated root motion; walk-in-place is the accepted baseline. Media rule: allowlist extension in the SAME commit as the media; visual check before shipping any image.
Deterministic ops: keyed sorts; same input = same output (tested).
NO subprocess string in any .py (spawn lives in shell glue / user shell / agent). No sockets in core (D-003).
Core dependency-free except lazy [inference].
Conventions: Python ≥3.10-compat, Z-up / facing −Y / character-left = +X, canonical roles frozen API, refusal codes public API, ruff + pytest green before commits (CI runs on every push), STATE logs append-only, timestamps REAL via date -u.
Errors are actionable (message (hint: ...)) — never trace dumps.
Do NOT tune solve priors or contact thresholds against fixtures (D-008); do not loosen benchmark thresholds to move numbers (D-010..016).
18+ module stays default-OFF, core-enforced, nothing explicit committed (P6-4/P6-5 shape) — Phase 6 scope.
End of session (non-negotiable)
Tick claimed tasks in STATE/TASKS.md (completed vs partially-done with what remains). Append PROGRESS lines (real UTC via date -u). Top of STATE/NEXT.md: "NEXT SESSION SHOULD:" — write it for Session 13 (likely P4-4 multi-camera panels, or line-art re-scope if the S12 probe killed it). Update STATE/SESSIONS.md row. Commit + push (routine commits authorized; CI runs — keep it green). If a Mimosa finding blocks: verify it's real, fix inline, re-scan focused, commit again.

Known blockers (parked — do not burn time on them)
PyPI upload + Blender Extensions upload + MCP registry submission — account-bound (LO); docs/PUBLISHING.md has the runbooks (MCP section added S11).
Windowed Blender GL stability on this box — best-effort only (~1-in-4); never fake media to compensate.
P1-8a fallback estimator — parked (D-011/D-012), needs a licensing-clean candidate; park unless LO raises it.
CI Blender bump — DECIDED (D-014: keep apt 4.0.2 + python3-numpy + the S11 GL stack); only revisit per its trigger.
P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md has the criteria: single person, full body, side-ish view, ≥3 s, steady fps, named license or LO-owned with a provenance statement). The instruments re-run unchanged on a real clip — and the agent demo re-runs with it too.
