# Review UX — per-defect fix affordances + the fallback estimator (P8-9)

Design page of record (S34). The SCENE_ANIMATION.md sibling: design → probe
(`xtask/review_ux_probe.py`, RM_RUX lines) → core/add-on lift → gate
(`xtask/review_ux_gate.py`, the sibling file). Nothing here re-solves
anything: P8-9 rides the EXISTING review overlay, the EXISTING apply paths,
and the EXISTING additive namespaces (D-021 fingers, D-022 face, D-023 roll,
P8-1 pins) — four small authored-correction affordances, one declared
time-to-fix instrument, and the D-011 dual-estimator interface with its
third-model ritual.

The ledger rows this phase closes (Annex A.2, pre-declared):

- **L10** (review/fix is workable but slow per-fix): closes CLOSED at the
  time-to-fix bar, else REFUSED-with-evidence.
- **L9** (anime detector gap, D-011/D-012: 3/10 outright detector failures
  on the anime benchmark): closes CLOSED only if a candidate estimator
  passes the FULL third-model ritual AND the adoption bars; missed after
  one candidate → REFUSED-with-evidence. **The dual-estimator INTERFACE
  remains either way** — it is product surface, not the claim.

## The one structural fact everything rides on

Every flagged defect is already LOUD DATA under the honesty law (suggest
what's inferred, enforce what's authored): low-margin flips are review items
(P1-7), skipped fingers live in the D-021 ledger, gated face params in the
D-022 ledger, unclosable pins in the P8-2 report, suggested pins carry
`origin: "suggested"`. P8-9 adds the other half of that loop: an AUTHORED
correction per defect class that (a) replaces the flagged data with
human-authored data at confidence 1.0, (b) keeps the provenance note loud,
(c) re-applies through the REAL apply path in one operation. No new solve,
no new namespace, no payload format change (the additive `estimator`
provenance field is the one new optional field, see the interface section).

## The four affordances (core `review.py`, additive)

Each is a pure function returning a NEW object (the `CanonicalPose.toggled`
pattern — never mutates), with loud `RiggermortisError` refusals and an
appended `notes` entry carrying the provenance. Each defect item in the
review surface names its affordance in an additive `fix` tag (below).

1. **`author_finger(pose, hand, finger, direction)` — click a finger, drag
   the direction.** `hand` is `hand.L`/`hand.R`, `finger` a FINGER_ORDER
   name, `direction` a canonical-space 3-vector (normalized by the
   function; zero-length refuses). The 4-joint chain (mcp→pip→dip→tip) is
   (re)built STRAIGHT along the direction with the canonical segment
   lengths: from the chain's existing mcp when one exists (a direction fix
   on a solved finger), else from the hand's wrist head (a rescue of a
   SKIPPED — ledgered — finger: the occlusion class becomes one drag).
   Confidence 1.0 (human-authored), the skip-ledger entry is removed, and
   the note reads `hand.L.index: authored in review (direction fix)`.
   Declared scope: ONE drag authors DIRECTION, not per-joint curl — a
   straight chain is the honest one-gesture answer; per-joint curl sculpting
   is post-V1, not silently claimed.
2. **`trim_face(pose, param, value)` — per-param face trim.** `param` a
   FACE_PARAMS name, `value` clamped to [0, 1]. Sets the param, removes it
   from the D-022 skipped ledger (an authored trim overrides the gate —
   the gate stays loud in the note:
   `smile.L: authored in review (trim; solver gate had skipped it)` or
   `... (trim; solved 0.42)` when it overrode a solved value).
3. **`flip_figure(scene, label)` — per-figure flip.** The figure's pose is
   `mirrored()` in place (label kept — labels are identity, P8-8). Pins
   REFERENCING that figure re-anchor via `mirror_role` on their role
   endpoint (a flip moves the whole figure; its pin anchors move with it).
   Note appended on the figure: `<label>: mirrored in review`.
4. **`retarget_pin(scene, pin_index, endpoint, new_role)` — pin nudge.**
   `endpoint` is `"a"`/`"b"`; the pin's that-endpoint role becomes
   `new_role` (must exist on the pin's figure at apply time — the coupling
   pass validates the chain), origin becomes `authored`, confidence 1.0,
   note appended (`retargeted hand->forearm in review`). Companion:
   `confirm_pin(scene, pin_index)` — a SUGGESTED pin becomes authored at
   confidence 1.0 (the P8-2 confirm, now one call).

