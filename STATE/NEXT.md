# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", critic-passed
   9.8/10; Annex A pre-declared bars are LAW): S26 landed P8-1 (the
   CanonicalScene, the Casting Desk, camera v0 with the published floor).
   The session map says **S27 = P8-2 contact coupling** — the "not touching
   = bad" fix and the product's core promise (NEVER cut, Annex A).

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly). Silent 14 straight sessions so far; the box side is READY
     (D-020-era diagnosis: the DroidCam client just was never running).
   - **Silent again (15th)** → the P8-2 work order below.

2. **Then read, in order**: STATE/ROADMAP.md P8-2 + Annex A.1/A.2 (bars are
   law), docs/SCENES.md (the P8-1 design of record — P8-2 EXTENDS it, the
   coupling pass hooks into the scene apply the page describes),
   STATE/TASKS.md (P8-1 DONE with the full S26 entry), STATE/PROGRESS.md
   (S26 entries), STATE/DECISIONS.md (D-019/D-020; D-018 + D-021 stay
   RESERVED — D-021 is written only when finger/face code lands), STATE/
   CONVENTIONS.md, STATE/SESSIONS.md, docs/BENCHMARKS.md (SCENE block =
   the S26 numbers), docs/MOTION_LIBRARY.md, docs/POLICY.md,
   docs/FINGERS.md (the S26 audit — P8-3 material, do NOT start the build).
   Register as **Session 27**, claim P8-2 with [S27]; PROGRESS stamps via
   `date -u` read IMMEDIATELY before every append, then verify the stamp.

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m pytest
   tests` (**459 expected** — S26 added 28 scene/contract tests; the
   write-side format pins in test_payload/pose_cmd/video/live now assert 3)
   + `make lint PY=/home/potato/miniconda3/bin/python3`, and `gh run list
   --branch main` (the S26 push is the newest run). If red: download the
   log, root-cause, fix the real substance FIRST.

## S27 work order — P8-2 Contact coupling (the "not touching = bad" fix)

Design → probe → build → gate, in that order (NON-NEGOTIABLE):

1. **DESIGN-FIRST: extend docs/SCENES.md** (never fork it) with the
   coupling pass design: deterministic iterative redistribution over the
   canonical figures, hooked AFTER the per-figure solves and BEFORE the
   bake. **The conflict rule is pre-declared (roadmap, critique-fixed)**:
   pins resolve in AUTHORED order (the scene model already preserves it —
   `ScenePose.pins` is never sorted), weighted by per-role confidence;
   an over-determined set solves least-squares with a keyed iteration
   order (deterministic); each pin REPORTS its residual; unclosable pins
   stay loud; the solve never moves a role below its confidence floor.
   Enforcement boundary: only AUTHORED pins are enforced; `origin:
   "suggested"` pins are confirmed in the Casting Desk first (the honesty
   law — the suggestion INFERENCE (keypoint proximity) is also P8-2 work:
   it feeds the desk as data, never auto-enforced).
2. **PROBE-FIRST xtask/coupling_probe.py** (RM_COUPLE lines, grep-tested
   both shapes before push): the Blender unknowns — (a) does the iterative
   redistribution converge on the gate fixture (hold-from-behind class)
   within the bar; (b) do non-chain roles stay byte-identical during the
   solve; (c) the conflict case (competing pins) behaves per the rule.
3. **Core**: the coupling pass in core (pure, deterministic — the
   keyed-sorts law), solving over `ScenePose` figures; per-pin residuals
   in the report; bounded repair cycle (Annex A.2: one default cycle —
   after it, coupling ships as rigid pin-SNAP reported as such, L1 =
   CLOSED-LIMITED in DECISIONS).
4. **Gate**: an RM_COUPLE section (scene_gate.py sibling shape): the
   coupled-pair fixture (hold-from-behind class, engine-built per Annex
   A.3 — no external sourcing), pin residual < **2% torso span**, roles
   NOT on any pin's dependency chain unchanged ≤ **0.5°** (chain roles on
   resolved pins report deviation as pin cost — strike S9 carve-out),
   twin-run byte-identical, conflict case documented + gated.
5. **Early-finish option**: the pin-suggestion inference (keypoint
   proximity) as DATA for the desk, or P8-3 prep — measured work only.

**S26's contract facts S27 builds on** (do not re-learn):

- `ScenePose.pins` is AUTHORED-ORDER (never sorted — that order is P8-2's
  precedence); figures are label-sorted. `validate_casting` allows SUBSETS
  (uncast labels are reported by the apply, never silent).
- Payload v3: FORMAT=3 write, formats 1+2+3 read; optional top-level
  `pins` (validated by `ContactPin.from_dict` — the ONE validator);
  a v2 payload through v3 code applies BYTE-IDENTICALLY (the pinned
  contract test); a pins-free v3 file differs from v2 output only in the
  format int.
- The scene apply COMPOSES the real per-figure `apply_payload` (tails
  repair per figure, one undo push); apply is order-insensitive and
  idempotent (probe-proven byte-identical).
- Camera v0: place, `view_layer.update()`, THEN measure
  (`world_to_camera_view` reads a stale `matrix_world` otherwise — the
  S26 gate-earned bug); reference normalization flips v and clamps to the
  frame; the 0.75 floor derivation is SYNTHETIC-labeled in BENCHMARKS.
- The gate's camera benchmark condition requires the scene layout to
  MATCH the reference (payload FROM the reference being posed) — the gate
  derives separation from the posed subject's measured aspect.
- The gate env trap (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  grab the broken apt 4.0.2).
- STATE stamps are REAL UTC, read-then-write-then-verify.
- Mimosa (standing): bash writes of source files blocked — use Write/Edit;
  the pagedoc.py import-struct FP at every commit; S26 added a RECURRING
  SQL-injection FP on operator-execute bodies in the add-on `__init__`
  (no SQL exists — D-003); new operator classes live in
  `addon/casting_desk.py`-style modules (new-file writes scan clean);
  heredoc/append FPs when text names source files — Edit tool + -F
  commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes, and get one grep sweep together when they do.

## Blocked / deferred (parked — do not burn time)

- Live capture device — parked LAST by LO; P5-4 runs when the phone comes
  up (box side READY; the client just never ran).
- PyPI description + Blender Extensions upload — LO's site-side steps
  (deferred to his final session by LO).
- P6-3 public benchmark suite packaging — UNBLOCKED (D-020), roadmap-slack
  work, scheduled by LO's priority call at a session fork.
- P6-2a `retarget_clip` session action — the refactor half is DONE; the
  executor wiring is roadmap-slack work.
- P1-8a fallback estimator — parked (D-011/D-012) until P8-9.
- Windowed Blender GL stability — best-effort only, never staged.
