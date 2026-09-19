# Session 15 prompt (riggermortis)

**Project (30-second context)**
riggermortis — local, free, rig-agnostic posing & animation engine: (1)
Blender add-on, (2) MCP server so AI agents drive Blender. Drop a rigged
model + reference image → pose applied. Drop a video → animation,
retargeted, foot-slide-cleaned. Photos AND anime art. Toon renders, manga
pages. No cloud, no accounts, no uploads, ever.

Repo: `/home/potato/osint/riggermortis` — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main). CI
IS GREEN (latest: 88fbe10 — tests 3.11+3.13 at **293**, blender-gate incl.
session + export + **style (P4-1..P4-6)** gates, media-guard all PASS).

Phases 0–3 CLOSED (honest: D-011/D-015; real-clip half still
NEEDS-HUMAN). Phase 4 OPEN, through P4-6: **P4-1** toon materials +
**P4-2** GPv3 line art + **P4-3** screentones + **P4-4** multi-camera
panel pages + **P4-5** speech bubbles + **P4-6** PDF/EPUB/PNG export —
presets/pages/bubbles as DATA-FILE schemas, deterministic builders
(`addon/style.py` / `addon/pages.py` / `addon/bubbles.py`), export in
`core/pagedoc.py` (pure stdlib, `rigpose export-pdf` / `export-epub`).
Gate = `make style-verify` (style_probe.py) — the dev box runs the FULL
gate with real EEVEE pixels (LINEART / TONES GRAPH / PAGES / EXPORT all
PASS); CI still runs apt 4.0.2 where those halves SKIPPED honestly.
Sources of record: docs/STYLE.md + docs/EXPORT.md.

Remaining in Phase 4: **P4-7** (animatic mode from pose sequences),
**P4-8** (the 6-page manga + 3-style hero).

**STEP 0 — Session protocol (do this first, always)**
Read, in order: STATE/NEXT.md (authoritative for S15 + the S14
watch-outs), STATE/TASKS.md, STATE/PROGRESS.md (S14 entries),
STATE/DECISIONS.md (esp. D-008, D-009, D-013..D-016 — and D-014: its
bump trigger is NOW MET, work order A executes the documented decision),
STATE/CONVENTIONS.md, STATE/SESSIONS.md, **docs/STYLE.md** + 
**docs/EXPORT.md** (keep both in sync).

Register yourself in STATE/SESSIONS.md as Session 15. Claim tasks in
STATE/TASKS.md by ticking + tagging [S15] before working. Append
timestamped PROGRESS lines per meaningful unit (real UTC via `date -u`).

Verify baseline: `cd core && /home/potato/miniconda3/bin/python3 -m pytest
tests` (expect **293 passed**) and `make lint
PY=/home/potato/miniconda3/bin/python3` from repo root (lint list now
includes `xtask/bubble_probe.py`).

**Environment facts (verified through S14)**
Blender 5.1.0 at `/home/potato/blender-5.1.0-linux-x64/` is the REAL
install. Gates need explicit env or they 127 on PATH:
`BLENDER=/home/potato/blender-5.1.0-linux-x64/blender`,
`RIGPOSE=/home/potato/miniconda3/bin/rigpose`,
`PY=/home/potato/miniconda3/bin/python3` (conda BASE is the project env).
EEVEE renders headless on the dev box AND on CI (llvmpipe). CI keeps apt
4.0.2 until work order A lands (D-014).

S14 facts (do not reintroduce):
- **GPv3 authoring (5.1)**: strokes are authored with
  `drawing.add_strokes([n, ...])` (`stroke.points.add` does NOT exist);
  the closed flag is named **`cyclic`**; per-point attrs are
  position/radius/opacity/vertex_color — **vertex_color drives only the
  STROKE** (color from it, opacity from point.opacity; the material
  color does not tint strokes).
- **The GPv3 FILL is a dead end for data-authored shapes**: material
  fills (show_fill + SOLID) render ONLY on `use_lights=False` layers
  (lit fills vanish — the 5.1 broken path); stroke fill_color/
  fill_opacity never render; the only fill ops are interactive cursor
  tools; the MONKEY preset's fills render black-unlit / vanish-lit.
  Bubble bodies are the **z-layered unlit MESH** (ellipse n-gon + tail
  triangle, Emission strength 1) for this reason — recorded in
  docs/STYLE.md so it is never "fixed" backwards.
