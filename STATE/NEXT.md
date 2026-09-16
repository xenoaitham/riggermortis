# NEXT SESSION SHOULD …

1. **P2-6 motion denoise** — hip stabilization (the root-motion-shaped gap;
   the honest path per D-008 — no fabricated translation, stabilize what the
   solve actually produces) + jitter pass tuning through the existing
   `condition_action` (1€ params). Wire through `load_action → condition →
   detect → lock_feet → bake` as the documented cleanup pipeline order and
   CI-test the composition.
2. **P2-7 export** — Blender actions are already written by the bake; add
   FBX/GLTF/VRMA via Blender edge scripts (glTF exporter is builtin; VRMA
   needs a writer — scope it honestly). CI-testable pieces through the
   payload/action contract only.
3. **P3-3 structured policy refusals through MCP** — shapes mirrored from
   `riggermortis.policy`; wire the gate + tests like any tool. P3-4
   progress streaming after.
4. Cheap wins while gates run:
   - **P2-8 prep**: source a licensing-clean REAL walking clip (SOURCES.md
     provenance rules; NEEDS-HUMAN if LO-owned) — the foot-lock gate
     currently publishes synthetic-labeled numbers by design (D-013); a real
     clip re-run makes them benchmark-grade.
   - A second windowed UI screenshot attempt on 5.1 (`xtask/ui_screenshot.sh`)
     is best-effort (flaky GL) — docs/media/ui_screenshot.png is committed +
     allowlisted, a genuine re-capture just replaces it.

Watch out for:
- **Blender 5.1.0 at `/home/potato/blender-5.1.0-linux-x64/` is the real
  install** (on PATH via ~/.bashrc + ~/.profile; or pass
  `BLENDER=…` explicitly). CI deliberately keeps apt 4.0.2 — decided and
  documented this session (D-014, ci.yml step name); bump only per D-014's
  trigger. After a box crash, `python3` may resolve to /usr/bin/python3 —
  the project env is conda BASE (`~/miniconda3/bin/python`, `rigpose`,
  ruff live there); pass `RIGPOSE=` to gate scripts if PATH is stale.
- **Addon bake foot lock**: `pb.matrix` reads are STALE once an action is
  assigned — world matrices are composed locally (W = P@(Mp⁻¹Mb)@B, see
  bake.py); bone rest LENGTH is `Bone.length`, not the matrix 3x3. Both
  bit us in S7; don't reintroduce.
- **noqa directives in files OUTSIDE core/**: ruff finds no repo config for
  `addon/`/`xtask/` paths from the repo root, so defaults apply and RUF100
  fires for known-but-disabled codes. S6 rule stands: no `# noqa: <code>`
  comments in addon/xtask files.
- Payload contract: v2 payloads MUST carry the `figures` list; canonical
  actions load ONLY through `payload.py` (D-009).
- Root motion stays unimplemented by design (D-008 hip anchoring); the foot
  lock's walk-in-place result IS the honest baseline — don't "fix" it by
  fabricating translation; P2-6 hip stabilization is the path.
- Windowed Blender under this box's GL segfaults on `space.show_region_ui`
  assignment from Python — do not reintroduce that in ui_screenshot.py.

Blocked / deferred (UPDATED 2026-09-16 S7):
- GitHub repo LIVE: https://github.com/xenoaitham/riggermortis — CI IS GREEN.
- Full Mimosa audit DONE, CLEAN (findingCount=0, seal sha256:7c594eb7...).
- Real Mixamo gate DONE via three.js Xbot (0 corrections; no Adobe login).
- Anime benchmark set at 10/10 (SOURCES.md); P1-8 re-decided at full n (D-012).
- CI Blender pin decided (D-014) — no longer open.
- PyPI: dist builds + twine PASSED; ONLY the upload needs LO's PyPI account
  (docs/PUBLISHING.md runbook). Blender Extensions needs LO's blender.org
  account (same runbook).
- P1-8a fallback estimator remains parked (D-011/D-012), needs a
  licensing-clean candidate.
