# Face (P8-4) — design of record

The P8-4 facial-expression extension, designed BEFORE the build (the
docs/FINGERS.md pattern — a sibling design page, never a fork). The data
audit is already DONE (FINGERS.md § The audit, measured in S26): all 68
face keypoints + confidences reach the DETECTION payload (face conf mean
0.958, 0/68 dropouts on the P1-9 photo); the drop is at the canonical
solve boundary (`observations_from_keypoints` reads only body/foot
indices). P8-4 is therefore a SOLVE+PAYLOAD+APPLY extension exactly like
P8-3: no new model, no wrapper change, the P6-6 never-list untouched.

NOTHING on this page is a claim until a test, probe line, or gate number
cites it. **D-022 is RESERVED for the facial namespace and is WRITTEN
only in the commit where the namespace code (`core face.py`) lands**
(the round-3 strike S2 rule; fingers took D-021 at its landing).

## The one structural insight (why faces are simpler than fingers)

Finger chains need CANONICAL 3D joints (they ride the body's FK space).
Face expressions do not: every P8-4 param is a **dimensionless landmark
RATIO** (normalized by the face's own inter-ocular distance or an eye's
own aspect ratio). The solve is pure 2D arithmetic on the detection the
body solve already consumed — no canonical conversion, no depth prior,
no anchor. The pose payload therefore carries SOLVED PARAMS (the D-009
pattern: payloads carry solved data, frontends apply), not landmark
geometry: `face` = params + ledgers + confidences.

## The landmark layout (declared, then measured)

COCO-WholeBody's 68 face keypoints (indices 23..90 in the 133 array,
named band `FACE_START 23 / FACE_END 91` since P0) follow the standard
68-point facial-landmark convention (iBUG-300W order, as DWPose's
wholebody model emits). Declared bands, consumed only through named
constants in `poses.py` (never re-typed literals — the hand precedent):

| band | indices | count |
|---|---|---|
| jaw contour | 0..16 (face-relative) | 17 |
| brow A | 17..21 | 5 |
| brow B | 22..26 | 5 |
| nose bridge | 27..30 | 4 |
| nose bottom + wings | 31..35 | 5 |
| eye A | 36..41 (p0 outer, p1/p2 upper lid, p3 inner, p4/p5 lower lid) | 6 |
| eye B | 42..47 (same convention) | 6 |
| mouth outer | 48..59 (48/54 corners, 49..53 upper, 55..59 lower; 51 upper center, 57 lower center) | 12 |
| mouth inner | 60..67 | 8 |

**Side convention (declared, then MEASURED — the measurement won)**: the
design DECLARED band A (brow 17..21 / eye 36..41) = the subject's left.
The S29 probe MEASURED it on real detections (RM_FACE LATERALITY): band
A sits at IMAGE LEFT — the subject's RIGHT for a camera-facing face — on
**18/18 real faces (median −51.5 px)**. The constants therefore map
`.L` (subject-left) to **band B** (eye 42..47, brow 22..26) and `.R` to
band A; consumers read points only through
`face_kp_index(side, region, ...)`, so the flip stayed the one-line
constant fix the design planned — never code archaeology. D-022 records
the measured map.

## The published landmark→param table (D-022, the 10 params)

DESIGN AMENDMENT (recorded BEFORE code, the FINGERS.md A1/A2 pattern):
**every metric consumes exactly the kps it gates** — the IOD anchor is
the four eye CORNER points (36, 39, 42, 45; outer+inner per eye), not a
band centroid, and the brow metrics read the eye LINE as the corner
midpoint (already gated), not a 12-kp centroid. A single low-confidence
lid point therefore cannot silently skew a scale built from a centroid
that mixes trusted and untrusted points — the gate and the arithmetic
cover the same points, always.

Every param is normalized to [0, 1]; 0 = population neutral; the
neutral is a POPULATION prior declared D-008-untuned (a single image
carries no personal neutral — say so in any report; a person whose
resting brow sits low reads slightly raised, that is the documented
limitation, never hidden). Face scale = IOD = the distance between the
two eye-band centroids (stable under every P8-4 expression — the chin
moves under jaw open, the eyes do not, which is why face HEIGHT is not
the scale). All raw metrics are IOD-normalized ratios except blink
(self-normalizing aspect ratio).

