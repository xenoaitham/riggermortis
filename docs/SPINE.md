# Spine arch + arm roll (P8-6) — design of record

The P8-6 torso articulation and limb roll alignment, designed BEFORE the
build (the docs/CAMERA.md sibling pattern — a sibling design page, never a
fork). It closes ledger rows L5 (torso = rigid hips→shoulders line, no
arch) and L6 (roll-free rotations, twisted forearms accepted) — both are
D-008 v1 declarations this phase replaces with observed-constraint solves.

NOTHING on this page is a claim until a test, probe line, or gate number
cites it. The pre-declared bars (Annex A.1 P8-6 row + the A.2 refusal
branch) are LAW: **the arch benchmark (neutral/arched/bow L/R) is a
monotone distribution + the FK bars hold (the 0.5° family through the REAL
apply) + D-008's 18/20 flip accept is unchanged; the roll fixture corrects
to bar; straight arms BIT-IDENTICAL (the no-op proven); the full battery
re-runs byte-identical on priors.** Refuse branch (Annex A.2): arch/roll
that cannot hold the FK bars → REFUSED, documented as the single-view
limit (the D-008 ledger entry updated).

## The one structural fact each solve rides on

Both solves are POST-SOLVE passes over the already-solved
`CanonicalPose` — they consume only what the payload already carries
(`positions` + `joint_confidence`), so **no payload format change** (the
v3 contract and the hands-free face-free byte-identity pins hold, pinned
by the existing tests).

- **Arch**: the 2D observations see hips and mid-shoulders directly, but
  NOTHING on the mid-spine — the torso's bow SHAPE is unobservable. What
  IS observable is the misalignment: in a straight pose the torso chord
  (hips→mid-shoulders) and the head axis (mid-shoulders→nose) are
  COLLINEAR in the image; any arch/bow/lateral bend rotates the head axis
  PAST the chord. That signed in-plane angle is the total turn the torso
  must absorb. The solve distributes it across the spine chain by the
  D-008 proportions and re-places `spine`/`chest` — the same
  positions-surgery class as the coupling pass (the certified apply
  derives the rotated bones on ANY rig with zero apply-path changes).
- **Roll**: the from-to apply is DIRECTION-exact everywhere, but the
  forearm's world frame is built INDEPENDENTLY (shortest arc from ITS
  rest direction to ITS target), ignoring where the upper arm's frame
  ended up. The anatomical chain is frame-continuous: the elbow is a
  hinge, so the forearm's frame should be the upper arm's frame carried
  through the observed flexion plane. The difference between the two is
  a pure twist about the forearm axis — computable in closed form from
  the wrist-vs-elbow geometry (u = shoulder→elbow, f = elbow→wrist). The
  correction rides an ADDITIVE namespace field (`pose.roll`, D-023,
  written when this code lands) and `fk_apply` composes it; poses
  without entries apply BYTE-IDENTICALLY (the straight-arm no-op is
  structural: a straight arm has no flexion plane, so no entry is
  produced).

## The ARCH model (declared)

**Inputs** (all already in the pose, round-trip safe): `positions` for
`hips`, `neck`, `head`; `joint_confidence["head"]` — present iff the nose
was observed (the solve only records observed roles; the confidence gate
below cleanly separates observed-nose poses from prior-head poses).

**The head-axis recovery (the CAMERA.md A3 identity reused)**: the
payload's `head` position is the DERIVED placement `neck + 0.11·dirv`
with the declared bias `dirv = norm((0.5·dx/h, −0.15, 0.5·dz/h + 0.5))`
(the nose direction (dx, dz) blunted by the +0.5 z-bias — the magnitude
is destroyed, the DIRECTION survives). With `v = head − neck` (in-plane),
the bias components give `v_x/v_z = dx/(dz + h) = tan(θ/2)` — the exact
half-angle identity (the normalization constant cancels in the ratio) —
so the observed nose direction is `θ = 2·atan2(v_x, v_z)`, recovered in
closed form from the STORED head position. Degenerate (`v ≈ 0`) → refuse
class.

