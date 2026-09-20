# riggermortis

**Any rig. Any image. One click — or one agent tool call. Your GPU, your characters, zero uploads.**

A local, free, rig-agnostic posing & animation engine with two frontends: a
**Blender add-on** for artists and an **MCP server** so coding agents can drive
Blender directly. Drop in an already-rigged model and a reference image — the
pose is applied. Drop in a video — the character is animated, retargeted,
foot-slide-cleaned. Photos and anime/manga art both work. Render as anime,
manga, or cartoon; lay scenes out into manga pages and comic PDFs.

Everything runs on the user's machine: no cloud, no accounts, no uploads, no
telemetry — and a CI test keeps that verifiably true.

## Status: Phases 0–3 closed (mapping, posing, video, MCP) — Phase 4 style system through P4-7 shipped

| | |
|---|---|
| ![BOOM: rest → posed on a real Rigify metarig](docs/media/boom.gif) | ![One synthetic walk retargeted to three real rigs, feet locked](docs/media/walk_3rigs.gif) |

Left: the pipeline's own BOOM render — rest rig → solved pose applied through
the add-on's apply path, regenerated headlessly by
`bash xtask/render_boom.sh` (the pipeline refuses to pose anything it can't
verify to ≤0.5° per bone before shooting). Right: the Phase-2 close — one
labeled SYNTHETIC walk retargeted to three real rigs (Rigify | Seed-san VRM |
Mixamo) through the documented cleanup pipeline, feet IK-locked during their
plants; regenerated headlessly by `make walk-gifs`. Per-rig numbers and the
honest synthetic-vs-real-clip status live in
[docs/BENCHMARKS.md](docs/BENCHMARKS.md) — regenerate them yourself instead
of trusting us.

What exists **right now** (every claim cites a test, gate, or number):

- **Rig-agnostic mapping** — Rigify / Mixamo / VRM / opaque custom rigs:
  name heuristics + geometry fallback, per-role confidence, ambiguity flags.
  Real-rig gate: metarig, 706-bone generated Rigify, Seed-san VRM, and a real
  Mixamo export all map with **0 manual corrections** (`xtask/blender_verify.sh`).
- **One-image posing** — DWPose detection → 2.5D canonical solve → FK apply
  on any mapped rig, applied in-process by the add-on at **≤0.5° per bone**
  (worst measured: 0.026°, `make pose-verify`), with a viewport review
  overlay and one-click flip fixes. Honest number: on a 10-photo benchmark
  **0/10 are usable with zero review** under strict criteria (median
  confidence 0.66; legs verify, arms often need a one-click flip) — the
  review UI is the designed remedy, and the gap is decomposed in
  [docs/BENCHMARKS.md](docs/BENCHMARKS.md).
- **Video pipeline (Phase 2, closed on honest numbers)** — frame extraction
  (ffmpeg shell glue) → per-frame detection/solve with crash-safe resume and
  an honest failure ledger → **canonical actions** → keyframed retarget baked
  onto any mapped rig (2-frame bake verified on a real rig at 0.024°/frame)
  → foot contact detection with hysteresis → IK foot lock (the labeled
  synthetic walk, retargeted to **three real rigs** through the add-on's real
  bake: ankle drift within a plant drops **21×/12×/21×** on Rigify / VRM /
  Mixamo rigs; walk-in-place by design — no fabricated root motion) →
  motion denoise: hip stabilization + 1€ jitter pass (stabilization alone
  halves the breathing-induced stance slide on the synthetic gate) →
  **FBX/glTF export with a verified round-trip** (skeleton, animation, and
  pose fidelity re-measured after re-import at ≤2° — measured ~0.02°,
  `make export-verify`; VRMA has no builtin exporter and is honestly scoped
  in [docs/EXPORT.md](docs/EXPORT.md)). Honest limits: the GIFs below are the
  LABELED SYNTHETIC walk (generator cited; a licensing-clean real clip is
  still NEEDS-HUMAN), and the "dance + fight clips" gate is recorded
  NOT-met-with-real-clips in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).
- **MCP server** — stdio JSON-RPC 2.0 with declared tool schemas and
  **progress streaming** (`notifications/progress` with
  phase/0..1/message per `mcp/DESIGN.md`); `inspect_rig`, `policy_status`,
  `policy_check` and `animate_from_video`'s canonical half work today;
  `pose_from_image` answers a structured `not_implemented` until it's real.
  The **session bridge** (P3-5) connects a live Blender to an agent over
  127.0.0.1-only local sockets: `inspect_scene`, `apply_pose`, `bake_action`,
  `render_turntable` and `apply_style` execute inside the artist's Blender
  and return structured results (the six-action gate: `make session-verify`).
