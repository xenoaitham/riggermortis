# Secondary motion (P6-1) — design

Written BEFORE the build (the LIVE.md/STYLE.md pattern): this page is the
design of record for Phase 6's secondary-motion rock. The as-built facts and
measured numbers get appended to their sections as they land; nothing here is
a claim until a test, probe line, or gate number cites it.

## What P6-1 is (and is not)

Secondary motion = follow-through on things that are NOT the canonical
humanoid: hair strands, a tail, a belly/fat chain, a scarf. The canonical
skeleton (P0-02) is a fixed 21-role humanoid; these appendages hang off it.
v1 models each appendage as a **spring chain**: a sequence of rigid links
that lag behind the anchor's motion under damped angular springs, then
settle. The engine output is a per-frame track of link directions; the
add-on bakes those onto real rig bones so any mapped rig with appendage
bones gets follow-through for free.

NOT in v1 (honest scope, each a deliberate non-goal — see § Out of scope):
cloth simulation, collision, wind fields, live-mode integration, embedded
track file formats, UI panel controls.

## Mechanism — spring chains over canonical roles

A chain is anchored at one canonical role's joint (the anchor bone). Each
link is a **spherical damped spring**: the link has a unit direction
``d_i`` (world space) and an angular velocity ``w_i``; a spring pulls
``d_i`` toward its REST direction defined in the parent frame, a damper
bleeds energy, and inertia produces the follow-through. Rigid length is
free — directions only, no constraint solver, no stretch.

Per substep (semi-implicit Euler, fixed timestep):

```
t_i     = R_parent(i) @ r_i          # world rest direction for link i
axis    = d_i × t_i                   # rotation axis, |axis| = sin(angle)
w_i    += (k·axis − c·w_i) · dt      # spring + damper, THEN integrate
d_i     = rotate(d_i, axis_of(w_i), |w_i|·dt)   # Rodrigues, re-normalized
```

- ``r_i`` is the link's rest direction authored in the **parent frame**
  (link 0's parent = the anchor bone; link i's parent = link i−1), so the
  chain inherits anchor rotation through the rest-direction springs and
  curvature propagates down the chain.
- Parent frames are built deterministically from a bone direction ``u``:
  ``Y = u`` (along bone), ``X = normalize(side_ref − (side_ref·Y)Y)`` with
  ``side_ref = (+1,0,0)`` (character-left), ``Z = X × Y`` … resolved so the
  frame is right-handed with the documented axis meaning
  (X = character-left, Y = along-bone, Z = character-back). Degenerate
  anchors (bone parallel to the side reference) are REFUSED loudly, not
  guessed. For the spine anchors v1 actually uses, the rest-pose frame is
  exact.
- Anchor frames come from the pose itself: ``u = normalize(pos[anchor] −
  pos[parent(anchor)])``, falling back to the primary child when the parent
  joint is coincident (root and hips share a joint in the canonical rest
  skeleton, so hips orients as hips→spine — still exactly the bone's up
  direction). A frame that still cannot orient the anchor is reported,
  never interpolated (the gap rule every core pass follows).