**The misalignment**: chord `c = neck − hips` (in-plane, canonical units),
head axis `n = normalize((v_x, v_z − 0.055))`,

    φ = atan2(c_z·n_x − c_x·n_z, c·n)      (radians; φ > 0 = the nose leans
                                            character-LEFT of the chord)

The declared single-view limit, stated up front: this reads the IN-PLANE
component of the arch only. A pure frontal backbend (head tipping away in
DEPTH) carries almost no in-plane misalignment and the solve stays flat —
depth is unobservable in one view (the D-008 class); never guessed.

**The placement**: a cubic Hermite through the PINNED endpoints —
P0 = hips, P1 = neck (both observed, both stay exactly where they are),
**T0 = T1 = |chord|·n** — both tangents along the observed head-axis
direction (amendment A1 below is the probe-earned record of WHY). The
interior joints land at the D-008 torso proportions — `t_spine =
0.09/0.45`, `t_chest = 0.26/0.45`, the SAME fractions the rigid line
already uses, so no proportion is introduced:

    H(t) = (2t³−3t²+1)·P0 + (t³−2t²+t)·T0 + (−2t³+3t²)·P1 + (t³−t²)·T1

`spine = H(t_spine)`, `chest = H(t_chest)`, depth (y) STAYS 0.0 (the
torso plane — girdle rigidity, the coupling precedent), everything else
(hips, neck, head, limbs, hands, face) byte-untouched. At φ = 0 both
tangents equal the chord and the Hermite reduces EXACTLY to the rigid
line (verified algebraically: H(t) = P0 + t·(P1−P0)) — the neutral case
is the current placement by construction, and the misalignment floor
below keeps it byte-exact.

**Amendment A1 (probe-earned, recorded before the core build)**: the
Hermite's end-tangent basis term `h11 = t³ − t²` is ≤ 0 on (0,1), so the
curve's BULGE must come from the START tangent. The first draft used T0
= the raw chord vector — the probe's sign row caught the counter-bow
(chest deviation −0.0165 canon on the +30° class, the WRONG side). The
symmetric −φ/+φ tangent splay keeps that wrong side (the same h11 fact).
The declared placement: **T0 = T1 = |chord|·n** — both tangents along
the observed head-axis. The torso bows toward the nose side (the
lateral-bow/back-arch body reading: the convex side faces where the
head tips), the sagitta matches the constant-curvature arc family
(`c²/8R` — Hermite 0.0284 vs arc 0.0293 canon at the chest on the 15°
class, diff ~0.001 against the 0.01 bar), and φ = 0 still degenerates
to the exact rigid line.

**Guards, in order (first match wins; each reason verbatim in the
report; a not-applied arch changes NO bytes — the ledger lives in the
returned report, not in pose.notes):**

1. `hips`/`neck`/`head` positions present, else SKIP "positions
   incomplete".
2. `joint_confidence["head"] >= SPINE_CONF_FLOOR 0.55` else SKIP "head
   unobserved or below floor" (an absent nose is no arch evidence — the
   D-008 observed-constraint law).
3. chord length `>= ARCH_CHORD_FLOOR 0.225` canon (half the declared
   torso span) else REFUSE "torso chord degenerate" (the
   heavily-foreshortened class, the camera solve's torso-degenerate
   precedent).
4. `|φ| >= ARCH_MISALIGN_FLOOR 5°` else SKIP "flat (misalignment below
   floor)" — declared untuned, order-of-magnitude above nose-kp noise;
   flat poses stay byte-identical.
5. `|φ| <= ARCH_ENVELOPE 60°` else REFUSE "beyond envelope — pose class
   not representable" (the contortion/perspective-lie class; the pose
   stays flat, reported, never guessed).
