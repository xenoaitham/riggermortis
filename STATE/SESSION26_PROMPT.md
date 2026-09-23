# SESSION 26 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Toon renders, manga pages. Live
pose-stream puppeteering shipped on the replay path. No cloud, no accounts,
no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).
Phases 0–4 CLOSED (D-017). Phase 5: P5-1/2/3 DONE; P5-4 needs the camera
(DIAGNOSED — see blockers — and PARKED LAST by LO). Phase 6: P6-1 (S22),
P6-1a (S25), P6-2 (S23+S24), P6-2a refactor half (S25), P6-4/P6-5 (S21),
P6-6 (S23) DONE; P6-3 UNBLOCKED (D-020). Phase 7: P7-1/2/3 DONE (S20);
**P7-4: LO REGISTERED the blender.org account — publish deliberately
deferred to LO's final session**; **P7-5: DONE — riggermortis_core 0.0.1
LIVE ON PYPI** (fresh-venv install verified; token rotated after use —
verify `pip install riggermortis-core` still on the manifest claims);
P7-6 PARTIAL — the 60s launch cut is BUILT (`make launch-cut`,
docs/media/launch_cut.mp4; the reserved live shot splices in after P5-4).

**THE MISSION SHIFT (read STATE/ROADMAP.md first — it is the plan of
record)**: Phase 8+ "the Producer" — coupled multi-character NSFW scenes
(ContactPins + a deterministic coupling pass), FINGERS (the detected-but-
unused hand keypoints), FACIALS (published landmark→param table), the
reference camera solve, spine arch + roll, root motion, multi-character
video → scene animation, review-UX speedrun + the anime fallback
estimator. Two-round adversarial critic: round 1 5.1/10 FAIL (ten
strikes), round 2 **9.8/10 PASS** — every strike answered in the
roadmap's standing constraints. Session map: S26=P8-1 … S35=Scene Test.
LO's ~15-session estimate is the envelope.

S25 + triage contract facts (what S26 builds on):

- **P6-1a chain-binding presets**: preset format 2 (write) / 1+2 (read);
  `secondary` bindings via the ONE ChainSpec validator; two-layer
  validation (file-level vs bake-level live-rig checks); CLI
  `preset save --secondary` / `preset set-secondary`;
  `resolve_secondary()` fingerprint gate; session `bake_action` params
  `preset_path`/`preset_force`/`fps`; gate rows RM_SECONDARY PRESET +
  PRESET_GATE. presets.py is package-imported — `__version__` import
  stays DEFERRED inside `preset_from_mapping`.
- **P6-2a refactor half**: the clip-sampler loop lives in
  `riggermortis_addon/clip_sample.py` (bpy inside functions, shim-tested
  via the generic `addon_module()` conftest helper);
  `xtask/sample_clip.py` is a thin caller. Byte-identity PROVEN at
  promotion; error exits: usage 64, refusals 3, DETERM fail 1.
- **P6-3 answers = D-020**: CC0 suite, ControlNet + BY-SA slots REPLACED
  (owned/CC0 art, n=10 kept, honest re-run note), LO reviews the photo
  set at packaging time, in-repo docs/ distribution, the public suite
  BECOMES the CI gate fixture, P2-8 RETIRED as satisfied-by-Xbot.
  Packaging is buildable work (S26+ backlog material, see roadmap slack).
- **P7-5 PyPI LIVE**: riggermortis_core 0.0.1 on PyPI, fresh-venv
  verified (rigpose CLI runs, PRESET_FORMAT=2 shipped, policy defaults
  OFF). The upload token was env-transient and is ROTATED — nothing to
  clean in-repo. Remaining: LO's site-side project description.
- **P7-6 pre-cut**: xtask/launch_cut.sh (shell-glue ffmpeg, D-009),
  60.0s/1280x720/1800 frames parse-back PASS, 7-shot visual check PASS
  (3 defects caught+fixed pre-ship: fontcolor, caption placement, an
  unwired caption), shot 6 typesets the REAL tail of a REAL gate run
  (cached out/launch_cut/gate_capture.log; --recapture-gate re-runs),
  no live footage pretended; media + allowlist landed same-commit.
- **431 tests** (S25 added 20). CI green through the triage pushes
  (runs 35924803826 + the triage chain). All gate numbers byte-identical
  through S25 (RM_BAKE 0.0242° ×3, RM_FOOT_LOCK, RM_SECONDARY 1.81°/280
  keys + the new PRESET rows, RM_TAILS, RM_MOTION block).
- **D-021 is PROPOSED by the roadmap, NOT yet written**: S26 writes the
  DECISIONS entry when the finger/face additive namespace lands in code
  (the frozen 22-role core stays frozen; fingers live in a separate
  additive map).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND: the phone came up — P5-4 becomes doable, but LO parked it
  LAST: confirm frames, tell LO, then CONTINUE the roadmap work order
  unless he says otherwise (the live demo is an endgame item).