## The review surface gains the defect items (additive, byte-safe)

`review.review_items` is UNTOUCHED (its output for the 22-role pose is
byte-identical, pinned). Three NEW functions return the namespace defect
items; the add-on panel draws the union, MCP stays as-is (D-019 — no new
MCP surface in P8-9, declared):

- `finger_defects(pose)` — one item per SKIPPED finger (the D-021 ledger:
  `hand.R.middle skipped (index conf 0.31 < floor 0.55) — click + drag to
  author`), plus one advisory per hand whose wrist confidence is below the
  amber band. fix tag: `finger_fix:<hand>.<finger>`.
- `face_defects(pose)` — one item per gated (skipped) D-022 param. fix tag:
  `face_trim:<param>`.
- `scene_defects(scene, couple_report=None)` — one item per unclosable pin
  when a P8-2 `CoupleReport` is supplied (the report already names them
  loud), one per SUGGESTED pin (confirmable, severity low). fix tags:
  `pin_retarget:<index>` / `pin_confirm:<index>`.

`ReviewItem` gains `fix: str = ""` — OMITTED from `to_dict` when empty, so
every existing item serializes byte-identically (the omit-when-empty house
pattern). Items sort exactly as before; the new functions share the sort.

**Untouched-path byte identity (the gate pins this)**: a pose with no
hands/face/roll defects and a scene with no pins produce ZERO new items and
apply byte-identically with all affordances registered. An affordance is a
pure function — registering it moves no byte of the certified apply.

## The time-to-fix instrument (declared BEFORE any measurement)

The Annex A.1 bar: **median scripted time-to-fix <= 15 s per flagged defect
on the benchmark fixture set** (click-through measured, published; missed →
L10 REFUSED-with-evidence). The instrument, declared before measurement:

- **Defect injection.** Each defect class is injected into the established
  gate fixture classes (engine-built, SYNTHETIC-labeled, per Annex A.3):
  - FLIP — the 20-pose canonical class (`core/tests/poses_fixtures.py`):
    for every MATERIAL flip (bend beyond the D-010 immaterial band) the
    payload carries the WRONG sign plus a below-floor joint confidence —
    exactly the payload state a real D-008 miss produces (D-010: real
    arms land 0.12–0.53). INSTRUMENT-labeled injection; the fix path is
    what is measured.
  - FINGER — the finger-gate hand class: skipped fingers from the real
    occlusion gating (the ledger), i.e. the defect is already the engine's
    own loud output, no injection needed.
  - FACE — the face-gate 10-expression class: the gated (ledgered) params
    of each expression state, same no-injection rule.
  - PIN — the couple-gate 2-figure scene class: one pin mis-targeted to a
    beyond-reach role pair (the S33 beyond-reach class) → the coupling
    report flags it unclosable; the defect is the engine's own flag.
- **The scripted click-through.** Per defect: the review surface FLAGS it
  (one of the functions above) → the affordance executes with the
  corrective parameter taken from the fixture's ground truth (the scripted
  artist drags to the reference — the instrument measures the PATH, not
  the aim) → the corrected apply runs the REAL apply path → re-measure:
  the defect is cleared (flip sign == GT; authored chain direction within
  the P8-3 bar family of the GT direction; face param == the authored
  value; pin residual within the 2 % torso-span bar after re-coupling).
- **The cost model (declared, untuned, D-008).** time-to-fix = Σ
  interaction costs + the measured wall-clock of the scripted ops.

  | interaction | declared cost | derivation |
  |---|---|---|
  | CLICK (pick a flagged item, invoke its operator) | 1.0 s | a deliberate viewport click + panel invoke is an order-1-second motor action |
  | DRAG (drag a direction/endpoint) | 3.0 s | aim + drag + release, 2–3 s |
  | SLIDER (set a trim value in the panel) | 2.0 s | click + adjust + release |

  The model makes the bar BITE: a fix needing more than ~5 interactions
  cannot meet 15 s, and a defect class with NO affordance (or one whose
  corrected apply needs a re-solve/restart) scores unbounded → the class
  fails the bar. The costs are the INSTRUMENT's declared constants, the
  same standing as the synthetic walk's drift rate — published with every
  number, never claimed as human-timed wall-clock.
