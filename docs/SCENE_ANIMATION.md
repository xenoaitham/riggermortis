# Scene animation (P8-8) — design of record

Multi-character video → scene animation, designed BEFORE the build (the
docs/ROOT_MOTION.md sibling pattern — a sibling design page, never a fork).
It closes ledger row L8 (single-character video only; multi-figure labels
unstable): the P2-1 job container already carries per-frame multi-figure
payloads (v2/v3 `figures[]`, the P1-11 B1 contract); what is missing is the
IDENTITY layer (which detected figure is which character across frames —
detector labels are per-frame local and swap freely), the per-frame SCENE
pass (coupling with placements measured per frame), and the scene ACTION
that bakes BOTH rigs. Nothing here is a claim until a test, probe line, or
gate number cites it.

The pre-declared bars (Annex A.1 P8-8 row) are LAW:

- **identity swap rate <= 2% of frames** on the synthetic fixture;
- **the swap alarm catches >= 90% of actual swaps**;
- **per-frame scene bake cost MEASURED on the mid-laptop baseline and
  PUBLISHED before any claim**;
- Refuse branch (Annex A.2): swap rate > 10% after the bounded repair
  cycle → auto-identity REFUSED, manual-assignment mode ships, labeled.

NEVER cut P8-3 visible fingers or P8-2 coupling (the cut order) — both are
consumed here, never weakened.

## The one structural fact everything rides on

Canonical poses are HIPS-ANCHORED and unit-less: every figure of every
frame is solved into the same canonical frame (hips at the origin, torso
span 0.45), which destroys where each person STOOD — exactly the ROOT_MOTION
insight one level down. For scenes this has two consequences. First, pose
SIMILARITY is shape similarity: hips-anchoring strips absolute position, so
the cost of confusing figure X with character A is measured on the skeleton
SHAPE (plus body scale — the one identity signal anchoring preserves), not
on screen position; two people doing the same dance are genuinely hard, and
the design says so instead of pretending. Second, the SCENE geometry has to
come back from the stream data the anchoring left behind: the payload
figure entries carry the detector `bbox` (pixels) and the solve's
pixels-per-canonical-unit `scale`, so per-frame in-plane placements and
per-character drift tracks (S32's `track_from_payload_stream`, reused
VERBATIM — D-016) are recoverable as MEASURED, LABELED-APPROXIMATE data.
Depth is unobservable from a single view and stays exactly zero — never
guessed (the P8-6/ROOT_MOTION declared limit, one level up).

## The stream model (core `scene_anim.py`, declared)

The P2-1 job container is UNCHANGED: a job directory of contract payloads,
each carrying `figures[]` (`label`, `index`, `score`, `bbox`, `pose`).
The new loader reads it:

``SceneStreamFrame`` — one frame's detected figures:

| field | type | meaning |
|---|---|---|
| `frame` | int | the source frame index (exact; gaps stay gaps) |
| `figures` | list[StreamFigure] | every detected figure of the frame, label-sorted |

``StreamFigure`` — one detected figure:

