# Conventions

Locked decisions and style rules. Changes go through DECISIONS.md.

## Language / runtime
- Python ≥ 3.10 (Blender 4.0 bundles 3.11 — code must run there; the CI env is 3.13).
- `from __future__ import annotations` in every module; type hints everywhere.
- Core has **zero runtime dependencies** until Phase 1; numpy/onnxruntime only
  ever enter as optional extras (`[inference]`), never hard deps.
- **No `subprocess` in the core library** (workspace security gate enforces
  this; it is also the right architecture — core is embeddable). Blender
  process interop lives in `xtask/*.sh`, CI, and tests-by-shell.
- No bare `except:`; catch narrow, always re-raise as `RiggermortisError`
  subclasses with an actionable `hint`.

## Domain conventions
- Coordinates: meters, Blender world convention — Z up, character faces −Y,
  **character-left = +X**.
- Canonical role names are stable public API (`hips`, `spine`, `chest`,
  `neck`, `head`, `shoulder.L/R`, `upper_arm.L/R`, …). Never rename casually.
- Presets are keyed by rig fingerprint (sha256 of names+parents+positions).
- Determinism: same input + settings = same output. Every sort is keyed
  (score desc, then name asc); never iterate sets in output paths.
- Geometry-only confidence is capped at 0.75; ambiguity flag < 0.55.
- Refusal codes (`minor_content_prohibited`, …) are part of the public API —
  add-on reports and MCP errors must match `riggermortis.policy` exactly.

## Repo / workflow
- `STATE/` logs are **append-only** (PROGRESS) or top-of-file (NEXT).
- Claim a task in TASKS.md before working; never silently redo claimed work.
- Ruff (`E,F,W,I,UP,B`), line-length 100; `make lint test` before commits.
- Blender add-on identifiers: `RM_` class prefix, `rm.` operator prefix,
  `rm_` custom-property prefix (`rm_role_<role>` on armatures).
- Demo media is always generated headlessly (`xtask/render_demos.py`); stale
  or hand-made media must never be committed.
- Honesty rule: unfinished features say so in the UI (see add-on Phase 1
  operator), README claims cite a test, benchmark, or GIF.
