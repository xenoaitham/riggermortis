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

## Status: Phase 0 (core skeleton + rig profiler) — in progress

What exists **right now** (honest, tested):

- `riggermortis-core` PyPI package, zero runtime dependencies, pure Python
- Canonical skeleton (joint roles, hierarchy, proportion priors)
- Automatic bone-role mapping for Rigify / Mixamo / VRM / opaque custom rigs —
  name heuristics + geometry, per-role confidence, ambiguity flags, no silent
  failures
- Per-rig mapping presets keyed by rig fingerprint
- Content-policy module enforced in the core (SFW default; opt-in 18+ module
  with explicit confirmation; unconditional hard lines)
- `rigpose` CLI: `inspect`, `map`, `preset save/load`, `policy status`
- Blender add-on skeleton that registers an N-panel, maps the active armature
  onto canonical roles as custom properties, and keeps unbuilt features
  honestly labeled (image posing says "Phase 1" instead of pretending)
- Headless `.blend` → rig JSON bridge (`xtask/extract_blend.sh`)

What does **not** exist yet: image posing, video animation, MCP server, style
presets, manga maker, live mode. The [phase plan](STATE/TASKS.md) covers them;
no vaporware claims, no "coming soon" marketing.

## Quickstart

```bash
pip install -e core
python xtask/export_fixture_rigs.py          # writes 5 example rigs
rigpose map out/fixture_rigs/mixamo.rig.json  # role mapping with confidences
rigpose policy status                         # SFW by default, documented
```

With a local Blender install:

```bash
bash xtask/blender_verify.sh   # end-to-end: .blend → bridge → mapping → add-on registers
```

## Architecture

| Piece | Package | Role |
|---|---|---|
| `core/` | `riggermortis-core` | Pure-Python engine: canonical skeleton, bone-role mapping, retargeting, cleanup, policy. No Blender dependency, no network. |
| `addon/` | Blender add-on | Artist UI (N-panel), viewport review, style presets, manga maker. Thin — calls core. |
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

- Mapping assumes a humanoid-ish skeleton with roughly human proportions;
  quadrupeds are detected and flagged, not solved (by design: they surface as
  review items, ≤2 corrections).
- `.blend` reading shells out to the user's own Blender via an edge script —
  the core library itself spawns no processes and opens no sockets.
- Image → pose, video → animation, live mode: not built yet. See STATE/TASKS.md.

## License

MIT — see [LICENSE](LICENSE).
