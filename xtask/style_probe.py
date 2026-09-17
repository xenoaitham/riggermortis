"""In-Blender probe for the P4-1 style gate (headless).

Applies all shipped toon presets to a shaded test object (a UV sphere —
the material needs real normals; armature bones do not shade), asserts the
node graph against each build report, rebuilds to prove determinism (same
preset = byte-identical report), then renders one EEVEE frame per preset.
A GPU-less environment degrades honestly: the graph checks still PASS, the
render reports RM_STYLE RENDER SKIPPED and no media is claimed.

Usage: blender -b --python xtask/style_probe.py -- OUT_DIR
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addon"))


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("RM_STYLE FAIL: expected -- OUT_DIR")
        return 2
    out_dir = Path(argv[argv.index("--") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)

    import bpy
    from mathutils import Vector
    from riggermortis_addon import style

    names = style.known_presets()
    if names != ["anime", "manga", "western"]:
        print(f"RM_STYLE FAIL: unexpected preset set {names}")
        return 1
    print(f"RM_STYLE PRESETS: {', '.join(names)}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(0, 0, 1))
    obj = bpy.context.object
    cam_data = bpy.data.cameras.new("style_cam")
    cam = bpy.data.objects.new("style_cam", cam_data)
    cam.location = (0.0, -4.0, 1.2)
    aim = Vector((0.0, 0.0, 1.0)) - cam.location
    cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
    bpy.context.collection.objects.link(cam)
    # Explicit world: an empty factory scene has none, and EEVEE renders
    # empty/black otherwise (the S4/S9 lesson, twice over).
    world = bpy.data.worlds.new("rm_style_world")
    world.use_nodes = False
    world.color = (0.08, 0.08, 0.09)
    bpy.context.scene.world = world
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 480, 360

    engines = [
        e.identifier
        for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    ]
    scene.render.engine = (
        "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    )
    scene.render.image_settings.file_format = "PNG"

    reports = {}
    rendered = []
    skipped = []
    ok = True
    for name in names:
        # One preset owns the object at a time — faces render SLOT 0, so
        # build, verify, and render each preset before clearing for the
        # next (a leftover or later material would star in the shot).
        obj.data.materials.clear()
        preset = style.load_preset(name)
        report = style.build_toon_material(obj, preset)
        rebuild = style.build_toon_material(obj, preset)  # determinism probe
        if report != rebuild:
            print(f"RM_STYLE {name.upper()}: FAIL — rebuild differs (not deterministic)")
            ok = False
            continue
        # The graph must be exactly what the preset promised.
        checks = {
            "bands": report["bands"] == len(preset["bands"]["colors"]),
            "cuts": report["band_cuts"] == [float(p) for p in preset["bands"]["positions"]],
            "emission": "ToonEmission" in report["nodes"],
            "assigned": report["material"]
            in [m.name for m in obj.data.materials if m is not None],
        }
        if report["rim"] is not None:
            checks["rim"] = (
                report["rim"]["start"] == float(preset["rim"]["start"])
                and "RimMix" in report["nodes"]
            )
        else:
            checks["rim"] = "RimMix" not in report["nodes"]
        failed = [k for k, v in checks.items() if not v]
        if failed:
            print(f"RM_STYLE {name.upper()}: FAIL — {failed}")
            ok = False
            continue
        reports[name] = report
        print(
            f"RM_STYLE {name.upper()} GRAPH: PASS bands={report['bands']} "
            f"cuts={report['band_cuts']} rim={report['rim']} "
            f"nodes={report['nodes']}"
        )
        scene.render.filepath = str(out_dir / f"style_{name}.png")
        try:
            bpy.ops.render.render(write_still=True)
            rendered.append(name)
            print(f"RM_STYLE {name.upper()} RENDER: {scene.render.filepath}")
        except Exception as exc:  # noqa: BLE001 — honest degradation, no faked media
            skipped.append(name)
            print(
                f"RM_STYLE {name.upper()} RENDER SKIPPED: "
                f"({exc.__class__.__name__}: {exc})"
            )

    if not ok:
        return 1

    (out_dir / "style_reports.json").write_text(
        json.dumps(reports, sort_keys=True, indent=2), encoding="utf-8"
    )
    if skipped:
        print(f"RM_STYLE RENDER SKIPPED: {skipped} (no GPU context — no media claimed)")
    print(
        f"RM_STYLE PROBE {'OK' if ok else 'FAIL'} "
        f"rendered={rendered} skipped={skipped}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