| param | consumes (gated = consumed) | exact arithmetic (image px, y grows down) |
|---|---|---|
| `brow.raise.L` | brow band A (5 kps) + eye A corner line (36, 39 — gated by IOD) | `raise = (eyeA_line_y − browA_mean_y)/IOD` where `eyeA_line_y = (y36 + y39)/2`; param = `clamp((raise − PRIOR_BROW_RAISE) / SPAN_BROW, 0, 1)` |
| `brow.raise.R` | brow band B (5 kps) + eye B corner line (42, 45) | same with band B |
| `blink.L` | eye band A (6 kps) | `EAR = ((|p1−p5| + |p2−p4|)/2) / |p0−p3|`; param = `clamp((EAR_OPEN − EAR) / EAR_OPEN, 0, 1)` |
| `blink.R` | eye band B (6 kps) | same with band B |
| `jaw.open` | kps 51, 57 | `gap = (y57 − y51)/IOD`; param = `clamp((gap − PRIOR_LIP_GAP) / SPAN_JAW, 0, 1)` |
| `smile.L` | kps 48, 54, 33 | `drop = (y48 − y33)/IOD` (corner L below the nose bottom; positive, image y grows down); param = `clamp((PRIOR_CORNER_DROP − drop) / SPAN_SMILE, 0, 1)` |
| `smile.R` | kps 48, 54, 33 | same with y54 |
| `pout` | kps 48, 54 | `w = |x48 − x54|/IOD`; param = `clamp((PRIOR_MOUTH_W − w) / SPAN_POUT, 0, 1)` (narrowing) |
| `cheek.L` | kps 40, 41, 31 | `d = dist(mean(40,41), 31)/IOD`; param = `clamp((PRIOR_CHEEK − d) / SPAN_CHEEK, 0, 1)` (under-eye↔nose-wing compression) |
| `cheek.R` | kps 46, 47, 35 | same with band B points |

Declared D-008 constants (declared as order-of-magnitude defaults BEFORE
any measurement; the three neutral-geometry priors the S29 probe found
disagreeing with real faces were REDECLARED from the measurement —
amendment A4; never fitted to evaluation fixtures — measure-and-declare,
the finger segment-lengths pattern):

