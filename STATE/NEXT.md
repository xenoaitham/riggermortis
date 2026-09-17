# NEXT SESSION SHOULD …

1. **Phase 4 continues — P4-2 Grease Pencil line art pass** (the natural
   next rock after P4-1's shading): toon presets exist as data files and
   the material graph is deterministic + gate-published; line art on top of
   the banded fills is what makes renders read as anime/manga. Reuse
   `make style-verify`'s scene as the visual harness and extend it (line
   art layer over the sphere/proxy), same honest SKIPPED degradation rules.
2. **P4-3 screentone/halftone compositor node groups** (data-file presets
   like P4-1's) if P4-2 lands cleanly; the manga preset's docstring
   deliberately does NOT fake tones — it awaits this.
3. **Wire style-verify into CI** only if apt Blender 4.0.2 handles the
   probe's SKIPPED path sanely (it should — graph checks gate); one
   deliberate ci.yml commit per the D-014 style. The EEVEE-pixel half
   stays a local-gate property until CI has a GPU.
4. **P3-7 leftovers to watch:** the demo GIF is committed; if CI's
   session-verify flakes on the new bake/turntable actions, fix timing
   budgets in `xtask/session_verify.sh` — never fake results. The
   MCP-side `apply_style` tool is still DECLARED (schema v1); wiring it to
   the session bridge as an action kind is additive and tested when needed.

Watch out for:
- **ShaderNodeMix sockets:** access by IDENTIFIER (`Factor_Float`,
  `A_Color`, `B_Color`, `Result_Color`) via a scan — name lookup grabs the
  float socket first, and this Blender's bracket lookup does NOT resolve
  identifiers. Recorded in `addon/style.py::_socket`.
- **Material slots:** faces render SLOT 0 — clear/rebind slots when
  swapping the star material (the flat-grey-sphere class). Rebuilds must
  REMOVE-then-create the datablock (create-first suffixes `.001`).
- **P3-5 facts (unchanged):** `pose_bone.matrix` is ARMATURE-space (world
  needs `matrix_world`); glTF/VRM imports bake a skin pose into
  `matrix_basis`; Blender's Python sockets have no `__dict__`.
- **D-016 tail rule is locked** (absurd-ratio 10x + co-located skip);
  don't loosen the pose gate's calibrated sane-band bars ([0.15, 0.40] m
  lift) without re-measuring the certified rigs.
- **Blender 5.1.0 at `/home/potato/blender-5.1.0-linux-x64/` is the real
  install**; CI keeps apt 4.0.2 (D-014). EEVEE RENDERS HEADLESS on the dev
  box (verified this session) — workbench remains the CI-safe engine.
- The certified lock composition is stabilize → detect → lock WITHOUT the
  1€ pass (min_cutoff=None); keep media + gates on it.
- PATH can go stale after a box crash: conda BASE is the project env
  (`/home/potato/miniconda3/bin/python3`, `RIGPOSE=/home/potato/miniconda3/bin/rigpose`).
- Noqa rule: no stale `# noqa` (RUF100); used ones are fine. Root
  `ruff.toml` covers addon/ + mcp/ + xtask/; core keeps its pyproject.
- Windowed Blender GL is flaky on this box (~1-in-4): the UI screenshot
  re-capture stays best-effort (S10 attempt: miss, prior genuine capture
  kept — never staged).

Blocked / deferred (unchanged unless noted):
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks (MCP section added this session).
- P1-8a fallback estimator — parked (D-011/D-012).
- CI Blender bump — DECIDED (D-014).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
  instruments (FOOTLOCK/HIPSTAB/WALKRIGS) and now the agent demo re-run
  unchanged on a real clip.