- Bubble ink = ops `grease_pencil_add(type='EMPTY')` + renames +
  `layer.use_lights = False`; tail is an OPEN polyline (no ink edge
  inside the body); the tail mesh fill z-orders OVER the ellipse ink so
  the join reads open. Ops-created GP is captured by DATABLOCK DIFF
  (`bpy.context.object` is stale after a render — the standing lesson).
- **Bubble data contract**: per-panel `bubbles` list on the page preset
  (pos/size = PANEL fractions of center/extents, tail enum
  n/ne/e/se/s/sw/w/nw/none default none, text str — validator fails
  loudly at page/panel/bubble level; footprint must stay inside the
  bleed-extended page). `pages.bubble_px` = edge-based px math.
  `build_page_graph(..., bubble_files=...)`: files required IFF the page
  carries bubbles, exact count, actionable errors otherwise; bubble-less
  pages build BYTE-IDENTICAL graphs to pre-P4-5 (report grows no key).
- **Render determinism standard**: re-renders are PIXEL-identical; PNG
  FILE bytes differ only in Blender's `tEXt RenderTime` stamp
  (chunk-located, measured) — pixel-level determinism is the claim, the
  P4-4 precedent. Same for the export gate (writer determinism IS
  byte-level: fixed inputs → identical PDF/EPUB bytes).
- **Export (P4-6)**: `core/pagedoc.py` — stdlib PNG decode is a
  deliberate 8-bit truecolor subset (RGB type 2 / RGBA type 6, no
  interlace; anything else = actionable PayloadError); the PDF has NO
  timestamps (byte-deterministic); EPUB mimetype is first + STORED,
  images copied VERBATIM, id = content hash. The parse-back readers are
  WRITER-SHAPED (they understand what build_pdf/build_epub write —
  documented, not a general reader); the EPUB OPF parser refuses
  DOCTYPE/ENTITY + >4MB before ElementTree (the Mimosa finding, real
  substance — keep it). NO subprocess strings anywhere (D-003/D-009);
  CLI tests run IN-PROCESS.
- **Gate regexes must match the probe's EXACT line format** — S14's CI
  red was a stray space in an alternation (`EXPORT (` vs `EXPORT:`);
  the S12 line-format-drift class hit twice now. After ANY probe print
  change: grep-test both the PASS and SKIPPED lines locally before
  pushing.
- The compositor/pages/bubbles machinery stages and RESTORES everything
  it touches (camera/resolution/film_transparent/view transform/dither/
  color mode/compositor group/hide_render). Never "simplify" a restore.
- Mimosa intercepts bash writes of ANY source-looking file (even /tmp) —
  use Write/Edit; the commit-hook compatibility note is normal, never
  claim project-wide safety. If a finding BLOCKS: verify real, fix
  inline, re-scan focused, commit again. Known FP on record: "command
  injection" on `import struct` in pagedoc.py (no process-execution
  interface exists in core — D-003 enforced).

**Work order (claim in this sequence; stop cleanly wherever you run out)**

A. **D-014 CI Blender bump** (FIRST — one deliberate commit; the
   documented decision whose trigger P4-5 met: every Phase-4 real-pixel
   half currently exercises only its SKIPPED path on CI).
   ci.yml changes ONLY (one commit): download the 5.1.0 linux-x64 tarball
   from download.blender.org via actions/cache (keyed on the version
   string), extract, export `BLENDER=` to the gate steps; KEEP the
   libegl1/libgl1/mesa apt installs (llvmpipe) and the python3-numpy
   export-gate fix. The gates' env-var interface does not change; the
   SKIPPED degradation paths STAY in the code (dev-box/older-Blender
   honesty — do not delete them because CI no longer hits them).
   Expected consequence, watched honestly: CI's style gate now renders
   pages/bubbles on llvmpipe — MEASURE the job time on the first run; if
   it blows CI minutes, that is a documented decision moment (record it
   in DECISIONS/PROGRESS), never a silent gate loosening.
   Accept: CI green with the style gate showing LINEART/TONES/PAGES/
   EXPORT **PASS** (not SKIPPED) on CI; the session + export gates still
   green; the 4.0.2 pin note in ci.yml updated to the new reality.