| field | type | meaning |
|---|---|---|
| `label` | str | the detector's per-frame local label (UNSTABLE across frames — the whole reason this phase exists) |
| `pose` | CanonicalPose | the FULL solved pose (hands/face/roll ride additively, D-021/D-022/D-023 — no new wiring needed) |
| `bbox_center` | (float, float) \| None | the detector bbox center in pixels (from the payload entry's `bbox`); None when absent — tracks/placements then report unavailable, never guess |

`load_scene_frames(job_dir)` builds the stream from a real job directory
through `video.load_state` + `payload.figure_entries` (the D-009
one-contract rule); unreadable frames land in a loud ledger, never
interpolated. A stream builder from in-memory entries exists for tests and
the fixture (the ONE validator: both paths produce SceneStreamFrame).

## Identity assignment (the committed algorithm)

Per frame, the detected figures are assigned to CHARACTERS — the stable
identity keys of the animation (the roster the artist casts; default =
the sorted figure labels of the first assignable frame). The algorithm is
the roadmap-committed direction, made concrete:

**Cost matrix** — `pose_cost(previous character pose, candidate figure)`.
Both poses are hips-anchored canonical; the declared cost is

```
cost = mean_dist(common observed roles) + SCALE_WEIGHT * |log(s_fig / s_char)|
```

- `mean_dist` over the INTERSECTION of observed roles (positions are the
  one convention-free metric, the S23 lesson); fewer than
  `MIN_COMMON_ROLES` common roles → the pair is UNCOMPARABLE (cost =
  None → loud refuse for that pairing; never a fabricated number).
- `SCALE_WEIGHT` = 1.0 (declared untuned, D-008): body scale is the
  identity evidence that SURVIVES pose convergence — two people matching
  poses are still two bodies, and the detector's pixels-per-unit scale
  sees the difference. `|log ratio|` is the scale-free size distance.
- The reference pose per character is its LAST SUCCESSFULLY ASSIGNED
  pose (temporal continuity — the standard identity-tracking formulation;
  the first frame seeds identity directly: its figures ARE the characters).
  Failed/gap frames never interpolate — the reference is the last
  observation, exactly.

**Assignment** — a deterministic rectangular assignment (the Hungarian /
Kuhn-Munkwes method, O(n^3), pure stdlib, implemented here — the core has
zero runtime dependencies, D-003): rows = characters in SORTED order,
columns = figure labels in SORTED order, so the matrix layout is keyed and
tie-breaking is deterministic (no set iteration anywhere — CONVENTIONS).
Characters > figures → the frame FAILS loud (a missing character cannot
animate that frame; gaps stay gaps). Figures > characters → the extras are
REPORTED (sorted labels, loud ledger) and stay unassigned. Overridden
pairings (below) bypass the matrix entirely.

**Swap alarm** — the per-frame evidence that identity MOVED. Declared
instrument, computed WITHOUT ground truth (it ships in the product):

- *Evidence alarm*: `continuation_cost > chosen_cost` by more than the
  declared margin — the previous frame's mapping is measurably WORSE on
  this frame than the chosen one, i.e. the identity evidence (pose shape +
  scale) says the figures crossed. `continuation_cost` = this frame's cost
  matrix evaluated on the PREVIOUS frame's assignment. Margin (declared
  untuned, the SCENES.md camera-floor derivation pattern — both
  distributions measured on the fixture and the constants published in the
  gap): `jump_abs > ALARM_ABS (0.02 canon)` AND
  `jump_rel = jump_abs / chosen_cost > ALARM_REL (0.25)`.
- *Flip record*: the solved assignment differs from the previous frame's
  for any character — the observable discontinuity, reported LOUD as a
  ledger row (not the GT bar's alarm; flips are how corrections and
  ambiguity SHOW).

**Manual override wins over everything** (the honesty law: suggest what is
inferred, enforce what is authored): `overrides[frame][character] = label`
bypasses the solve for that pairing, marks the frame `overridden`, and the
row reports the solved-vs-authored disagreement (the artist's word is
recorded, never silently absorbed). Overridden frames are EXCLUDED from
the automatic swap-rate measurement (they are authored, not inferred) and
reported as their own count.

**Swap rate (the Annex bar, made checkable)**: a solved frame t is an
ACTUAL SWAP iff any character's assigned figure carries a different
AUTHORED character (the fixture's ground truth — real streams have none,
which is exactly why the bar binds on the synthetic fixture).
`swap_rate = swapped frames / solved frames` on the PRIMARY fixture class
(see the probe plan; the true-ambiguity class is excluded and reported as
its own loud number — unresolvable ambiguity is REPORTED, never averaged
into a pass rate).

## The scene action + the per-frame scene pass

``SceneActionFrame`` — one solved frame:

| field | type | meaning |
|---|---|---|
| `frame` | int | source frame index |
| `scene` | ScenePose | figures keyed by CHARACTER label (stable), pins carried (authored order) |
| `assignment` | dict[char, label] | the detector label each character drew its pose from (provenance travels) |
| `costs` | dict[char, float] | the chosen assignment's per-character cost |
| `alarms` | tuple[SwapAlarm, ...] | the frame's evidence alarms + flip records |
| `overridden` | bool | an override participated in this frame |

