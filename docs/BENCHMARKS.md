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

### Real-rig gate (P0-15, session 2, local Blender 4.0.2 headless)

Proved on real rigs, not just synthetic fixtures. "Corrections" = reassignments
a human must make in the review UI; review-confirm flags are listed separately.

| Rig | Source + license | Bones | Roles | Core | Corrections | Flags |
|---|---|---|---|---|---|---|
| Rigify human meta-rig | Blender 4.0.2 factory metarig add-on (bundled) | 159 | 21 | complete | 0 | 1 review-confirm (structural hips) |
| Rigify generated rig | same metarig via `rigify_generate` | 706 (220 ctl / 160 DEF- / 167 MCH- / 159 ORG-) | 22/22 | complete | 0 | 0 |
| VRM 1.0 sample | Seed-san by VirtualCast, Inc. — [VRM Public License 1.0](https://vrm.dev/en/licenses/1.0/index); kept unmodified in git-ignored `out/` | 55 | 21 | complete | 0 | 0 |
| Mixamo export | not run — needs an Adobe login (NEEDS-HUMAN, DECISIONS queue). The synthetic Mixamo-style fixture (incl. the `LeftLeg`-is-a-shin trap) covers the naming traps meanwhile | — | — | — | — | — |

Reproduce (all local, no uploads):

```bash
blender -b --python xtask/build_rigify_rigs.py          # writes out/real_rigs/*.blend
bash xtask/extract_blend.sh out/real_rigs/metarig.blend out/real_rigs/metarig.rig.json
bash xtask/extract_blend.sh out/real_rigs/rigify_generated.blend out/real_rigs/rigify_generated.rig.json rig
blender -b --python xtask/import_and_extract.py -- out/real_rigs/Seed-san.vrm out/real_rigs/seedsan.rig.json
rigpose map out/real_rigs/metarig.rig.json --strict
rigpose map out/real_rigs/rigify_generated.rig.json --strict
rigpose map out/real_rigs/seedsan.rig.json --strict
```

Mapping fixes this gate forced (details in STATE/DECISIONS.md D-007): hips
flank rule (`pelvis.L` ≠ hips), structural-fork hips pre-pass with a
both-sides discriminator, prefix-duplicate barring from `spine`, pose-target
prefix preference (control > DEF- > ORG-), `MCH-`/`parent` skip tokens,
duplicate-limb-view filtering, review-feed completeness.

## Planned (from the mission gates)

- **Phase 1:** 20-image benchmark (10 photo, 10 anime) — ≥90% usable-straight-away poses.
- **Phase 2:** dance + fight clips on 3 rigs; published foot-slide metric.
- **Phase 5:** live-mode latency budget (<100 ms, mid laptop).
- **Always:** network-audit test (zero outbound connections in default use).
