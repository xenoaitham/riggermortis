# NEXT SESSION SHOULD …

1. **P3-7 — E2E agent demo run** (the Phase-3 gate; P3-5 unblocked it):
   real MCP client drives a live Blender end-to-end — inspect → pose →
   animate → render turntable — with the **agent-driven turntable GIF** as
   the launch asset. The natural order: implement the declared
   `bake_action` session action (its honest `not_implemented` answer is the
   last gap between `animate_from_video`'s canonical half and a rig-space
   result — the add-on bake path already exists and is gate-certified),
   then a `render_turntable` action reusing `xtask/render_demos.py`'s
   staging (bone-proxy + FLAT shading + explicit world — see the S9
   lessons), then record the demo through the real stdio+loopback loop
   (`xtask/session_verify.sh` is the harness to extend). Launch GIF =
   pipeline-generated only, media-guard allowlist extension in the same
   commit as the media.
2. **P3-8 — MCP registry listing prep** if P3-7 lands (manifest metadata,
   honest capability list citing the golden schema).
3. Phase 4 opening (toon shaders, P4-1) if Phase 3's gate closes.

Watch out for:
- **P3-5 facts (this session):** `pose_bone.matrix` is ARMATURE-space —
  world needs `matrix_world` (metarig has identity transform so the old
  gates could not tell). glTF/VRM imports BAKE a skin pose into
  `matrix_basis` (66/67 non-identity on Xbot) — evaluated-vs-rest is only
  meaningful calibrated against sane rigs, never absolute. Blender's Python
  sockets have no `__dict__` — never stash attributes on a socket object
  (the session client carries its readline handle on itself).
- **D-016 tail rule is locked** (absurd-ratio 10x + co-located skip;
  addon/tails.py and xtask/walk_media.py in LOCKSTEP): sane rigs are
  bit-for-bit no-ops (metarig noop gate), the glTF garbage class (>= ~76x)
  is fully caught. Don't loosen the pose gate's calibrated sane-band bars
  ([0.15, 0.40] m lift) without re-measuring the certified rigs.
- **Blender 5.1.0 at `/home/potato/blender-5.1.0-linux-x64/` is the real
  install**; CI deliberately keeps apt 4.0.2 (D-014) — the session-verify
  gate now runs in CI on 4.0.2 (verified stable twice on 5.1.0; if it
  flakes in CI, time budgets are in the script — fix timing, never fake
  results).
- The certified lock composition is stabilize → detect → lock WITHOUT the
  1€ pass (min_cutoff=None); keep media + gates on it.
- PATH can go stale after a box crash: conda BASE is the project env
  (`/home/potato/miniconda3/bin/python3`, `RIGPOSE=/home/potato/miniconda3/bin/rigpose`).
- Noqa rule: no stale `# noqa` (RUF100); used ones are fine. The repo now
  has a ROOT `ruff.toml` (S10): the core standard (E,F,W,I,UP,B; E402/E501
  ignored repo-wide — bl_info/sys.path glue is structural) applies to
  addon/ + mcp/ + xtask/; core keeps its own pyproject config.
- Windowed Blender GL is flaky on this box (~1-in-4): the UI screenshot
  re-capture stays best-effort (S10 attempt: miss, prior genuine capture
  kept — never staged).

Blocked / deferred (unchanged unless noted):
- PyPI + Blender Extensions uploads — account-bound (LO);
  docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- CI Blender bump — DECIDED (D-014).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
  instruments (FOOTLOCK/HIPSTAB/WALKRIGS) re-run unchanged on a real clip.