``SceneAction`` — the scene animation: ordered frames + `failed` (the
honest gap ledger) + `characters` (sorted tuple) + `pins` (authored order,
the P8-2 contract) + `tracks` (per-character `DriftTrack | None`, S32
reuse) + notes. `actions_view()` decomposes it into per-character
`CanonicalAction`s (frames, failed, per-character root_track) — the exact
input the CERTIFIED bake already consumes; the bake path itself is
UNTOUCHED. Consumers that ignore SceneAction are byte-identical (a new
module, nothing modified).

**Per-frame placements** (the coupling input, MEASURED from the stream —
never guessed): `placement_from_stream(frame, ref)` builds, per figure,
`Placement(quat=identity, t=in-plane, s=apparent-size)`:

- `t = ((cx − o_x)/U, 0.0, −(cy − o_y)/U)` — the bbox-center displacement
  against the SHARED scene origin `o` = the reference frame's (the minimum
  frame with all characters present) ANCHOR center — the minimum-label
  character's bbox center there — so the figures keep their real
  separation in scene space. The scene unit `U` = that anchor character's
  `scale` (px per canonical unit — one deterministic constant). Pixel
  v-down vs canonical z-up: the same sign convention
  `track_from_payload_stream` publishes.
- `s = figure_scale / U` — apparent-size staging (a closer/bigger subject
  covers more pixels per canonical unit, so it places bigger). LABELED
  APPROXIMATE: single view cannot separate body size from distance (the
  P8-5 declared limit); the placement report says so, every time.
- `dy = 0.0` exactly (depth unobservable — never guessed).

**Per-frame coupling**: for each solved frame,
`couple_scene(frame.scene, placements)` (P8-2's pass, UNTOUCHED — D-016)
closes the scene's AUTHORED pins with the measured placements. Per-frame
residuals carry the same pre-declared bar (residual_frac < 0.02, the
scale-free 2% torso-span family). Frames without enforceable pins pass
through byte-identically (the zero-pins contract). Fingers/facials ride
per figure BY CONSTRUCTION (the additive namespaces live inside
CanonicalPose, which SceneFigure embeds — no new wiring, nothing weakened:
the cut order holds).

## What rides where (the composition map)

- The certified composition (`condition_action → detect_contacts →
  lock_feet` per character) is UNTOUCHED. Scene animation COMPOSES it:
  the per-character actions condition and lock exactly as single-character
  actions do (the root-motion-aware pass rides per character where the
  stream carried drift — `lock_feet_root_aware` with the character's own
  track, S32 reused verbatim).
- The BAKE is UNTOUCHED: `actions_view()` feeds the existing
  `bake_action` per rig. The declared user-facing half — ONE session
  action baking N rigs — is the follow-up wiring (the S31/S32
  CLI-wiring precedent: a user-facing change needs its own gate rows);
  THIS page's bake bar is the measured COST of the real per-rig bake
  over the scene, published, not a new bake path.
- The P2-1 job container is UNCHANGED (the payload contract's additive
  read of per-figure `bbox` is a READ of a field the detector already
  writes). NO payload format change. NO new DECISIONS entry (no frozen
  API surface touched — no new canonical roles, no namespace).

## Accept bars (pre-declared — the probe/gate implement these)

1. **Swap rate <= 2%** on the PRIMARY synthetic fixture class (two
   figures, KNOWN authored identities, ONE authored label-swap crossing —
   the swap-prone class). The TRUE-AMBIGUITY class (identical pose AND
   identical scale through the crossing — the duplicated-person class) is
   measured and reported SEPARATELY as the declared single-view limit:
   no honest algorithm resolves it; the manual override is the answer and
   the probe demonstrates it (row e). [SYNTHETIC, prior-consistent GT;
   the optimism caveat verbatim: measured on synthetic prior-consistent
   ground truth; real-detector noise is not in these numbers; the Annex
   A.1 re-validation trigger applies when real labeled fixtures enter the
   workflow.]
2. **Alarm catch >= 90%**: the evidence alarms fire within
   `ALARM_HALO = 2` frames of the fixture's authored swap events (the
   authored events ARE the alarm's ground truth). The margin constants
   are published with BOTH cost-jump distributions (event vs non-event
   frames) and the constants' place in the gap (the strike-S12 derivation
   pattern).
