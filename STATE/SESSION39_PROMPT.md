# SESSION 39 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes (P8-1), contact
coupling (P8-2), fingers (P8-3), facials (P8-4), the MEASURED camera
(P8-5), spine arch + roll (P8-6), root motion as gated additive core with
L7 REFUSED-with-evidence (P8-7), scene animation (P8-8: swap 0.0000),
review fix affordances (P8-9: L10 CLOSED, L9 REFUSED-with-evidence), THE
SCENE TEST (P8-10) GREEN — V1's launch gate MET, the honest-limits ledger
fully CLOSED/REFUSED (the V1 launch announcement itself is a session-sized
event LO owns). Phase 9: P9-1 proportion auto-sculpt MEASURED and LANDED
(S36: `armature_scale_correctives`, pose-translation delivery, worst frac
0.0000 on both rig classes). P9-2 volume from silhouette MEASURED and
LANDED (S37: D-025 ADOPTED `u2net.onnx` — the P6-6 never-list amends to
three — and `shape_key_inflate` SELECTED, worst region IoU 0.9499 vs bar
0.85, joints byte-identical through the warp, CI green). P9-3 sculpt +
animation wiring LANDED (S38: `rigpose solve-sculpt` — the format-1 solve
artifact, LIVE-VERIFIED on a real reference; the `rm.apply_sculpt`
operator + the `sculpt` session action through ONE shared addon path; THE
ANIMATION-ORDER PROOF GREEN — the baked action stays rotation-only, the
sculpt survives it byte-identically, frame-one width drift 0.00e+00 m, FK
0.0000 deg x70 checks, re-sculpt at the sculpt frame re-lands
byte-identically; the S37 measurement lifted verbatim into core and the
certified volume rows re-ran byte-identical). Toon renders, manga pages.
Live pose-stream puppeteering on the replay path. No cloud, no accounts,
no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

## LO'S STANDING RULES (LAW for this and every future session)

1. **The commit surface reads like LO's own work.** Commit messages carry
   NO session numbers, NO AI/tooling mentions, NO em dashes. The STATE/
   journal keeps the project's own format; the git history does not
   advertise how the work was done. Compose commit messages in a scratch
   file and pass `-F <file>` (the Mimosa heredoc/append FP shape).
   Rewriting already-pushed main history is LO's explicit call, never a
   default.
2. **Every session ends with a LOCAL devlog**: a markdown file under
   `out/devlog/` (gitignored, NEVER pushed), named by UTC date and topic,
   plus one or two REAL proof images — actual renders or screenshots of
   the work itself, never terminal dumps. The devlog is the human-readable
   record; STATE/ is the machine-readable one.
3. Every claim cites a test/gate; every gate keeps its grep contract;
   every prior gate number stays byte-identical unless the change is the
   change. (Standing law — restated here because it is the same spirit:
   the work speaks in numbers.)

## THE MISSION (read STATE/ROADMAP.md first — plan of record, Annex A
pre-declared bars are LAW for every session): S39's rock is **sculpt
polish — the measured gaps S38's landing exposed, each with its own
declared bar + gate rows — and the P10-1 opener if early** (the PoseSpec
contract skeleton, pure core, model-free, design-first docs/POSE_SPEC.md,
the red-set refusal bar pre-declared). The S38-thin spots: the Mixamo-class
re-sculpt worst frac 0.047085 vs bar 0.05 (the frame-one rotations are not
exactly identity after the bake — the polish declares the tolerance basis
or improves the solve); the oblique-reference limit (the volume solve
assumes the declared frontal class — a measured oblique class or a loud
refusal with measured error bars, never a silent wrong solve); the
driven-shape-key staging limit (a driven key ignores the staged zero —
stage the driver or refuse loud with the measured class). **NEVER cut
P8-2 coupling or P8-3 visible fingers (Annex A cut order). NEVER let the
polish relabel a claim** — every new surface cites its own gate rows;
every prior gate number stays byte-identical unless the change is the
change.

