# SESSION 29 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes landed (P8-1): one
payload poses N paired rigs in one action, pins carried as data, an
APPROXIMATE camera stages from the reference framing. Contact coupling
landed (P8-2): AUTHORED pins close deterministically (fracs 0.00016/0.00035
vs the 0.02 bar), suggested/below-floor pins stay loud data, the solve is
pure position-space surgery the certified apply consumes unchanged. Fingers
landed (P8-3): the D-021 additive namespace solves per-finger 3-segment
chains ONLY from observed hand keypoints — below the 0.55 floor a finger is
skipped + LEDGERED, never guessed (occlusion fixtures 100% gated-skip; the
20-pose bench measures median 0.00°/p90 10.30° vs bars 20°/35°; preset-
mapped apply at 0.0070° worst on metarig- and Mixamo-class rigs). Toon
renders, manga pages. Live pose-stream puppeteering on the replay path.
No cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** V1 = Phase
8 complete + the Scene Test scorecard green (target S35; Annex A.3: the
scorecard overrides the calendar). S28 landed P8-3. **S29's rock is P8-4
facials** — the PUBLISHED landmark→param table (brow raise / blink / jaw
open / smile-pout / cheeks; gaze ONLY with iris kps — the pinned DWPose
has none, so gaze stays out unless a detector variant supplies them),
bone + shape-key binding classes (both loud, neither present → "no facial
targets"), **D-022 RESERVED for the facial namespace, WRITTEN only at
that landing** (never cited before — the strike-S2 rule; fingers took
D-021), per-param refusal branch after two failed cycles (Annex A.2).
NEVER cut P8-3 fingers or P8-2 coupling (Annex A cut order).

## S28 contract facts (what S29 builds on)

- **P8-3 LANDED** (full entry in TASKS.md; numbers in BENCHMARKS FINGERS):
  core `fingers.py` — the 40-role namespace `hand.<SIDE>.finger.<name>.
  <joint>` in a SEPARATE additive map (ALL_ROLES/PRIMARY_CHILD/CORE_ROLES
  untouched, contract-pinned); FingerChain/HandPose loud-validating;
  `solve_hands` pure + deterministic (per-finger gate = all 4 chain kps ≥
  FINGER_CONF_FLOOR 0.55, the CONVENTIONS bar reused; below → skipped +
  ledgered with verbatim reasons; depth magnitude from declared segment
  lengths; depth SIGN = the declared FORWARD-CURL rule — the probe
  PROVED a flatten-prior enumeration un-curls grips); named hand
  constants in poses.py (`hand_kp_index` — the wrist is a BODY keypoint,
  index 9; the hand block covers only the 20 finger kps).
- **CanonicalPose.hands**: additive, keyed hand.L/hand.R, default EMPTY;
  `to_dict` OMITS the key when empty (hands-free poses serialize
  byte-identically — contract-pinned; S29 copies this for `face`);
  `from_dict` tolerates absence; `mirrored` swaps sides with x-negation.
- **Apply**: fk_apply `apply_canonical_pose(rig, mapping, pose,
  finger_map=None)` — finger roles join the same top-down parent-space
  pass; the LOUD capability line when a pose carries hands and no
  bindings exist (and the mirror note when bindings exist but the pose
  has no hands); `.tip`/non-finger binding keys refuse. Preset `hands`
  bindings additive in format 2 (segment roles only, unique bones, no
  body-mapping double-key) with `resolve_hands` on the SAME fingerprint
  gate. CLI solves hands by default; session `apply_pose` gains additive
  `preset_path`/`preset_force` (KNOWN_ACTION_KINDS 6 + MCP tool tables
  untouched).
- **Gate**: `xtask/finger_gate.py` (couple_gate's SIBLING — new files
  scan clean where in-place edits trip Mimosa path FPs) wired into
  verify_pose_apply.sh: FINGER-BENCH median 0.00°/p90 10.30° (bars
  20/35) over 300 segments × the 20-pose class [SYNTHETIC,
  prior-consistent GT]; FINGER-GATE-OCCL 100% gated-skip both classes;
  FINGER-APPLY/FINGER-MIXAMO live finger FK worst 0.0070° (bar 0.5)
  through the FULL preset contract; FINGER-NOTARGET the capability line
  verbatim; FINGER-TWIN 36 bones byte-identical. Probe:
  `xtask/finger_probe.py` 8/8 with REAL rows (frame span median 0.280 u
  over 11 hands, 0 degenerate; 25 solved / 30 gated-skipped on real
  photos; the hand-behind-head photo gated 5/5).
- **P8-4 audit precedent DONE** (docs/FINGERS.md table): all 133 kps +
  confidences reach the detection payload (face conf mean 0.958, 0/68
  dropouts); the drop is at `observations_from_keypoints`. P8-4 = a
  SOLVE+PAYLOAD+APPLY extension; no new model, no wrapper change, P6-6
  never-list untouched.
- **507 → expect ~530+ tests** (S28 added 25 finger contract tests); CI
  green through the S28 push; all gate numbers through S28 byte-
  identical (RM_BAKE 0.0242° ×2, RM_FOOT_LOCK 0.0371→0.0000, RM_TAILS,
  RM_MOTION 44997×, RM_SCENE, RM_COUPLE, RM_FINGER).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-4 work order below.
- Silent (17th): proceed with P8-4 directly.
- Then read, in order: STATE/ROADMAP.md (P8-4 + Annex A.1/A.2 — bars are
  law: per-param monotonicity ≥ 9/10 per param on the 10-expression
  benchmark, bone apply ≤ 0.5° family, shape-key applied-vs-intended
  delta ≤ 0.1 normalized; a param below bar after two redesign cycles →
  REFUSED per param, documented), docs/FINGERS.md (the P8-3 as-built —
  the pattern S29 reuses; the audit table row for face), docs/STYLE.md
  (shape-key surfaces), STATE/NEXT.md, STATE/TASKS.md (claim P8-4 with
  [S29]), STATE/PROGRESS.md (S28 entries), STATE/DECISIONS.md (D-021 now
  WRITTEN as the additive-namespace precedent; D-022 RESERVED; D-018
  stays reserved), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
  docs/BENCHMARKS.md (FINGERS block), docs/POLICY.md (D-019: facials
  carry no content by themselves, but CHECK the subject list —
  expressions on fictional rigs ride the existing checks; MCP stays SFW,
  test-pinned), and the claim-bearing surfaces docs/LAUNCH.md +
  docs/TUTORIALS.md (one grep sweep together IF a number changes).
- Register as Session 29 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**507 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S28 discipline).