- **Direction-only state means translation inertia is NOT modeled** (v1):
  the chain feels anchor ROTATION through the parent-frame springs, but a
  pure translation of the whole pose is invisible to it. Walk-in-place
  poses (the certified pipeline's only motion, D-008) are
  rotation-dominant, so this is the honest v1 boundary; positional chain
  state is the declared upgrade and it changes the schema.
- Frames are held zero-order between action frames (consistent with the
  bake's per-frame keys — no fabricated in-betweens). Each frame is
  advanced by an integer number of substeps of ``dt_sub = (1/fps)/n`` with
  ``n = ceil((1/fps)/DT_TARGET)``, ``DT_TARGET = 1/240 s`` — exact frame
  alignment for any fps, and integer substeps keep the integrator
  deterministic.
- The simulation is a PURE function: ``simulate_secondary(action, chains,
  fps) -> dict[str, SecondaryTrack]``. It reads the (already-certified)
  action, never mutates it, iterates chains in sorted-name order, and is
  stdlib-only (D-003).

### Constants (D-008: order-of-magnitude, declared untuned)

| constant | default | rationale |
|---|---|---|
| link frequency ``freq_hz`` | 3.0 | hair/tail on a ~1.7 m figure swings at single-digit Hz; 3 Hz is the middle of that band. ``k = (2π·freq_hz)²`` |
| damping ratio ``damping_ratio`` | 0.5 | underdamped enough to show follow-through, settles in a few swings. ``c = 2·ζ·2π·freq_hz`` |
| integration target ``DT_TARGET`` | 1/240 s | ω·dt ≈ 0.08 at 3 Hz — two orders inside the semi-implicit Euler stability bound (ω·dt < 2); cheap |
| schema bands | freq 0.1–20 Hz, ζ in (0, 5] | validation bands, not physics claims; outside them the spec is refused with a hint |

Every one of these is a starting point declared UNTUNED. They are never
fitted to the gate fixture (D-008); the gate asserts BEHAVIOR (follow, lag,
settle, determinism), not specific trajectory values.

## Data model

``ChainSpec`` (core, frozen dataclass + ``from_dict``/``to_dict``) —
validated loudly at construction (unknown fields fail; every refusal gets an
actionable hint). v1 simulates DIRECTIONS ONLY, so the schema carries no
lengths or offsets — rigid length is free in direction space, and fields the
engine does not read would be dishonest payload:

| field | type | meaning |
|---|---|---|
| ``format`` | int | schema format, 1; unknown values refused |
| ``name`` | str | unique chain id (output dict is keyed by it) |
| ``anchor_role`` | str | canonical role with a parent (``hips``…``head``, limb roles); ``root`` refused — no parent direction |
| ``links`` | int | 1–16 rigid segments |
| ``rest_direction`` | Vec3 | one rest direction for every link, in the parent frame, normalized on load |
| ``rest_directions`` | Vec3 list | OR per-link rest directions (parent frame); length must equal ``links`` |
| ``freq_hz``, ``damping_ratio`` | float | the D-008 constants above (defaults 3.0 / 0.5) |

``SecondaryTrack`` (core, output): chain name, anchor role, the observed
frame indices, and per frame a tuple of unit world directions (one per
link). Deterministic: same action + specs + fps = byte-identical track.

Rig binding: which real bones implement a chain is RIG-SPECIFIC data and
enters at the add-on bake boundary — ``bake_action(..., secondary=[(track,
[bone names])])`` (exactly ``links`` existing bones, validated; the rig's
own hierarchy parents the chain bones under the anchor role's bone, which
is what the composition walks). A preset-file home for that binding
(extending the P0-09 per-rig preset) is the declared follow-up; v1 does
not touch the frozen preset schema.

Example DATA file: ``addon/riggermortis_addon/presets/secondary/demo_tail.json``
(a 4-link tail off ``hips``, droop authored into the rest direction) —
validated through core's ``from_dict`` so the validator is the single
implementation, in the style-presets discipline (data file, loud
validation, no code duplication).

## Where it hooks — the certified composition is untouchable

The certified composition is **stabilize → smooth/reduce → detect → lock**
(``condition_action`` + ``contacts.lock_feet``; the CI gate runs it with
smoothing/reduction off). Secondary motion rides AFTER, as a 4th stage:

```
action ──► condition_action ──► detect_contacts ──► lock_feet ──► simulate_secondary ──► bake ──► bake_secondary
                                 (foot-lock guarantee lives HERE — untouched)   (pure read)        (keys NEW bones only)
```

Guarantees, each pinned by a test:

1. **FK roles are never touched.** Secondary writes only NEW appendage
   bones; canonical role positions/rotations are consumed read-only.
   Baking a locked action with chains yields byte-identical FK role keys
   as baking it without.
2. **The foot-lock guarantee cannot reorder.** ``lock_feet`` runs strictly
   BEFORE the simulation and the simulation cannot move an ankle: it never
   writes to the action at all.
3. **No new latency surface.** The simulation is per-frame pure math on
   the same frame indices the bake already walks; it adds no process, no
   socket, no I/O (D-003/D-009 boundaries untouched).
4. **Determinism.** Sorted chain order, integer substeps, no wall-clock
   input anywhere.

## Add-on surface (v1)

The certified bake grows one optional binding —
``addon bake_action(obj, frames, core, secondary=[(track, [bone names])])``:
per frame, AFTER the FK roles are keyed, each chain link bone is keyed so
its world Y points along the track direction (``_aligned_world``'s minimal
rest-preserving roll, composed through the carried ``world_t`` chain state —
the same local-composition discipline as the FK keys, ``pb.matrix`` never
read mid-bake). Structured report additions: per-chain bone/key counts;
wrong bone counts or missing bones refuse with hints. The Blender-side math
was probe-validated FIRST (below). NOT an MCP session action in v1 (schema
stays v1 additive — documented follow-up), NOT a panel control yet.

## Probe answers (as-built, 2026-09-22 — `xtask/secondary_probe.py`,
RM_SECONDARY lines, Blender 5.1.0 headless)

- **RELATION**: the pose-basis composition is ``pb = C @ rest @ basis``
  with ``C = parent_pose @ parent_rest⁻¹`` (rest@basis delta 0.000000 vs
  basis@rest 1.000000 on a non-commuting roll test) — the first probe
  draft got this wrong (177°/90° off) and the probe caught it BEFORE any
  build code existed, which is why it runs first.
- **COMPOSE 0.0000° / REEVAL 0.0000°** (bar 0.05°): keyed chain directions
  reproduce the simulated track exactly through a POSED parent chain
  (stepped anchor) and re-evaluate byte-identically from the fcurves.
- **COMPOSE-XFORM 0.0000°**: a 30°-rotated armature object does not leak
  into the keys.
- **FOLLOW max 24.84°** (bar ≥5°): the spring chain visibly lags a stepped
  anchor and swings through.
- **SETTLE 0.00°** (bar ≤2°): with the untuned defaults (3 Hz / ζ=0.5) the
  chain is at rest within the 1 s hold after the step.
- **DETERM byte_identical=True**: two independent sims agree exactly.

## What is honestly out of scope (v1)

- **Cloth simulation / collision / wind** — chains are rigid-link
  follow-through; nothing collides, nothing billows.
- **Gravity as a force term** — droop is authored into rest directions; a
  gravity term would demand per-rig tuning (D-008) for no v1 benefit.
- **Anchor translation inertia** — direction-only v1 (see § Mechanism);
  positional chain state is the declared upgrade.
- **Live mode (P5)** — driving chains per poll on the smoother output is
  the obvious extension but needs the camera to measure honestly; deferred
  until P5-4 lands.
- **Track embedding in the payload/action file format** — a contract
  change; v1 recomputes tracks deterministically at bake time instead.
- **Chain-binding presets, MCP session action, panel UI** — declared
  follow-ups in that order.
- **Uniform segments only** — per-link lengths are trivial to add later;
  v1 keeps the schema minimal.

## Instruments (planned — filled with as-built numbers at close)

- **CI** ``core/tests/test_secondary.py``: spec validation (every band +
  unknown-field refusal), determinism (two sims byte-identical), input
  never mutated, translation inertness (a pure translation moves nothing —
  the pinned direction-only contract), rotation follow (anchor pitch lags
  then catches), settle to rest after motion stops (ζ does its job),
  bounded excursion + unit directions at defaults (no blow-up),
  1-frame/empty actions, held frames when the anchor cannot orient,
  multi-chain keyed order, the demo DATA file validates.
- **Probe** ``xtask/secondary_probe.py`` (BEFORE the build): the
  Blender-side unknowns — (a) extra bones can be added headlessly to an
  armature and keyed; (b) the world-direction → parent-space rotation
  composition reproduces a target direction on a real armature; (c)
  re-evaluating from fcurves (5.1 slotted actions) returns the keyed
  directions.
- **Gate**: an ``RM_SECONDARY`` section in ``xtask/verify_pose_apply.sh``
  driven by ``demo_tail.json`` + the SYNTHETIC walk fixture
  (``xtask/walk_job.py`` — labeled synthetic, the real-clip rule holds):
  chain-bone world directions re-evaluated from fcurves vs the simulated
  track (bar: the 0.5° FK family), FK-invariance (bake with vs without
  chains), settle, determinism. grep-tested like every RM_ section.

## Reproduce (as-built)

```bash
# the capability probe (self-contained, no models — answers the Blender
# unknowns; RM_SECONDARY lines, exit 0 = all answered)
blender -b --python xtask/secondary_probe.py

# the unit contract (validation, determinism, inertness, follow/settle)
cd core && python3 -m pytest tests/test_secondary.py

# the real-bake integration (inside the pose-apply gate; needs the local
# rig/payload prerequisites the gate already builds — RM_SECONDARY lines)
BLENDER=/path/to/blender RIGPOSE=/path/to/rigpose PY=/path/to/python3 \
  make pose-verify
```