6. `confidence = min(conf_hips, conf_neck, conf_head)` capped at
   **0.75** (the CONVENTIONS geometry-only cap) and `>= 0.55` else SKIP.
7. Apply. One note appended: `spine: arch applied (misalignment X.X°,
   confidence 0.XX)` — an applied arch is VISIBLE in the payload; a
   skipped/refused one is invisible (byte-identical) by contract.

## The ROLL model (declared)

**The artifact (what minimal rotations get wrong)**: for a bent arm, the
applied forearm frame is `q_f = from_to(rest_f, f)` — the shortest arc
for the forearm ALONE. The anatomical chain is frame-continuous: the
elbow is a hinge, so the forearm's frame should be
`q_c = q_u ∘ L` where `q_u = from_to(rest_u, u)` (the upper arm keeps
its minimal frame — the declared zero-humeral-twist convention) and `L =
from_to(rest_f, conj(q_u)·f)` is the observed hinge in the upper arm's
local frame. `q_c` and `q_f` both map the rest direction onto the same
observed `f` (direction fidelity is never at stake); they differ by a
pure twist about the forearm axis — THE roll correction:

    ρ = signed angle about f from (q_f·v₀) to (q_c·v₀)
    v₀ = the declared canonical rest hinge (0, 0, −1) projected
         perpendicular to rest_f, normalized

The declared rest hinge: the D-008 forward-bend prior says forearms bend
forward (−Y), which hinges the rest T-pose arm (+X) about
`(1,0,0)×(0,−1,0) = (0,0,−1)` — v₀ transfers it to any bone direction.
Straight arm: `f ∥ u` makes L identity and `q_c = q_f` exactly, so ρ = 0
by construction — and the bend floor below refuses to produce an entry
anyway (two independent layers on the no-op).