B. **P4-7 — Animatic mode from pose sequences** (the next rock).
   DESIGN FIRST: a P4-7 section in docs/STYLE.md — what an animatic IS
   in this project (timed panel sequence from a canonical action /
   pose sequence: which frames, which cameras, what timing data, where
   it hangs on the P4-4 page/preset schema), same schema discipline
   (format field, validator fails loudly, unknown fields fail).
   Then PROBE the Blender-uncertain mechanism BEFORE building. The
   likely candidate is the Video Sequence Editor (VSE): image-sequence
   strips per panel + scene fps + render animation — all inside Blender,
   NO subprocess (D-009: video encode outside .py would need ffmpeg
   shell glue; the VSE route keeps it in-process). Probe questions with
   RM_* evidence: does an ops/data-built VSE strip stack render to a
   movie headless on 5.1 (FFMPEG container available in background
   builds?); is strip timing deterministic from preset data; does the
   page machinery (cameras/panels/bubbles) compose per frame. If VSE
   fails honestly, record the dead end and fall back to per-frame PNG
   sequences + shell-glue assembly (still D-009-clean).
   Implement: timing/sequence preset data + deterministic builder +
   gate extension + honest SKIPPED degradation + VISUAL CHECK. No
   "final render" claims — an animatic is a TIMED ROUGH, label it so.

C. **P4-8 pre-work if B closes early**: the 6-page manga + 3-style hero
   has every ingredient verified AND shipped (P4-1..P4-6 + animated
   stability RM_TT PASS). Pre-work = character-framing re-tune of the
   lineart radii (DATA edit per docs/STYLE.md P4-2 notes), the hero
   material list, and the 6-page layout data (which preset schema
   extensions the story needs, if any — design in docs/STYLE.md first).

D. **Cheap wins while gates run**
- Windowed UI screenshot attempt (best-effort ~1-in-4; replaces
  docs/media/ui_screenshot.png ONLY if genuine; misses are fine, never
  staged).
- Doc cross-checks: docs/STYLE.md + docs/EXPORT.md vs reality after your
  changes; README status line if Phase 4 closes further; AGENT_DEMO.md
  numbers vs current gates (untouched unless actions change).

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
frozen API, refusal codes public API, ruff + pytest green before commits
(verify with a status check, not a piped tail — S14 let one red lint
slip through a pipeline exit code), STATE logs append-only, timestamps
REAL via `date -u`. Errors are actionable — `(hint: ...)` never trace
dumps. Do NOT tune solve priors or contact thresholds against fixtures
(D-008); do not loosen benchmark or gate thresholds to move numbers
(D-010..016). The style gate's dev-box expectation stays LINEART: PASS /
TONES GRAPH: PASS / PAGES: PASS / EXPORT PDF+EPUB: PASS — after work
order A, CI's expectation rises to MATCH it (that is the bump), not
converge the other way. 18+ module stays default-OFF, Phase 6 scope.

**End of session (non-negotiable)**
Tick claimed tasks in STATE/TASKS.md (completed vs partially-done with
what remains). Append PROGRESS lines (real UTC via `date -u`). Top of
STATE/NEXT.md: "NEXT SESSION SHOULD:" — write it for Session 16 (likely
P4-8 the 6-page manga + 3-style hero if P4-7 landed, or P4-8 pre-work +
the animatic remainder). Update STATE/SESSIONS.md row. Commit + push
(routine commits authorized; CI runs — keep it green, fix inline like
S12/S14 did: download the run log, root-cause, fix the real substance).
If a Mimosa finding blocks: verify it's real, fix inline, re-scan
focused, commit again.

**Known blockers (parked — do not burn time on them)**
PyPI + Blender Extensions + MCP registry submissions — account-bound
(LO); docs/PUBLISHING.md runbooks. Windowed Blender GL stability —
best-effort only (~1-in-4); never fake media to compensate. P1-8a
fallback estimator — parked (D-011/D-012). CI Blender bump — REMOVE this
blocker once work order A lands and CI is green on 5.1 (the D-014
decision executed; keep the ci.yml note truthful). P2-8 real walking
clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md has the criteria); the
instruments and the agent demo re-run unchanged on a real clip.