| constant | value | role |
|---|---|---|
| `FACE_CONF_FLOOR` | 0.55 | the CONVENTIONS ambiguity bar, reused (the coupling + finger floor precedents) |
| `FACE_ACT_FLOOR` | 0.08 | activation floor: a solved param value below this is BELOW-THRESHOLD — recorded in the skip ledger with its value, stays 0/absent, never interpolated (the work order's "a param below its observation threshold is skipped + flagged") |
| `PRIOR_BROW_RAISE` | 0.30 | neutral brow-to-eye gap / IOD (measured median 0.296 — stands) |
| `SPAN_BROW` | 0.15 | param 1.0 at +0.15 IOD above the prior |
| `EAR_OPEN` | 0.28 | population open-eye aspect prior (measured median 0.283 — stands) |
| `PRIOR_LIP_GAP` | 0.02 | lips-touching gap / IOD. The probe's measured 0.31 median on the P1-9 set is GENUINE open-mouth expression in that expressive photo set, not neutral geometry — the anatomical prior stands and the measured median publishes next to it |
| `SPAN_JAW` | 0.55 | param 1.0 at a 0.55-IOD mouth gap |
| `PRIOR_CORNER_DROP` | 0.40 | neutral corner-below-nose-bottom distance / IOD (pooled measured median 0.403; declared 0.45 would have fired smile on every real neutral) |
| `SPAN_SMILE` | 0.12 | param 1.0 at corners raised 0.12 IOD toward the nose line |
| `PRIOR_MOUTH_W` | 0.83 | neutral mouth width / IOD (pooled measured median 0.832; declared 1.00 would have fired pout on every real neutral) |
| `SPAN_POUT` | 0.25 | param 1.0 at 0.25-IOD narrowing |
| `PRIOR_CHEEK` | 0.72 | neutral under-eye↔nose-wing distance / IOD (pooled measured median 0.731; declared 0.45 could never have fired on a real face) |
| `SPAN_CHEEK` | 0.10 | param 1.0 at 0.10-IOD compression |

**Gaze is NOT a param.** The pinned DWPose has NO iris keypoints; gaze
enters ONLY if a detector variant supplies iris kps (a capability probe
at detection time) — no corner-geometry guessing, ever (the roadmap's
pre-declared condition). D-022 records the conditional.

## Amendment record (probe-earned, recorded before the core build)

- **A1 — the smile reference is the nose bottom, not the corners' own
  line.** The draft corner-elevation metric (`corner vs the corners'
  own mean line`) is DEGENERATE under a symmetric smile: both corners
  rise, the line rises with them, the metric reads zero. A symmetric
  smile is the most common human expression — the reference must be a
  landmark the mouth cannot move: the nose bottom (kp 33). The table
  above already carries the fix.
- **A2 — GT faces are 2D in IMAGE space.** Face fixtures carry no
  depth and need no projection flip (every param is a ratio): the GT
  generator places landmarks directly in image pixels (y grows down,
  brows at negative y of the eye line, mouth at positive y), exactly
  the space the solve reads. The finger probe's 3D→2D projection habit
  was a latent sign-flip here — caught by the probe's own MONOTONIC
  row reading several params as dead zeros.
- **A3 — monotonicity alone cannot see a DEAD param** (an all-zero
  sequence is trivially monotone). The MONOTONIC row therefore also
  demands REACH: at each param's max-GT state the solved value must
  reach ≥ 0.5 of the GT. Reach + violations together are the
  operational meaning of the Annex A.1 "monotonicity ≥ 9/10" bar.
- **A4 — the real rows redeclared three priors and flipped the side
  map** (S29 probe, n=18 real faces on the P1-9 set; priors POOLED over
  both face bands — a population prior is side-agnostic): (i) the
  laterality measurement put band A at image-left on 18/18 faces — the
  declared subject-left reading was wrong; `.L` constants read band B
  (§ The landmark layout). (ii) The neutral-geometry priors
  `PRIOR_CORNER_DROP 0.45→0.40` (pooled median 0.403),
  `PRIOR_MOUTH_W 1.00→0.83` (0.832), `PRIOR_CHEEK 0.45→0.72` (0.731)
  were redeclared from the pooled medians — the declared values had
  smile/pout firing on every real neutral and cheek structurally unable
  to fire at all. `EAR_OPEN` (0.283) and `PRIOR_BROW_RAISE` (0.296)
  stand; `PRIOR_LIP_GAP` keeps the anatomical 0.02 with the measured
  0.31 median published as genuine expression in the set (§ constants
  table). This is the D-008 loop working: declared → measured →
  redeclared, all BEFORE the core build, cited here and in D-022.

## Gates (the honesty line, made numeric — the finger rules one level up)

- The face is SOLVED iff the IOD anchor's four corner kps (36, 39, 42,
  45) all clear `FACE_CONF_FLOOR`. Below → NO face entry (an absent face
  reads as clean — the absent-hand rule verbatim).
- A param is SOLVED iff every kp it consumes clears the floor. Below →
  the param is SKIPPED + LEDGERED with its verbatim confidences, never
  guessed (100% gated-skip is the Annex A.1 honesty row).
- A solved param below `FACE_ACT_FLOOR` goes to the ledger as
  below-threshold with its exact value — it never enters `params`, so a
  neutral face serializes as an EMPTY-or-ledger-only face, and a
  barely-smiling face does not drift the shape keys.
- Param confidence = the MINIMUM of its consumed kps' confidences (the
  chain-is-as-strong-as-its-weakest-joint midpoint rule, reused).

