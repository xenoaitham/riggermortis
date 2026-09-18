# Session 13 prompt (riggermortis)

**Project (30-second context)**
riggermortis — local, free, rig-agnostic posing & animation engine: (1)
Blender add-on, (2) MCP server so AI agents drive Blender. Drop a rigged
model + reference image → pose applied. Drop a video → animation,
retargeted, foot-slide-cleaned. Photos AND anime art. Toon renders, manga
pages. No cloud, no accounts, no uploads, ever.

Repo: `/home/potato/osint/riggermortis` — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main). CI
IS GREEN (latest: 896690d — tests 3.11+3.13 at 264, blender-gate incl.
session + export + **style** gates, media-guard all PASS).

Phases 0–3 CLOSED (honest: D-011/D-015; real-clip half still
NEEDS-HUMAN). Phase 4 OPEN. Style system through P4-3: **P4-1** toon
materials + **P4-2** Grease Pencil line art + **P4-3** screentones — all
as DATA-FILE presets (`addon/riggermortis_addon/presets/
{anime,manga,western}.json`, fields `bands`/`rim`/`lineart`/`tones`; anime
deliberately has NO tones) + deterministic builders in `addon/style.py`
(`build_toon_material` / `build_lineart` / `build_screentones` +
`remove_lineart` / `remove_screentones`). Gate = `make style-verify`
(style_probe.py), IN CI since S12 with honest SKIPPED halves on apt 4.0.2;
the dev box runs the full gate with real EEVEE pixels. Source of record:
docs/STYLE.md.

Remaining in Phase 4: **P4-4** (multi-camera panel system + layout
presets, manga RTL / western LTR), P4-5 (speech bubbles), P4-6
(PDF/EPUB/PNG export), P4-7 (animatic mode), P4-8 (the 6-page manga +
3-style hero).

