# Style-LoRA training — a documented recipe, not a feature (P6-6)

This page is **documentation only**. Nothing in this repository trains a
model, downloads training tooling, or reads/writes LoRA artifacts: the core
stays dependency-free and process-free (D-003), the add-on and MCP server
never grow a training path, and CI has no training job — `ci.yml` runs ruff,
pytest, the Blender gate, and the media guard, and this page adds nothing to
it. There is no `[training]` extra, no weights, no dataset, no code. If you
`grep -ri lora` the sources after reading this, you will find exactly one
hit: this file.

The page exists because the style system's most common follow-up question is
"how do I get *my* style instead of the three presets?" — and the honest
answer is: the procedural style system ([docs/STYLE.md](STYLE.md)) covers
output stylization deterministically, and a diffusion LoRA is the external,
GPU-bound answer people reach for on the *input* side. Pretending that is a
checkbox would be a false claim; documenting what it actually costs is the
useful thing.

## Where a LoRA would sit in this engine

**On the input side only.** riggermortis consumes reference images
(`rigpose pose`) and styles its own renders procedurally (banded toon
materials, line art, screentones — no ML anywhere in the render path). The
engine never needs a LoRA. The one sensible use is generating additional
pose-reference images in a consistent personal style, to feed the existing
one-image posing path. Such images are consumed like any other image: same
detection, same solve, same review loop.

## The honest cost (order-of-magnitude, community-reported)

The numbers below are the publicly reported experience ranges for the
standard community LoRA toolchains on consumer hardware. **None of them were
measured in this repo** — no training was ever run for this project, on any
machine, and this page deliberately does not cite fake precision:

| base model class | typical VRAM | wall-clock, small LoRA (~20–50 images, 1–2k steps) |
|---|---|---|
| SD 1.5-class (512 px) | ~6–8 GB | ~0.5–1.5 h on a mid GPU (RTX 3060-class) |
| SDXL-class (1024 px) | ~12–20 GB (12 GB is tight; gradient checkpointing + 8-bit optimizers are the usual squeeze) | ~2–6 h |
| Flux-class (~12 B) | ~24 GB comfortable; offload tricks reach ~16 GB slowly | half a day and up |
| CPU-only | — | **not viable**: days-to-weeks per run; do not attempt |

**This box's reality, for calibration:** the pinned DWPose detector runs
CPU-only (`onnxruntime` 1.25.1, CPU provider — an RTX 3060 exists here but no
GPU ORT provider is installed, which is exactly the honest mid-laptop
baseline the benchmarks cite). No PyTorch/CUDA training stack is installed,
and installing one is a step this repo never performs for you. If your
machine matches this class, training is the one part of the wider ecosystem
that genuinely does not fit on it — that is a fact about the workload, not a
limitation of this engine.

## What riggermortis itself never does

- **No weights bundled or fetched.** The model manager downloads exactly two
  checksum-pinned DWPose models, once, on an explicit user command — that
  remains the ONLY network action any tool in this repo takes. No diffusion
  base model is pinned, listed, or downloadable through it.
- **No training code in `core/`, `addon/`, or `mcp/`.** The core library
  stays dependency-free and process-free (D-003); a trainer would violate
  both boundaries, so it never enters.
- **No CI training job.** CI exercises the engine gates; it has no GPU and
  this page requests none. Media generation in CI is deterministic
  pipeline-render, not ML.
- **No optional extra.** `core[inference]` (numpy + onnxruntime + pillow)
  stays the only extra; the dependency surface does not grow.

## Licensing and policy, soberly

- Train only on images you have the rights to use. Whether a LoRA trained on
  a living artist's work is acceptable is a licensing and ethics question
  this project takes no position on and ships no tooling for; the trained
  artifact is yours and so is the responsibility.
- [docs/POLICY.md](POLICY.md)'s lines apply to **inputs as much as
  outputs**: no real, identifiable people in explicit content; nothing
  involving minors, regardless of framing. A style-LoRA does not move those
  lines and nothing in this repo helps you move them.
- Nothing a third-party LoRA produces is shipped, hosted, linked, or
  endorsed by this repository.

## If you still want it — the shape of the recipe

Deliberately no tool names pinned to versions this repo does not test; the
steps are the stable ones every current toolchain shares:

1. Pick a base diffusion model you have a license to use, that runs on the
   VRAM you actually have (see the table above — the base model, not the
   LoRA, sets the hardware bar).
2. Assemble 20–50 images in the target style that you have rights to; consistent
   framing and resolution beat quantity.
3. Caption them (or train uncaptioned for a pure-style adapter); keep a
   small held-out set for eyeballing drift.
4. Train a low-rank adapter (rank 8–32 is the usual band) with the standard
   community tooling; expect the wall-clock in the table.
5. Export a single adapter file (safetensors), use it in any image generator
   you run locally, and feed the resulting images to `rigpose pose` like any
   photo.

**Detection-quality honesty, up front:** generated reference images land in
the same detection reality already measured in
[docs/BENCHMARKS.md](BENCHMARKS.md) — anime-style imagery medians 0.50
confidence vs 0.66 for photos, and no-person detection failures happen on
line-art. A LoRA makes your references *consistent*; it does not make the
detector *better*. The review loop (confidence bands, one-click flips)
exists precisely because of this.

## Reproduce (the "nothing", provable)

```bash
# no training dependency anywhere in the package metadata
grep -n "torch\|diffusers\|peft\|accelerate" core/pyproject.toml   # no hits

# no training job in CI
grep -n "train\|gpu\|torch" .github/workflows/ci.yml               # no hits

# the model manager's complete, pinned universe — two detector models
rigpose models list                                                # DWPose yolox_l + dw-ll_ucoco_384, sha256-pinned

# the only LoRA in the repo is this page
grep -ril "lora" --include="*.py" --include="*.toml" --include="*.yml" .   # no hits
```