## Payload contract (format 3 UNCHANGED — additive per-figure field)

`CanonicalPose.face` — one additive `FacePose | None` (default None):

| field | type | meaning |
|---|---|---|
| `params` | dict[str, float] | the 10 D-022 param names → solved values in [0, 1] (stored sorted; ledgered params are absent) |
| `skipped` | dict[str, str] | per skipped/below-threshold param: the LOUD verbatim reason (confidence values or the below-threshold value) |
| `iod_conf` | float | the min of the four IOD-anchor confidences (the solve's strength) |

- `to_dict()` OMITS the `face` key when empty — a face-free pose
  serializes BYTE-IDENTICALLY to pre-P8-4 output (the `hands` contract,
  pinned by contract test). `from_dict` reads `face` when present,
  tolerates absence (every older fixture stays valid).
- `mirrored()` swaps `.L`/`.R` param values (`brow.raise.L` value moves
  to `brow.raise.R`, center params carry); the ledger transfers with
  sides swapped. A geometry-free param swap — depth semantics do not
  exist here. `toggled()` never touches face (the finger precedent).
- `solve_face(kps, confs) -> FacePose | None` is PURE + deterministic
  (stdlib, sorted keys): same 133-kp arrays the body solve consumed.

## Apply — two explicit binding classes, both LOUD per rig

- **(a) Bones via preset mapping** (`face_bones`, the `hands` precedent):
  additive optional preset field `{param: bone}`, format 2 unchanged.
  Validation: every key a known D-022 param (loud refusal with the
  table), values unique bones, no bone double-keyed with the body
  mapping or finger bindings (the cross-binding class the preset guards
  already refuse). `resolve_face(preset, fingerprint, force=False)` —
  the SAME fingerprint gate as `resolve_hands`. Rotation semantics are
  DECLARED per param (axis + max angle, D-022): `jaw.open` = param ×
  25° about canonical X; `brow.raise.*` = param × 20° about canonical Y
  (side-sensed sign); `blink.*` = param × 12° about canonical X
  (side-sensed sign); `smile.*`/`pout`/`cheek.*` = param × 10° about
  canonical Y (side-sensed sign) — declared untuned defaults, the
  rig's authored preset decides WHICH bone, the table decides HOW MUCH.
  Face bone rotations join the FK report additively (a separate pass
  after body + fingers, same parent-space discipline).
- **(b) Shape keys by documented naming convention**: the convention is
  `shape key name == param name` exactly (`jaw.open`, `brow.raise.L`,
  …) on any mesh deformed by the armature (armature-modifier
  consumers). Applied value = the param value (clamped [0, 1]).
  Validated against the LIVE mesh: a missing key reports LOUD (per-key
  line, never a silent skip); a convention key whose param is
  ledgered-not-solved reports and stays untouched. The scan + apply is
  addon-side (bpy surface); core receives the resolved key-name SET for
  its honesty accounting only.
- **NEITHER present** → the loud capability line, verbatim:
  `face: N expression param(s) solved; no facial targets for this rig —
  face not applied` (the FINGER-NOTARGET precedent). Never silent.
- Core stays pure: `apply_canonical_pose` gains additive
  `face_bones=None, face_shape_keys=None` (a set of key NAMES for
  accounting, no bpy). The addon applies shape-key values; core math is
  the param→axis-angle table.

## Accept bars (Annex A.1, pre-declared — the gate implements these)

1. **Per-param monotonicity ≥ 9/10** on the 10-expression benchmark
   (neutral + 9: brows_raise, brow_raise_L, blink_both, blink_L,
   jaw_open, smile, smile_L, pout, cheeks). Definition: sort the 10
   states by that param's GT value (ties by state name); walk the
   solved sequence; a VIOLATION is an adjacent step whose solved value
   DECREASES by more than `MONO_TOL = 0.05` (the declared noise band);
   PASS iff violations ≤ 1 of the 9 steps. Fixtures are parametric GT
   faces (prior-consistent, projected to 2D — the finger_probe recipe;
   SYNTHETIC-labeled).
2. **Bone apply ≤ the 0.5° family**: engine-built fixture rig with
   facial bones + `face_bones` preset bindings through the REAL addon
   apply path — applied axis-angle vs intended within 0.5°.
3. **Shape-key apply ≤ 0.1 normalized**: applied key value vs intended
   param within 0.1, keys actually displacing the fixture mesh.
4. **Loud no-target**: pose with face + rig with neither class → the
   capability line, verbatim-greppable.
5. **Byte-identity**: face-free payload write byte-identity; all prior
   gate numbers byte-identical; the 507-test suite green (plus the new
   contract tests).

Refusal branch (Annex A.2): a param below monotonicity after two
redesign cycles → REFUSED per param, documented (gaze already
conditional-OUT). Never cut P8-3 fingers or P8-2 coupling (Annex A cut
order); gaze is the declared first cut if slack runs low — it is
already OUT by detector condition.

## Policy (D-019)

Expressions carry no content by themselves — no new policy surface; the
add-on's existing subject checks apply unchanged; MCP gains no new tool
and stays SFW (test-pinned). D-022 records this statement at the
namespace landing.

## What P8-4 deliberately does NOT do

- No gaze (no iris kps from the pinned detector — conditional-OUT).
- No identity/shape work (expressions, not identity; the population
  neutral is the declared limit, a personal-neutral calibration would
  be a new feature with its own session).
- No payload format 4 (v3 stays; `face` is an additive per-figure
  field).
- No per-frame face streaming (rides P5's existing pipeline after the
  static path is proven).
- No body re-solve from face kps (the head role stays body-keypoint
  driven; the face solve never writes `positions`).

## Probe plan (xtask/face_probe.py — BEFORE the core build, RM_FACE lines)

- (a) LAYOUT — the declared band table tiles 23..91 exactly; the
  consumed indices exist and are disjoint per param.
- (b) MONOTONIC — the 10-expression prior-consistent GT set, projected
  to 2D + conf, solved: per-param violations ≤ 1 of 9 steps (the bar).
- (c) GATE-OCCL / GATE-PARTIAL — conf-0 face → no entry; per-param
  below-floor → 100% ledgered skips, zero guessed; below-threshold
  solved values → ledgered, params empty.
- (d) LATERALITY — real detections: measured mean-x sign of band A vs
  band B + per-band conf distributions (the audit's 0.958 band,
  per-region).
- (e) REAL-PRIORS — real detections: the raw metrics' distributions
  (EAR open spread = the blink-prior question, brow gap, mouth width,
  jaw gap, cheek distance) published next to the declared priors —
  measured, never fitted.
- (f) DETERM — twin solves byte-identical.

The probe contains the DRAFT solve (the coupling_probe/finger_probe
recipe): core `face.py` lifts it, tests pin it.

## Probe answers (as-built, 2026-09-25 — `xtask/face_probe.py`, RM_FACE
### lines; 7/7 PASS exit 0, pure core + the pinned DWPose models)

- **LATERALITY (the finding that flipped a constant)**: the declared
  band-A = subject-left reading is WRONG for this detector — band A
  sits at image-left = the subject's RIGHT on **18/18 real faces**
  (median −51.5 px). The `.L` constants read band B; the flip was the
  one-line constant fix the design planned. Amendment A4.
- **REAL-PRIORS (the finding that redeclared three priors)**: pooled
  over both face bands (a population prior is side-agnostic), n=18
  faces / 36 eyes: EAR median **0.283** (prior 0.28 — stands), brow gap
  **0.296** (0.30 — stands), mouth width **0.832** (declared 1.00 →
  redeclared 0.83), corner drop **0.403** (declared 0.45 → 0.40), cheek
  distance **0.731** (declared 0.45 → 0.72), jaw gap **0.310** (the
  anatomical lips-touching 0.02 stands — the measured median is genuine
  open-mouth expression in this expressive photo set, published next to
  the prior). As declared, the old priors had smile/pout firing on
  every real neutral and cheek structurally unable to fire.
- **MONOTONIC**: 0 violations / 9 steps (bar 1), min reach **1.00**
  (bar 0.5) across all 10 params on the prior-consistent 10-expression
  set [SYNTHETIC]. The probe's first draft caught TWO design flaws
  pre-build: the corner-line smile metric is degenerate under symmetric
  smiles (A1 — replaced by the nose-bottom reference) and a y-up GT
  fixture silently read several params as dead zeros (A2 — GT faces are
  2D in image space; monotonicity alone cannot see a dead param, hence
  the reach demand, A3).
- **GATE-OCCL / GATE-PARTIAL**: face conf 0 → no entry (absent reads
  clean); one starved brow band → only `brow.raise.R` ledgered with its
  verbatim confidences, the rest of the face solves; a neutral face →
  0 params, all 10 below-threshold ledgered. Zero guessed params.
- **DETERM**: twin solves byte-identical.
- **Band confidences on the real photos**: brow 0.97 / eye 0.99 /
  nose 1.00 / mouth 0.99 medians — the audit's 0.958 face-conf band is
  uniformly strong across regions.

## As-built (S29, 2026-09-25) — the landing

Landed as designed, with the four probe-earned amendments (§ Amendment
record) recorded before the core build. The whole stack: named face
constants + `face_kp_index` (`poses.py`, the measured side map) → the
namespace + solve (`core face.py`, D-022 WRITTEN at that landing) →
`CanonicalPose.face` (additive, omit-when-empty byte-identity pinned) →
preset `face_bones` bindings (format 2 unchanged, `resolve_face`
fingerprint gate, cross-binding guards) → FK apply (`face_bones` +
`face_shape_keys` params joining the same top-down pass with the
declared `FACE_BONE_PLAN` axis-angle; the loud no-target line on the
no-target side) → shape-key convention class (addon-side scan of
armature-deformed meshes, keys named == param, missing keys report
loud) → CLI `rigpose pose` solves face by default → session
`apply_pose` preset path resolves `face_bones` (kinds + MCP tool tables
untouched).

- **CI contract**: 25 tests in `core/tests/test_face.py` — the
  10-param namespace, kp-index tiling + loud refusals, neutral-ledger,
  exact solve on prior-consistent GT (including the honest nose-lift
  cross-talk term), conf-0 no-entry, partial-face per-param gating,
  determinism, monotonicity+reach over the 10-expression benchmark,
  byte-identity (`to_dict` omits `face`), round-trips, mirrored
  side-swap, declared axis-angle apply, ledgered-param skip-loud,
  unknown-key refusal, both loud no-target shapes, double-binding
  refusal, preset validation + fingerprint gate. **532 tests total**
  (507 + 25); lint clean.
- **Gate** (`xtask/face_gate.py` via `make pose-verify`, RM_FACE rows,
  Blender 5.1.0, engine-built fixtures, the REAL addon apply path
  through the FULL preset contract): FACE-BENCH 0 violations / 9
  (bar 1) + reach 1.00 (bar 0.5) over the 10-expression class;
  FACE-GATE-OCCL zero guessed (conf-0 no-entry, per-param ledgers,
  neutral all-ledgered); FACE-BONE-APPLY live world-rotation worst
  **0.0000°** (bar 0.5°) with 5/5 facial bones keyed; FACE-SHAPE-APPLY
  4/4 convention keys applied, value delta **0.0000** (bar 0.1), mesh
  displaced; FACE-NOTARGET the capability line verbatim; FACE-TWIN
  byte-identical (26 bones + keys). ALL prior gate numbers
  byte-identical.
- **What P8-4 deliberately does not claim**: monotonicity bars are
  measured on SYNTHETIC prior-consistent GT (the Annex A.1
  re-validation trigger applies when real expression-labeled fixtures
  enter the workflow); the neutral is a POPULATION prior (a single
  image carries no personal neutral — a resting-low brow reads
  slightly raised, published, never hidden); gaze is conditional-OUT
  (the pinned DWPose has no iris kps; no corner-geometry guessing).