**STEP 0 — Session protocol (do this first, always)**
Read, in order: STATE/NEXT.md (authoritative for S13 + the S12
watch-outs), STATE/TASKS.md, STATE/PROGRESS.md (S12 entries),
STATE/DECISIONS.md (esp. D-008, D-009, D-013, D-014, D-015, D-016),
STATE/CONVENTIONS.md, STATE/SESSIONS.md, **docs/STYLE.md** (the style
system's source of record — keep it in sync).

Register yourself in STATE/SESSIONS.md as Session 13. Claim tasks in
STATE/TASKS.md by ticking + tagging [S13] before working. Append
timestamped PROGRESS lines per meaningful unit (real UTC via `date -u`).

Verify baseline: `cd core && /home/potato/miniconda3/bin/python3 -m pytest
tests` (expect **264 passed**) and `make lint
PY=/home/potato/miniconda3/bin/python3` from repo root (lint list now
includes `xtask/lineart_probe.py` + `xtask/tone_probe.py`).

**Environment facts (verified through S12)**
Blender 5.1.0 at `/home/potato/blender-5.1.0-linux-x64/` is the REAL
install. Gates need explicit env or they 127 on PATH (hit twice in S12):
`BLENDER=/home/potato/blender-5.1.0-linux-x64/blender`,
`RIGPOSE=/home/potato/miniconda3/bin/rigpose`,
`PY=/home/potato/miniconda3/bin/python3` (conda BASE is the project env).
EEVEE renders headless on the dev box AND on CI (llvmpipe — answered S12).
CI keeps apt 4.0.2 (D-014).

S12 facts (do not reintroduce):
- **GPv3 LineArt** (5.1): the ONLY working wiring is ops
  `grease_pencil_add(type='LINEART_OBJECT')` + renames — data-API builds
  evaluate 0 strokes, `target_material` assignment is Blender-blocked
  ("has to be used by the Grease Pencil object already"). Legacy GPv2 is
  GONE (objects are type GREASEPENCIL, no `grease_pencil_modifiers`
  stack). GPv3 layer API: `layers.new()`, `layer.name` (`.info` is
  legacy), layer needs its initial frame.
- **`bpy.context.object` is STALE after a render** — capture ops-created
  objects by DATABLOCK DIFF (`set(bpy.data.objects.keys())` before/after).
- **Compositor (5.1)**: the graph lives in `scene.compositing_node_group`
  (a node GROUP; `scene.node_tree` is GONE; unset = nothing composited).
  Sink = the group-output INTERFACE. **EXACTLY ONE Group Output node,
  created AFTER the interface socket** — a stale unlinked first one
  renders the whole frame BLACK. The interface gets rewritten behind the
  scenes and an EXISTING Group Output never refreshes after a socket
  change.
- Unified `ShaderNode*` classes work inside compositor trees
  (Math/Mix/SeparateXYZ/ValToRGB/VectorMath) but there is NO combine node
  of any flavor (`ShaderNodeCombineColor` is shader-only). The
  Python-subclass node enumeration returns NOTHING in 5.1 —
  construct-test candidates instead.
- **NO UV pass** under 5.1 EEVEE (RL outputs = Image/Alpha only).
  Coordinates come from the `rm_tones_uv` view layer whose
  `material_override` emits Generated coords.
- `ShaderNodeMix` sockets by IDENTIFIER via the scan pattern
  (`Factor_Float`/`A_Color`/`B_Color`/`Result_Color`) — in material AND
  compositor trees.
- **SUBTRACT operand order is load-bearing** in the tone chain
  (`bw - 1.0` silently kills it; the scene looks identical until you
  render the intermediate). Bisect by rendering intermediates through a
  ColorRamp.
- **Freestyle is a dead end in 5.1**: draws zero lines under EEVEE and
  Blender's internal Freestyle Python crashes. Recorded; never faked.
- bake_action session executor order is LOCKED (D-016 tails FIRST →
  core.load_action → certified composition min_cutoff=None → detect →
  lock → bake → RM_BAKE re-eval with the FK/locked split).
- turntable.py restores everything it stages; cycles actions
  proportionally.
- Mimosa intercepts bash writes of ANY source-looking file (even /tmp) —
  use Write/Edit; commit-hook compatibility note is normal, never claim
  project-wide safety. If a finding BLOCKS: verify real, fix inline,
  re-scan focused, commit again.

**Work order (claim in this sequence; stop cleanly wherever you run out)**

A. **P4-4 — Multi-camera panel system + layout presets** (the next rock
on the road to P4-8's 6-page manga).
DESIGN FIRST: a P4-4 section in docs/STYLE.md — panel layouts as DATA (a
page preset JSON: panel rectangles + per-panel camera binds + gutters/
bleed), same schema discipline as P4-1..P4-3 (format field, validator
fails loudly on unknown fields, manga RTL vs western LTR as layout data
not code forks). Then probe whatever Blender-uncertain part you pick as
the mechanism BEFORE building (candidates: per-panel camera +
border-render + composition; or compositor-based page assembly; the S12
probe files are the pattern — smallest script, evidence printed `RM_*`,
committed as an instrument). Implement: preset data file(s) +
deterministic builder + gate extension (graph asserts + determinism + one
rendered page per layout, honest SKIPPED degradation, VISUAL CHECK before
claiming anything).
Accept: every claim cites the probe/gate; determinism tested (rebuild ==
report); no fabricated "hand-lettered" media.

B. **Styled turntable re-check** (the P4-2/P4-3 honest-scope follow-up):
line art + tones are verified SINGLE-FRAME only. Re-run the turntable
(agent-demo path or a small variant) with a styled subject (toon material
+ `build_lineart` + `build_screentones`) under an ORBITING camera and
check per-frame stability honestly. If LineArt or the tone view layer
misbehaves per frame, record it as a documented limitation in
docs/STYLE.md — never fake a styled GIF. If it works, this unlocks the
P4-8 hero material.

C. **`apply_style` session action** (cheap win, now justified — the
builder API is stable): the MCP tool is DECLARED (schema v1). Wiring
`apply_style(kind, params)` → add-on executor is additive:
KNOWN_ACTION_KINDS 4→5 BOTH sides, golden-schema pin update same-commit,
session gate extension (enqueue → execute → assert report),
`mcp/manifest.json` tool table stays pinned by test. Do NOT start until
A's builder surface is final.

D. **Cheap wins while gates run**
- Windowed UI screenshot attempt (best-effort ~1-in-4; replaces
  docs/media/ui_screenshot.png ONLY if genuine; misses are fine, never
  staged).
- Doc cross-checks: docs/STYLE.md vs reality after your changes;
  mcp/README.md walkthrough still matches; AGENT_DEMO.md numbers vs
  current gates.

**Non-negotiable rules (locked, from mission + CONVENTIONS)**
QUALITY ABOVE ALL. Anything 80% done is 0% shipped. LOCAL OR NOTHING
(zero outbound in default use; the loopback socket is opt-in and
127.0.0.1 ONLY). Rig-agnostic or fake — ambiguity reported, never
swallowed. Honest claims: every claim cites a test, number, or GIF;
synthetic stays labeled synthetic; media rule — allowlist extension in
the SAME commit as the media, visual check before shipping any image.
Deterministic ops: keyed sorts, same input = same output (tested). No
subprocess strings in any .py; no sockets in core (D-003); core
dependency-free except lazy [inference]. Conventions: Python
≥3.10-compat, Z-up / facing −Y / character-left = +X, canonical roles
frozen API, refusal codes public API, ruff + pytest green before commits,
STATE logs append-only, timestamps REAL via `date -u`. Errors are
actionable — `(hint: ...)` never trace dumps. Do NOT tune solve priors or
contact thresholds against fixtures (D-008); do not loosen benchmark or
gate thresholds to move numbers (D-010..016). The style gate's dev-box
expectation stays LINEART: PASS / TONES GRAPH: PASS — CI's SKIPPED is
honest, don't converge the two by weakening the local bar. 18+ module
stays default-OFF, Phase 6 scope.

**End of session (non-negotiable)**
Tick claimed tasks in STATE/TASKS.md (completed vs partially-done with
what remains). Append PROGRESS lines (real UTC via `date -u`). Top of
STATE/NEXT.md: "NEXT SESSION SHOULD:" — write it for Session 14 (likely
P4-5 speech bubbles — they'll reuse the GPv3 surface, see the P4-2
probe's layer/frames/drawing notes — or P4-6 export; plus whatever B/C
left open). Update STATE/SESSIONS.md row. Commit + push (routine commits
authorized; CI runs — keep it green, fix inline like S12 did). If a
Mimosa finding blocks: verify it's real, fix inline, re-scan focused,
commit again.

**Known blockers (parked — do not burn time on them)**
PyPI + Blender Extensions + MCP registry submissions — account-bound
(LO); docs/PUBLISHING.md runbooks. Windowed Blender GL stability —
best-effort only (~1-in-4); never fake media to compensate. P1-8a
fallback estimator — parked (D-011/D-012). CI Blender bump — DECIDED
(D-014), **but note: Phase 4 keeps landing 5.1-only features (GPv3
LineArt, scene compositor node groups) — if P4-5+ continues that trend,
the D-014 revisit trigger is approaching; raising it is a deliberate
documented decision, not a silent bump**. P2-8 real walking clip —
NEEDS-HUMAN (out/video_smoke/SOURCES.md has the criteria); the
instruments and the agent demo re-run unchanged on a real clip.
