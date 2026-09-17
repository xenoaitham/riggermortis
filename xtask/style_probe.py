"""In-Blender probe for the style gate (headless).

P4-1: applies all shipped toon presets to a shaded test object (a UV sphere
— the material needs real normals; armature bones do not shade), asserts the
node graph against each build report, rebuilds to prove determinism (same
preset = byte-identical report), then renders one EEVEE frame per preset.
P4-2: for presets carrying a ``lineart`` section, builds the LineArt ink
overlay over the banded fill (ops LINEART_OBJECT wiring, canonical renames —
docs/STYLE.md), asserts the report + determinism, HARD-checks that strokes
actually evaluate on the depsgraph (engine-independent), and renders one
composed bands+ink frame per preset.

A GPU-less environment degrades honestly: the graph/stroke checks still
PASS, the renders report RM_STYLE RENDER SKIPPED and no media is claimed.

Usage: blender -b --python xtask/style_probe.py -- OUT_DIR
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addon"))


def _evaluated_strokes() -> int:
    """Count strokes on the canonical ``rm_lineart`` overlay after a
    depsgraph evaluation — the engine-independent proof the build is not
    an empty shell."""
    import bpy

    overlay = bpy.data.objects.get("rm_lineart")
    if overlay is None:
        return 0
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    total = 0
    for layer in overlay.evaluated_get(dg).data.layers:
        for frame in layer.frames:
            drawing = getattr(frame, "drawing", None)
            if drawing is not None and hasattr(drawing, "strokes"):
                total += len(drawing.strokes)
    return total


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
        base_px: list[float] | None = None
        try:
            bpy.ops.render.render(write_still=True)
            rendered.append(name)
            base_img = bpy.data.images.load(str(out_dir / f"style_{name}.png"))
            base_px = list(base_img.pixels)
            bpy.data.images.remove(base_img)
            print(f"RM_STYLE {name.upper()} RENDER: {scene.render.filepath}")
        except Exception as exc:  # noqa: BLE001 — honest degradation, no faked media
            skipped.append(name)
            print(
                f"RM_STYLE {name.upper()} RENDER SKIPPED: "
                f"({exc.__class__.__name__}: {exc})"
            )

        # P4-2: line art composes OVER the banded fill (bands + ink in one
        # frame). Stroke evaluation is checked even when renders skip.
        if preset.get("lineart") is not None:
            la = style.build_lineart(obj, preset)
            la_rebuild = style.build_lineart(obj, preset)
            if la != la_rebuild:
                print(
                    f"RM_STYLE {name.upper()} LINEART: FAIL — "
                    "rebuild differs (not deterministic)"
                )
                ok = False
                continue
            la_failed = [
                key
                for key, want in {
                    "object": la["object"] == "rm_lineart",
                    "layer": la["layer"] == "Lines",
                    "modifier": la["modifier"] == "rm_lineart",
                    "material": la["material"] == f"rm_ink_{name}",
                    "source": la["source"] == obj.name,
                    "values": (
                        la["radius"] == float(preset["lineart"]["radius"])
                        and la["opacity"] == float(preset["lineart"]["opacity"])
                        and la["contour"] is preset["lineart"]["contour"]
                        and la["crease"] is preset["lineart"]["crease"]
                        and la["crease_threshold"]
                        == float(preset["lineart"]["crease_threshold"])
                        and la["color"] == preset["lineart"]["color"]
                    ),
                }.items()
                if not want
            ]
            if la_failed:
                print(f"RM_STYLE {name.upper()} LINEART: FAIL — {la_failed}")
                ok = False
                continue
            strokes = _evaluated_strokes()
            if strokes <= 0:
                print(
                    f"RM_STYLE {name.upper()} LINEART: FAIL — 0 strokes "
                    "evaluated (the overlay is an empty shell)"
                )
                ok = False
                continue
            print(
                f"RM_STYLE {name.upper()} LINEART: PASS strokes={strokes} "
                f"radius={la['radius']} color={la['color']}"
            )
            scene.render.filepath = str(out_dir / f"style_{name}_ink.png")
            try:
                bpy.ops.render.render(write_still=True)
                rendered.append(f"{name}_ink")
                ink_img = bpy.data.images.load(
                    str(out_dir / f"style_{name}_ink.png")
                )
                ink_px = list(ink_img.pixels)
                bpy.data.images.remove(ink_img)
                if base_px is not None and len(base_px) == len(ink_px):
                    darkened = sum(
                        1
                        for a, b in zip(base_px, ink_px, strict=True)
                        if b < a - 0.05 and a > 0.05
                    )
                    print(
                        f"RM_STYLE {name.upper()} INK PIXELS: darkened="
                        f"{darkened}"
                    )
                    if darkened <= 0:
                        print(
                            f"RM_STYLE {name.upper()} LINEART: FAIL — ink "
                            "evaluates but is invisible in the render"
                        )
                        ok = False
                print(
                    f"RM_STYLE {name.upper()} COMPOSE RENDER: "
                    f"{scene.render.filepath}"
                )
            except Exception as exc:  # noqa: BLE001 — honest degradation
                skipped.append(f"{name}_ink")
                print(
                    f"RM_STYLE {name.upper()} COMPOSE RENDER SKIPPED: "
                    f"({exc.__class__.__name__}: {exc})"
                )
            style.remove_lineart()  # next preset's base render must be ink-free

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
