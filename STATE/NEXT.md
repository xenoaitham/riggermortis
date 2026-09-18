# NEXT SESSION SHOULD …

1. **P4-4 multi-camera panel system + layout presets** (manga RTL, western
   LTR): the style system has all three layers now (P4-1 materials, P4-2
   line art, P4-3 tones — data files + deterministic builders), so panels
   are the next rock on the road to P4-8's 6-page manga. DESIGN FIRST in
   docs/STYLE.md (panel layout as DATA like everything else), probe
   anything Blender-uncertain before building.
2. **Styled turntable re-check (the honest-scope follow-up)**: P4-2/P4-3
   are verified SINGLE-FRAME; re-run the agent-demo turntable with a styled
   character (materials + lineart + tones) under an ORBITING camera and
   only then claim animated line art / tone stability. If the LineArt
   modifier (or the tone view layer) misbehaves per frame, record it as a
   documented limitation — never fake a styled GIF.
3. **`apply_style` session action** (cheap win, now justified): the MCP
   tool is DECLARED (schema v1) and the style builder API is stable
   (build_toon_material / build_lineart / build_screentones). Wiring it as
   a 5th session action kind is additive: kinds 4→5 both sides, golden pin
   update same-commit, session gate extension.
4. **Doc cross-checks**: docs/STYLE.md is new — keep it in sync as the
   style system grows; mcp/README.md + AGENT_DEMO.md unchanged by S12 but
   re-verify when apply_style lands; BENCHMARKS.md untouched (style work is
   gate-verified, not benchmark-numbered).

Watch out for:
- **5.1 API breaks the probes keep catching** (do not reintroduce the old
  ways): compositor graph = `scene.compositing_node_group` (node_tree is
  GONE); unified ShaderNode classes inside compositor trees but NO combine
  node; NO UV pass — coordinates come from the rm_tones_uv view layer;
  GPv3 LineArt only works through ops LINEART_OBJECT + renames; created
  objects must be captured by DATABLOCK DIFF (context.object lies after a
  render); the compositor group needs EXACTLY ONE Group Output node,
  created after the interface socket (a stale first one renders black);
  SUBTRACT operand order in the tone chain is load-bearing.
- **P4-5/P4-6 prerequisites**: speech bubbles (P4-5) will likely reuse the
  GPv3 surface (the add-operator enum EMPTY/STROKE paths) — the P4-2
  probe's layer/frames/drawing API notes apply.
- **ShaderNodeMix sockets**: by IDENTIFIER via the scan pattern
  (Factor_Float/A_Color/B_Color/Result_Color) — works in material AND
  compositor trees.
- **Gates' env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/blender,
  RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/miniconda3/
  bin/python3 — otherwise they 127 (hit twice this session).
- **D-016 tail rule is locked**; certified lock composition is stabilize →
  detect → lock WITHOUT the 1€ pass; don't tune against fixtures (D-008).
- **Style gate in CI**: the P4-2/P4-3 halves legitimately report SKIPPED on
  apt 4.0.2 — do NOT "fix" CI by loosening the dev-box PASS expectations;
  the local gate must keep showing LINEART: PASS / TONES GRAPH: PASS.
- Windowed Blender GL is flaky on this box (~1-in-4): the UI screenshot
  re-capture stays best-effort (S10/S12 precedent: misses are fine, never
  staged).

Blocked / deferred (unchanged unless noted):
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- CI Blender bump — DECIDED (D-014); note the style gate's P4-2/P4-3 halves
  are the first features that NEED a 5.x-class Blender: if Phase 4 keeps
  landing 5.1-only capabilities, the revisit trigger is approaching.
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
  instruments and the agent demo re-run unchanged on a real clip.