- **The published table.** Per class: defect count, median/p90
  time-to-fix, interaction sequences (clicks/drags/sliders), the measured
  op wall-clock separately; plus the median over ALL defects (the bar).
  Reproduce: `xtask/review_ux_probe.py` (probe) and
  `xtask/review_ux_gate.py` (gate, through the REAL Blender apply).

## The estimator half — the D-011 dual-estimator interface + the ritual

D-011/D-012 history: the pinned DWPose fails outright on 3/10 anime
benchmark images (line-art AND soft-shaded hand-drawn — the gap is NOT
line-art-only); the Phase-1 usable gate is honestly unmet on strict
criteria. D-011 planned the fallback estimator; A.2 strike S4 ruled P1-8a
IS a third pinned model. The design:

- **The interface (ships regardless — `inference/estimator.py`)**:
  - `Estimator` protocol: `name`, `detect_keypoints(image) -> (kps,
    confs)` — the SAME 133-keypoint layout downstream already consumes
    (nothing below the interface changes).
  - The registry: the default (`dwpose`) is registered; fallbacks register
    EXPLICITLY (manifest-pinned models only — the P1-1 manager is the only
    door a third model gets through).
  - `select_estimator(image, floor)`: run the default; if NO figure passes
    the person-confidence floor, retry with each registered fallback in
    keyed (name-ascending) order; all fail → the honest no-person error
    (never a fabricated pose). With only the default registered, behavior
    is byte-identical to today (pinned by test).
  - **Payload provenance (the D-011 `estimator` field, additive)**: a
    per-figure optional `estimator` string in the `figures[]` entries
    (mirrored top-level like `pose`), written ONLY when the entry was NOT
    produced by the default estimator — today that is never, so every
    payload stays byte-identical (pinned). Readers ignore unknown entry
    fields (the v3 ignore-with-note policy); a round-trip test with a
    faked estimator proves the field travels.
- **The third-model ritual (binds any adoption; the P9-2/P10-3 law)**, in
  order, BEFORE any adoption claim: (1) license verified verbatim from the
  publisher (redistributable, named); (2) checksum + byte size pinned in
  `manifest.json` via the P1-1 manager (the only download door; SSRF
  guard rides along); (3) CPU budget measured on the mid-laptop baseline
  (this box: i5-10400F, onnxruntime CPU) — the adoption bars are
  per-image latency <= 2x DWPose CPU, no-person <= 1/10 on the anime
  benchmark, flip-margin parity within the D-010 tolerance on the detected
  set; (4) the DECISIONS entry WRITTEN at the landing. **NO fine-tune in
  the repo; adopted weights only; no scraped Danbooru-class data, ever**
  (D-011 verbatim). The candidate class is D-011's: a sketch/anime
  whole-body estimator with published weights — ONNX or CPU-exportable.
- **The refusal branch is first-class.** One candidate (the strongest the
  landscape offers) is evaluated through the ritual; missing any ritual
  step or any adoption bar → **L9 REFUSED-with-evidence**: the estimator
  documented as not viable at this benchmark n, the interface ships, the
  never-list stands. The probe publishes the evidence rows either way.

## Accept bars (pre-declared — the probe/gate implement these)

| measure | bar | derivation |
|---|---|---|
| RUX-T2F | median time-to-fix <= 15 s over ALL flagged defects of the benchmark fixture set; per-class medians published with the interaction model | Annex A.1 (strike 4.1) |
| RUX-UNTOUCHED | a clean pose + a clean scene: zero new review items, apply byte-identical with the affordances registered | an affordance that moves a byte of the certified apply is S34-failure by definition |
| RUX-FIX | every corrected apply clears its defect within its family bar (flip == GT sign; finger direction within the P8-3 median bar vs GT; face param == authored; pin residual < 2 % torso span) | each fix must actually fix, not just run |
| RUX-REFUSE | unknown hand/finger/param/pin-index/role, zero-length direction, out-of-range value → loud `RiggermortisError` with an actionable hint, nothing applied | the errors-actionable law |
| RUX-EST-DEFAULT | default-only registry: payload bytes + review behavior byte-identical to the pre-P8-9 path | the interface is additive or it is nothing |
| RUX-EST-RITUAL | any adoption claim carries license + checksum + measured CPU budget + the DECISIONS entry; otherwise the REFUSED-with-evidence rows publish | A.2 strike S4 |
| RUX-DETERM | the scripted click-throughs are twins byte-identical | determinism everywhere |