**Envelopes + floors (declared untuned)**: bend angle
`β = angle(u, f) >= ROLL_BEND_MIN 15°` else no entry ("flexion plane
noise-dominated below 15°" — the structural straight-arm no-op band);
`confidence = min(conf_forearm, conf_hand)` capped at 0.75 (geometry
cap), `>= 0.55` else no entry; both guards skip + ledger per side in the
report, never guess. The upper arm carries NO entry in v1 (its twist is
declared zero by the convention above); `upper_arm.L/R` are RESERVED
namespace keys.

**The additive namespace (D-023, WRITTEN when this code lands)**:
`CanonicalPose.roll: dict[str, RollEntry]` — keys `forearm.L`/`forearm.R`
(v1 writes; `upper_arm.L/R` reserved), each `RollEntry(twist_rad,
confidence)`. Omitted from `to_dict` when empty (the hands/face
byte-identity contract, pinned by test); `from_dict` validates keys loud
(the D-021 pattern). `mirrored()` swaps sides and NEGATES the twist (an
x-mirror reverses handedness about the mirrored axis); the test pins
solve-after-mirror == mirror-after-solve. `fk_apply` composes any present
entry: `world = Twist(target, ρ) ∘ from_to(rest, target)` — direction
exact (the twist is ABOUT the target axis), `verify_application` errors
stay 0. Poses without entries take the unchanged code path — consumers
that ignore roll are byte-identical, the D-021 rule one level up.

## The benchmark (monotone distribution — the Annex bar)

**GT protocol (engine-built, prior-consistent, SYNTHETIC-labeled per
Annex A.3)**: four pose classes whose torsos are authored ON the
declared arch family (the A1 Hermite with the gain-2 start tangent) —
the engine-fixture precedent (the flip fixtures author limbs on the
D-008 prior directions; the face benchmark authors expressions on the
published table). The class value IS the observable chord→nose
misalignment:

| class | misalignment φ | authored torso |
|---|---|---|
| neutral | 0° | the straight line (current placement) |
| bow_L | +18° | C-bow bulging character-left (the head-tip side) |
| bow_R | −18° | C-bow bulging character-right |
| arched | +30° | the deep class (side-view backbend signature) |

Torso authored at the D-008 fractions; the nose at
`neck + 0.11·(head axis)`; limbs hang (the fixture law — girdle kps are
rulers, arms swing about the shoulder kps); confidences 0.95. The GT
observations feed the REAL `solve_pose` (the flat solve) → the arch
pass → measures: applied flags, STRICT monotonicity of the solved
chest deviation from the chord across neutral < bow < arched, sign
correctness (bow_L > 0 > bow_R), declared-family recovery (solved
spine/chest within 0.002 canon of the authored positions — the
observation→solve→arch chain inverts), and the neutral flat no-op
BYTE-IDENTITY.

**The family note (declared, honest)**: a constant-curvature arc
through the same pinned endpoints is FORCED into the splay family
(its chord is the mid-seam: end tangents at ∓φ/2 about the chord), and
a splay arc bulges AWAY from the head tip — the opposite of the
physical C-bow reading (the torso's convex side faces where the head
tips past the chord, sagittal and lateral alike). The declared prior
chooses the physical C-bow family (A1); the circular arc is documented
here as the rejected alternative, not a hidden dead end.

Every claim from this set ships with the optimism caveat VERBATIM:
*measured on synthetic prior-consistent ground truth; real-detector
noise is not in these numbers; the Annex A.1 re-validation trigger
applies when real labeled fixtures enter the workflow.*

**Roll fixture (engine-built)**: a canonical-exact rig; the LEFT arm
bent in a non-trivial orientation (the artifact class), the RIGHT arm
straight (the per-side no-op class). The measured quantities: the
uncorrected forearm twist (the frame split the minimal apply produces,
published — the artifact made numeric), the corrected twist (≤ the
bar), and per-bone direction fidelity (exact in both paths — positions
are never disturbed). In Blender the gate re-measures through the REAL
`apply_canonical_pose` on the fixture rig.

## Accept bars (pre-declared — the probe/gate implement these)

1. **Monotone distribution**: on the declared-family benchmark, solved
   |chest deviation from the chord| strictly increasing across neutral <
   bow < arched (both sides); bow_L positive / bow_R negative / neutral
   not applied; declared-family recovery ≤ 0.002 canon. Neutral is also
   BYTE-IDENTICAL through the pass (the flat no-op, the arch twin of the
   straight-arm bar).
2. **FK bars hold**: through the REAL apply, per-role direction error
   ≤ 0.5° (the family) on every benchmark class and the roll fixture,
   both roll paths.
3. **D-008's 18/20 flip accept unchanged**: the 20-pose fixture set
   through solve → arch → roll keeps the accept count at 18 and every
   `flips` dict byte-equal to the plain solve (the passes touch no
   distal segment; the probe proves it).
4. **Roll corrects to bar**: the roll fixture's forearm twist error
   ≤ **0.5°** corrected (the family), with the uncorrected error
   published next to it; direction fidelity exact in both paths.
5. **Straight arms BIT-IDENTICAL**: a straight-arm pose produces NO roll
   entries and `apply_canonical_pose` output rotations byte-equal to the
   pre-P8-6 path (pinned by test, not prose).
6. **DETERM twins**: twin arch+roll solves byte-identical; the full gate
   battery green with every prior number byte-identical.

Refuse branch (Annex A.2): if the arch or the roll cannot hold the FK
bars after the bounded repair cycle (DEFAULT one), the solve is REFUSED,
documented as the single-view limit — the D-008 ledger entry (roll) and
the L5/L6 rows updated REFUSED-with-evidence. Never cut P8-2 coupling or
P8-3 fingers (the cut order); P8-6 roll is itself the last cut item — a
park here produces its evidence and the rows end REFUSED-with-evidence,
never unknown.

## Probe plan (xtask/spine_probe.py — BEFORE the core build, RM_SPINE lines)

- (a) ARCH-BENCH — the four-class monotone distribution + sign +
  declared-family recovery + the flat no-op byte-identity.
- (b) FK-ARCH — `verify_application` ≤ 0.5° family on every class
  through the REAL apply.
- (c) FLIPS — the 20-pose D-008 accept through the passes: 18/20 and
  flips dicts byte-equal.
- (d) ROLL — the roll fixture: uncorrected vs corrected twist (the bar)
  + direction fidelity.
- (e) STRAIGHT — straight arms: no entries across the 20-pose set.
- (f) REAL — the P1-9 photos: arch misalignment + confidence + roll
  entries per detected figure, refusals honest. Outputs are the data;
  never prose claims.
- (g) DETERM — twins byte-identical.

The probe contains the DRAFT solves (the coupling/finger/face/camera
recipe); core `spine.py` lifts them, tests pin them, the gate wires the
REAL Blender apply.

## Probe answers (as-built, 2026-09-26 — `xtask/spine_probe.py`,
### RM_SPINE lines; 7/7 PASS exit 0, pure core + the pinned DWPose)

- **ARCH-BENCH**: chest deviation from the chord 0.0000 < 0.0076 <
  0.0084 canon (neutral < bow < arched, monotone, signs bow_L > 0 >
  bow_R); declared-family recovery max 0.00000 canon (bar 0.002);
  neutral flat no-op byte-identical. [SYNTHETIC, prior-consistent GT;
  the optimism caveat verbatim above.]
- **FK-ARCH**: worst per-role direction error 0.0000° (bar 0.5°)
  through the REAL apply on all four classes.
- **FLIPS**: D-008's flip accept 18/20 (bar ≥ 18) through
  solve → arch → roll; every flips dict byte-equal to the plain solve.
- **ROLL**: fixture forearm twist uncorrected **53.64°** (the artifact,
  published), corrected **6.9e-15°** (bar 0.5°); upper-arm direction
  exact; REAL apply worst 0.0000°. Entries: forearm.L twist −53.6°
  conf 0.75; R skipped (bend 0.0° below the 15° floor).
- **STRAIGHT**: zero roll entries on any sub-15° bend across the
  20-pose set.
- **REAL** (tier 3, the P1-9 photos, no GT exists): 10 figures on 10
  photos; the arch applied on 5 with published misalignments
  (+27.6°/−8.0°/−15.8°/... + confidences 0.71–0.75), flat on the rest
  with verbatim reasons (confidence-below-floor / below-floor
  misalignment); 2 roll entries. The outputs ARE the data.
- **DETERM**: twin arch + roll solves byte-identical.
- Probe-earned amendment A1 (recorded above, before the core build):
  the Hermite tangents — three drafts measured (raw chord,
  ∓φ splay, equal head-axis) before the declared gain-2 form.

## Policy (D-019)

The spine and roll carry no content — no new policy surface; the
existing subject checks apply unchanged; MCP gains no new tool and stays
SFW (test-pinned). Both solves consume geometry only.

## What P8-6 deliberately does NOT do

- No payload format change and no new payload field for the arch (it
  edits solved positions; the roll rides the D-023 additive field).
- No DEPTH articulation (the y=0 torso plane stands — the depth
  component of an arch is unobservable in one view, the declared limit).
- No neck/head re-placement (the head keeps the declared placement
  model; the nose evidence that drives the arch is the same evidence the
  placement consumes).
- No CLI/addon invocation wiring this session (the work order's unit
  boundary is the pure core + the REAL-apply gate; the gate exercises
  the full apply path — the payload-carrying-roll apply needs NO addon
  change since the addon path builds poses through
  `CanonicalPose.from_dict`). Wiring into the user-facing solve flow is
  the Scene-Test integration's decision, recorded as the open follow-up.
- No upper-arm roll entries in v1 (reserved keys; no evidence source for
  humeral twist from point landmarks — declared, not hidden).
