# NEXT SESSION SHOULD …

1. **P0-15 — real-rig gate (top priority).** The 5-rig gate currently runs on
   synthetic rigs. Close it with real files:
   - Generate a real Rigify meta-rig headlessly:
     `blender -b --python-expr "import bpy; bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.object.armature_human_metarig_add(); bpy.ops.wm.save_as_mainfile(filepath='out/real_rigs/metarig.blend')"`
     (verify the operator name on 4.0: `bpy.ops.object.armature_human_metarig_add`).
   - Download one Mixamo GLTF/FBX export and one VRM sample (needs network;
     keep them in `out/real_rigs/`, git-ignored; document sources + licenses in
     `docs/BENCHMARKS.md`). Convert via `xtask/extract_blend.sh` or a GLTF
     import script, then `rigpose map --strict` each.
   - Target: ≤2 corrections each; record results in `docs/BENCHMARKS.md`.
2. **P0-16 — CI skeleton.** GitHub Actions: `ruff`, `pytest`, `blender_verify.sh`
   (install Blender via blender-org CI action or apt), plus the **network-audit
   test** (assert zero outbound connections during `rigpose map` on a fixture —
   run under `unshare -n` or a socket-audit wrapper; test the test).
3. **P0-17 — review data model.** `RoleAssignment.ambiguous` + `ambiguities[]`
   exist; add a `propose_reassignment(role, bone)` helper that mutates a
   mapping and re-serializes it, so the add-on's click-to-reassign UI has a
   one-call API.
4. If time remains: start **Phase 1 P1-1** — checksum-pinned model manager
   (`core/src/riggermortis/inference/models.py`): manifest of DWPose ONNX
   URLs+SHA256s, one-time local download **only on explicit user action**,
   offline verification. Keep numpy/onnxruntime OUT of core's hard deps
   (optional extra `riggermortis-core[inference]`; see DECISIONS D-005).

Blocked / deferred:
- Publishing (GitHub repo, PyPI, Blender Extensions) needs LO's accounts —
  registration is a human step; everything is prepared for it.
- No `subprocess` anywhere in core library code (workspace security gate +
  embeddability; see DECISIONS D-004). Blender process interop lives in
  `xtask/*.sh`, the add-on (already inside Blender), and CI.