- **Style system + manga maker (Phase 4 through P4-7)** — toon material
  presets (anime/manga/western), GPv3 line art, screentone compositor
  graphs, and multi-camera panel page layouts — all as DATA files with
  deterministic builders, animated stability verified over a 360° orbit
  (`make style-verify`). Speech bubbles are per-panel page data (generated
  geometry + typeset text — never "hand-lettered"), pages export to
  deterministic PDF/EPUB (`rigpose export-pdf` / `export-epub`, pure
  stdlib, parse-back-verified), and animatic mode renders timed panel
  sequences from canonical pose actions (deterministic per-frame PNGs;
  the movie is shell-glued ffmpeg — labeled a TIMED ROUGH, never a final
  render). The real-pixel halves run on Blender 5.1 in CI and in the dev
  box alike (the D-014 bump; the honest SKIPPED degradation paths remain
  in the gate code for older Blenders).
- Content-policy module enforced in the core (SFW default; opt-in 18+ module
  with explicit confirmation; unconditional hard lines).

## Quickstart

```bash
pip install -e "core[dev]"
python xtask/export_fixture_rigs.py           # writes 5 example rigs
rigpose map out/fixture_rigs/mixamo.rig.json  # role mapping with confidences
rigpose policy status                          # SFW by default, documented
```

Image → pose (downloads two pinned ONNX models on the explicit `download`
command — the only network action the tool ever takes):

```bash
rigpose models download all
rigpose pose photo.jpg my_rig.rig.json --out payload.json
# then in Blender: the add-on's Apply Pose reads that payload in-process
```

With a local Blender install:

```bash
bash xtask/blender_verify.sh   # end-to-end: .blend → bridge → mapping → add-on registers
make pose-verify               # payload apply + review overlay + action bake on real rigs (needs models)
```

## Architecture

| Piece | Package | Role |
|---|---|---|
| `core/` | `riggermortis-core` | Pure-Python engine: canonical skeleton, bone-role mapping, pose solve, FK retarget, actions, contacts, cleanup, policy. No Blender dependency, no network. |
| `addon/` | Blender add-on | Artist UI (N-panel), viewport review, payload apply/bake. Thin — calls core. |
| `mcp/` | `riggermortis-mcp` | Agent tools over stdio/local socket. Thin — calls core. Structured policy refusals. |
| `xtask/` | — | Demo scene scripting, headless media rendering, benchmarks, CI glue. |
| `docs/` | — | Tutorials, benchmarks, policy, launch kit. |
| `STATE/` | — | Cross-session project state (tasks, decisions, progress). |

## Content policy (short version)

The default build is SFW. An opt-in 18+ module — off by default, enabled only
with explicit confirmation in preferences — permits adult content of fictional
adult characters, processed and rendered entirely locally. Hard lines are
enforced in the engine core and never toggle: no sexual content involving
minors, no explicit content of real identifiable people, nothing illegal. Full
text: [docs/POLICY.md](docs/POLICY.md).

## Honest limitations (current)

- One-image poses are review-ready, not zero-review: arm flips often need the
  one-click toggle (see the benchmark decomposition above). Deep forward kicks
  and hands held behind the back are known single-view ambiguities (documented
  solve limitations, not bugs).
- Anime/line-art detection is the weakest link: 3/10 of the anime benchmark
  images get no detection at all (DWPose trains on photoreal data). A fallback
  estimator is planned (P1-8a) — not implemented yet.
- The video pipeline bakes rotations, not root motion: the single-view solve
  is hip-anchored per frame, so fabricating world translation would be fake
  data. The IK foot lock makes contacts walk-in-place; hip stabilization
  removes anchor-frame noise only — a steady per-frame drift is
  low-frequency by construction and is deliberately left to the lock.
- All shipped animation media is the labeled SYNTHETIC walk: a
  licensing-clean real walking clip is still NEEDS-HUMAN
  (`out/video_smoke/SOURCES.md`), so the Phase-2 real-clip gate is recorded
  NOT-met-with-real-clips — the GIFs demonstrate retarget + lock, not
  real-clip quality.
- glTF-imported rigs (VRM/Mixamo) can carry synthesized bone tails that
  disagree with the skeleton — the walk pipeline repairs them when detected;
  add-on import normalization is a planned follow-up (D-015).
- Mapping assumes a humanoid-ish skeleton with roughly human proportions;
  quadrupeds are detected and flagged, not solved.
- `.blend` reading shells out to the user's own Blender via an edge script —
  the core library itself spawns no processes and opens no sockets.

## License

MIT — see [LICENSE](LICENSE).
