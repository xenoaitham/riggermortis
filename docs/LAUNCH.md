# Launch drafts (P7-3)

Drafts, not publications. The submission steps themselves are account-bound
([docs/PUBLISHING.md](PUBLISHING.md) has the runbooks). Rules every draft
below already follows — keep them true if you edit:

- **Every claim cites its test, gate, number, or GIF.** Numbers live in
  [docs/BENCHMARKS.md](BENCHMARKS.md); where a generator owns a block, we
  link, never re-transcribe.
- **The live half is labeled, verbatim**: measured on replayed frames;
  real-camera number pending. The Phase-5 <100 ms mid-laptop gate stays
  UNCLAIMED in launch copy too.
- **No promised-but-unfilmed footage.** The 60s script cuts only from
  material the pipeline generates today.
- A draft that needs a number the repo hasn't published states the
  number's absence instead of rounding up.

---

## 1. Show HN

**Title:** Show HN: Riggermortis – local image/video-to-pose engine for Blender (add-on + MCP server)

**Author's first comment (the post body):**

Hi HN — we built Riggermortis: a local, free, rig-agnostic posing &
animation engine for Blender. Two frontends: a Blender add-on for artists,
and an MCP server so coding agents can drive a real Blender. Drop a rigged
model + a reference image → the pose is applied to your rig. Drop a video →
it's retargeted into a foot-slide-cleaned animation. It also renders toon
styles and lays out wordless manga pages. No cloud, no accounts, no
uploads — ever. MIT: https://github.com/xenoaitham/riggermortis

Why: cloud mocap (DeepMotion, Rokoko, Mixamo) either uploads your footage
or locks the rig. The interesting technical bet here is the **rig-agnostic
middle layer** — a canonical 22-role skeleton every input and output goes
through — so "any rig" is the architecture, not an import filter.

What works today, with receipts:

- **Any-rig mapping**: Rigify metarig, a 706-bone generated Rigify rig, a
  VRM, and a real Mixamo export all map with 0 manual corrections — name
  heuristics + a geometry fallback, with per-role confidence and ambiguity
  flags (gate: `xtask/blender_verify.sh`, table: docs/BENCHMARKS.md Phase 0).
- **One-image posing**: DWPose → a 2.5D canonical solve → FK apply, applied
  in-process at ≤0.5°/bone (worst measured 0.026°, gate: `make
  pose-verify`). Honest number: on a 10-photo benchmark, 0/10 are usable
  with ZERO review under strict criteria — legs verify, arms often need a
  one-click flip fix in the review overlay (docs/BENCHMARKS.md, POSES
  block). It's review-ready, not magic, and we publish the 0/10 rather
  than redefine the metric.
- **Video → animation**: per-frame detection with crash-safe resume →
  canonical action → retarget + IK foot lock. One synthetic walk retargeted
  to three real rigs drops in-plant ankle drift 21.7×/12.0×/21.1×
  (Rigify/VRM/Mixamo; labeled SYNTHETIC — the licensing-clean real clip is
  still being sourced; docs/BENCHMARKS.md, WALKRIGS block). Export
  round-trips FBX/glTF at ≤0.02° measured error (gate: `make export-verify`).
- **Agents**: the MCP server (stdio JSON-RPC, 9 tools) drives a real
  Blender through a 127.0.0.1-only session bridge — the committed demo GIF
  is a scripted agent inspecting, posing, animating, baking, and rendering
  a turntable on a live Blender (docs/AGENT_DEMO.md, transcript committed).
  Claude Desktop/Cursor configs in `mcp/examples/`.
- **Toon + manga**: deterministic toon shaders/line art/screentones as data
  files, page layout, bubbles, PDF/EPUB export — closed out with a 6-page
  wordless manga the pipeline renders end-to-end (docs/manga/).

The local-only claim is enforced, not vibes: a CI test runs an audit hook
over the whole default-use path and asserts zero socket events
(`core/tests/test_network_audit.py`).

What's NOT done, plainly: single-view solve limits (deep kicks, hands
behind the back are documented ambiguities); anime/line-art detection is
the weakest link (3/10 anime benchmark images get no detection at all — a
fallback estimator is planned, not built); all shipped animation media is
synthetic-labeled; and the live webcam-puppeteering mode is shipped and
gate-verified **on replayed frames only** — measured on replayed frames;
real-camera number pending (the capture device on our dev box has been
silent; the recorded live demo is the last Phase-5 piece).

Ask: roast the architecture, the honesty policy, or the MCP angle.
Blender 4.2+/5.x, Python ≥3.10, everything on-device.

---

## 2. BlenderNation blurb (~200 words, news tone)

**Riggermortis: local, rig-agnostic posing from images and video**

