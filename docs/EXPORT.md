# Animation export (P2-7)

The add-on bake (`riggermortis_addon.bake.bake_action`) writes keyframed
Blender actions. Getting them OUT of Blender uses Blender's **builtin
exporters**, driven by an edge script — per D-009, the spawn lives in shell
glue, never in a `.py` file.

## What is verified

`bash xtask/export_clip.sh` (or `make export-verify`) — self-contained, no
models, no local assets; runs in CI on the 4.0.2 pin and locally on 5.1.0:

1. builds the proven test armature (same layout as `blender_verify.sh`);
2. bakes a 2-frame canonical action (pose A at frame 1, its mirror at frame
   2) through the add-on's own bake path;
3. exports **glTF 2.0** (`GLTF_SEPARATE`) and **FBX** via the builtin
   exporters;
4. re-imports EACH file into a fresh scene and verifies the round-trip:
   - skeleton survives — bone count matches the source;
   - animation survives — an action exists, its fcurves cover the baked
     frames (probes both the pre-5.x `Action.fcurves` API and the 5.x
     slotted-action API);
   - pose fidelity — at BOTH frames every mapped bone's world direction is
     re-measured against the canonical targets (the same independent measure
     as `verify_pose_apply.sh`).

Numbers (Blender 5.1.0, 2026-09-17): round-trip worst error **0.0164°**
(glTF) / **0.0140°** (FBX) against a 2.0° bar — the bar has honest headroom
for exporter-version resampling; the measured numbers are the claim.
In-process bake fidelity is 0.0000° (the RM_BAKE gate in
`verify_pose_apply.sh` holds the 0.5° bar).

## What is honestly NOT here: VRMA

VRM Animation (`.vrma`) has **no builtin Blender exporter**. Scoping it
honestly: a minimal writer is feasible — VRMA is a JSON document with
per-humanoid-bone quaternion tracks plus a signaling track — and our role
mapping (`rm_role_*` / `core.map_rig`) provides the humanoid-bone bridge.
It is a deliberate work item, NOT a claim: nothing in this repo writes
`.vrma` today, and no doc may say otherwise until a test proves it.

## Reproduce

```bash
BLENDER=/path/to/blender bash xtask/export_clip.sh
```
