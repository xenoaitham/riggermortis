# PROGRESS (append-only)

- 2026-09-06T07:0xZ [S1] Researched prior art (DeepMotion/Rokoko pricing, Mixamo lock-in, blender-mcp scope, DWPose + anime gap) and name availability (riggermortis free on PyPI + Blender Extensions; unrelated Go repo on GitHub). → DECISIONS D-001/D-002.
- 2026-09-06T07:2xZ [S1] Scaffolded repo per ARCHITECTURE: core/ addon/ mcp/ xtask/ docs/ STATE/, README, LICENSE (MIT), Makefile, .gitignore.
- 2026-09-06T07:4xZ [S1] Core: linalg, errors, types (RigData+fingerprint), canonical skeleton (roles/ratios/bands/rest pose), names lexicon (Mixamo trap overrides, VRM/Rigify/Unreal tokenization), geometry features.
- 2026-09-06T08:0xZ [S1] Mapper v1: name pass + chain promotion + geometry fallback + quadruped detection + confidence/ambiguity reporting. Workspace security gate rejected subprocess in library code → core is now formally process-free; Blender interop moved to edge scripts. → DECISIONS D-003/D-005.
- 2026-09-06T08:2xZ [S1] Presets (fingerprint-keyed), policy module (SFW default, opt-in adult module with confirm, hard lines) + docs/POLICY.md, CLI (inspect/map/preset/policy, --json/--strict).
- 2026-09-06T08:4xZ [S1] Test suite: 5 synthetic rigs (Rigify, Mixamo w/ LeftLeg trap + Spine2, VRM, opaque b00.. geometry-only, ambiguous quadruped), determinism, presets, policy, CLI, I/O. 49 passed.
- 2026-09-06T08:5xZ [S1] Add-on skeleton (N-panel, inspect&map → rm_role_* props, policy prefs, honest Phase-1 stub), blender_manifest.toml for 4.2+, MCP design draft (tool contract + refusal shape), xtask (extract_blend.sh, blender_verify.sh, fixture exporter, render_demos stub).
- 2026-09-06T15:5xZ [S1] Fixed canonical parent side-qualification bug (upper_arm.L parent was "shoulder", not "shoulder.L"); hardened geometry pass against clobbering name-pass assignments; widened leg-chain band (quadruped front legs now detected); fixed bone-count expectations; ruff clean.
- 2026-09-06T16:0xZ [S1] Installed riggermortis-core (editable), 49/49 tests green, fixtures exported, CLI strict-maps the geometry-only rig 20/22 with core complete and 0 corrections.
- 2026-09-06T16:1xZ [S1] PHASE 0 BLENDER GATE PASS (Blender 4.0.2): headless .blend build → bridge extraction → strict mapping (19/22, core complete, conf 0.89–0.94) → add-on skeleton registers in Blender. Session bar met.
- 2026-09-06T16:2xZ [S1] STATE seeded: TASKS (69 tasks across Phases 0–7 w/ acceptance + media notes), DECISIONS D-001..D-006 + NEEDS-HUMAN queue, CONVENTIONS, SESSIONS, NEXT (P0-15 real rigs, P0-16 CI, P0-17 review API, then P1-1).
