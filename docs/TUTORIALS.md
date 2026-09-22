# Tutorials (P7-2) — outlines with real command sequences

Four audience tracks. **Every command below is real and works today** unless
the section names a gap in a `GAP:` line — camera-dependent or unshipped
steps stay listed as gaps instead of pretending. Paths are relative to a
clone of this repo; the numbers each step relies on cite
[docs/BENCHMARKS.md](BENCHMARKS.md) and the gates that produce them.

Common setup (once):

```bash
pip install -e "core[inference]"     # engine + ONNX runtime extra
rigpose models download all          # two checksum-pinned models; the only network action ever
```

Blender add-on (once): zip the `riggermortis_addon/` folder → Blender →
Get Extensions → Install from Disk (4.2+; classic add-on load on 4.0.x).
Every gate exercises this add-on headlessly on Blender 5.1.

---

## 1. Gamedev — photo/video → animation on your game rig → FBX/glTF

*Full pipeline works today. Nothing in this track is gap-blocked.*

1. **Get your rig into the engine** (one command per source):

   ```bash
   bash xtask/extract_blend.sh my_character.blend my_rig.rig.json     # .blend
   blender -b --python xtask/import_and_extract.py -- my_character.vrm my_rig.rig.json   # VRM/GLB/FBX via your Blender
   ```

2. **Map it** and read the confidences:

   ```bash
   rigpose map my_rig.rig.json --strict
   # review flags? reassign in one flag:
   rigpose map my_rig.rig.json --strict --set upper_arm.L=my_arm_l
   # save the correction keyed to this exact rig:
   rigpose preset save my_rig.rig.json --out my_rig.preset.json
   ```

   Real-rig gate for context: metarig / 706-bone Rigify / VRM / real Mixamo
   export all map with 0 manual corrections (BENCHMARKS.md Phase 0).

3. **Pose from one image:**

   ```bash
   rigpose pose ref_pose.jpg my_rig.rig.json --out payload.json
   ```

   In Blender: select the armature → N-panel → pick the payload → Apply
   Pose. Something bent the wrong way? The viewport overlay's flip buttons
   fix it in one click (that's the designed remedy for the documented
   single-view ambiguities).

4. **Animate from a video:**

   ```bash
   bash xtask/extract_frames.sh clip.mp4 out/frames 15
   rigpose pose-video out/frames my_rig.rig.json --out out/walk_job --stride 2
   ```

5. **Bake the action.** GAP (named): there is no N-panel bake *button* yet —
   the verified bake path today is the session bridge's `bake_action`
   action, driven by any MCP client (`mcp/README.md`, 5-minute connect;
   gate: `make session-verify`). It runs foot-contact detection + the IK
   foot lock during the bake (in-plant drift drop 21.7×/12.0×/21.1× on the
   test rigs — WALKRIGS block) and re-verifies the baked fcurves against
   the canonical targets. A panel button around the same executor is
   future scope.

6. **Export** with Blender's own File → Export → FBX / glTF. The round-trip
   gate re-imports both formats and re-measures pose fidelity: worst
   0.0164° (glTF) / 0.0140° (FBX) vs a 2.0° bar (`make export-verify`).

7. **Honest limits for game work**: walk-in-place — no root motion is baked
   (the single-view solve is hip-anchored; fabricating world translation
   would be fake data). Plan to move the character with your controller,
   animate the body in place.

---

## 2. VTuber — webcam puppet mode

*The consumer half is real and gate-tested; the capture half needs a
working camera on your machine.*

1. **The pieces that exist today** (verified on replayed streams —
   measured on replayed frames; real-camera number pending):

   ```bash
   # replay a recorded frame dir through the realtime side process:
   rigpose live out/live_probe/frames out/real_rigs/metarig.rig.json \
       --out live.jsonl --detect-every 5
   ```

   In Blender: N-panel → Live driver → point it at `live.jsonl` → Start.
   The rig puppeteers through the same apply path the one-image flow uses;
   the panel shows live/stale state, per-line latency, apply cost, and the
   smoothing toggle (1€ filter, per role; defaults are documented untuned
   starting points).