- Silent: proceed with the roadmap work order below.
- Then read, in order: STATE/ROADMAP.md (THE plan of record — the
  standing constraints section is law for every phase), STATE/NEXT.md,
  STATE/TASKS.md, STATE/PROGRESS.md (S25 + triage entries),
  STATE/DECISIONS.md (D-003, D-008, D-009, D-015/016, D-017, D-019,
  D-020; D-018 RESERVED; D-021 to be WRITTEN by S26), 
  STATE/CONVENTIONS.md, STATE/SESSIONS.md, docs/SECONDARY_MOTION.md,
  docs/MOTION_LIBRARY.md, docs/LIVE.md, docs/BENCHMARKS.md, docs/POLICY.md,
  docs/STYLE_LORA.md, and the claim-bearing surfaces docs/LAUNCH.md +
  docs/TUTORIALS.md. Register as Session 26, claim tasks with [S26],
  PROGRESS stamps: `date -u` IMMEDIATELY before every append, and VERIFY
  the stamp against the clock after writing (S25 misjudged elapsed time
  repeatedly and corrected in minutes — use the echoed value, not a
  guess).

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**431 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (green). If red: download the log, root-cause,
fix the real substance FIRST.

## S26 work order — P8-1 CanonicalScene + the casting desk + camera v0

Per STATE/ROADMAP.md P8-1 (the rock; the roadmap's standing constraints
are law):

1. DESIGN-FIRST in a new docs/SCENES.md (the SECONDARY_MOTION pattern):
   ScenePose/ContactPin data model, payload v3 ADDITIVE schema
   (figures[], pins[]; unknown-field policy unchanged), the casting-desk
   UX, camera v0 semantics (approximate, labeled, refuse-to-stage floor).
2. PROBE FIRST for the Blender unknowns (multi-armature apply order,
   per-armature payload recomputation, camera staging) — one
   xtask/scene_probe.py, RM_SCENE lines, before any build code.
3. Core `scene.py` + payload v3 + CI tests (back-compat v2
   byte-identical, determinism, loud validation); D-021 DECISIONS entry
   if/when the additive namespace solidifies (fingers are P8-3 — D-021
   can land with P8-1's versioning discipline or defer, say which).
4. Add-on Casting Desk operator + session `apply_scene` (v1 additive);
   camera v0 button with the confidence floor.
5. Gate: RM_SCENE section (verify_pose_apply.sh or a sibling) — 2-rig
   apply fidelity bars, v2 back-compat, camera staging bars; grep-test
   both PASS and refuse shapes.
6. If A lands early: P8-3 fingers DESIGN sections (the data is already
   in the detection payload — check what the payload carries today vs
   what detection exposes; the 133-kp question needs a measured answer
   before P8-3's design page).

Watch out for (standing — the roadmap's constraints + the earned facts):

- The roadmap's honesty law: pins enforce ONLY authored links; inferred
  = suggestion; cameras refuse below the floor; every residual loud.
- The frozen-API amendment rule + payload additive-only policy (v3).
- Park criteria: two stalled probe/gate cycles → park, reorder, move on.
- Policy D-019 across scene surfaces; MCP stays SFW (test-pinned).
- The env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/blender,
  RIGPOSE=/home/potato/miniconda3/bin/rigpose,
  PY=/home/potato/miniconda3/bin/python3.
- Mimosa: bash writes of source-looking files blocked (Write/Edit only);
  pagedoc.py import-struct FP at every commit — disclose, move on;
  commit messages via -F files.
- STATE stamps: real UTC, read-then-write-then-verify.
- Claim-bearing surfaces: only touched when a number changes; grep all
  three together (README status, LAUNCH, TUTORIALS) when it does.

End of session (non-negotiable) Tick claimed tasks (completed vs
partially-done + what remains). Append PROGRESS (real UTC). Top of
STATE/NEXT.md: "NEXT SESSION SHOULD" for 27 (P8-2 coupling per the map,
or the parked-reorder reality — say which). Write
STATE/SESSION27_PROMPT.md (this pattern + the roadmap facts). Update
STATE/SESSIONS.md row. Commit + push; keep CI green, fix inline
(S12..S25 discipline). Mimosa FPs expected and disclosed.

Known blockers (parked) — Live capture device: DIAGNOSED (loopback
ready, DroidCam client was never running, nothing on 4747); LO PARKED IT
LAST — when he brings the phone up (WiFi mode, same network, app open),
confirm frames with the one command and ask whether P5-4 jumps the queue.
PyPI description + Blender Extensions upload: LO's site-side steps
(account registered; publish deferred to LO's final session by LO).
Windowed GL stability: best-effort, never staged. P1-8a: roadmap P8-9.