## S38 contract facts (what S39 builds on)

- **P9-3 LANDED end to end**: core `sculpt.py` (SCULPT_FORMAT 1,
  `SculptSolve` loud validation, `anchor_points_px` — the A1 product
  anchors are the DETECTOR's body keypoints, torso-line interpolation at
  the certified fracs 0.0/0.25/0.80 and the thigh extension −0.70;
  `region_widths`/`solve_factors`/`runs` are the ONE copies —
  `volume_common` aliases them and the certified volume rows re-ran
  BYTE-IDENTICAL: BAR 0.9499, counterfactual 0.8907, model-mediated
  0.8592) + `inference/segment.py` (the ONE u2net wrapper; the P1-1 flow
  is the only download path: `rigpose models download u2net` —
  live-verified) + CLI `rigpose solve-sculpt <image> <payload> --out
  sculpt.json` (re-detects the image — the payload carries no 2D kps;
  the payload figure label must match the image's detection, loud on
  stale; anchor kps below the 0.55 floor refuse; LIVE-VERIFIED end to
  end on the benchmark reference).
- **The addon wiring**: `sculpt_wire.py` — `apply_sculpt(arm, payload,
  solve, proportions, volume)` is the ONE shared path (operator +
  session): proportion = payload positions → core target build → the S36
  apply UNCHANGED (space_scale derived 1/object-scale); volume = the
  STAGED REST-SNAPSHOT measurement (pose basis cleared, shape keys
  zeroed with a driven-key loud note, the ACTION MUTED — fcurves
  override matrix_basis at evaluation — the WORKBENCH render recipe +
  the fitted frontal camera staged and RESTORED, anchors projected from
  the REST heads, the certified region_widths) → factors (clamp notes
  loud) → the S37 apply UNCHANGED. CAPABILITY_NO_PAYLOAD /
  CAPABILITY_NO_SCULPT lines; a missing half never blocks the other;
  the solve-figure-vs-payload-figure mismatch is a loud note.
- **The surfaces**: operator `rm.apply_sculpt` ({'REGISTER','UNDO'} +
  {'FINISHED'}, poll, ERROR reports) + the panel section riding the
  pose-apply panel (sculpt_path + Apply Sculpt); session `sculpt`
  (KNOWN_ACTION_KINDS additive BOTH sides in the same commit; params
  payload_path/sculpt_path/armature_name/proportions/volume; validates
  inputs BEFORE any bpy; CI-tested missing-input refusals). MCP tool
  table untouched — D-019's SFW pin holds, test-pinned (the sculpt
  carries no content by itself).
- **The gate**: `xtask/wiring_gate.py` — 11 RM_WIRE grep rows
  (WIRE-FIXTURE/MEASURE/SOLVE/FLOW/RESCULPT/OPS/SESSION/NOTARGET/DETERM
  + WIRE + GATE) wired into pose-verify after the volume gate block +
  the Makefile lint list. THE ORDER PROOF numbers: WIRE-MEASURE 0.0000
  worst rel both classes (bar 2e-2); WIRE-FLOW sculpt survives the
  animation BYTE-IDENTICALLY, frame-one drift 0.00e+00 m (bar 1e-05),
  bake + independent re-eval 0.0000 deg over 70 checks (bar 0.5),
  fcurves ROTATION-ONLY; WIRE-RESCULPT values byte-identical + target
  re-landed (0.000029 metarig / **0.047085 mixamo vs bar 0.05** — the
  S39 polish item) + the action intact; WIRE-OPS/SESSION byte-identical
  to the direct path.
- **The S38 gate-earned amendments (A2-A4 in WIRING.md, do not
  re-learn)**: the SCENE LAW's second earn — the two rig-class fixtures
  share one world position and a sculpted neighbour poisons the next
  case's render-based base measurement (factors read 0.9895-1.0127 on an
  authored 1.15); fresh scene per render-adjacent case. The re-eval
  frame: the bake's default frame_offset 1 maps source f to Blender f+1
  — a re-eval reading frame_set(f) measures exactly the frame spacing
  (20.0000 deg). The re-sculpt semantics: a re-solve compensates the
  current frame's rotation BY DESIGN (the target is the joint POSITION,
  not the pose-bone location) — byte-comparing locations across an
  animation is the wrong instrument; the honest checks are
  values-bytes + target-frac + action-intact.