2. **Safety rails you can rely on** (gate-tested, `make live-verify`):
   brief stream silence keeps the last pose and reports STALE; sustained
   silence clears the rig to rest and says FAILSAFE; a recovered stream
   re-applies automatically.

3. **GAP (named): the camera.** `bash xtask/live_capture.sh out/frames 15`
   turns any v4l2 device (webcam, DroidCam) into the frames dir the side
   process watches — it is shipped UNTESTED against a streaming device
   because our capture node has delivered zero frames for five sessions
   (NEEDS-HUMAN). When your camera streams, this track becomes the full
   loop: capture → `rigpose live` → Live driver. The Phase-5 <100 ms
   mid-laptop gate gets claimed (or retired) by that same measurement —
   not before.

4. **Multi-figure streams**: currently one figure per frame (largest),
   single-person framing recommended.

---

## 3. Webcomic — image → posed render → manga page → PDF

*Full pipeline works today.*

1. **Pose your character** (track 1, steps 1–3), then dress the frame:
   camera, lens (wide panels like ~35 mm), workbench or EEVEE.

2. **Style it** — the three shipped presets are DATA, not code:

   - In the agent path: `apply_style` session action (manga / anime /
     western; gate: `make style-verify`).
   - Preset JSONs live in `addon/riggermortis_addon/presets/` — banded
     toon shading + rim + (per style) GPv3 line art and screentone dots.

3. **Lay out a page**: page presets are DATA too
   (`presets/pages/manga_koma3.json` is RTL, `western_cross3.json` LTR;
   per-panel style overrides supported — the shipped manga page mixes
   anime into a manga page on purpose). Speech bubbles are per-panel data:
   8-way tails, typeset text — never hand-lettered.

4. **Export**: `rigpose export-pdf` / `rigpose export-epub` — pure-stdlib
   writers with parse-back readers, byte-deterministic (same input, same
   bytes; gate-tested).

5. **The reference implementation is the tutorial**: `bash
   xtask/manga_build.sh` renders the shipped 6-page wordless manga
   ([docs/manga/](manga/) — "Paper Dart") end-to-end, per-panel scene
   `frame` references included. Read its driver (`xtask/manga_build.py`)
   as the canonical "how a page gets made" example.

6. **Honest scope**: static cameras per panel (camera animation within a
   shot is recorded future scope); animatic output is a TIMED ROUGH, not a
   final render.

---

## 4. Indie-animator — the review-and-fix loop, animatics, turntables

*Full pipeline works today.*

1. **The posing loop** (the core craft loop): Apply Pose → the overlay
   shows confidence bands per role (<0.55 red / <0.75 amber / else green)
   → click a joint to inspect, one click to flip a flagged elbow/knee →
   re-apply verified at 0.0000° in the gate. Manual flips live in the
   session; the payload file is never mutated.

2. **Turn a pose sequence into an animatic**: canonical actions (track 1
   step 4) feed the animatic builder — panel layouts + per-shot timing
   from the action, rendered as deterministic per-frame PNGs, assembled by
   shell ffmpeg. Labeled honestly everywhere: TIMED ROUGH. Gate:
   `RM_STYLE ANIMATIC: PASS` inside `make style-verify`.

3. **Turntables for review**: the session bridge's `render_turntable`
   orbits a bone-proxy visualization of the mapped rig playing any baked
   action (that's exactly what the committed
   [agent demo](AGENT_DEMO.md) shows). GAP (named): turntable control
   lives behind the MCP bridge today; an artist-facing panel button is
   future scope.

4. **Cleanup arsenal for motion clips** (all documented order-of-magnitude
   defaults, none tuned against fixtures): hip stabilization (halves the
   "breathing" stance slide on the synthetic gate), 1€ jitter smoothing,
   greedy keyframe reduction, foot-contact detect + IK lock
   (BENCHMARKS.md HIPSTAB/FOOTLOCK blocks).