3. **Per-frame coupling holds**: residuals `residual_frac < 0.02` for
   every enforced pin on every solved frame (the P8-2 bar, per frame).
4. **Bake cost MEASURED and PUBLISHED**: the per-frame cost of the REAL
   `bake_action` over the scene's characters (both rigs), on the
   mid-laptop baseline (this machine), published in docs/BENCHMARKS.md —
   measured BEFORE any claim; no bar beyond publication (the Annex bar is
   the publication itself).
5. **Override wins**: an authored override that contradicts the solve
   produces the overridden pairing, marks the frame, reports the
   disagreement; overridden frames are excluded from the automatic rate
   and counted separately.
6. **Refuse classes loud**: a single-figure stream into a multi-character
   roster; characters > figures frames (missing character); uncomparable
   cost pairs; a stream with no assignable first frame. Every refusal
   carries an actionable hint; zero guessed frames anywhere.
7. **Byte-identity**: no existing module modified (new file + the errors
   entry); the certified per-character path, the payload contract, and
   all prior gate numbers byte-identical (pinned by the gate re-run).
8. **DETERM twins**: twin streams → twin assignments, twin scene actions,
   twin couplings — byte-identical.

Refuse branch (Annex A.2): swap rate > 10% on the primary class after the
bounded repair cycle (DEFAULT one) → auto-identity REFUSED; the
manual-assignment mode ships labeled (overrides are already first-class —
the refusal demotes the SOLVER, never the data model). Never cut P8-2
coupling or P8-3 visible fingers (the cut order).

## Probe plan (xtask/scene_anim_probe.py — BEFORE the core build, RM_SANIM lines)

- (a) FIXTURE — the deterministic two-person stream: engine-built
  contract-valid v3 payloads written into a temp job dir (the REAL P2-1
  container shape), loaded back through `load_scene_frames`. Character A:
  left arm raised, gentle sway; character B: arms lowered, opposite-phase
  bounce — distinct shapes AND distinct scales (A 1.0, B 0.85 px/unit —
  the identity evidence that survives everything). ONE authored label-swap
  crossing (frames 24–26) + a converged-pose window (frames 30–40,
  identical shapes, scales STILL distinct) carrying a second authored
  label-swap event (frame 36) — the hard class that scale resolves.
- (b) IDENTITY — swap rate on the primary classes (bar 0.02); the true-
  ambiguity class (scales equalized through the window) measured and
  reported SEPARATELY; alarm margins published with both distributions;
  catch rate >= 0.90 within the halo.
- (c) COUPLING — an authored wrist-to-wrist pin across the stream, closed
  per frame with the measured placements; worst residual_frac < 0.02.
- (d) BAKE COST — the REAL `bake_action` over both characters' actions on
  the metarig (two armatures, one scene), wall-clock measured and
  published per frame (SKIPPED honestly without RM_METARIG_BLEND in the
  probe; the GATE measures it unconditionally).
- (e) OVERRIDE — an authored override contradicting the solved assignment
  on the ambiguity window: the override wins, the frame is marked, the
  disagreement is reported, the automatic rate excludes it.
- (f) REFUSE — single-figure stream, missing-character frame,
  uncomparable pair, no assignable first frame: 4/4 loud with hints.
- (g) TRACKS — per-character drift tracks from the stream bboxes
  (S32 verbatim): the crossing visible in both tracks, depth exactly
  zero, the APPROXIMATE label present.
- (h) DETERM — twin streams: twin assignments + twin scene actions +
  twin couplings byte-identical.

The probe contains the DRAFT pass (the coupling/finger/face/camera/spine/
root-motion recipe); core `scene_anim.py` lifts it, tests pin it, the
gate wires the REAL Blender paths (the fixture through the real
container + the REAL bake cost row).

