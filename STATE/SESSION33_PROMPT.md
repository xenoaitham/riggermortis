# SESSION 33 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes landed (P8-1): one
payload poses N paired rigs in one action, pins carried as data, a camera
stages from the reference framing. Contact coupling landed (P8-2): AUTHORED
pins close deterministically, suggested/below-floor pins stay loud data.
Fingers landed (P8-3): the D-021 additive namespace solves per-finger
chains ONLY from observed hand keypoints — below the 0.55 floor a finger
is skipped + LEDGERED, never guessed. Facials landed (P8-4): the D-022
facial parameter namespace — 10 dimensionless expression params solved
ONLY from observed face landmarks through the PUBLISHED table, the
MEASURED side map, per-param gates + ledgers, gaze conditional-OUT, the
two-class apply. The MEASURED camera landed (P8-5): yaw/pitch/distance/
height fitted from the body keypoints, GT bars met with margin, BOTH
floors gate the staging, CAM-MODEL matches Blender at 2.32e-07; tier-2
render+detector NOT MET with evidence (published, never relabeled). Spine
arch + roll landed (P8-6): the A1 Hermite arch + the D-023 roll namespace,
monotone benchmark, FK bars through the REAL apply, straight arms
BIT-IDENTICAL. Root motion landed (P8-7) as gated additive core — and L7
ended **REFUSED-with-evidence** (the first exercised Annex A.2 branch):
the drift track + root-motion-aware contact model work and are gated
(the >= 5x family demonstrated at 46351.9x on the drift GT class), but
the pre-declared bar's REAL fixture measurably carries NO root motion —
the Xbot.glb's seven clips are all in-place in the imported scene graph
(A3 corrected finding), so walk-in-place ships. Toon renders, manga
pages. Live pose-stream puppeteering on the replay path. No cloud, no
accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** V1 = Phase
8 complete + the Scene Test scorecard green (target S35; Annex A.3: the
scorecard overrides the calendar). S32 landed P8-7 (L7 REFUSED-with-
evidence — the machinery ships, the claim doesn't, exactly as pre-declared).
**S33's rock is P8-8 multi-character video → scene animation**: the P2-1
job container gains per-frame multi-figure payloads + per-frame coupling
(P8-2) + fingers/facials (P8-3/4) → scene actions → bake BOTH rigs in one
pass; identity stability by the COMMITTED algorithm (per-frame
figure→character assignment by pose-similarity cost matrix, deterministic
Hungarian with keyed order, a cost jump raising a swap alarm, manual
override winning over everything); **bars: identity swap rate <= 2% of
frames on the synthetic fixture, the swap alarm catching >= 90% of actual
swaps, per-frame scene bake cost MEASURED on the mid-laptop baseline and
PUBLISHED before any claim; the A.2 branch: swap rate > 10% after the
repair work → auto-identity REFUSED, manual-assignment mode ships
labeled**; NEVER cut P8-3 visible fingers or P8-2 coupling (Annex A cut
order).

## S32 contract facts (what S33 builds on)

- **P8-7 LANDED as gated additive core; L7 = REFUSED-with-evidence**
  (full entry in TASKS.md; numbers in BENCHMARKS ROOT block): the drift
  track (DriftTrack: clip source measured-3D via the sampler's world
  hips heads; video source approximate-in-plane, depth == 0 exactly)
  rides the ACTION (additive `CanonicalAction.root_track`; NO payload
  format change); the root-motion-aware contact pass detects on the
  compensated frames and pins walk-in-place in stored space (A1); the
  >= 5x family demonstrated at 46351.9x on the drift GT fixture; a zero
  track is byte-identical to the in-place path (pinned by test + gate
  row); clip-sample format 2 = the additive `hips_track` carrier
  (`--root-track`, default bytes unchanged — the 57111-byte fixture
  sample re-printed identical). **A3 (the corrected finding): the
  Xbot.glb carries NO root motion on ANY of its seven clips** — the
  S24 mechanism attribution was wrong; MOTION_LIBRARY.md carries the
  dated correction note (history not rewritten). All prior gate
  numbers byte-identical (RM_BAKE 0.0242° ×2, RM_FOOT_LOCK
  0.0371→0.0000, RM_MOTION 44997x, RM_SCENE 0.3388/0.8279, RM_COUPLE
  0.00016/0.00035, RM_FINGER 0.0070°/0.00°/10.30°, RM_FACE 6 rows,
  RM_CAM 6 rows, RM_SPINE 5 rows, RM_ROOT 11 grep rows).
- **Core `root_motion.py`**: DriftTrack + track_from_clip_field +
  track_from_payload_stream + compensate/decompensate (zero-delta
  tuple REUSE = the byte-identity mechanism) + detect_contacts_root_aware
  + lock_feet_root_aware (delegating to the UNTOUCHED contacts.py —
  LOCK_NOTE_SUFFIX is a shared constant, the D-016 way); **17 tests in
  test_root_motion.py = 585 total.**
- **NOT landed (declared)**: the root-motion BAKE (keying the track
  onto the rig's root — needs its own gate rows + byte-identity
  argument; no real source exists locally per A3); the video-path
  track ATTACH (the constructor exists + probe-tested; the
  load_action wiring is a session/addon decision, the S31 precedent);
  the certified-composition rewiring (the session executor / MCP keep
  the in-place path verbatim; the root-aware pass is opt-in core API).
- **Gate env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- **Instrument lessons (S32, do not re-learn)**: Blender can mask a
  crashed script with exit 0 — the gates grep the FINAL row (`RM_ROOT
  GATE: PASS`), never trust the exit code alone (S32's gate crashed
  twice before the greps caught it; both crashes were
  ActionFrame-vs-pairs confusion in the gate's own glue); a fixture
  keyed on joint angles about a translating joint DRAGS its distal
  joints (the A2 counter-sweep lesson — author world-truth fixtures
  against the translation, then measure); ruff I001 wants the
  `riggermortis_addon` import AFTER the `riggermortis` import block in
  the gate files (autofix knows); a "tuple" of adjacent string literals
  without per-element commas is ONE string (S32's notes bug).
- **549 → 568 → expect 585+ tests** (S32 added 17); CI GREEN through
  the S32 pushes (checked at close; appended in PROGRESS).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-8 work order below.
- Silent (21st): proceed with P8-8 directly.
- Then read, in order: STATE/ROADMAP.md (P8-8 + Annex A.1/A.2 — the
  bars are law: swap <= 2%, alarm >= 90%, bake cost measured+published
  BEFORE any claim; A.2: swap > 10% after repair → auto-identity
  REFUSED, manual-assignment ships labeled), docs/SCENES.md (the
  CanonicalScene + the coupling pass), docs/ROOT_MOTION.md (the S32
  as-built + A1–A3), docs/MOTION_LIBRARY.md (the corrected note),
  STATE/NEXT.md, STATE/TASKS.md (claim P8-8 with [S33]),
  STATE/PROGRESS.md (S32 entries), STATE/DECISIONS.md (D-023 WRITTEN;
  D-018 stays reserved), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
  docs/BENCHMARKS.md (the ROOT + SCENE blocks), docs/POLICY.md (D-019 —
  scene animation IS a content-carrying surface: check the subjects;
  MCP stays SFW, test-pinned), and the claim-bearing surfaces
  docs/LAUNCH.md + docs/TUTORIALS.md (one grep sweep together IF a
  number changes).
- Register as Session 33 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**585 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S32 discipline).

## S33 work order — P8-8 Multi-character video → scene animation

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST**: open docs/SCENE_ANIMATION.md (the ROOT_MOTION.md
   sibling pattern — never a fork): the P2-1 job container gains
   per-frame MULTI-FIGURE payloads; per-frame coupling runs P8-2's
   `couple_scene` with placements MEASURED per frame; fingers/facials
   ride per figure (P8-3/P8-4 namespaces, already additive); the
   identity-stability algorithm is COMMITTED in the roadmap — per-frame
   figure→character assignment by pose-similarity cost matrix, a
   DETERMINISTIC assignment (Hungarian, keyed order — never iterate
   sets), a cost jump between consecutive frames raising a swap alarm,
   the manual per-frame override map winning over everything; the drift
   track rides per figure where the stream carries drift (reuse
   `root_motion.py` verbatim, D-016); scene actions → bake BOTH rigs in
   one pass. Declare every additive field; NO payload format change
   beyond the existing v3 `figures[]` (the track precedent rides the
   action).
2. **PROBE-FIRST xtask/scene_anim_probe.py** (RM_SANIM lines,
   grep-tested both shapes before push): (a) the synthetic two-person
   fixture — the engine-built deterministic renderer, two figures with
   KNOWN per-frame poses and ONE authored crossing (the swap-prone
   class; the A.3 engine-fixture law); (b) identity assignment: the
   swap rate MEASURED on the fixture (<= 2% bar), the swap alarm
   catching >= 90% of the authored crossings (the fixture IS the
   alarm's GT); (c) per-frame coupling residuals <= the 2% torso-span
   bar; (d) per-frame scene bake cost MEASURED on the mid-laptop
   baseline and PUBLISHED (never claimed before measured); (e) the
   manual-override-wins row; (f) REFUSE classes loud (single-figure
   streams, unassignable frames); (g) DETERM twins.
3. **Core**: the deterministic assignment + the swap alarm + the
   per-frame scene-action builder as additive pure-core modules (the
   spine.py pattern); consumers that ignore them byte-identical; the
   additive-only law everywhere.
4. **Gate**: `xtask/scene_anim_gate.py` (the sibling file per the
   Mimosa workaround, RM_SANIM rows wired into verify_pose_apply.sh +
   the Makefile lint list): the bars above + twin byte-identity + all
   prior numbers byte-identical (incl. the S32 RM_ROOT rows).
5. **If early**: the S31 declared-open CLI/addon invocation wiring for
   the arch/roll passes (measured work only), or the P8-2 pin-suggestion
   inference (keypoint proximity) as desk DATA — measured work only,
   never auto-enforced.

Definition of S33 failure (name it, avoid it): a swap-rate claim without
a measured number on the fixture, an identity assignment that iterates a
set (non-deterministic), a bake-cost claim made before its measurement,
an in-place pose/action that moves a single byte, a touched frozen-role
set / D-021 / D-022 / D-023 namespace, or ANY claim without a test/gate
citation. Anything 80% done is 0% shipped — park cleanly at a unit
boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored; every inferred thing carries confidence + residual); park
  criteria (two stalled probe/gate cycles → park with evidence,
  reorder); the cut order (P8-9 time-to-fix → P8-6 roll (LANDED) →
  NEVER P8-2/P8-3); policy D-019 across new surfaces (scene animation
  carries content — check the subjects; MCP stays SFW, test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap (above).
- STATE stamps: real UTC, read-then-write-then-verify.
- Mimosa: bash writes of source files blocked — Write/Edit; new sibling
  FILES scan clean where in-place edits trip path FPs; expect the
  pagedoc.py import-struct FP at every commit; heredoc/append FPs when
  text names source files — Edit tool + -F commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- Blender's exit-0 masking of crashed scripts (S32) — grep the final
  gate row; mathutils nested rich-compare FLAKY (plain-float tuples);
  place-update-then-measure; the two-pass fixture-builder rule; the
  S15..S32 facts in SESSION32_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S34 =
P8-9 review UX speedrun + the P1-8a fallback estimator per the session
map (the P8-9 bars: median scripted time-to-fix <= 15 s per flagged
defect; estimator adoption: no-person <= 1/10 on the anime benchmark,
latency <= 2x DWPose CPU, flip-margin parity — the full third-model
amendment ritual applies to P1-8a), UNLESS a park/reorder happened (say
which and why); write STATE/SESSION34_PROMPT.md in this pattern
(contract facts, STEP 0, the P8-9 work order with its Annex bars);
update STATE/SESSIONS.md row; commit + push (routine commits
authorized; keep CI green, fix inline like S12..S32); expect and
disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up). PyPI
description + Blender Extensions upload — LO's site-side steps (his final
session). P6-3 packaging + P6-2a wiring — roadmap slack. P1-8a — P8-9.
Windowed Blender GL stability — best-effort only, never staged.
Detector-visible mannequin fixtures (the P8-5 tier-2 path) — NOT MET with
evidence; reopened only if a detector-visible engine-built fixture path
exists (the A.3 re-validation trigger). Root-motion BAKE — declared S32
follow-up; revisit only when a real root-motion source exists.
