#!/usr/bin/env python
"""Build REAL Rigify rigs headlessly for the P0-15 real-rig gate.

Run inside Blender:

    blender -b --python xtask/build_rigify_rigs.py

Produces (under $RM_REAL_OUT, default out/real_rigs/):
    metarig.blend          — the unmodified human meta-rig
    rigify_generated.blend — the full generated rig (DEF-/ORG-/MCH- prefixes,
                             100+ bones: stresses prefix stripping)

Self-contained: imports nothing but stdlib + bpy, like the bridge scripts.
Sentinels on stdout: RM_METARIG_SAVED / RM_GENERATED_SAVED / RM_FAIL.
"""
from __future__ import annotations

import os
import sys

import bpy  # type: ignore[name-defined]

SENTINEL = "RM_"


def _armatures() -> list[bpy.types.Object]:
    return [o for o in bpy.data.objects if o.type == "ARMATURE"]


def _save(path: str, tag: str, arm: bpy.types.Object) -> None:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path))
    print(f"{tag} {os.path.abspath(path)} bones={len(arm.data.bones)}")


def main() -> int:
    out_dir = os.environ.get("RM_REAL_OUT", "out/real_rigs")
    os.makedirs(out_dir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    # The metarig add-operators and rigify_generate are registered by the
    # bundled `rigify` add-on, which use_empty=True leaves disabled.
    res = bpy.ops.preferences.addon_enable(module="rigify")
    if "FINISHED" not in res:
        print(f"{SENTINEL}FAIL addon_enable(rigify) -> {res}")
        return 1

    bpy.ops.object.armature_human_metarig_add()
    metarigs = _armatures()
    if len(metarigs) != 1:
        print(f"{SENTINEL}FAIL expected 1 metarig, found {len(metarigs)}")
        return 1
    meta = metarigs[0]
    _save(os.path.join(out_dir, "metarig.blend"), f"{SENTINEL}METARIG_SAVED", meta)

    # Generate the full rig from the metarig (must be active + in object mode).
    bpy.ops.object.select_all(action="DESELECT")
    meta.select_set(True)
    bpy.context.view_layer.objects.active = meta
    if meta.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    try:
        bpy.ops.pose.rigify_generate()
    except Exception as exc:  # noqa: BLE001 — logged and turned into a failure exit
        print(f"{SENTINEL}FAIL rigify_generate: {type(exc).__name__}: {exc}")
        return 1
    generated = max(_armatures(), key=lambda o: (len(o.data.bones), o.name))
    _save(
        os.path.join(out_dir, "rigify_generated.blend"),
        f"{SENTINEL}GENERATED_SAVED",
        generated,
    )
    prefixes: dict[str, int] = {}
    for b in generated.data.bones:
        pre = b.name.split("-", 1)[0] + "-" if "-" in b.name else "(none)"
        prefixes[pre] = prefixes.get(pre, 0) + 1
    print(f"{SENTINEL}PREFIXES {sorted(prefixes.items())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