- **669 tests** (S38 added 15); CI GREEN — verify the newest
  run on main at open (the S38 push). All prior gate numbers
  byte-identical (RM_BAKE 0.0242°, RM_FOOT_LOCK 0.0371→0.0000,
  RM_MOTION 44997x, RM_COUPLE 0.00016/0.00035, RM_FINGER
  0.0070°/0.00°/10.30°, RM_FACE 6 rows, RM_CAM 6 rows, RM_SPINE 5 rows,
  RM_ROOT 11 rows, RM_SANIM 10 rows, RM_RUX 10 rows, RST 12 rows,
  RM_ASCULPT 8 rows, RM_VOL 7 rows + the pipeline block, RM_WIRE 11
  rows).
- **D-026 is the next free number** (S38 added no payload field and no
  pose field — the solve artifact is a separate format-1 file);
  D-018 stays reserved.
- **A logo set exists locally** (`out/devlog/logo/`: icon dark/light,
  lockup, icon.svg master, the make_logo.py generator — hand-placed
  geometry, the keypoint-skeleton mark with the orange root joint). It
  is LO's asset; if LO asks, S39 may land it in-repo (a headless
  generator in xtask/ + the media-guard allowlist extension in the
  SAME commit — the media law). Never commit the out/ copies.
- **Gate env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3, and for the gate scripts RM_ADDON_DIR=$REPO/
  addon — pose-verify needs ALL FOUR (the first S38 battery run died on
  an unbound $PY at the volume stage).
