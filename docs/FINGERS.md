# Fingers (P8-3) — data audit + design skeleton

The P8-3 DATA AUDIT (measured 2026-09-24, S26 early-finish work — "what the
detection layer actually exposes of the 133 kps today") plus the design
skeleton S28 will build against. DESIGN SKELETON ONLY: nothing here is a
claim until a test, probe line, or gate number cites it; the build lands in
S28 per the session map, with the D-021 DECISIONS entry WRITTEN when that
code lands (never cited as existing before then — the round-3 strike S2
rule).

## The audit — where the 133 keypoints live today (measured)

COCO-WholeBody partition (pinned by an assertion in
`core/src/riggermortis/inference/poses.py`): 17 body + 6 foot + 68 face +
21 + 21 hand = 133. Index ranges are NAMED CONSTANTS: `FACE_START 23 /
FACE_END 91`, `HAND_L_START 91 / HAND_L_END 112`, `HAND_R_START 112 /
HAND_R_END 133` — P8-3 consumes the hands through these constants, never
re-typed literals.

| stage | hands/face present? | measured on the P1-9 photo (real models) |
|---|---|---|
| ONNX output (`detect_keypoints`) | YES — the wrapper asserts the 133-simcc shape | all 133 emitted |
| `Figure` (`inference/poses.py`) | YES — all 133 kps + 133 confidences, validated `!= 133` raises | — |
| `rigpose detect --json` (detection payload) | YES — full 133 + confidences ride | hand.L conf mean **0.650** max 0.700, 0/21 zero; hand.R mean **0.857** max 0.894, 0/21 zero; face mean **0.958**, 0/68 zero; body mean 0.812 |
| `observations_from_keypoints` (solve input) | NO — maps ONLY the 17 body + 6 foot indices; hand/face indices never read | the drop point |
| `CanonicalPose` / pose payload (`pose` dict) | NO — 22 canonical roles only | `positions` keys = the 22 roles |

**Conclusion (measured, not assumed): the finger data already flows
end-to-end to the DETECTION payload with per-keypoint confidences — the
per-finger visibility gate signal P8-3 needs is already shipped. The drop
happens at the canonical-solve boundary** (`observations_from_keypoints`
reads only body/foot indices), so P8-3 is a SOLVE+PAYLOAD+APPLY extension,
not a detector change. No new model, no new download, no wrapper change
(P6-6's never-list untouched).

## Design skeleton (S28 fills this in; each section becomes as-built there)

1. **Payload path (ADDITIVE, format 3 unchanged)**: a new optional
   top-level `hands` field — per figure… carried per FIGURE entry (each
   entry gains optional `hands`: `{"hand.L": {"wrist": [x, y, conf], …21
   kps}, "hand.R": {…}}`) so a figure's hands travel with the figure.
   Readers that ignore unknown fields keep working byte-identically (the
   standing policy); the contract test pins a hands-free payload byte
   shape. COCO-WholeBody hand layout: kp 0 = wrist, then 5 fingers × 4
   (mcp/pip/dip/tip) in the fixed order thumb→index→middle→ring→pinky —
   pinned by named constants added to `poses.py` in the same commit.
2. **Solve (per hand, per finger)**: finger chains solve ONLY from observed
   kps — each of the 5 fingers gets a 3-joint direction chain (mcp→pip,
   pip→dip, dip→tip in canonical units, wrist-anchored, hand-frame from the
   canonical wrist→forearm direction). Per-finger confidence gate: a finger
   is SOLVED iff its chain's kp confidences clear the declared floor
   (D-008-order-of-magnitude default, declared untuned); below it the
   finger is SKIPPED + FLAGGED — a wrong finger reads as broken, an absent
   one reads as clean (the roadmap's honesty rule; Annex A.1 demands 100%
   gated-skip on the occlusion fixtures: hand-behind-back, clenched fist).
3. **Canonical namespace (the D-021 amendment)**: `hand.L.finger.<name>[0..2]`
   chains (`thumb`, `index`, `middle`, `ring`, `pinky`) in a SEPARATE
   additive map — the frozen 22-role core untouched; consumers that ignore
   fingers work unchanged. The DECISIONS entry D-021 is WRITTEN at this
   landing (additive-map format version + policy coverage per the roadmap's
   standing constraints). Nothing renames, nothing reorders.
4. **Apply**: finger bones via the preset mapping (authored once per rig in
   the preset's additive `hands` binding — the P6-1a `secondary` pattern);
   `bake_action`/`apply_payload` gain the additive binding, validated
   against the live rig (exists, parent-first under the mapped hand bone).
   A rig without finger targets reports a LOUD capability line, never a
   silent no-op (the P8-4 two-class pattern's precedent).
5. **Accept bars (Annex A.1, pre-declared)**: 20-pose hand benchmark
   (fist/spread/grip/pinch…): per-finger direction error median ≤ 20°,
   p90 ≤ 35° on VISIBLE fingers; occlusion fixtures (hand-behind-back,
   clenched) 100% gated-skip; metarig + Mixamo-class apply ≤ the FK family
   bar. The measured audit above (hand conf means 0.65–0.86 on a real
   photo, zero dropouts) says the confidence signal is strong enough to
   gate on — the benchmark measures the DIRECTION bars.
6. **Policy (D-019)**: fingers carry no content by themselves — no new
   policy surface; the add-on's existing subject checks apply unchanged.

## What P8-3 deliberately does NOT do (until its own session says so)

- No face work (P8-4's 68-kp table is its own design page section).
- No payload format 4 (v3 stays; `hands` is an ADDITIVE field).
- No re-solve of the body from hand kps (the wrist stays the boundary).
- No live-mode finger streaming (rides P5's existing pipeline after the
  static path is proven).

## As-built design (S28, written BEFORE the build — the sections below are
## what the probe/core/gate implement; the skeleton above is extended, not
## forked)

Two amendments to the skeleton, earned while designing (recorded here
BEFORE code, so the D-021 entry cites this page):

- **A1 — the payload carries SOLVED chains, not raw kps.** The skeleton's
  `hands` example shape (`{"wrist": [x, y, conf], …}`) was raw detection
  data. The D-009 pattern says payloads carry SOLVED data (frontends
  apply, they don't re-solve), and the audit proved the raw 21 kps +
  confidences already ride the DETECTION payload — carrying them again in
  the pose payload would duplicate the same bytes under two names. As
  built, `hands` carries the solved canonical finger chains + per-finger
  skip ledgers. The detection payload is untouched.
- **A2 — the namespace stores 4 joints per finger, not 3.** The
  roadmap's `hand.L.finger.<name>[0..2]` counted the 3 articulated
  SEGMENTS (mcp→pip, pip→dip, dip→tip). The apply path orients a bone
  toward `child_joint − joint`, so the tip must exist for the dip segment
  to have a target. As built, each finger chain stores its 4 observed
  joints (`mcp`, `pip`, `dip`, `tip`) — 3 segment directions derive from
  them at apply time. D-021 records the 4-joint wording.

### Data model (core `fingers.py`, fingers-format 1 — pure stdlib)

``FingerChain`` — one solved finger:

| field | type | meaning |
|---|---|---|
| ``joints`` | dict[str, Vec3] | the 4 solved joints keyed `mcp`/`pip`/`dip`/`tip` (canonical units, same space as the 22 body roles) |
| ``confidence`` | float | min of the chain's 4 kp confidences (the observation midpoint rule: the chain is only as strong as its weakest joint) |

``HandPose`` — one solved hand:

| field | type | meaning |
|---|---|---|
| ``fingers`` | dict[str, FingerChain] | solved fingers keyed `thumb`/`index`/`middle`/`ring`/`pinky` (stored sorted) |
| ``skipped`` | dict[str, str] | per skipped finger: the LOUD reason with the exact confidence values (`"confidence 0.21/0.34/0.02/0.30 below floor 0.55"`) — the skip ledger, never silent |
| ``wrist_conf`` | float | the wrist kp's confidence (the anchor's strength) |

``CanonicalPose.hands`` — additive field, `dict[str, HandPose]` keyed
`hand.L`/`hand.R`, default EMPTY:

- The frozen 22-role `positions` map is untouched. Consumers that ignore
  fingers never see them (the roadmap's additive-namespace rule).
- `to_dict()` OMITS the `hands` key when empty — a hands-free pose's
  output is byte-identical to pre-S28 output (the pins precedent; pinned
  by contract test). `from_dict` reads `hands` when present, tolerates
  absence (v2-era payloads and every older fixture stay valid).
- `mirrored()` mirrors hands (roles swap `hand.L`↔`hand.R`, x negates;
  depth y unchanged — geometry operation, not a re-solve). `toggled()`
  never touches hands.

### COCO-WholeBody hand layout (poses.py, named constants, same commit)

- `HAND_KP_COUNT = 21`; kp 0 = wrist, then 5 fingers × 4 joints
  (mcp/pip/dip/tip) in the fixed order thumb→index→middle→ring→pinky.
- `FINGER_ORDER: tuple[str, ...]` + `FINGER_JOINTS: tuple[str, ...]` +
  `hand_kp_index(hand: str, finger: str, joint: str) -> int` — the ONE
  table; consumers never re-type literals (the FACE/HAND start-end
  constants stay the index-range source of record).
- The helper validates its arguments loudly (unknown hand/finger/joint →
  ValueError with the known names).

### The solve (core `fingers.solve_hands(keypoints, confidences, pose)`)

Inputs: the figure's full 133-kp arrays + the solved body `CanonicalPose`
(the hand anchor comes from `pose.positions["hand.X"]`, the hand frame
from the canonical wrist→forearm direction). Returns
`{"hand.L": HandPose | None, "hand.R": HandPose | None}` — `None` when
the hand's WRIST kp is unusable (below the gate: no anchor, no solve,
reason loud in… nothing — a wrist below floor means the whole hand is
skipped; the returned dict simply has no entry, and the pose's payload
shows the hand absent = clean, the honesty rule: an absent hand reads as
clean, a wrong finger reads as broken).

Per hand, per finger (all math in the body solve's plane space — in-plane
(u, v) from pixels exactly as the body solve transforms them: centered on
the anchor, scaled by `pose.scale`, v flipped):

1. **Confidence gate (the honesty line, made numeric)**: the finger is
   SOLVED iff ALL FOUR chain kps (mcp, pip, dip, tip) have confidence ≥
   `FINGER_CONF_FLOOR = 0.55` — the CONVENTIONS ambiguity bar, reused
   (the coupling enforcement floor precedent), declared untuned. Below:
   the finger goes to `skipped` with its four exact values; it is NEVER
   guessed. (100% gated-skip on the occlusion fixtures is this rule,
   measured.)
2. **Chain root**: the mcp joint = the observed in-plane mcp position at
   the WRIST's depth (`y = y_wrist`) — the chain-root flatten prior
   (declared untuned; the hand is ~0.05 canonical units deep at most, so
   the wrist's depth is the best anchor the 2D view supports).
3. **The 3 segments** (mcp→pip, pip→dip, dip→tip): in-plane Δ(u, v) read
   off the image; canonical segment length `L` from
   `FINGER_SEGMENT_LENGTHS` (declared D-008 priors below); depth
   magnitude `|Δy| = sqrt(L² − inplane²)` (0 when the segment is at or
   over full length in-plane — straightened, like the body solver's
   clamp); SIGN: the DECLARED FORWARD-CURL rule — every segment takes
   `Δy = −|Δy|` (canonical forward, the D-008 elbow-forward prior one
   level down). PROBE-EARNED AMENDMENT (the first draft enumerated 2³
   signs under a flatten prior `E = Σ conf·(y−y_wrist)²`): the
   enumeration is WRONG for curled fingers — the all-flat combo
   minimizes the flatten energy, so a "solved" grip un-curls itself. A
   declared sign solves curled hands exactly (prior-consistent GT:
   median 5.87° on the 35°-curl fixture) and hands curling AWAY from
   canonical forward are the documented single-view miss class (the
   elbow prior's exact analog — review-fixable in a later session, never
   guessed). Clenched hands are occlusion fixtures (gated-skip per Annex
   A.1) and never reach the direction bars.
4. **Positions**: finger joints = wrist position + solved offsets — the
   chain lives in the same canonical world space as the body, so FK
   target directions derive without any hand-local frame algebra.
5. **Hand frame**: `wrist→forearm` canonical direction
   (`positions[hand.X] − positions[forearm.X]`) is the v1 degeneracy
   surface, not a solve input: probe (a) measures its stability on real
   detections (near-zero forearm projections = near-degenerate frame)
   and the number publishes; if a later session needs palm-plane priors
   (curl depth), the frame is there.

`FINGER_SEGMENT_LENGTHS` (declared untuned D-008 priors, canonical units
of hip height; the hand role spans 0.11 total): proximal 0.030,
middle 0.022, distal 0.016 for the four fingers; thumb 0.032/0.026/0.020
(thumb segments run longer). The probe measures real 2D chain lengths
against these and the numbers publish next to them — priors stay
declared, never fitted to the fixtures (D-008).

### The namespace (D-021) — additive finger roles

- Role names: `hand.<SIDE>.finger.<name>.<joint>` — e.g.
  `hand.L.finger.index.pip`. 2 sides × 5 fingers × 4 joints = 40 roles.
- They live in a SEPARATE topology table (`FINGER_PARENT` +
  `finger_parent(role)` in `fingers.py`) — `ALL_ROLES`, `CANONICAL`, and
  `PRIMARY_CHILD` are untouched; the mapper never assigns finger roles
  (they bind via presets only); `CORE_ROLES` untouched.
- FK topology: `hand.L` (the mapped body role) parents
  `…finger.<f>.mcp` parents `…pip` parents `…dip` parents `…tip`.
  `bone_target_direction` gains an additive branch: finger roles read
  their target from `pose.hands` through this table; body roles are
  unchanged (byte-identical behavior pinned).
- **D-021 is WRITTEN in the commit where this namespace code lands** —
  additive-map policy coverage, the 4-joint wording (amendment A2), and
  the no-new-policy-surface statement (fingers carry no content by
  themselves; D-019's subjects unchanged).

### Payload contract (format 3 UNCHANGED — additive per-figure field)

- Each figure entry (and the mirrored v1 top-level pose) carries the
  pose dict as before; `pose.to_dict()` now emits `hands` ONLY when the
  pose has any. `build_pose_payload` needs no signature change —
  entries flow through. Readers that ignore unknown fields keep working
  (the standing policy); the contract test pins:
  (a) a hands-free payload written by this build is byte-identical to
  pre-S28 output; (b) a payload WITH hands round-trips through
  `CanonicalPose.from_dict` exactly; (c) an old-format payload applies
  byte-identically (the existing back-compat pins keep passing).
- The apply path never writes payloads (S27's full-precision write-back
  rides in-memory dicts) — fingers ride the same way.

### Apply — preset-mapped, loud on both no-target sides

- **Preset schema**: format 2 GAINS an optional `hands` object —
  `{finger_role: bone_name}`, values must be unique bones (a bone
  implementing two finger roles = the cross-binding double-key class the
  secondary guard refuses). Validation: every key must be a known finger
  role (loud refusal with an example), every value a non-empty string.
  Format stays 2 (additive optional field, the pins-in-v3 pattern);
  older builds ignore the unknown field (Preset.from_dict reads known
  keys only). `resolve_hands(preset, rig_fingerprint, force=False)`
  mirrors `resolve_secondary` — the SAME fingerprint gate.
- **Core FK**: `apply_canonical_pose(rig, mapping, pose,
  finger_map=None)` — optional additive parameter; finger roles from
  `finger_map` join the same top-down parent-space pass (depth-then-name
  order inherited), so parent-space accumulation stays exact. `None` =
  no finger application; when the POSE carries hands and `finger_map` is
  None/empty, the report gains the LOUD capability line:
  `"hands: N finger chain(s) solved; no finger bindings for this rig —
  fingers not applied"` — never a silent no-op (the P8-4 two-class
  pattern's precedent, landed here first).
- **Apply fidelity**: finger bones inherit the 0.5° family bar —
  `verify_application` reports finger-role errors through the same
  simulate-FK path (targets from `pose.hands`).
- **CLI/session/addon wiring**: `rigpose pose` runs `solve_hands` after
  `solve_pose` (default on; fingers appear only when kps clear the
  floor — a hands-free figure's payload is unchanged). The add-on's
  `apply_pose`/`apply_payload` builds `finger_map` from the loaded
  preset's `hands` bindings when present; `rm_role_*` props stay
  body-roles-only (finger bindings are preset-authored once per rig, per
  the roadmap).

### Accept bars (Annex A.1 — restated, the gate implements these)

1. **Direction bars**: per finger SEGMENT direction error on the
   20-pose synthetic hand benchmark (fist/spread/grip/pinch/point/cup/…,
   deterministic generator with GT 3D chains, projected to 2D + conf —
   SYNTHETIC-labeled): median ≤ 20°, p90 ≤ 35° over VISIBLE (solved)
   fingers. Errors measure solved-vs-GT 3D segment directions.
2. **Occlusion gating**: the named fixtures (hand-behind-back: hand kps
   conf 0; clenched: kps present but below-floor) show 100% gated-skip —
   zero solved fingers, zero guessed fingers, every skip LEDGERED with
   its reason.
3. **Apply ≤ FK family**: metarig-class + Mixamo-class fixture rigs
   (engine-built, TWO-PASS builder) with preset hand bindings apply
   finger chains at ≤ 0.5° worst (the family bar); hands-free rig
   behavior unchanged.
4. **Loud no-target**: a rig without bindings + a pose with hands → the
   capability line, verbatim-greppable in the gate.
5. **Byte-identity**: hands-free payload write byte-identity; all prior
   gate numbers byte-identical; the 482-test suite green.

### Probe plan (xtask/finger_probe.py — BEFORE the core build, RM_FINGER
### PROBE lines, grep-tested both shapes)

- (a) HAND-FRAME: on real detections (the benchmark photos with real
  models), measure the canonical wrist→forearm span per hand —
  distribution + degeneracy count (span < 10% of canonical 0.28). The
  frame's stability number, published.
- (b) CHAIN ACCURACY: real detections → solve → re-project the solved
  chains to 2D → per-finger reprojection residual in px vs observed kps
  (the depth priors' honesty measured on the audit's 0.65/0.86 conf
  bands). Also: measured real 2D segment lengths vs the declared priors
  (published next to them).
- (c) OCCLUSION GATE: the synthetic occlusion fixtures → 100%
  gated-skip, ledger verbatim.
- The probe contains the DRAFT solve (the coupling_probe recipe): core
  `fingers.py` lifts it, tests pin it.

### Probe answers (as-built, 2026-09-25 — `xtask/finger_probe.py`, RM_FINGER
### lines; 8/8 PASS exit 0, pure core + the pinned DWPose models)

- **DEPTH-SIGN (the finding that earned its keep)**: the first draft's
  flatten-prior sign enumeration un-curls gripped hands (the all-flat
  combo wins the energy) — replaced by the declared forward-curl sign
  (§ The solve, item 3). Prior-consistent GT then reconstructs curled
  chains at median 5.87° (curl fixture), 0.00° (flat/spread).
- **DIRECTION**: 45 segments over flat/spread/curl fixtures — median
  0.00° (bar 20), p90 7.63° (bar 35) [SYNTHETIC, prior-consistent GT].
- **GATE-OCCL / GATE-FIST**: finger kps conf 0 and conf 0.3 fixtures →
  0 solved, 5/5 ledgered with verbatim below-floor reasons each.
- **GATE-SOLVE**: visible hand → 5/5 solved, finite joints.
- **LAYOUT / DETERM**: the 40 draft indices tile the COCO hand ranges
  exactly (91..133); twin solves identical.
- **REAL-FRAME** (6 P1-9 photos, real models): 11 poseable hands, wrist→
  forearm span median **0.280 u** — the canonical forearm ratio, i.e.
  the frame's stability surface is solid; **0 degenerate** hands (span
  < 10% of canonical never occurred).
- **REAL-CHAINS**: **25 fingers solved / 30 gated-skipped** at the 0.55
  floor across those photos — real photos skip loudly roughly half the
  time (honest: an absent finger reads as clean), and the
  occlusion-class photo (human_hand_behind_head) gated **all 5 fingers**
  of its hand — the Annex A.1 gated-skip requirement holds on REAL data,
  not just fixtures.
