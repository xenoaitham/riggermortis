# NEXT SESSION SHOULD …

1. **P2-8 — clips × rigs + side-by-side GIFs (closes Phase 2)** — the last
   Phase 2 item. Instruments are READY: `xtask/foot_lock_gate.py` +
   `xtask/hip_stab_gate.py` publish the metric harnesses a real clip
   re-runs; the full pipeline is wired end to end
   (`load_action → condition_action(hip_stabilize=…) → detect_contacts →
   lock_feet → bake(contacts=…) → export FBX/glTF via
   `make export-verify`'s path). NEEDS-HUMAN blocks the REAL-clip half: a
   licensing-clean walking clip (search exhausted S8 — see
   out/video_smoke/SOURCES.md). Two honest paths:
   - LO drops a clip (LO-owned is fine — provenance = ownership statement);
     then: extract → pose-video job → the S8 pipeline → REAL numbers in the
     gate blocks + the side-by-side GIFs (P2-8's media deliverable).
   - OR scope P2-8 on the synthetic instruments explicitly labeled as such
     (GIFs from the synthetic walk retargeted to 3 rigs) — still honest, all
     claims cite the generator script.
2. **P3-4 progress streaming** for long MCP tools (notifications with
   `phase`/`0..1` per mcp/DESIGN.md) — P3-3's refusal plumbing is the
   pattern to follow (tested like any tool).
3. **P3-5 session manager** (add-on ↔ server loopback socket, action queue)
   if P3-4 lands fast — this unblocks the E2E agent demo (P3-7's launch GIF).

Watch out for:
- **Blender 5.1.0 at `/home/potato/blender-5.1.0-linux-x64/` is the real
  install**; CI deliberately keeps apt 4.0.2 (D-014). S8 note: `Action.fcurves`
  is GONE in 5.x (slotted actions) — `xtask/export_clip.sh` probes BOTH APIs;
  copy that pattern for any new action-introspection code.
- After a box crash, `python3` may resolve to /usr/bin/python3 — project env
  is conda BASE; pass `RIGPOSE=/home/potato/miniconda3/bin/rigpose` and/or
  `BLENDER=` explicitly to gate scripts.
- **S7 bake lessons** (do not reintroduce): `pb.matrix` reads are STALE once
  an action is assigned — compose worlds locally via `W = P @ (Mp⁻¹Mb) @ B`;
  bone rest LENGTH is `Bone.length`. Both live in bake.py + D-013.
- S8 export-gate lesson: after `read_factory_settings`, old `bpy` object
  references are INVALIDATED — capture counts/values before switching scenes.
- Noqa rule: no `# noqa: <code>` comments in addon/ or xtask/ .py files
  (RUF100); core/src exempt.
- Payload contract: v2 payloads MUST carry the `figures` list; actions load
  ONLY through `payload.py` (D-009).
- Root motion stays unimplemented by design (D-008); hip stabilization
  re-anchors, it never fabricates translation; walk-in-place is the honest
  baseline. Do not loosen gate numbers (D-010..013) — S8's HIPSTAB block is
  separate from the P2-5 FOOTLOCK block on purpose.
- Windowed Blender GL is flaky on this box — the S5 UI screenshot stays
  committed + allowlisted; a genuine re-capture is optional best-effort
  (S8 skipped it deliberately: ~1-in-4 success odds, low value vs the
  closeout).

Blocked / deferred (unchanged since S7 unless noted):
- PyPI + Blender Extensions uploads — account-bound (LO);
  docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- NEW S8 — P2-8 real walking clip — NEEDS-HUMAN (see #1).