Riggermortis is a free, MIT-licensed Blender add-on (plus an MCP server for
agent control) that applies poses from a single reference image — photo or
anime art — to any mapped rig, and turns video clips into retargeted
animation with IK-locked feet. Everything runs locally: models are
checksum-pinned one-time downloads, and a CI test asserts the default
pipeline makes zero network connections.

Under the hood, inputs and outputs pass through a canonical 22-role
skeleton, which is how Rigify, Mixamo, and VRM rigs all map without manual
corrections (benchmark table on the repo). Poses apply at ≤0.5° per bone,
verified by the pipeline's own gate before any media is rendered; FBX/glTF
exports round-trip with sub-0.02° measured error. A toon style system
(anime/manga/western presets, line art, screentones) assembles pages,
bubbles, and PDF/EPUB exports — the repo ships a 6-page wordless manga
rendered entirely by its build script.

The project publishes its failures next to its wins: the pose benchmark
currently reads 0/10 "usable with zero review" (arms need the built-in
one-click flip fixes), animation media is synthetic-labeled pending a
licensing-clean real clip, and the live puppeteering mode is verified on
replayed streams — real-camera numbers pending. Docs, benchmarks, and
reproduction commands: https://github.com/xenoaitham/riggermortis

---

## 3. r/blender post

**Title:** I'm building a free, local "any image → any rig" posing engine for Blender — it also retargets video and renders manga pages. Here's the honest build log.

Hey r/blender. For the last few weeks I've been building **Riggermortis**
(MIT, free, everything on your machine — no uploads, ever), and I want to
show it with the receipts attached, because the honest parts are the
interesting parts.

**What it does today:**