## Policy (D-019)

Scene animation IS a content-carrying surface: the existing policy
subjects apply to the scene stream exactly as to single figures (the
poses are solved by the SAME solve; no new inference, no new model). The
add-on's adult-module gate covers scene apply/bake unchanged; MCP gains
NO new tool and stays SFW (test-pinned). The fixture is clothed-mannequin
class, engine-built, committed as CODE not media (the A.3 fixture law).

## What P8-8 deliberately does NOT do

- No payload format change (the container already carries everything;
  the additive `bbox` read is a read).
- No auto-casting of characters to RIGS (the artist pairs, the Casting
  Desk law — identity here is figure-to-CHARACTER; character-to-armature
  stays the desk's authored mapping).
- No depth (dy = 0 exactly; placements are in-plane, APPROXIMATE-labeled
  — the P8-5 camera solve is the declared future depth source).
- No new bake path (the certified per-rig bake is composed, not forked;
  the one-action scene bake is the declared follow-up wiring).
- No true-ambiguity resolution (identical pose + identical scale is
  unresolvable from single-view keypoints — reported, overridden by the
  artist, never silently decided).
- No threshold changes anywhere in the certified path (the contact
  bars stay D-008-untuned; the alarm margins are NEW instruments with
  published derivations, not tune-until-passes).

## Probe answers (as-built, 2026-09-27 — `xtask/scene_anim_probe.py`,
### RM_SANIM lines; 10/10 PASS exit 0; re-run against the CORE after the
### lift — numbers reproduced exactly)

- **FIXTURE**: 49 frames / 98 figures through a REAL v3 job container
  (payload files + `job.json` written at probe time, loaded back through
  the core loader), every figure carrying a bbox center.
- **IDENTITY**: swap_rate **0.0000** (0/49 solved frames, bar <= 0.02)
  through BOTH authored label-swap events — the assignment follows the
  pose+scale identity; gaps stay gaps; extras never observed on the
  primary stream.
- **AMBIGUITY**: the equal-pose equal-scale window class measures
  **0.1224** (6/49) — reported SEPARATELY (the declared single-view
  limit; the manual override is the answer, see OVERRIDE).
- **ALARM**: caught **2/2** authored events within the 2-frame halo
  (catch 1.00 >= 0.90); the jump distributions: event frames min_abs
  **0.4463** vs non-event max_abs **0.0000** — ALARM_ABS 0.02 sits in
  the gap; ALARM_REL 0.25 guards the near-zero-cost class (the
  strike-S12 derivation pattern, both constants published).
- **COUPLING**: the authored hand-holding pin closes **13/13**
  contact-window frames at worst_frac **0.000190** (bar 0.02) with
  placements MEASURED per frame; **25** beyond-reach frames report
  unclosable LOUD (the P8-2 REACH honesty, per frame).
- **BAKE-COST**: the REAL bake over both characters: **0.8–0.9
  ms/frame-bake = 1.7–1.8 ms per scene-frame across 2 rigs**, worst FK
  0.0000° — MEASURED and PUBLISHED here before any claim (the Annex
  publication bar; SKIPPED shape honestly without RM_METARIG_BLEND).
- **TRACKS**: per-character tracks (S32 verbatim): A path 1.6195u,
  ref→end span 1.0000u (the side swap is IN the track); depth exactly
  zero; the APPROXIMATE label present.
- **REFUSE**: 4/4 loud (single-figure stream, missing-character frame,
  uncomparable pairing, empty stream); zero guessed frames anywhere.
- **OVERRIDE**: the authored override wins on frame 36 (the free solve
  held the keyed tie on identical pose+scale; the artist's word moved
  A), the frame is marked, the solve-vs-authored disagreement is
  reported verbatim, and the frame is excluded from the automatic rate.
- **DETERM**: twin streams — twin actions, twin reports, twin couplings
  byte-identical.

## Gate-earned corrections (recorded before the gate finalized)

- **A1 — the placements' reference is the SHARED scene origin.** The
  first draft referenced each character to its OWN reference-frame
  center, which zeroes every steady-state translation: both figures
  staged ON the origin and the coupling row passed VACUOUSLY (a pin
  whose endpoints never separate). As built, `scene_reference` returns
  the reference frame's ANCHOR center (the minimum-label character's
  bbox center there) as the shared origin, and every figure's
  translation measures against it — the figures keep their real
  separation (the unit test pins B at +0.9u).
