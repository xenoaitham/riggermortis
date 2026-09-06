# Benchmarks

Every performance/quality claim in the README will have a number here, with
the harness that produced it. No claim without a benchmark.

## Phase 0 — rig mapping gate

Five rigs, headless, deterministic. "Corrections" = roles the review UI would
need a human to reassign; the gate allows ≤2 per rig.

| Rig family | Source | Core roles mapped | Ambiguities flagged | Corrections needed | Status |
|---|---|---|---|---|---|
| Rigify-style | synthetic (tests/rigs.py) | 23/23 mapped, core complete | 0 | 0 | pending CI run |
| Mixamo-style | synthetic, incl. LeftLeg trap + Spine2 | core complete, Spine2 honestly unmapped | 0 | 0 | pending CI run |
| VRM (J_Bip) | synthetic | core complete | 0 | 0 | pending CI run |
| Opaque custom (b00..) | synthetic, geometry-only mapping | core complete | review items flagged | 0–1 | pending CI run |
| Quadruped | synthetic, deliberately ambiguous | torso/head mapped, legs flagged | ≥2 (front-leg remap) | ≤2 | pending CI run |

(Filled automatically by CI once the benchmark harness lands; the synthetic
suite backing this table runs on every commit via `make test`.)

## Planned (from the mission gates)

- **Phase 1:** 20-image benchmark (10 photo, 10 anime) — ≥90% usable-straight-away poses.
- **Phase 2:** dance + fight clips on 3 rigs; published foot-slide metric.
- **Phase 5:** live-mode latency budget (<100 ms, mid laptop).
- **Always:** network-audit test (zero outbound connections in default use).
