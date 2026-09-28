# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", critic-passed
   9.8/10; Annex A pre-declared bars are LAW): S35 landed P8-10 — **THE
   SCENE TEST IS GREEN, V1's launch gate is MET** (the composite scorecard:
   11/11 RST rows — pin residual frac 0.000174, fingers 0.00°/10.30°, face
   0 violations/reach 1.00, framing IoU 0.8630, swap 0.0000 + alarm 2/2,
   FK 0.0000°; every residual limitation a labeled choice; twins
   byte-identical; docs/BENCHMARKS.md § SCENE TEST + docs/SCENE_TEST.md).
   **The honest-limits ledger is fully CLOSED/REFUSED — every L-row.**
   V1's launch ANNOUNCEMENT itself is a session-sized event LO owns; the
   repo ships the scored surfaces (README/LAUNCH/TUTORIALS already claim
   exactly the scored reality). Per the session map **S36 = Phase 9 opens:
   P9-1 proportion auto-sculpt — the MECHANISM PROBE** (lattice vs
   shape-key binding vs scale-correctives; SELECTION BAR: 5% on metarig +
   Mixamo-class, fewest rig-side artifacts, name-ascending tie-break;
   ALL candidates missing the bar on either rig ends Phase 9
   REFUSED-with-evidence — the proportion REPORT still ships as data).
   The honest physics first: keypoints give SKELETON, not VOLUME —
   volume is P9-2's separate third-model decision, never a P9-1 claim.

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement). Silent 23 straight sessions through S35.
   - **Silent again (24th)** → the P9-1 work order below.

2. **Then read, in order**: STATE/ROADMAP.md (Phase 9 — the honest
   physics, the P9-1 selection bar, P9-2's third-model decision, Annex
   A), docs/SCENE_TEST.md (the V1 gate's design of record + amendments
   A1–A3 — the newest sibling), docs/FACE.md (the shape-key binding
   precedent P9-1's candidate (b) generalizes), docs/SPINE.md +
   core/spine.py (the positions-surgery class candidate (c) rides),
   STATE/TASKS.md (claim P9-1 with [S36]), STATE/PROGRESS.md (S35
   entries), STATE/DECISIONS.md (D-018 stays reserved; D-025 is the next
   free number), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
   docs/BENCHMARKS.md (the SCENE TEST block — the scorecard must stay
   green), docs/POLICY.md (D-019), and the claim-bearing surfaces README
   + docs/LAUNCH.md + docs/TUTORIALS.md (one grep sweep together IF a
   number changes). Register as **Session 36**, claim P9-1 with [S36];
   PROGRESS stamps via `date -u` read IMMEDIATELY before every append,
   then verify the stamp.

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**634 expected** — S35 added no core tests; the
   Scene Test is probe/gate-side) + `make lint
   PY=/home/potato/miniconda3/bin/python3`, and `gh run list --branch
   main` (the S35 push is the newest; if red: download the log,
   root-cause, fix the real substance FIRST).

## S36 work order — P9-1 proportion auto-sculpt (the mechanism probe)

1. **DESIGN-FIRST**: docs/AUTO_SCULPT.md (the SCENE_TEST.md sibling): the
   honest physics verbatim; the three candidate mechanisms + their
   declared deformation instruments; the SELECTION BAR verbatim; the
   REFUSED branch; NO payload format change (any new pose field is
   additive, its DECISIONS entry WRITTEN at the landing — D-025 next).
2. **PROBE-FIRST xtask/auto_sculpt_probe.py** (RM_ASCULPT rows,
   grep-tested both shapes): all THREE candidates as probe-local pure
   functions; the proportions benchmark fixture set (heavy/slender/tall
   vs one base rig, prior-consistent GT, SYNTHETIC-labeled); MEASURE
   post-sculpt joint positions vs intent per mechanism per rig;
   fewest-artifact count; tie-break; DETERM twins.
3. **Core + apply**: ONLY the selected mechanism lands as core; rigs
   without a viable target report loudly (the P8-4 capability pattern);
   the proportion REPORT ships as data regardless.
4. **Gate**: xtask/auto_sculpt_gate.py (the sibling file) wired into
   verify_pose_apply.sh + the Makefile lint list: the 5% bar on BOTH rig
   classes + all prior numbers byte-identical (incl. the S35 RST rows).
5. **If early**: the declared wiring items (scene-animation session/MCP
   wiring; the S31 CLI/addon invocation wiring) — measured work only,
   each needs its own gate rows.

**S35's contract facts S36 builds on** (do not re-learn):

- The Scene Test composes, it does not re-derive: class instruments are
  imported (ONE fixture copy); reusing one must reproduce its published
  numbers byte-identically (they did). A canonical-vs-world raw-direction
  comparison is INVALID (the solve's frame is yawed/scaled by design).
- The S35 fixture lessons: the staging subject cloud is ALL pose-bone
  heads (the canonical-class fixture is the honest kp-set match); the
  scale pairing `dist = consensus × rig_torso/0.45` is LOAD-BEARING; the
  off-axis KEYSTONE fakes a depth gradient past the vertical-regime
  switch (the A8 fixture law); two-figure parallax splits the solo pitch
  solves at yaw ≠ 0; the STATIC scene path carries the arrangement in
  the ARTIST'S rig placement, never from bboxes.
- The gate-earned operator facts (S34): execute returns {'FINISHED'};
  operators subclass an Operator MIXIN; background Blender raises an
  operator's ERROR report at the invoking script; grep the FINAL gate
  row (Blender masks crashes with exit 0).
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  zero-IO gates are the proven shape; expect the pagedoc.py import-struct
  FP at every commit; heredoc/append FPs when text names source files —
  Edit tool + -F commit-message files.
- The gate env trap (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127.
- STATE stamps are REAL UTC, read-then-write-then-verify (the session
  date is the UTC date; use the echoed `date -u` value).

## Blocked / deferred (parked — do not burn time)

- Live capture device — parked LAST by LO; P5-4 runs when the phone comes
  up (box side READY; the client just never ran; silent 23 sessions).
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
- The anime fallback estimator — REFUSED-with-evidence (D-024); reopened
  only through the full P1-1 third-model ritual with a real candidate.
