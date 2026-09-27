# Root motion (P8-7) — design of record

The P8-7 treadmill fix, designed BEFORE the build (the docs/SPINE.md
sibling pattern — a sibling design page, never a fork). It closes ledger
row L7 (walk-in-place only; no root motion — the treadmill finding): the
S24 REAL-row finding is the motivation — the Xbot `walk` clip carries
Mixamo ROOT MOTION, so hips-anchoring (walk-in-place per D-008) turns it
into a treadmill whose stance feet glide 0.022–0.19 u/frame, above the
D-008-UNTUNED enter_speed 0.02 → the contact detector honestly reports 0
plants → the certified foot lock is a verified bit-for-bit no-op. Nothing
was re-tuned to force plants (D-008); THIS phase is the declared remedy:
the coordinated positional upgrade — a MEASURED hips drift track plus a
root-motion-aware contact model — designed so plants are detected ON the
drifting subject and the lock can do its job, with every threshold
untouched.

NOTHING on this page is a claim until a test, probe line, or gate number
cites it. The pre-declared bar (Annex A.1 P8-7 row) is LAW: **the drift
track must beat walk-in-place slide on the REAL fixture (the Xbot walk
row) by the >= 5x family, else L7 ends REFUSED** — walk-in-place stays
the shipped behavior and the treadmill finding remains the published
truth. Refuse branch (Annex A.2): REFUSED means exactly that, documented
with the measured evidence — never a silent shrink of the claim.

## The one structural fact each piece rides on

Canonical poses/actions are HIPS-ANCHORED: every stage (the 2D solve, the
clip converter) pins hips at the origin per frame, so whole-body
translation is destroyed BY CONSTRUCTION — that is why a planted foot
glides in canonical space when the subject translates (the treadmill).
But the translation is only destroyed, never invented: at the moment of
anchoring, the subject's absolute position per frame is still in hand
(the sampler reads the posed hips head in armature space BEFORE the
converter subtracts it; the video payload carries the detector bbox +
the solve's pixels-per-unit scale). The drift track is that quantity,
RESCUED at the source instead of reconstructed after the fact — a
MEASURED record of where the subject's hips went, in canonical units,
carried as DATA alongside the action it describes.

Both contact stages then gain the same one-line upgrade: a planted foot
is stationary in the WORLD, so contact classification runs on the
COMPENSATED positions `p_world(t) = p_hipsrel(t) + track(t)` — the same
thresholds, the same hysteresis, the same lock machinery, applied in the
frame where "stationary" is the true statement. A zero track reduces
every formula to the existing behavior byte-identically (the in-place
path has no new numbers by construction).

## The drift track (core `root_motion.py`, declared)

`DriftTrack` — per-frame canonical-space hips translation, referenced to
the track's FIRST observed frame (that frame's entry is exactly
`(0.0, 0.0, 0.0)`; declared reference choice, deterministic):

| field | meaning |
|---|---|
| `source` | `"clip-measured-3d"` (sampler world hips heads — full 3D) or `"video-approximate-in-plane"` (bbox drift — no depth, labeled) |
| `ref_frame` | the reference frame (the first observed one) |
| `translations` | dict source-frame → `(dx, dy, dz)` canonical units; EXACT frame keys only — gaps stay gaps, never interpolated |
| `notes` | provenance lines that travel with the track |

Loud validation (the ChainSpec discipline): strictly increasing frame
keys, finite floats, the reference frame present and zero, `at()` answers
EXACT frames only (`None` for an unobserved frame — ambiguity is
reported, never smoothed over).

