# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", critic-passed
   9.8/10; Annex A pre-declared bars are LAW): S34 landed P8-9 — **L10 =
   CLOSED** (median scripted time-to-fix 2.00 s over 54 flagged defects,
   bar <= 15 s; the four affordances ride the existing namespaces; gate
   RM_RUX) and **L9 = REFUSED-with-evidence after one candidate** (no
   adoptable anime/sketch estimator exists — D-024's scan evidence; the
   dual-estimator INTERFACE ships). **THE LEDGER IS NOW FULLY CLOSED OR
   REFUSED — every L-row.** The session map says **S35 = P8-10 the Scene
   Test + V1 launch** (the composite scorecard: pin residuals, per-finger
   accuracy, per-param expression monotonicity, camera framing IoU,
   identity swap rate, FK fidelity — each against its pre-declared bar;
   pass = every measure green AND every residual limitation is a labeled
   choice; per A.3 the scorecard overrides the calendar). The Scene Test
   fixtures: engine-rendered couple fixtures (the pipeline's own
   deterministic renderer, clothed and unclothed mannequins; NO external
   sourcing; LO-authored references stay LOCAL, never committed; the SFW
   fallback is the same renderer, clothed).

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement). Silent 22 straight sessions so far.
   - **Silent again (23rd)** → the P8-10 work order below.

2. **Then read, in order**: STATE/ROADMAP.md (the Scene Test section +
   Annex A.1/A.3 — the scorecard's bars and precedence), docs/REVIEW_UX.md
   (the S34 as-built + the gate-earned corrections), docs/SCENE_ANIMATION.md
   + docs/SCENES.md (the surfaces the Scene Test composes), STATE/NEXT.md,
   STATE/TASKS.md (claim P8-10 with [S35]), STATE/PROGRESS.md (S34
   entries), STATE/DECISIONS.md (D-024 — the ledger is closed/refused;
   D-018 stays reserved), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
   docs/BENCHMARKS.md (every block the scorecard composes: COUPLING,
   FINGERS, FACE, CAMERA, SCENE, SCENE ANIMATION, REVIEW-UX), docs/POLICY.md
   (D-019 — the Scene Test fixtures are engine-rendered; MCP stays SFW),
   and docs/LAUNCH.md + docs/TUTORIALS.md + README (the launch surfaces —
   they MUST claim exactly the scored reality after the scorecard; one
   grep sweep together when a number changes). Register as **Session 35**,
   claim P8-10 with [S35]; PROGRESS stamps via `date -u` read IMMEDIATELY
   before every append, then verify the stamp.

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**634 expected** — S34 added 19 review-UX contract
   tests) + `make lint PY=/home/potato/miniconda3/bin/python3`, and `gh
   run list --branch main` (the S34 push is the newest; if red: download
   the log, root-cause, fix the real substance FIRST).

## S35 work order — P8-10 the Scene Test + V1 launch

The composite scorecard (ROADMAP § The Scene Test — non-circular): one
E2E scenario per the A.3 fixture law, INDEPENDENT measures per stage, each
against its pre-declared Annex A.1 bar, assembled into ONE table shipped
in docs/BENCHMARKS.md:

1. **DESIGN-FIRST**: docs/SCENE_TEST.md (the REVIEW_UX.md sibling): the
   fixture plan (engine-rendered couple scenes, clothed + the SFW
   fallback; deterministic renders; nothing external committed), the
   scorecard's measures + bars verbatim from Annex A.1 (pin residuals <
   2% torso span; per-finger direction median <= 20 deg / p90 <= 35 deg
   visible; per-param expression monotonicity >= 9/10; camera framing
   IoU >= 0.75; identity swap rate <= 2% with the alarm >= 90%; FK
   fidelity <= 0.5 deg family), and the labeled-choices section (every
   residual limitation must be a labeled choice: skips, unclosable pins,
   camera error bars, the AMBIGUITY class, walk-in-place, the estimator
   refusal).
2. **PROBE/BUILD xtask/scene_test_probe.py**: run the E2E chain on the
   fixture set — reference -> detect -> solve -> scene + pins + fingers +
   face + camera + (video) identity assignment -> apply/couple/bake —
   MEASURING each scorecard row independently; RST rows, grep-tested both
   shapes before push.
3. **The scorecard table** lands in docs/BENCHMARKS.md SCENE TEST block:
   every measure with its number, bar, and PASS/FAIL; the labeled
   choices; the optimism caveat verbatim on synthetic-derived claims.
4. **Pass = every measure green AND every residual limitation labeled**
   -> V1: the launch surfaces (README/LAUNCH/TUTORIALS) refreshed to
   claim exactly the scored reality (one grep sweep together), the
   ledger cited as fully CLOSED/REFUSED. Miss = the A.3 precedence (the
   scorecard overrides the calendar; a parked row keeps its refusal).
5. **If early**: the declared wiring items (scene-animation session/MCP
   wiring; the S31 CLI/addon invocation wiring) — measured work only,
   each needs its own gate rows.

**S34's contract facts S35 builds on** (do not re-learn):

- The ledger reads CLOSED/REFUSED everywhere — the Scene Test cites it,
  it does not re-litigate it (L9's refusal carries D-024's evidence; the
  estimator interface is product surface, not an open claim).
- The gate-earned operator facts: execute returns {'FINISHED'} (never
  REGISTER); operators subclass an Operator MIXIN (never (Operator,
  mixin) — MRO); background Blender raises an operator's ERROR report at
  the invoking script; Blender masks crashed scripts with exit 0 (grep
  the FINAL gate row).
- Mimosa (standing): bash writes of .py source blocked — Write/Edit; the
  scanner blocks env-sourced file-WRITE shapes in gate scripts (the S27
  zero-IO gate pattern is the proven shape); expect the pagedoc.py
  import-struct FP at every commit; heredoc/append FPs when text names
  source files — Edit tool + -F commit-message files.
- The gate env trap (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  grab the broken apt 4.0.2).
- STATE stamps are REAL UTC, read-then-write-then-verify (the session
  date is the UTC date; use the echoed `date -u` value).

## Blocked / deferred (parked — do not burn time)

- Live capture device — parked LAST by LO; P5-4 runs when the phone comes
  up (box side READY; the client just never ran).
- PyPI description + Blender Extensions upload — LO's site-side steps
  (deferred to his final session by LO).
- P6-3 public benchmark suite packaging — roadmap-slack work.
- P6-2a `retarget_clip` session action — the refactor half is DONE; the
  executor wiring is roadmap-slack work.
- Windowed Blender GL stability — best-effort only, never staged.
- Detector-visible mannequin fixtures (the P8-5 tier-2 path) — NOT MET
  with evidence; reopened only if a detector-visible engine-built
  fixture path exists (the A.3 re-validation trigger).
- Root-motion BAKE — revisit only when a real root-motion source exists.
- Scene-animation session/MCP wiring — declared S33 follow-up (needs its
  own gate rows).