- **A2 — the fixture's contact distance must clear anatomy, not just
  arithmetic.** At a 45 px half-separation the placed shoulders stand
  1.71u apart while the arm chains' combined reach is ~1.35u: the pin
  is honestly unclosable (the solver clamps at residual_frac 0.499) and
  the gate row FAILED — the honesty law working as designed. The
  fixture tightens to 25 px (pair separation 1.0 scene unit, an
  anatomical hand-holding distance); the coupling then closes 13/13 for
  real. The A8/S24 fixture-law class, again: fix the FIXTURE, never the
  solver.
- **A3 — a label swap moves the WHOLE data stream.** The first unit
  test's swap split shape from scale (a "chimera" figure carrying A's
  scale with B's pose) — a configuration a real detector glitch never
  produces, and the assignment correctly refused to treat it as a swap.
  The fixture swaps shape AND scale together (the full stream), which
  is what the per-frame labels actually drag with them.

## As-built (S33, 2026-09-27) — the landing

- **Core** `scene_anim.py` (additive; NOTHING existing modified — new
  file only, errors stay `SceneError`): the stream model
  (`StreamFigure`/`StreamFrame`, `load_scene_frames` through the real
  container readers), the deterministic assignment (`hungarian()`
  Kuhn-Munkres O(n³) stdlib, SORTED keys everywhere, the transpose case
  for characters > figures, the uncomparable loud refusal),
  `assign_stream() -> (SceneAction, IdentityReport)` (keyed seed,
  failed-frame gaps, extras reported, evidence alarms + flip records,
  overrides winning with the free-solve disagreement comparison), the
  per-frame scene pass (`scene_reference` shared origin +
  `placements_for` + `couple_scene_action` composing the UNTOUCHED P8-2
  pass), the per-character S32 tracks (`track_for_character` /
  `attach_tracks`, verbatim, None-absent loud), and `actions_view()`
  decomposing into the certified bake's exact per-character input. 30
  CI tests (`test_scene_anim.py`, **615 total**).
- **Gate** `scene_anim_gate.py` (the sibling file; fixture builders
  imported from the probe — ONE fixture copy), wired into
  verify_pose_apply.sh + the Makefile lint list: 10 RM_SANIM rows, ALL
  PASS (the numbers above; BAKE-COST unconditional at the gate).
- **The ledger outcome**: L8 = **CLOSED** — both Annex bars met with
  margin (swap 0.0000 <= 0.02; alarm catch 1.00 >= 0.90; bake cost
  measured + published), the A.2 refusal branch never reached. The
  ambiguity limit is PUBLISHED as a labeled choice (the override),
  which is exactly what "pass" means under the Scene Test scorecard.
- **NOT landed (declared)**: the session/MCP scene-animation wiring
  (the S31/S32 user-facing-wiring precedent — needs its own gate rows);
  real-detector-stream validation (the Annex A.1 re-validation trigger
  applies when real labeled fixtures enter the workflow); depth (dy ≡
  0 — the P8-5 camera solve remains the declared future source).

## Reproduce (as-built)

```bash
# the capability probe (RM_SANIM lines; add RM_METARIG_BLEND for the
# bake-cost row)
/home/potato/blender-5.1.0-linux-x64/blender -b --python xtask/scene_anim_probe.py

# the unit contract
cd core && /home/potato/miniconda3/bin/python3 -m pytest tests/test_scene_anim.py

# the gate rows (RM_SANIM; inside the pose-apply gate)
BLENDER=/home/potato/blender-5.1.0-linux-x64/blender \
RIGPOSE=/home/potato/miniconda3/bin/rigpose \
PY=/home/potato/miniconda3/bin/python3 make pose-verify
```