**The clip source (measured, 3D)**: the sampler already reads the posed
hips head per frame — `track(t) = (hips(t) − hips(ref)) · (0.45 /
scale_ref)`, the converter's own scale constant (`TORSO_SPAN /
scale_ref`), so track and positions are convention-consistent BY
CONSTRUCTION. The sampler emits it as an ADDITIVE field on the
clip-sample JSON (below); the converter attaches the track to the action
whenever the field is present (loud note).

**The video source (approximate, in-plane)**: per-frame detector bbox
center `c(t)` (pixels) and the payload's own solve scale `s(t)` (pixels
per canonical unit): `dx = (c_x(t) − c_x(ref)) / s(ref)`,
`dz = −(c_y(t) − c_y(ref)) / s(ref)` (pixel v-down vs canonical z-up),
**`dy = 0.0` — depth is unobservable from bbox drift alone and is never
guessed** (the declared single-view limit, the P8-6 depth line one level
down). The reference frame's scale is the one constant (the
per-step-trapezoid refinement is the documented rejected alternative —
second-order for the drift class, not worth its own moving part in v1).
Every track from this source is LABELED approximate in its `source` and
its notes.

**Clip-sample format 2 (the additive carrier)**: `MotionClip` reads
formats 1+2; the sampler writes format 1 — byte-identical to today —
unless the new `--root-track` flag is passed, in which case it writes
format 2: the format-1 fields PLUS the required `hips_track` object
(`{"ref_frame": int, "samples": [[frame, x, y, z], ...]}` — source
meters, the sampler's own ROUND_DIGITS). The preset-schema precedent
(write 2 / read 1+2; old files keep working byte-identically; unknown
fields still refuse). Format 2 without `hips_track` refuses with a hint.

**No payload format change**: the POSE payload (v3) is untouched — the
track rides the ACTION as an additive `CanonicalAction.root_track`
field (default `None`; dataclasses `replace()` carries it for free;
`action_from_poses` gains an optional keyword; `condition_action` copies
it through). Consumers that ignore it are byte-identical (pinned by
test). Actions are never serialized to disk, so there is no on-disk
contract to bump.

## The root-motion-aware contact model (declared)

**Detection**: `detect_contacts_root_aware(frames, track)` shifts every
action frame by the track's entry for that frame (rigid per-frame
translation — FK-identical within the frame, the P2-6 stabilize
precedent) and runs the UNTOUCHED `contacts.detect_contacts` state
machine on the compensated positions. Same thresholds, same hysteresis,
same gap semantics — the only change is the frame the numbers live in.
Frames without a track entry: the pass REFUSES LOUD (a partial track
would poison the speed chain at the boundary frames with fabricated
discontinuities — refuse with a hint, never guess); a track that covers
every frame but measures ZERO drift everywhere is VALID data — the pass
delegates and the results are byte-identical to the in-place path, with
a loud `no drift measured — walk-in-place path` note.

**The lock**: `lock_feet_root_aware(action, track)` runs the UNTOUCHED
`contacts.lock_feet` with plants DETECTED on the compensated frames:
the detection finds the true planted intervals in world space (the S24
fix), and the lock pins those plants in the action's own stored
(hips-relative) space — the certified walk-in-place product, unchanged
machinery. (Amendment A1 below records why the first draft's
world-space pin was replaced: it served the root-motion bake, which is
declared out of this landing; the world truth stays in the data —
unlocked stored + track = stationary world ankles.) The 5x metric is
the slide measured on the STORED positions over the root-aware
intervals: before = the treadmill glide, after = pinned. In-place
(zero/absent track) reduces to the existing lock byte-identically
(pinned, not asserted).

**The 5x claim's exact shape (the Annex bar, made checkable)**: on the
Xbot REAL row, the intervals are the ROOT-AWARE detection's (the status
quo detects none, so the comparison needs the new model's plants);
`slide_before` = `contacts.foot_slide` of the UNLOCKED STORED frames
over those intervals (the treadmill glide, measured where it lives);
`slide_after` = the same metric on the locked stored frames. The row
PASSes at `slide_after <= slide_before / 5` (the >= 5x family — the
published foot-lock bar). Regression-framed: the new model vs the
status quo it replaces, same intervals, same metric, one number each.
(A1 above records why the metric lives in the stored space; A3 records
the measured outcome on this row — the clip carries no drift to
recover, and the ledger row ends REFUSED-with-evidence.)

## What rides where (the composition map)

- The certified composition (`condition_action → detect_contacts →
  lock_feet`, wired in the addon session executor + MCP) is UNTOUCHED —
  its numbers and its code are the in-place path's byte-identity
  guarantee. The root-motion-aware pass is a NEW pure-core consumer
  (the spine.py pattern); wiring it into the session executor /
  `retarget_clip` action is the declared follow-up (the S31
  CLI-wiring precedent — a user-facing change needs its own gate rows).
- The BAKE is UNTOUCHED in this landing: it keys hips-relative rotations
  exactly as before. A root-motion-locked action therefore bakes to the
  DECLARED intermediate: legs that compensate the drift on a rig whose
  root stays put. Applying the track at bake time (keying the root
  translation so the rig physically crosses the floor) is the
  user-facing half of the coordinated upgrade and is NOT CLAIMED here —
  it needs its own gate rows and its own byte-identity argument. This
  page's bars bind on the TRACK (measured), the PLANTS (detected), and
  the SLIDE RATIO (>= 5x) — all core-side, all reproducible.
- `stabilize_hips`/`condition_action` carry the track through
  unmodified; the interaction of a per-frame SCALE correction with the
  track's canonical units is declared out of v1's claims (the gate
  exercises the fresh-conversion path, which is the clip pipeline's
  actual shape — clip poses carry confidence 1.0 and the composition
  keeps smoothing off in CI).

## Accept bars (pre-declared — the probe/gate implement these)

1. **Track recovery (synthetic GT)**: an engine-built walking fixture
   with KNOWN authored hips drift → bridge sample (`--root-track`) →
   convert → the recovered track matches the authored curve (converted
   by the same `0.45/scale_ref` constant) within **0.005 canon** per
   frame (the RM_MOTION round-trip family — the track is the same
   sampled-positions arithmetic). The fixture's plants are detected ON
   the compensated model at the authored phase structure.
2. **The Xbot REAL row**: plants detected on the root-aware model
   (> 0 — the S24 finding reversed by design, not by tuning); the >= 5x
   slide ratio (§ above); the track published (total drift, per-frame
   stats) as the measured record. No authored GT exists for a real
   clip — the track IS the measurement of it; the accuracy claim binds
   on bar 1's synthetic GT, and this row carries the consistency checks
   (DETERM, world-reconstruction exactness) instead of a fabricated
   accuracy number.
3. **In-place byte-identity**: a zero/absent track →
   `detect_contacts_root_aware` ≡ `detect_contacts` and
   `lock_feet_root_aware` ≡ `lock_feet` BYTE-IDENTICAL (reports and
   locked positions, pinned by test AND gate row); the certified
   composition untouched → RM_FOOT_LOCK 0.0371→0.0000, RM_MOTION
   44997x, RM_BAKE 0.0242° ×2 re-print byte-identical.
4. **Refuse classes stay loud**: partial track coverage → loud refuse
   (detection and lock both); empty action → loud refuse; a
   no-drift stream → valid, delegated, byte-identical, loudly noted.
   Zero guessed frames, zero fabricated translation anywhere (D-008:
   the track is MEASURED drift, never authored root motion).
5. **The bake path is indifferent**: the root-motion-locked action
   bakes onto the real metarig through the REAL `bake_action` and
   re-evaluates from its fcurves within the **0.5°** family (the
   apply-path-unchanged proof, the RM_MOTION BAKE pattern).
6. **DETERM twins**: twin tracks, twin detections, twin locks —
   byte-identical.

Refuse branch (Annex A.2): if the Xbot row cannot meet the >= 5x
family after the bounded repair cycle (DEFAULT one), L7 ends REFUSED —
walk-in-place stays the shipped behavior, the treadmill finding remains
the published truth, and the ledger row records the measured evidence.
Never cut P8-2 coupling or P8-3 visible fingers (the cut order).

## Probe plan (xtask/root_motion_probe.py — BEFORE the core build, RM_ROOT lines)

- (a) TRACK-GT — the synthetic drift fixture (the P6-2 walking fixture
  builder extended with an OPTIONAL authored hips translation curve —
  default off, so the in-place fixture is byte-identical): recovery vs
  authored within 0.005 canon + plants at the authored phases.
- (b) XBOT — the real Mixamo walk re-visited: track summary, plants >
  0, the >= 5x slide ratio, DETERM.
- (c) INPLACE — the zero-track byte-identity pins (detect + lock).
- (d) REFUSE — partial coverage / empty action loud; no-drift stream
  delegates loudly.
- (e) VIDEO — the approximate in-plane constructor on a synthetic
  payload stream with known bbox drift: mechanical recovery + the
  depth-stays-zero pin + the approximate label.
- (f) DETERM — twins byte-identical.

The probe contains the DRAFT pass (the coupling/finger/face/camera/
spine recipe); core `root_motion.py` lifts it, tests pin it, the gate
wires the REAL Blender paths (fixture build + sampler spawns + the REAL
`bake_action` row).

## Amendment record (probe-earned, recorded before the gate finalized)

- **A1 — the lock pins WALK-IN-PLACE in stored space; the world truth
  stays in the data.** The first draft bracketed the lock in the
  compensated (world) space and de-compensated back — which stores
  planted ankles that MOVE opposite the drift (world pin − track). That
  is the root-motion-BAKE product's semantics, and the bake is declared
  out of this landing — the certified product is walk-in-place. As
  built: detection runs on the compensated frames (plants are found
  where feet are actually stationary — the S24 fix), and the UNTOUCHED
  `contacts.lock_feet` pins those plants in the action's own stored
  space (the slide numbers measured on the stored positions over the
  root-aware intervals are the >= 5x metric: before = the glide,
  after = pinned). The world truth remains recoverable from the DATA
  (unlocked stored + track = stationary world ankles — that IS the
  detection space); the stored pin and the track are two honest views
  of one measurement. The measured consequence: the world-compensated
  frames are ALREADY stationary on a real planted walk (that is why
  detection works there), so a world-space slide metric would read
  ~0 before AND after — the stored-space metric is the only one that
  measures the artifact the lock removes.
- **A2 — the drift fixture counter-sweep (the fixture, not the model,
  was wrong — the A8 class again).** The walk fixture keys JOINT ANGLES
  about the hip head; a translating hip head DRAGS the stance feet
  along, so the first drift fixture's planted feet receded in world at
  hips-speed + arc and the compensated GT row honestly found no plants.
  The fix tilts the stance thigh back by
  `phi(n) = degrees(atan2(d_sag · n, 0.84))` (n = frames into the
  stance; 0.84 m = the hip→ankle sagittal radius), so the authored
  ankles hold their world spots while the subject crosses the floor.
  This trades C1 smoothness at liftoff (the accumulated tilt releases
  in one frame — the detector reads exactly that as the exit) for a
  physically-planted stance; landing stays C1 (phi starts at 0 each
  stance). The GT plant expectation maps each authored stance [s, e]
  to [s+1, e] and drops single-frame spans: a landing frame carries
  approach speed, so the enter contract can only fire one frame into
  the stance (the sliding fixture's published phases hid this because
  its landing speeds happened to dip below the bar at the landing
  instant).
- **A3 — THE CORRECTED FINDING: the Xbot.glb carries NO root motion on
  ANY of its seven clips (walk/run/idle/agree/headShake/sad_pose/
  sneak_pose), measured.** The S24 attribution ("the clip carries
  Mixamo ROOT MOTION, so hips-anchoring turns it into a treadmill") is
  WRONG about the mechanism: the walk clip's hips bone carries no
  translation (y constant to the sampler's 1e-6 m precision), the run
  clip's track span measures 0.0000u, the armature object never moves —
  the imported scene graph has no root motion ANYWHERE. The published
  0.022–0.19 u/f stored glide is real but is the in-place walk cycle's
  own leg KINEMATICS (stance sweep), which hips-anchoring cannot and
  should not remove: for an in-place cycle, the glide IS the
  walk-in-place truth. Consequence for the Annex A.1 bar: the >= 5x
  family on the Xbot walk row is unmeetable BY THE FILE'S CONTENT
  (no source drift exists to recover; both models find the same 0
  plants; there is no slide-interval pair for the track to beat).
  Per Annex A.2 (row-local trigger, no dead bands), **L7 ends
  REFUSED-with-evidence: walk-in-place ships** and the treadmill
  finding remains the published truth — with its mechanism corrected
  by this measurement. The bounded repair cycle is not exercisable:
  nothing about the model is broken on the actual input class — the
  clip has nothing for the model to consume. The machinery LANDS as
  gated additive core (this page, the tests, the gate): consumers are
  byte-identical, and the track is the standing instrument for every
  stream that DOES carry drift (real detector video, third-party clips
  with true root motion, P8-8's multi-figure path). The >= 5x
  demonstration lives on the drift GT fixture (46351.9x, SYNTHETIC-
  labeled), the class the track addresses.

## Probe answers (as-built, 2026-09-27 — `xtask/root_motion_probe.py`,
### RM_ROOT lines; 7/7 PASS exit 0, pure core + the pinned sampler)

- **TRACK-GT-RECOVERY**: max_err **0.000000 canon** (bar 0.005) — the
  authored 0.03 m/frame hips translation survives BVH export → import →
  sampler → format-2 clip → conversion EXACTLY (path=1.5429u,
  span=1.5429u over 49 frames, k=1.0714). [SYNTHETIC, prior-consistent
  GT; the optimism caveat verbatim: measured on synthetic
  prior-consistent ground truth; real-detector noise is not in these
  numbers; the Annex A.1 re-validation trigger applies when real
  labeled fixtures enter the workflow.]
- **TRACK-GT-PLANTS**: the compensated detection lands exactly on the
  observable stance structure — foot.L (2–12)(26–36), foot.R
  (14–24)(38–48) — authored stances with the landing frames excluded by
  the enter contract (A2).
- **TRACK-GT-FIX**: the root-aware lock on the drift fixture zeroes the
  stored glide **0.6479u → 0.0000u = 46351.9x** (bar >= 5x); the
  in-place reading of the SAME action finds 5 spurious intervals on the
  gliding stored positions (the treadmill confusion, reproduced).
- **XBOT** (the corrected finding, A3): hips track span **0.0017u**
  (<= 0.01 = NO translatable drift in the file; path 0.2273u is
  sway/bounce); plants in-place=0, root-aware=0 — the model degenerates
  to the status quo on a no-drift clip, byte-identical by contract.
  The A.3 re-validation trigger applies if a real fixture WITH root
  motion ever enters the workflow.
- **INPLACE**: zero-track byte-identity PASS — detect structure equal,
  locked positions equal, honest no-drift note present, stale
  walk-in-place suffix line absent.
- **REFUSE**: partial coverage (detect + lock) and empty action refuse
  LOUD (3/3, hints verbatim); a no-drift stream delegates
  byte-identically with the loud note.
- **VIDEO**: mechanical recovery (dx=0.0900, dz=0.0450 at the declared
  model), depth ≡ 0 exactly, the APPROXIMATE label present, 3/3 loud
  refusals (scale <= 0, out-of-order, empty).
- **DETERM**: twin tracks and twin detect+lock byte-identical.

## As-built (S32, 2026-09-27) — the landing

- **Core** `root_motion.py`: DriftTrack (loud validation, exact-frame
  `at()`, path/span), track_from_clip_field (the converter's own
  `TORSO_SPAN/scale_ref` constant), track_from_payload_stream (in-plane,
  depth ≡ 0, APPROXIMATE-labeled), compensate/decompensate (zero delta
  reuses the ORIGINAL tuples — the byte-identity mechanism),
  detect_contacts_root_aware + lock_feet_root_aware (the untouched
  certified stages, per A1). 17 CI tests (`test_root_motion.py`,
  **585 total**): the track contract, the conversion constants, the
  zero-track byte-identity, the treadmill shape (in-place finds
  nothing / root-aware finds the plant), the stored-pin + world-in-data
  pins, purity, conditioning carry-through, the format-2 carrier
  round-trip, DETERM twins.
- **Clip-sample format 2** (the additive carrier): `MotionClip` reads
  formats 1+2, requires `hips_track` in format 2, refuses it in format
  1; `to_dict` writes format 1 bytes when no track (the preset-schema
  pattern); the sampler's `--root-track` flag (default OFF — format-1
  output byte-identical, the in-place fixture sample stays 57111
  bytes); `action_from_clip` attaches the measured track with a loud
  note. NO payload format change (the track rides the ACTION — the
  additive `CanonicalAction.root_track` field, carried through
  conditioning by construction).
- **Fixture** (`motion_fixture.py`): optional `--drift dx,dy,dz` (world
  meters/frame; default off = byte-identical in-place fixture) + the A2
  counter-sweep; the sampler flag passes through the thin caller.
- **Gate** `root_motion_gate.py` (the sibling file, wired into
  verify_pose_apply.sh + the Makefile lint list): 8 RM_ROOT rows, ALL
  PASS — ROOT-TRACK-RECOVERY 0.000000 (bar 0.005), ROOT-TRACK-PLANTS
  exact, ROOT-TRACK-FIX **46351.9x** (bar >= 5x), ROOT-INPLACE
  byte-identical, ROOT-BAKE through the REAL `bake_action` on the
  metarig worst **0.0000°** (bar 0.5; locked=44, the certified path
  untouched), ROOT-REEVAL **0.0000°** (98 checks), ROOT-REFUSE 3/3
  loud + delegation, ROOT-XBOT the corrected finding (PASS|SKIPPED
  both grep shapes), ROOT-DETERM byte-identical.
- **The ledger outcome**: L7 = **REFUSED-with-evidence** (A3 above) —
  walk-in-place ships; the treadmill finding stands with its mechanism
  corrected; the drift track + the root-motion-aware contact model land
  as gated, byte-identical, opt-in core instrumentation for streams
  that carry real drift. Every prior gate number byte-identical (the
  certified composition, the sampler default path, and the bake are
  untouched).

## Policy (D-019)

The drift track and the root-motion-aware contact pass carry no content
— no new policy surface; the existing subject checks apply unchanged;
MCP gains no new tool and stays SFW (test-pinned). The track consumes
geometry only (sampled joint positions; bbox pixels + scale).

## What P8-7 deliberately does NOT do

- No payload format change (the track rides the ACTION, not the pose —
  the v3 contract and the hands-free face-free byte-identity pins hold,
  pinned by the existing tests).
- No root-motion BAKE (the rig's root stays put; the track is landed,
  measured, and carried — the bake-side keying is the declared
  follow-up with its own bars).
- No certified-composition rewiring (the session executor / MCP keep
  the in-place path verbatim; the root-aware pass is opt-in at the
  core API until its own wiring gate exists).
- No depth from the video path (dy ≡ 0.0, labeled — bbox drift cannot
  see depth; the P8-5 camera solve is the future depth source, a
  separate gate).
- No threshold changes ANYWHERE (enter/exit bars are D-008-untuned and
  stay so — the S24 finding is answered by measuring the drift, not by
  moving the goalposts).
- No per-step scale-trapezoid refinement in the video track (declared
  rejected alternative, documented above).