- **Instrument lessons (standing)**: Blender masks crashed scripts with
  exit 0 — grep the FINAL row (`RM_WIRE GATE: PASS`); place-update-then-
  measure; mathutils nested rich-compare FLAKY in 5.1 (plain-float
  tuples only); the session DATE is the UTC date (`date -u`);
  removing a Blender object orphans its data and the purge kills the
  RNA — capture names BEFORE removal; accumulated scenes poison renders
  AND instruments (fresh scene per render-adjacent case — earned TWICE
  now); Mimosa: bash writes of .py source blocked (Write/Edit);
  parameterized-path write opens trip the path-traversal FP — the
  proven shape is module-level literal Path constants + `.write_text()`
  (walk_job's shape) and inline literal-join opens for reads; expect
  the pagedoc.py import-struct low FP at every commit (disclose it,
  non-blocking, every session).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the S39 work order below.
- Silent (27th): proceed with the S39 work order directly.
- Then read, in order: STATE/ROADMAP.md (P9-3 landed; P10-1's scope),
  docs/WIRING.md (the wiring design of record + as-built A2-A4),
  docs/AUTO_SCULPT.md + docs/VOLUME.md (the sculpt mechanisms the
  polish rides), docs/SCENE_TEST.md + docs/BENCHMARKS.md (the scorecard
  + the WIRING block that must stay green), STATE/NEXT.md,
  STATE/TASKS.md (claim the session's rock with [S39]),
  STATE/PROGRESS.md (S38 entries), STATE/DECISIONS.md (D-018 reserved;
  D-026 next free), STATE/CONVENTIONS.md (**LO's standing rules live
  here now — reread them**), STATE/SESSIONS.md, docs/POLICY.md, and the
  claim-bearing surfaces README + docs/LAUNCH.md + docs/TUTORIALS.md
  (one grep sweep together IF a number changes; S38 swept them — a
  polish number change re-sweeps them together).
- Register as Session 39 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**669 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S38 discipline).

## S39 work order — sculpt polish (+ the P10-1 opener if early)

The ritual order is NON-NEGOTIABLE:

1. **DESIGN-FIRST any polish page** (extend docs/WIRING.md — never fork
   it): the measured gaps, each with its declared bar + gate rows BEFORE
   code (the thin mixamo re-sculpt frac; the oblique-reference limit;
   the driven-key staging limit — S39's declared candidates; measured
   work only, each needs its own gate rows).
2. **The polish lands** with its own RM_WIRE (or sibling) grep rows;
   every prior gate number stays byte-identical.
3. **If early**: the P10-1 opener — the PoseSpec contract skeleton (pure
   core, model-free: the versioned per-role spec + the loud validator's
   shape), declared in docs/POSE_SPEC.md design-first, the red-set
   refusal bar pre-declared per the roadmap (validator refuses 100% of
   the impossible-spec red set; asymmetry/injection constants frozen in
   the contract BEFORE any measurement).

Definition of S39 failure (name it, avoid it): a polish without gate
rows, a silently-scoped claim, a fix that relabels a limit instead of
measuring it, a commit message that breaks LO's standing rules, or ANY
claim without a test/gate citation. Anything 80% done is 0% shipped —
park cleanly at a unit boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored; every inferred thing carries confidence + residual); park
  criteria (two stalled probe/gate cycles → park with evidence,
  reorder); the cut order (NEVER P8-2/P8-3); policy D-019 across new
  surfaces (MCP stays SFW, test-pinned; the model's download path is
  the P1-1 manifest flow — checksum-pinned, user-initiated, zero
  default-use outbound).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped. The out/ tree is gitignored — probe renders and the
  devlog live there, never committed.
- The gate env trap (above).
- STATE stamps: real UTC, read-then-write-then-verify; the session date
  is the UTC date.
- 5.x slotted actions, the posed-head lesson, joint-angle keying,
  factory-EMPTY FBX scenes, rotation modes before quaternion writes,
  the two-pass fixture-builder rule, place-update-then-measure, the
  wrist-is-body-kp-9 lesson, mathutils nested rich-compare FLAKY in 5.1
  (plain-float tuples only), the operator return/poll/ERROR-report
  classes, the RNA-purge lesson, the absolute-target solve law, the
  frame_offset-1 re-eval mapping, the action-mute staging — the
  S15..S38 facts in SESSION38_PROMPT.md remain true.

End of session (non-negotiable):

- Tick claimed tasks (completed vs partially-done + what remains).
- Append PROGRESS lines (real UTC, read-then-write-then-verify).
- Top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S40 = P10-1 PoseSpec +
  the plausibility validator per the session map — say which shape
  landed.
- Write STATE/SESSION40_PROMPT.md in this pattern (contract facts, STEP
  0, the next work order) — and keep LO'S STANDING RULES section at the
  top, verbatim or better.
- Update STATE/SESSIONS.md row.
- **Write the LOCAL devlog** under out/devlog/ (UTC-dated markdown:
  what landed, the measured fight worth remembering, the numbers) plus
  one or two REAL proof images (pipeline renders/screenshots of the
  work itself — never terminal dumps). Never pushed.
- Commit + push: routine commits authorized; CLEAN messages per LO's
  standing rules (no session markers, no AI mentions, no em dashes;
  scratch-file + `-F`); keep CI green, fix inline like S12..S38.
- Expect and disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up; silent 26
straight sessions through S38). PyPI description + Blender Extensions
upload — LO's site-side steps (his final session). P6-3 packaging +
P6-2a wiring — roadmap slack. Windowed Blender GL stability —
best-effort only, never staged. Detector-visible mannequin fixtures (the
P8-5 tier-2 path) — NOT MET with evidence; reopened only if a
detector-visible engine-built fixture path exists. Root-motion BAKE —
revisit only when a real root-motion source exists. Scene-animation
session/MCP wiring — S33's declared follow-up, still open (measured work
only, its own gate rows). The anime fallback estimator —
REFUSED-with-evidence (D-024); reopened only through the full P1-1
third-model ritual with a real candidate.