## S29 work order — P8-4 Facials

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST: open docs/FACE.md** (the FINGERS.md sibling pattern —
   never a fork): the additive per-figure `face` payload field (format 3
   unchanged, omit-when-empty byte-identity pinned — the `hands`
   contract, contract-test a face-free payload); the PUBLISHED
   landmark→param table with each param's exact landmark arithmetic
   (brow raise = brow-kp row height delta vs face height; blink = eye
   aspect ratio vs the subject's open-eye prior; jaw open = lower-lip
   drop vs face height; smile/pout = mouth-corner elevation + width
   ratio; cheeks); neutral = a POPULATION prior declared D-008-untuned
   (single images carry no personal neutral — say so in the report);
   COCO-WholeBody face layout via NAMED constants in poses.py the same
   commit (FACE_START 23 / FACE_END 91 exist; add the per-point names
   P8-4 consumes through them, never re-typed literals). **D-022 WRITTEN
   in the commit where the facial namespace code lands** — the frozen
   22-role core and the D-021 finger namespace untouched.
2. **PROBE-FIRST xtask/face_probe.py** (RM_FACE lines, grep-tested both
   shapes before push): (a) landmark stability on real detections (the
   audit's 0.958 conf band — per-region conf distributions); (b)
   per-param monotonicity on synthetic GT faces (parametric face
   fixtures with known param values, projected to 2D — the
   finger_probe.py recipe); (c) the no-observation gate (partial faces
   = skipped + LEDGERED, never guessed — the finger gate's honesty
   row); (d) the blink-prior question: the open-eye prior is
   population-level — measure its spread on real detections and publish.
3. **Core**: the param table into the solve path (additive namespace +
   loud validation + round-trips; the pose payload carries face per
   figure; skip ledgers per param; a param below its observation
   threshold is skipped + flagged, never interpolated).
4. **Apply + gate**: the two binding classes, both LOUD per rig — (a)
   bones via preset mapping (jaw/eye/brow chains — the `hands` binding
   precedent, additive preset field or a `face` section with the same
   validation), (b) shape keys by documented naming convention
   (validated against the live mesh; missing keys report, never
   silently skip); NEITHER present → the loud "no facial targets" line
   (the FINGER-NOTARGET precedent). Gate: `xtask/face_gate.py`
   (sibling file, RM_FACE rows wired into verify_pose_apply.sh): the
   10-expression benchmark (neutral + 9) — per-param monotonicity ≥
   9/10, bone apply ≤ the 0.5° family, shape-key delta ≤ 0.1
   normalized, loud no-target rig, twin byte-identical.
5. **If early**: the P8-2 pin-suggestion inference (keypoint proximity)
   as desk DATA — measured work only, never auto-enforced.

Definition of S29 failure (name it, avoid it): a guessed facial param,
an ungated unobserved param, a touched frozen-role set (or the D-021
finger namespace), a D-022 citation before its commit, a face-free
payload byte change, or ANY claim without a test/gate citation. Anything
80% done is 0% shipped — park cleanly at a unit boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored); park criteria (two stalled probe/gate cycles → park with
  evidence, reorder); the cut order (P8-9 time-to-fix → P8-5 full solve
  → P8-6 roll; NEVER cut P8-3 visible fingers or P8-2 coupling); policy
  D-019 across new surfaces (MCP stays SFW, test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- STATE stamps: real UTC, read-then-write-then-verify.
- Mimosa: bash writes of source files blocked — Write/Edit; new sibling
  FILES scan clean where in-place edits trip path FPs (couple_gate.py /
  finger_gate.py precedent); expect the pagedoc.py import-struct FP at
  every commit; heredoc/append FPs when text names source files — Edit
  tool + -F commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson (pb.matrix.to_translation()),
  joint-angle keying, factory-EMPTY FBX scenes, rotation modes before
  quaternion writes, place-update-then-measure (view_layer.update()
  BEFORE any world-space read), the two-pass fixture-builder rule, the
  wrist-is-body-kp-9 lesson — the S15..S28 facts in
  SESSION28_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S30 =
P8-5 reference camera solve per the session map, UNLESS a park/reorder
happened (say which and why); write STATE/SESSION30_PROMPT.md in this
pattern (contract facts, STEP 0, the P8-5 work order with its Annex
bars: yaw MAE ≤ 7.5° / pitch MAE ≤ 5° / distance MAE ≤ 12% on the GT
set, framing IoU ≥ 0.75, low confidence REFUSES to stage); update
STATE/SESSIONS.md row; commit + push (routine commits authorized; keep
CI green, fix inline like S12..S28); expect and disclose the Mimosa
pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up). PyPI
description + Blender Extensions upload — LO's site-side steps (his final
session). P6-3 packaging + P6-2a wiring — roadmap slack. P1-8a — P8-9.
Windowed Blender GL stability — best-effort only, never staged.