- Drop a reference image (photo or anime art) next to an already-rigged
  character → the pose is applied to YOUR rig — Rigify, Mixamo exports,
  VRM, weird custom stuff. The mapping benchmark: 4 real rigs, 0 manual
  corrections ([BENCHMARKS.md](https://github.com/xenoaitham/riggermortis/blob/main/docs/BENCHMARKS.md)).
  GIF: the pipeline posing a Rigify metarig from a photo, refusing to
  render anything it can't verify to ≤0.5° per bone first
  ([boom.gif](https://github.com/xenoaitham/riggermortis/blob/main/docs/media/boom.gif)).
- Drop a video → it becomes an animation on your rig, with foot contacts
  detected and IK-locked so feet don't skate (lock ratios 21.7×/12.0×/21.1×
  across the three test rigs). Honest label: the shipped walk media is a
  synthetic test motion, because I won't ship a licensing-dirty real clip —
  the GIFs prove retarget + lock, not real-clip quality.
- FBX/glTF export round-trips verified at ≤0.02° error (gate re-imports and
  re-measures — the export gate caught a real bug once and I fixed the
  probe, not the bar).
- A toon/manga system: three style presets as data files, line art,
  screentones, panel layouts, speech bubbles, and PDF/EPUB export. The
  close-out is a 6-page wordless manga rendered start-to-finish by one
  build script ([docs/manga/](https://github.com/xenoaitham/riggermortis/tree/main/docs/manga)).

**The honest limitations** (also in the README): single-image poses are
review-ready, not zero-review — arm bends often need the one-click flip
toggle in the overlay (the benchmark literally reads 0/10 under the strict
"no review" criterion, and I publish that); anime/line-art detection misses
entirely on 3/10 of the anime test set (planned fix, not built yet); no
root motion — it's walk-in-place by design because fabricating world
translation from a single view would be fake data; and the webcam puppet
mode is shipped and gate-tested on replayed streams — the real-camera
latency number is still pending because my capture device won't cooperate.

**Try it:** `pip install -e "core[inference]"`, `rigpose models download
all` (two checksum-pinned models — the only network call the tool ever
makes), `rigpose pose photo.jpg my_rig.rig.json --out payload.json`, then
Apply Pose in the add-on. Repo:
https://github.com/xenoaitham/riggermortis — every number on the README
links the gate that produced it. Feedback wanted, especially: which rig
broke, and what should the video pipeline do that it doesn't?

---

## 4. Tweet thread (7 tweets)

**1/** We built a free, local, rig-agnostic posing engine for Blender.
Image → pose on YOUR rig. Video → retargeted animation. Manga pages out the
other end. No cloud, no uploads — a CI test proves zero network calls in
default use. MIT. 🧵
(claim receipts: `core/tests/test_network_audit.py`)

**2/** The trick is a canonical 22-role skeleton in the middle. Rigify
metarig, 706-bone generated Rigify, VRM, and a real Mixamo export all map
to it with ZERO manual corrections. Name heuristics + geometry fallback,
per-role confidence.
(receipts: docs/BENCHMARKS.md Phase-0 real-rig gate, `xtask/blender_verify.sh`)

**3/** Poses apply at ≤0.5° per bone — the pipeline self-checks before it
renders anything. And we publish the bad number too: on a strict 10-photo
benchmark, 0/10 poses need ZERO review. Arms often want the one-click flip
fix in the overlay. Review-ready, not magic.
(receipts: `make pose-verify`, docs/BENCHMARKS.md POSES block)

**4/** Video in → animation out, feet IK-locked so they don't skate:
in-plant ankle drift drops 21.7×/12.0×/21.1× across our three test rigs
(Rigify / VRM / Mixamo). Labeled honestly: synthetic test walk — the
licensing-clean real clip is still being sourced.
(receipts: `make walk-gifs`, docs/BENCHMARKS.md WALKRIGS block, GIF:
docs/media/walk_3rigs.gif)

**5/** For the agent people: it ships an MCP server. 9 tools over stdio,
zero sockets by default. A scripted agent drove a real Blender end to end —
inspect → pose from a photo → animate → bake → turntable — and the
transcript is committed next to the GIF.
(receipts: docs/AGENT_DEMO.md, `make session-verify`, GIF:
docs/media/agent_turntable.gif)

**6/** Bonus engine: toon styles (anime/manga/western) as data files, line
art, screentones, page layout, bubbles, PDF/EPUB. The Phase-4 close-out is
a 6-page wordless manga rendered by one build script.
(receipts: `make style-verify`, docs/manga/, GIF: hero_3styles.png)

**7/** What's not done, on the record: single-view solve has documented
limits (deep kicks, hands behind back); anime/line-art detection misses
3/10 of that test set (fallback planned, not built); and live webcam
puppeteering is gate-verified on replayed frames only — measured on
replayed frames; real-camera number pending. ⭐ if honesty is your kink:
https://github.com/xenoaitham/riggermortis

---

## 5. Sixty-second video script

**Cut-from rule honored:** every shot below maps to footage the pipeline
generates today (committed media, or gate renders the commands regenerate
deterministically). There is NO live-camera footage and the script does not
pretend otherwise — the live mode appears as a screen-recorded CLI/panel
segment ONLY if you record it after P5-4 ships; as drafted, it's covered by
the replay-gate readout shot (shot 6), which exists.

| # | time | VO (read by author) | footage (source of record) |
|---|---|---|---|
| 1 | 0:00–0:06 | "This is a rigged character in Blender. This is a photo of a person." | Title card over `docs/media/ui_screenshot.png` (genuine windowed capture of posed metarig + review overlay) |
| 2 | 0:06–0:14 | "Riggermortis turns the photo into a pose — on your rig. Rigify, Mixamo exports, VRM: zero manual corrections in the mapping benchmark." | `docs/media/boom.gif` (rest → posed turntable; the pipeline's ≤0.5° self-check gates this shot) |
| 3 | 0:14–0:24 | "It's honest about what it can't do: single-view solve has documented limits, and the published benchmark reads zero-out-of-ten poses needing no review. Arms get a one-click flip fix instead of a shrug." | `docs/media/ui_screenshot.png` + a slow zoom on one flip-toggle region of the overlay (same capture; no new staging) |
| 4 | 0:24–0:34 | "Feed it video and it retargets with feet locked — ankle drift inside a plant drops over twenty-fold on the test rigs. Labeled honestly: this walk is synthetic test motion." | `docs/media/walk_3rigs.gif`, then `docs/media/walk_lock_metarig.gif` (raw | locked side-by-side) |
| 5 | 0:34–0:44 | "It ships an MCP server, so your coding agent drives a real Blender: inspect, pose, animate, bake, render — the transcript is committed next to the demo." | `docs/media/agent_turntable.gif` (the scripted-agent turntable; SYNTHETIC chip visible on purpose) |
| 6 | 0:44–0:52 | "And everything is local — the CI suite runs an audit hook that proves zero network calls in default use. Even the live puppeteering mode ships gate-tested, on replayed frames; the real-camera number is still pending, and we say so." | Terminal capture of `make gate` output ending in `PHASE 0 GATE: PASS` (regenerable: `make gate`); overlay a lower-third: "live mode: measured on replayed frames; real-camera number pending" |
| 7 | 0:52–1:00 | "It renders toon styles and assembles manga pages — this whole short came out of the same pipeline. Free, MIT, link in the description." | `docs/manga/hero_3styles.png` → quick 3-page flip of `docs/manga/page_01..03.png` → end card (repo URL) |

**Production notes:**

- Every asset is regenerable from the repo: `bash xtask/render_boom.sh`,
  `make walk-gifs`, `make agent-demo`, `bash xtask/manga_build.sh`,
  `make gate`. Nothing hand-animated, nothing staged.
- The zoom in shot 3 is a crop of the committed capture, not a re-render.
- If/when P5-4 (the recorded live demo) ships, add an 8th shot (0:52–0:56
  steal from shot 7) showing the real camera → posed rig with the measured
  capture→apply number on screen — until then the thread/post copy keeps
  the live half labeled exactly as above.
- Music/sfx: author's choice, not part of the pipeline's claim surface.
