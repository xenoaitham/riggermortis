# NEXT SESSION SHOULD …

1. **P2-5 IK foot lock + ground-plane fit** — the pieces are staged: contact
   intervals attach to the action (`contacts.attach_contacts`), the bake
   lives in `addon/bake.py`, and the gate metric exists
   (`contacts.foot_slide`; gate = ≥5× improvement, baseline instrument
   verified). Lock each ankle's in-contact frames (per-interval position
   hold or IK to a ground projection), re-measure `foot_slide` before/after
   on a real clip, publish both numbers in docs/BENCHMARKS.md.
2. **P2-6 motion denoise** (hip stabilization, jitter pass) — or P2-7 export
   (Blender actions done; FBX/GLTF/VRMA via Blender where needed).
3. **P3-3 structured policy refusals through MCP** — refusal shapes already
   designed in mcp/DESIGN.md and mirrored by `riggermortis.policy`; wire the
   gate + tests like any tool. P3-4 progress streaming is next after that.
4. Cheap wins while gates run:
   - a second windowed UI screenshot attempt (`xtask/ui_screenshot.sh`) is
     best-effort (flaky GL, ~1-in-4) — docs/media/ui_screenshot.png is now
     committed + allowlisted, so a re-capture just replaces it (media-guard
     pins the exact filename).
   - P1-8a fallback estimator (anime detector gap: 3/10 no-person at n=10)
     remains the Phase-1 follow-up when a licensing-clean candidate exists.

Watch out for:
- **Blender location changed (LO, 2026-09-16)**: the real install is
  **5.1.0 at `/home/potato/blender-5.1.0-linux-x64/`** — on PATH via
  ~/.bashrc + ~/.profile, or pass `BLENDER=/home/potato/blender-5.1.0-linux-x64/blender`
  explicitly (both gate scripts honor it). The old /usr/bin/blender 4.0.2 is
  broken on this box. Both Blender gates were RE-VERIFIED against 5.1.0 in
  S6b (Phase 0 + pose-apply, identical numbers). CI still runs apt 4.0.2 on
  ubuntu-24.04 — decide next session whether to bump CI to a 5.1 official
  download (ci.yml edit) or keep 4.0.2 as the CI pin.
- **noqa directives in files OUTSIDE core/**: ruff finds no repo config for
  `addon/`/`xtask/` paths from the repo root, so defaults apply and ruff
  0.16 validates noqa codes there (RUF100 fires for known-but-disabled
  codes like PLC0415). core/src files resolve core/pyproject.toml and are
  exempt. S6 rule: no `# noqa: <code>` comments in addon/xtask files.
- Payload contract: v2 payloads MUST carry the `figures` list — video.py
  writer was fixed in S6; `figure_entries` raises otherwise (the old
  git-ignored jobs under out/video_smoke/{job,pjob} predate the fix and
  fail honestly with "unreadable payload" notes; regenerate).
- `make pose-verify` needs local assets (out/real_rigs/*, out/payloads/*,
  out/benchmark/images/*) — all present as of S6; regenerate per
  docs/BENCHMARKS.md reproduce blocks if you switch machines.
- Root motion stays unimplemented by design (D-008 hip anchoring) — don't
  "fix" the bake by fabricating translation; P2-6 hip stabilization is the
  honest path.
- Windowed Blender under this box's GL segfaults on `space.show_region_ui`
  assignment from Python — do not reintroduce that in ui_screenshot.py.

Blocked / deferred (UPDATED 2026-09-15 NEEDS-HUMAN-clearing run):
- GitHub repo LIVE: https://github.com/xenoaitham/riggermortis — CI IS GREEN
  (first-ever run + fixes: ruff 0.16 semantics, env-coupled onnxruntime test).
- Full Mimosa audit DONE, CLEAN (findingCount=0, seal sha256:7c594eb7...).
- Real Mixamo gate DONE via three.js Xbot (0 corrections; no Adobe login).
- Anime benchmark set at 10/10 (SOURCES.md); P1-8 re-decided at full n (D-012).
- PyPI: dist builds + twine PASSED; ONLY the upload needs LO's PyPI account
  (docs/PUBLISHING.md runbook). Blender Extensions needs LO's blender.org
  account (same runbook).
