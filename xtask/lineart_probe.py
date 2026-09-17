"""P4-2 capability probe: does THIS Blender expose a scriptable line-art path?

The P4-2 design depends on a real unknown (the S11 lesson: probe the Blender
capability before designing — EEVEE-headless was a probe win). Grease Pencil
was rewritten (GPv3) across 4.3→5.x and the LineArt modifier may or may not
exist / be scriptable here. Paths, each verified by DOING it (strokes actually
evaluated on a sphere target, pixels actually changed in a render) — never by
attribute existence alone:

1. legacy GP LineArt modifier (``GP_LINEART`` on ``grease_pencil_modifiers``)
2. new Grease Pencil (GPv3) modifier stack — ``LINEART`` here?
3. Freestyle over the render (and WHICH engines actually draw lines)
4. THE P4-2 QUESTION: GP LineArt strokes composing OVER a P4-1 toon material
   in ONE EEVEE frame (bands + ink contour = the manga look).

Prints ``RM_LINEART`` lines; exit 0 = at least one path usable.
Usage: blender -b --python xtask/lineart_probe.py -- OUT_DIR
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _set_source(mod: Any, obj: Any) -> str | None:
    """Set the line-art source object on whatever this modifier calls it."""
    for prop in ("source_object", "target", "object", "source"):
        if hasattr(mod, prop):
            setattr(mod, prop, obj)
            return prop
    return None


def _make_scene(sphere_name: str) -> tuple[Any, Any]:
    """Factory-empty scene + UV sphere + aimed camera + flat world.

    Returns (scene, sphere). A camera matters: LineArt traces from a camera's
    point of view (no camera -> no strokes), and EEVEE renders black without
    an explicit world (the S4/S9 lesson, twice over).
    """
    import bpy
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(0, 0, 1))
    sphere = bpy.context.object
    cam_data = bpy.data.cameras.new("probe_cam")
    cam = bpy.data.objects.new("probe_cam", cam_data)
    cam.location = (0.0, -4.0, 1.2)
    aim = Vector((0.0, 0.0, 1.0)) - cam.location
    cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
    bpy.context.collection.objects.link(cam)
    world = bpy.data.worlds.new("probe_world")
    world.use_nodes = False
    world.color = (0.08, 0.08, 0.09)
    scene = bpy.context.scene
    scene.world = world
    scene.camera = cam
    return scene, sphere


def _count_new_gp(gp_data: Any, tag: str) -> tuple[int, list[str]]:
    """Count strokes on a (possibly evaluated) new-GP datablock, reporting
    WHICH API shape worked — the GPv3 Python surface is exactly what the
    probe is here to record."""
    total = 0
    shape: list[str] = []
    for layer in gp_data.layers:
        frames = getattr(layer, "frames", None)
        if frames is not None:
            for frame in frames:
                drawing = getattr(frame, "drawing", None)
                if drawing is not None and hasattr(drawing, "strokes"):
                    total += len(drawing.strokes)
                    if "frames->drawing->strokes" not in shape:
                        shape.append("frames->drawing->strokes")
            continue
        drawing = getattr(layer, "drawing", None)
        if drawing is not None and hasattr(drawing, "strokes"):
            total += len(drawing.strokes)
            if "layer.drawing->strokes" not in shape:
                shape.append("layer.drawing->strokes")
    if not shape:
        attrs = [a for a in dir(layer) if not a.startswith("_")][:30]
        print(f"RM_LINEART {tag} LAYER API: {attrs}")
    return total, shape


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("RM_LINEART FAIL: expected -- OUT_DIR")
        return 2
    out_dir = Path(argv[argv.index("--") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)

    import bpy

    print(f"RM_LINEART BLENDER: {bpy.app.version_string}")
    inventory = sorted(
        n for n in dir(bpy.types) if "lineart" in n.lower() or "line_art" in n.lower()
    )
    print(f"RM_LINEART TYPES: {inventory or 'none'}")
    engines = [
        e.identifier
        for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    ]
    print(f"RM_LINEART ENGINES: {engines}")

    usable = {"legacy_gp_lineart": False, "new_gp_lineart": False,
              "freestyle": False, "compose_over_toon": False}

    # ---- Path 1: legacy GP LineArt modifier ------------------------------
    # Finding so far (v1 probe): bpy.data.grease_pencils.new() yields a
    # type-GREASEPENCIL object with NO grease_pencil_modifiers stack — the
    # legacy GPv2 object class is gone in 5.1. Re-affirm, then move on.
    scene, sphere = _make_scene("legacy")
    gp_data = bpy.data.grease_pencils.new("probe_legacy")
    gp_obj = bpy.data.objects.new("probe_legacy", gp_data)
    bpy.context.collection.objects.link(gp_obj)
    print(
        f"RM_LINEART LEGACY GP: object type={gp_obj.type!r} "
        f"legacy_stack={hasattr(gp_obj, 'grease_pencil_modifiers')}"
    )
    print("RM_LINEART LEGACY GP: verdict — legacy GPv2 LineArt path is GONE in 5.1")

    # ---- Path 2: new Grease Pencil modifier stack ------------------------
    # The v1 probe recorded the full LINEART property set (source_object,
    # use_contour/use_crease/..., radius/opacity, levels, chaining). A bare
    # bpy.data.grease_pencils.new() datablock has NO layer for the modifier
    # to write strokes into — the ops LINEART_OBJECT preset wires layer +
    # modifier + source in one step, so that is the shape under test.
    scene, sphere = _make_scene("newgp")
    try:
        bpy.ops.object.grease_pencil_add(type="LINEART_OBJECT")
        gp_new = bpy.context.object
        mods = [m.type for m in gp_new.modifiers]
        print(f"RM_LINEART NEW GP: ops-created type={gp_new.type!r} mods={mods}")
        mod = next((m for m in gp_new.modifiers if m.type == "LINEART"), None)
        if mod is not None:
            src = getattr(mod, "source_object", None)
            print(
                f"RM_LINEART NEW GP: preset source={src.name if src else None} "
                f"contour={getattr(mod, 'use_contour', None)} "
                f"radius={getattr(mod, 'radius', None)}"
            )
            mod.source_object = sphere
            mod.use_contour = True
            mod.use_crease = True
            if hasattr(mod, "radius"):
                mod.radius = 3.0
            if hasattr(mod, "opacity"):
                mod.opacity = 1.0
            scene.frame_set(1)
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            gp_eval_data = gp_new.evaluated_get(dg).data
            strokes, shape = _count_new_gp(gp_eval_data, "NEW GP EVAL")
            print(
                f"RM_LINEART NEW GP STROKES: {strokes} via {shape or 'UNKNOWN-API'}"
            )
            usable["new_gp_lineart"] = strokes > 0
        else:
            print("RM_LINEART NEW GP: LINEART preset created no LINEART modifier")
    except Exception as exc:  # noqa: BLE001 — a probe reports, it does not crash
        print(f"RM_LINEART NEW GP: UNAVAILABLE ({exc.__class__.__name__}: {exc})")

    # ---- Path 3: Freestyle over the render -------------------------------
    # v1 finding kept: EEVEE in 5.1 draws NO freestyle lines (0 changed
    # channels) and Blender's internal Freestyle Python stage crashes
    # ('NoneType' has no attribute 'use_chaining'). Re-affirm once, cheaply.
    try:
        scene.render.use_freestyle = True
        fs = scene.view_layers[0].freestyle_settings
        print(
            f"RM_LINEART FREESTYLE: linesets={[ls.name for ls in fs.linesets]} "
            f"modes={[m.identifier for m in fs.bl_rna.properties['mode'].enum_items]}"
        )
        scene.render.image_settings.file_format = "PNG"
        scene.render.resolution_x, scene.render.resolution_y = 320, 240
        for engine in [e for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES")
                       if e in engines]:
            try:
                scene.render.engine = engine
                if engine == "CYCLES":
                    scene.cycles.samples = 1
                    scene.cycles.use_denoising = False
                scene.render.filepath = str(out_dir / f"fs_off_{engine}.png")
                scene.render.use_freestyle = False
                bpy.ops.render.render(write_still=True)
                scene.render.filepath = str(out_dir / f"fs_on_{engine}.png")
                scene.render.use_freestyle = True
                bpy.ops.render.render(write_still=True)
                off = bpy.data.images.load(str(out_dir / f"fs_off_{engine}.png"))
                on = bpy.data.images.load(str(out_dir / f"fs_on_{engine}.png"))
                off_px, on_px = list(off.pixels), list(on.pixels)
                bpy.data.images.remove(off)
                bpy.data.images.remove(on)
                changed = sum(
                    1
                    for a, b in zip(off_px, on_px, strict=True)
                    if abs(a - b) > 0.02
                )
                usable["freestyle"] = usable["freestyle"] or changed > 0
                print(
                    f"RM_LINEART FREESTYLE {engine}: changed_channels={changed} "
                    f"{'LINES DRAWN' if changed > 0 else 'no visible lines'}"
                )
            except Exception as exc:  # noqa: BLE001 — per-engine honesty
                print(
                    f"RM_LINEART FREESTYLE {engine}: FAILED "
                    f"({exc.__class__.__name__}: {exc})"
                )
        scene.render.use_freestyle = False
    except Exception as exc:  # noqa: BLE001
        print(f"RM_LINEART FREESTYLE: UNAVAILABLE ({exc.__class__.__name__}: {exc})")

    # ---- Path 4: compose LineArt over a P4-1 toon material ---------------
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
        from riggermortis_addon import style

        scene, sphere = _make_scene("compose")
        scene.render.engine = (
            "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
        )
        scene.render.image_settings.file_format = "PNG"
        scene.render.resolution_x, scene.render.resolution_y = 320, 240
        scene.frame_set(1)
        sphere.data.materials.clear()
        style.build_toon_material(sphere, style.load_preset("manga"))
        scene.render.filepath = str(out_dir / "compose_base.png")
        bpy.ops.render.render(write_still=True)
        base = bpy.data.images.load(str(out_dir / "compose_base.png"))
        base_px = list(base.pixels)
        bpy.data.images.remove(base)

        bpy.ops.object.grease_pencil_add(type="LINEART_OBJECT")
        ink = bpy.context.object
        mod = next((m for m in ink.modifiers if m.type == "LINEART"), None)
        if mod is not None:
            mod.source_object = sphere
            mod.use_contour = True
            mod.use_crease = True
            if hasattr(mod, "radius"):
                mod.radius = 3.0
            if hasattr(mod, "opacity"):
                mod.opacity = 1.0
        ink_mats = [m.name for m in ink.data.materials if m is not None]
        print(f"RM_LINEART COMPOSE: ink object materials={ink_mats}")
        for ink_mat in ink.data.materials:
            if ink_mat is None:
                continue
            gp_mat = getattr(ink_mat, "grease_pencil", None)
            if gp_mat is not None and hasattr(gp_mat, "color"):
                gp_mat.color = (0.0, 0.0, 0.0, 1.0)
        scene.frame_set(1)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        strokes, shape = _count_new_gp(ink.evaluated_get(dg).data, "COMPOSE INK")
        print(f"RM_LINEART COMPOSE STROKES: {strokes} via {shape or 'UNKNOWN-API'}")
        scene.render.filepath = str(out_dir / "compose_ink.png")
        bpy.ops.render.render(write_still=True)
        inked = bpy.data.images.load(str(out_dir / "compose_ink.png"))
        ink_px = list(inked.pixels)
        bpy.data.images.remove(inked)
        changed = sum(
            1
            for a, b in zip(base_px, ink_px, strict=True)
            if abs(a - b) > 0.02
        )
        darkened = sum(
            1
            for a, b in zip(base_px, ink_px, strict=True)
            if b < a - 0.05 and a > 0.05
        )
        usable["compose_over_toon"] = changed > 0 and darkened > 0
        print(
            f"RM_LINEART COMPOSE: changed_channels={changed} "
            f"darkened_channels={darkened} "
            f"{'INK OVER BANDS' if usable['compose_over_toon'] else 'no visible ink'}"
        )
    except Exception as exc:  # noqa: BLE001 — honest degradation
        print(f"RM_LINEART COMPOSE: FAILED ({exc.__class__.__name__}: {exc})")

    print(f"RM_LINEART PROBE RESULT: {usable}")
    if not any(usable.values()):
        print("RM_LINEART PROBE: NO usable line-art path in this Blender")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