## Probe plan (xtask/review_ux_probe.py — BEFORE the core build, RM_RUX lines)

1. `RUX-T2F` — the instrument as declared, draft-inlined; the medians land
   in docs/BENCHMARKS.md REVIEW-UX block at the gate.
2. `RUX-UNTOUCHED` / `RUX-DETERM` — byte-identity + twin rows (draft).
3. `RUX-EST-BASELINE` — the DEFAULT detector re-measured on the local
   anime benchmark (no-person count, per-image latency, pose-only
   latency): the numbers the adoption bars are ratios of. Models are
   local-store only; no downloads.
4. `RUX-EST-RITUAL` — the candidate scan evidence rows: for each
   landscape candidate checked, license/checksum/CPU status; the adopted
   or REFUSED verdict with reasons. (The session's web search evidence is
   recorded in the DECISIONS entry; the probe row verifies the manifest
   state — two pinned models unless an adoption landed.)
5. `RUX-REFUSE` — refusal classes loud (draft).

After the core lift, the probe re-runs against the CORE and the numbers
must reproduce exactly (the ONE-copy rule; scene_anim precedent).

## Policy (D-019)

The affordances carry ONLY artist-authored corrections (clicks, drags,
trims) — local data, no content class of its own. The estimator consumes
images locally only (the network promise stands; any third model rides the
manifest's one door). MCP stays SFW permanently and gains NO new tool in
P8-9 (declared; the review surface is add-on/core-side).

## What P8-9 deliberately does NOT do

- No viewport gizmo/drag-handle polish — the bar is the SCRIPTED
  click-through (windowed-GL work stays best-effort per the standing
  scope note; the operators ARE the interactive surface).
- No new MCP/session tools (the S31/S33 declared wiring items are
  separate, each needing its own gate rows).
- No fine-tune, no scraped data, no new model without the full ritual.
- No payload format change: v3 stays v3; the additive `estimator`
  entry field is omitted-when-default so today's bytes never move.

## Probe answers (as-built, 2026-09-28 — `xtask/review_ux_probe.py`,
### RM_RUX lines; 7/7 PASS exit 0; re-run against the CORE after the lift —
### numbers reproduced exactly: same defect counts, same medians)

- RUX-FIXTURE: 54 flagged defects on the benchmark fixture classes —
  flip 39 (the 20-pose class's material flips, wrong-sign injected,
  INSTRUMENT-labeled), finger 1 (the finger-gate occlusion ledger — the
  engine's own loud output), face 13 (the 10-expression class under the
  declared occlusion rule: only the IOD corners visible — every non-zero
  GT param confidence-gated), pin 1 (a beyond-reach pin the coupling pass
  reports unclosable — fix the FIXTURE, never the solver).
- RUX-T2F: **overall median 2.00 s (bar <= 15 s)**; per-class medians
  flip 2.00 / finger 4.00 / face 3.00 / pin 4.00 s; T2F-OP: the measured
  op wall-clock component 0.0001-0.0002 s median (54 click-throughs in
  ~6 ms core-side) — the model carries the bar, the ops are effectively
  free, published alongside.
- RUX-UNTOUCHED / RUX-DETERM: zero new items on clean inputs, round-trips
  byte-identical; 54 re-run fixes byte-identical.
- RUX-REFUSE: 8/8 loud refusals (unknown hand/finger/param, zero
  direction, bad pin index/endpoint, unknown figure label).
- RUX-EST-BASELINE: the default detector on the local anime benchmark
  n=10: no-person 3/10 (matches D-012 exactly), full p50 ~550-614 ms,
  pose-only p50 ~89-107 ms (CPU, this box) — the numbers any future
  candidate's adoption bars are ratios of.
- RUX-EST-DEFAULT: the interface draft proven with fakes (no weights, no
  downloads): default-only registry byte-identical; keyed-order fallback
  selected exactly on the no-person probe; provenance rides the additive
  `estimator` entry field, never written for the default.
- RUX-EST-RITUAL: the manifest pins exactly the two DWPose models; the
  candidate scan (D-024) found no adoptable anime/sketch estimator —
  **L9 = REFUSED-with-evidence after one candidate; the INTERFACE ships**.

## Gate-earned corrections (recorded before the gate finalized)

1. **The Blender stale-operator-return class**: five EXISTING operators
   (`flip_toggle`, `pick_joint`, `flip_reset`, `show_report`,
   `clear_pose`) returned `{'REGISTER'}` from `execute()` — an invalid
   return (REGISTER is a `bl_options` value, not a result). Blender 5.1
   validates strictly, so every button click of those operators raised
   RuntimeError; no earlier gate ever invoked them through `bpy.ops` (the
   P1-11 gate drove the core directly). All execute returns are
   `{'FINISHED'}` now; the P8-9 operators were born clean.
2. **The Blender mixin-MRO class**: an operator may not list
   `(Operator, PlainMixin)` — the MRO refuses. The shared scene-fix body
   lives in `_SceneFixOp(Operator)` and the concrete operators subclass
   the mixin only.
3. **The background-blender ERROR-report class**: an operator's
   `report({'ERROR'}, ...)` RAISES RuntimeError at the invoking script in
   background mode (and a failed poll raises its own). The gate's refusal
   row treats both as the loud CANCELLED path they are.
4. **The pin fixture's label space**: couple_gate's payload labels its
   figures A/B — the first pin fixture mixed in girls_multi labels and
   the scene validation refused it loudly (the honesty law working; the
   FIXTURE was fixed).

## As-built (S34, 2026-09-28) — the landing

- **Core** (`review.py` additive): `ReviewItem.fix` (omitted-when-empty —
  pre-P8-9 bytes pinned), the four affordances (`author_finger`,
  `trim_face`, `flip_figure`, `retarget_pin`, + `confirm_pin`), the three
  defect surfaces (`finger_defects`, `face_defects`, `scene_defects`) —
  pure functions, loud refusals, provenance notes, `review_items`
  untouched. `inference/estimator.py`: the D-011 interface (protocol +
  `select_estimator` keyed fallback + `with_estimator_entry` provenance).
  `payload.build_pose_payload` carries the additive per-figure `estimator`
  field (non-default only — the default-only pipeline writes
  byte-identical payloads, contract-pinned). 19 CI tests
  (test_review_ux.py) = **634 total**.
- **Add-on** (`review_fix.py` — the casting_desk pattern): `rm.finger_fix`
  / `rm.face_trim` (pose-level, the P1-6 apply path) and `rm.figure_flip`
  / `rm.pin_retarget` / `rm.pin_confirm` (scene-level, the P8-1 desk
  pairing + `apply_scene_payload`, coupling included); panel sections in
  the main panel + the Casting Desk; registered with the house table.
- **Gate** (`xtask/review_ux_gate.py`, the sibling file): 10 RM_RUX rows
  through the REAL operators — OPS / FINGER (segment lengths 1.4e-17 u,
  op ~13 ms) / FACE / FIGURE (op quats == direct-path quats, 42 bones) /
  PIN (library-path positives + operator pin-less refusal) / UNTOUCHED
  (159 bones byte-identical) / REFUSE 6/6 / DETERM (twins, 159 bones) /
  T2F (op wall-clock ~7-14 ms per class) — wired into verify_pose_apply.sh
  + the Makefile lint list; the FULL battery re-ran byte-identical (every
  prior number held).
- **NOT landed (declared)**: viewport drag-gizmo polish (the operators
  ARE the interactive surface; windowed-GL stays best-effort); no new
  MCP/session tools (the S31/S33 wiring items remain declared); no
  fine-tune, no scraped data, no third model (D-024).

## Reproduce (as-built)

- `python3 xtask/review_ux_probe.py` — the RM_RUX instrument rows
  (models optional; `--skip-models` for the core-only rows).
- `BLENDER=... RIGPOSE=... bash xtask/verify_pose_apply.sh` — the full
  battery incl. `RM_RUX GATE: PASS`.
- `python3 -m pytest core/tests/test_review_ux.py` — the contract tests.
