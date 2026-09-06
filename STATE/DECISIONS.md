# DECISIONS

Append-only. `NEEDS-HUMAN` items block nothing else — switch tasks and move on.

## D-001 Name availability — `riggermortis` confirmed usable (2026-09-06)
- PyPI `riggermortis`: **free** (404 on pypi.org/pypi/riggermortis/json).
- Blender Extensions: **free** (0 search results on extensions.blender.org).
- GitHub: one unrelated repo `TheOutdoorProgrammer/riggermortis` (Go,
  fishing-rig reference, 0 stars). Repo names are per-account → no conflict,
  but expect mild search collision; our README/keywords will dominate over time.
- Alternates `snapose`, `rigshot`, `posemd`: all free on PyPI too — kept as
  fallbacks, primary stays `riggermortis`.
- NEEDS-HUMAN: GitHub repo/org creation, PyPI account + name registration,
  extensions.blender.org account (publishing steps in Phase 7).

## D-002 Positioning vs prior art (researched 2026-09-06)
- **DeepMotion Animate 3D**: cloud SaaS, credit/second model — free tier ~60
  credits/mo, Starter ~$9/mo (180s), Studio $180/mo (7,200s). Uploads your
  video/character to their cloud. [deepmotion.com/pricing-animate3d](https://www.deepmotion.com/pricing-animate3d)
- **Rokoko Video/Studio**: free tier caps Vision AI (~30s/mo trial), $10/mo
  Basic = 600s/mo AI mocap, Plus ~$20/mo for full retargeting; cloud storage
  time-limited even on free. [rokoko.com/pricing](https://www.rokoko.com/pricing)
- **Mixamo**: free but rig-locked — auto-rigged skeletons can't be edited or
  extended, retargeting to custom rigs needs pose-matching + converters
  (Terribilis Mixamo Converter, UNAmedia), FBX round-trips fragile (0.01
  scale, axis conventions). Confirms "any rig" is a real pain point, not a
  made-up one. (Adobe community threads, Blender SE, Polycount.)
- **blender-mcp (ahujasid)**: closest to our MCP angle — but it is a generic
  scene-control bridge (LLM writes bpy code, executed unguarded; telemetry
  ON by default; blender.org Lab warns it executes LLM code without data
  guards). It has **no rig tools, no pose/animation semantics, no policy
  layer**. Our MCP contract = domain tools + structured refusals + local-only
  guarantee. [github.com/ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp), [blender.org/lab/mcp-server](https://www.blender.org/lab/mcp-server/)
- **Cascadeur**: desktop keyframing assistant (physics/AI-assisted posing),
  not image-driven, not rig-agnostic retargeting for arbitrary Blender rigs —
  adjacent, not competing on our core loop.
- **DWPose** (ICCV 2023, IDEA-Research): 133-keypoint whole-body estimator,
  ONNX Runtime CPU+GPU, the ControlNet-adjacent standard. Caveat found:
  trained on photoreal data; anime/sketch accuracy is a known gap (see
  SKEP-120K sketch-pose literature, arXiv 2510.26196). **Consequence:** the
  Phase 1 anime benchmark is load-bearing; if DWPose <90% usable on anime,
  plan a second estimator or fine-tune path (P1-8).
- **Unshipped combination confirmed:** local + rig-agnostic + art-pose
  support + MCP agent-drivable + manga output. Nothing found shipping all five.

## D-003 Core stays dependency-free AND process-free (2026-09-06)
- Phase 0 core has zero runtime deps (stdlib math only; numpy enters with
  inference as an optional extra).
- The core library performs **no subprocess spawning and no socket opens**.
  Initially architectural preference; then the workspace security gate
  (Mimosa) rejected any `subprocess` in library code — the boundary is now
  enforced by tooling and matches the embeddability goal (the add-on imports
  core inside Blender's Python; the MCP server may run it sandboxed).
- Blender interop therefore lives at the edges: `core/.../bridge/blender_extract.py`
  (runs *inside* Blender), `xtask/extract_blend.sh` + `xtask/blender_verify.sh`
  (shell glue), CI. `load_rig()` on a `.blend` returns an actionable error
  pointing at the edge script.

## D-004 Inference runs OUTSIDE the Blender process (Phase 1 architecture)
- onnxruntime in Blender's bundled Python is fragile (version/ABI, manylinux
  wheels). Decision: the add-on/MCP server invoke the core **inference CLI as
  a local subprocess** (edge layer only, per D-003) or a localhost helper;
  Blender consumes plain JSON keypoint/pose payloads. Keeps Blender stable,
  keeps the local-only property testable, allows GPU pickling-free lazy loads.

## D-005 Mapping algorithm v1 (locked until real-rig gate says otherwise)
- Name evidence → role-major greedy assignment (score desc, name asc),
  side-mismatch ×0.3, side-unknown ×0.8, one-to-one.
- Family overrides for Mixamo lies (`LeftLeg` = shin) keyed on the joined
  raw token string *including* side tokens (`leftleg`), computed before side
  stripping.
- Spine families (spine.001 / Spine1/2) resolved by chain-order promotion:
  leftover same-lexicon bones fill empty [spine, chest, neck, head] slots in
  height order; extras honestly unmapped.
- Geometry pass fills only still-empty roles, never clobbers name-pass
  results: root/hips disambiguation via parentless-fork shape, spine chain by
  height ordering, limb chains by direction+proportion+side(x).
- Confidence: 0.7·name + 0.3·geometry; geometry-only capped 0.75; ambiguous
  below 0.55; quadruped detection = mapped legs + remaining downward chains > 2.

## D-006 Conventions locked
- Side convention: character-left = +X (Blender world, facing −Y).
- Refusal codes are public API; presets keyed by rig fingerprint; determinism
  rules in CONVENTIONS.md.

## D-007 Mapping algorithm v2 — real-rig gate findings (2026-09-06, S2)
Driven by P0-15 on real Blender 4.0.2 Rigify rigs (metarig 159 bones,
generated 706 bones: 220 controls / 160 DEF- / 167 MCH- / 159 ORG-):
- **Side-marked hips flanks** (`pelvis.L/.R`) carry no hips evidence — half a
  pelvis is not the center hips (metarig previously mapped `hips → pelvis.L`).
- **Structural pre-pass**: a fork to downward limb chains spanning BOTH
  character sides at hip height pins `hips` when no name claims hips (the
  metarig's hips bone is lexicon-named `spine`); a single-child parentless
  bone directly above pins `root`. Both-sides requirement rejects a lowered
  (A-pose) hand fanning its fingers downward.
- **Prefix-duplicate barring**: bones sharing the fork's family signature
  (``DEF-spine``/``ORG-spine`` of a pinned ``spine``) are barred from the
  `spine` role — kills the one-vertebra-low torso chain on generated rigs
  (`spine → DEF-spine.001` now).
- **Pose-target preference**: name-pass ties break by prefix rank
  (unprefixed control > `DEF-` > `ORG-`); `MCH-` is a skip token (checked
  against pre-strip tokens so `MCH-spine` never maps) and `parent` is skipped
  (Rigify IK/FK parent helpers). Controls are the right FK posing target for
  generated rigs; DEF- wins where no control exists.
- **Duplicate-limb views** (co-located with or descending from a mapped
  thigh: `ORG-thigh.L`, bendy `DEF-thigh.L.001`) are not "extra limb chains";
  the quadruped detector also ignores skip-token bones (fingers).
- **Review-feed completeness**: every geometry-assigned role appends to
  `mapping.ambiguities[]`, not just low-confidence ones.

Gate results after v2 (see docs/BENCHMARKS.md): metarig 21 roles, core
complete, 0 corrections + 1 review-confirm (structural hips); generated 22/22
roles, core complete, 0 corrections, 0 flags.

## NEEDS-HUMAN queue
- GitHub org/repo + PyPI registration + Blender Extensions account (D-001).
- Decide public repo name string exactly (`riggermortis` recommended).
- Sample-rig sourcing for P0-15 needs network access in the next session
  (Mixamo export requires an Adobe login — NEEDS-HUMAN to obtain a
  redistributable-license sample or use a CC0 VRM + Rigify-generated rigs).
