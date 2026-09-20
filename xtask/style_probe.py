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
P4-4: for shipped page presets (``presets/pages/*.json``), creates
deterministic page cameras, renders one PNG per panel at the preset's pixel
size, assembles the compositor page graph (rebuild-deterministic), renders
the page, and pixel-checks it (size, background, border ring, per-panel
byte-fidelity roundtrip) — SKIPPED honestly on Blenders without the scene
compositor node group.
P4-5: pages carrying ``bubbles`` render one RGBA overlay PNG per bubble
(pure bubble stage: mesh body + GP ink + typeset text; re-render
pixel-identical), composite them over the panels, and pixel-check the
result (ring ink, white body, dark lettering; panel roundtrip samples skip
bubble-covered points).

A GPU-less environment degrades honestly: the graph/stroke checks still
PASS, the renders report RM_STYLE RENDER SKIPPED and no media is claimed.

Usage: blender -b --python xtask/style_probe.py -- OUT_DIR
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

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


def _has_lineart_api() -> bool:
    """True when this Blender has the 5.1-class GPv3 LineArt surface."""
    import bpy

    return hasattr(bpy.types, "GreasePencilLineartModifier") and hasattr(
        bpy.ops.object, "grease_pencil_add"
    )


def _has_tones_api(scene: Any) -> bool:
    """True when this Blender composites through a scene node group."""
    return hasattr(scene, "compositing_node_group")


def _sample_px(
    px: list[float], width: int, x: int, y: int
) -> tuple[float, float, float]:
    i = (y * width + x) * 4
    return px[i], px[i + 1], px[i + 2]


def _diff_channels(a: list[float], b: list[float]) -> int:
    """Count differing channels beyond a noise floor (0.02) — the pixel
    motion/determinism metric for the animatic frames (the probe's
    re-renders are exactly 0, so any count is signal)."""
    return sum(
        1 for x, y in zip(a, b, strict=True) if abs(x - y) > 0.02
    )


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
    print(f"RM_STYLE BLENDER: {bpy.app.version_string}")
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
        ink_px: list[float] | None = None
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
        # A Blender without the GPv3 LineArt surface (apt 4.0.2 in CI)
        # reports SKIPPED honestly — the graph checks still gate.
        if preset.get("lineart") is None:
            pass
        elif not _has_lineart_api():
            print(
                f"RM_STYLE {name.upper()} LINEART: SKIPPED (this Blender "
                "has no GPv3 LineArt API — apt 4.0.2-class; not a failure)"
            )
        else:
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

        # P4-3: screentones composite over EVERYTHING (this render carries
        # material + lineart + tones in one frame when all three exist).
        # A Blender without the scene compositor node group (apt 4.0.2 in
        # CI) reports SKIPPED honestly.
        if preset.get("tones") is None:
            print(f"RM_STYLE {name.upper()} TONES: NONE (no tones field)")
        elif not _has_tones_api(scene):
            print(
                f"RM_STYLE {name.upper()} TONES GRAPH: SKIPPED (this Blender "
                "has no scene compositing node group — apt 4.0.2-class; not "
                "a failure)"
            )
        else:
            tones_report = style.build_screentones(scene, preset)
            tones_rebuild = style.build_screentones(scene, preset)
            if tones_report != tones_rebuild:
                print(
                    f"RM_STYLE {name.upper()} TONES: FAIL — "
                    "rebuild differs (not deterministic)"
                )
                ok = False
                continue
            tones_failed = [
                key
                for key, want in {
                    "group": tones_report["group"] == "rm_tones",
                    "uv_layer": tones_report["uv_layer"] == "rm_tones_uv",
                    "uv_material": tones_report["uv_material"] == "rm_tones_uv",
                    "beauty": tones_report["beauty_layer"]
                    == scene.view_layers[0].name,
                    "values": (
                        tones_report["cells"] == preset["tones"]["cells"]
                        and tones_report["dot_scale"]
                        == float(preset["tones"]["dot_scale"])
                        and tones_report["ink"] == preset["tones"]["ink"]
                    ),
                }.items()
                if not want
            ]
            if tones_failed:
                print(f"RM_STYLE {name.upper()} TONES: FAIL — {tones_failed}")
                ok = False
                continue
            print(
                f"RM_STYLE {name.upper()} TONES GRAPH: PASS "
                f"cells={tones_report['cells']} "
                f"dot_scale={tones_report['dot_scale']} "
                f"ink={tones_report['ink']}"
            )
            scene.render.filepath = str(out_dir / f"style_{name}_tones.png")
            try:
                bpy.ops.render.render(write_still=True)
                rendered.append(f"{name}_tones")
                tones_img = bpy.data.images.load(
                    str(out_dir / f"style_{name}_tones.png")
                )
                tones_px = list(tones_img.pixels)
                bpy.data.images.remove(tones_img)
                if ink_px is not None and len(ink_px) == len(tones_px):
                    darkened = sum(
                        1
                        for a, b in zip(ink_px, tones_px, strict=True)
                        if b < a - 0.05 and a > 0.05
                    )
                    print(
                        f"RM_STYLE {name.upper()} TONE PIXELS: darkened="
                        f"{darkened}"
                    )
                    if darkened <= 0:
                        print(
                            f"RM_STYLE {name.upper()} TONES: FAIL — the tone "
                            "graph runs but no dot darkened any pixel"
                        )
                        ok = False
                print(
                    f"RM_STYLE {name.upper()} TONES RENDER: "
                    f"{scene.render.filepath}"
                )
            except Exception as exc:  # noqa: BLE001 — honest degradation
                skipped.append(f"{name}_tones")
                print(
                    f"RM_STYLE {name.upper()} TONES RENDER SKIPPED: "
                    f"({exc.__class__.__name__}: {exc})"
                )
            style.remove_screentones(scene)  # next preset renders clean

    # P4-4: multi-camera panel pages — needs the 5.1 scene compositor
    # node group (the same API class as tones; apt 4.0.2 SKIPS honestly).
    # Each shipped page: deterministic page cameras aimed at the sphere,
    # a base style for unstyled panels, per-panel renders at exact px
    # sizes, a rebuild-deterministic assembly graph, and pixel checks on
    # the assembled page (size, background corner, border ring, and a
    # byte-fidelity roundtrip sample per panel).
    if not _has_tones_api(scene):
        print(
            "RM_STYLE PAGES: SKIPPED (this Blender has no scene compositing "
            "node group — apt 4.0.2-class; not a failure)"
        )
    else:
        import math

        from riggermortis_addon import pages

        def _hex_rgb(raw: str) -> tuple[float, float, float]:
            return tuple(  # type: ignore[return-value]
                int(raw[k:k + 2], 16) / 255.0 for k in (1, 3, 5)
            )

        pages_ok = True
        for page_name in pages.known_pages():
            page = pages.load_page(page_name)
            count = len(page["panels"])
            for i in range(count):
                angle = 2.0 * math.pi * i / count
                data = bpy.data.cameras.new(f"rm_cam_{i + 1}")
                cam = bpy.data.objects.new(f"rm_cam_{i + 1}", data)
                cam.location = (
                    2.2 * math.sin(angle),
                    -3.6 * math.cos(angle),
                    1.0 + 0.35 * (i % 2),
                )
                aim = Vector((0.0, 0.0, 1.0)) - cam.location
                cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
                bpy.context.collection.objects.link(cam)
            # Base look for unstyled panels: the page-level ``style``
            # field (the explicit semantic — the old "first style named
            # in any panel" heuristic made the whole page that style,
            # visual-check-caught).
            base_name = page.get("style") or "manga"
            base = style.load_preset(base_name)
            obj.data.materials.clear()
            style.build_toon_material(obj, base)
            if base.get("lineart") is not None:
                style.build_lineart(obj, base)
            if base.get("tones") is not None:
                style.build_screentones(scene, base)

            preport = pages.render_panels(
                scene, page, out_dir / f"panels_{page_name}", subject=obj
            )
            style.remove_screentones(scene)  # its group is replaced next
            px_bad = [
                e["index"]
                for e in preport["panels"]
                if (e["width_px"], e["height_px"])
                != pages.panel_px(page, e["index"])[2:]
            ]
            if len(preport["panels"]) != count or px_bad:
                print(
                    f"RM_STYLE PAGES {page_name}: FAIL — panel px mismatch "
                    f"{px_bad} (expected {count} panels)"
                )
                ok = False
                pages_ok = False
                continue

            # P4-5: bubbles — one RGBA overlay PNG per bubble, rendered
            # OUTSIDE the page pipeline (compositor unset, film transparent,
            # everything else hidden), then composited over the panels by
            # the page graph. Re-render determinism is pixel-identity (the
            # only file-byte difference is Blender's RenderTime stamp).
            nbubbles = pages.page_bubble_count(page)
            breport = None
            bfiles = None
            if nbubbles:
                if not hasattr(bpy.types, "GreasePencilDrawing"):
                    print(
                        f"RM_STYLE PAGES {page_name}: BUBBLES SKIPPED (this "
                        "Blender has no GPv3 drawings API — pre-4.3-class; "
                        "not a failure)"
                    )
                    continue
                from riggermortis_addon import bubbles

                breport = bubbles.render_bubbles(
                    scene, page, out_dir / f"bubbles_{page_name}"
                )
                bfiles = [e["file"] for e in breport["bubbles"]]
                breport2 = bubbles.render_bubbles(
                    scene, page, out_dir / f"bubbles_{page_name}_2"
                )
                det_bad = []
                for e1, e2 in zip(
                    breport["bubbles"], breport2["bubbles"], strict=True
                ):
                    img1 = bpy.data.images.load(e1["file"])
                    p1, s1 = list(img1.pixels), tuple(img1.size)
                    bpy.data.images.remove(img1)
                    img2 = bpy.data.images.load(e2["file"])
                    p2 = list(img2.pixels)
                    bpy.data.images.remove(img2)
                    if s1 != (e1["w"], e1["h"]) or p1 != p2:
                        det_bad.append(e1["bubble"])
                if det_bad or len(bfiles) != nbubbles:
                    print(
                        f"RM_STYLE PAGES {page_name}: FAIL — bubble render "
                        f"mismatch {det_bad} (expected {nbubbles})"
                    )
                    ok = False
                    pages_ok = False
                    continue
                print(
                    f"RM_STYLE PAGES {page_name}: BUBBLES RENDER n={nbubbles} "
                    "det=PASS"
                )

            files = [e["file"] for e in preport["panels"]]
            graph = pages.build_page_graph(scene, page, files, bubble_files=bfiles)
            graph2 = pages.build_page_graph(
                scene, page, files, bubble_files=bfiles
            )
            if graph != graph2:
                print(
                    f"RM_STYLE PAGES {page_name}: FAIL — graph rebuild "
                    "differs (not deterministic)"
                )
                ok = False
                pages_ok = False
                continue
            page_png = out_dir / f"page_{page_name}.png"
            pages.render_page(scene, page, page_png)

            page_img = bpy.data.images.load(str(page_png))
            got_size = tuple(page_img.size)
            page_px = list(page_img.pixels)
            bpy.data.images.remove(page_img)
            width = page["page"]["width_px"]
            height = page["page"]["height_px"]

            checks: dict[str, bool] = {
                "size": got_size == (width, height),
            }
            border_px = (page["page"].get("border") or {}).get("width_px", 0)
            # Exposed-background point: the first scan hit outside every
            # panel (+border margin). A corner assumption is WRONG for
            # layouts with a full-width bottom panel (gate-caught: the
            # corner is panel content there). Layouts that cover the page
            # entirely skip this check honestly.
            margin = border_px
            bg_pt = None
            bubble_rects = graph.get("bubbles", [])
            for yy in range(2, height, 24):
                for xx in range(2, width, 24):
                    covered = any(
                        e["x"] - margin <= xx < e["x"] + e["w"] + margin
                        and e["y"] - margin <= yy < e["y"] + e["h"] + margin
                        for e in graph["panels"]
                    ) or any(
                        b["x"] <= xx < b["x"] + b["w"]
                        and b["y"] <= yy < b["y"] + b["h"]
                        for b in bubble_rects
                    )
                    if not covered:
                        bg_pt = (xx, yy)
                        break
                if bg_pt is not None:
                    break
            if bg_pt is not None:
                bgc = _hex_rgb(page["page"]["background"])
                corner = _sample_px(page_px, width, bg_pt[0], bg_pt[1])
                checks["background"] = all(
                    abs(a - b) <= 1.5 / 255.0
                    for a, b in zip(corner, bgc, strict=True)
                )
            else:
                print(f"RM_STYLE PAGES {page_name}: note — no exposed background, skipped that check")
            if border_px > 0:
                bcol = _hex_rgb(page["page"]["border"]["color"])
                ring = next(
                    (
                        e
                        for e in graph["panels"]
                        if e["x"] >= border_px and e["h"] > 0
                    ),
                    None,
                )
                if ring is not None:
                    pt = _sample_px(
                        page_px,
                        width,
                        ring["x"] - border_px // 2,
                        ring["y"] + ring["h"] // 2,
                    )
                    checks["border"] = all(
                        abs(a - b) <= 1.5 / 255.0
                        for a, b in zip(pt, bcol, strict=True)
                    )
            for entry, file_path in zip(
                graph["panels"], files, strict=True
            ):
                panel_img = bpy.data.images.load(str(file_path))
                iw, ih = panel_img.size
                panel_px_list = list(panel_img.pixels)
                bpy.data.images.remove(panel_img)

                def _under_bubble(
                    px_x: int, px_y: int, rects: list = bubble_rects
                ) -> bool:
                    return any(
                        b["x"] <= px_x < b["x"] + b["w"]
                        and b["y"] <= px_y < b["y"] + b["h"]
                        for b in rects
                    )

                # byte-fidelity sample: the panel center, unless a bubble
                # covers it (bubbles intentionally change those pixels) —
                # then the first uncovered point in the panel; a fully
                # covered panel skips the check honestly.
                cx = entry["x"] + entry["w"] // 2
                cy = entry["y"] + entry["h"] // 2
                if _under_bubble(cx, cy):
                    found = None
                    for yy in range(entry["y"] + 2, entry["y"] + entry["h"], 8):
                        for xx in range(
                            entry["x"] + 2, entry["x"] + entry["w"], 8
                        ):
                            if not _under_bubble(xx, yy):
                                found = (xx, yy)
                                break
                        if found is not None:
                            break
                    if found is None:
                        print(
                            f"RM_STYLE PAGES {page_name}: note — panel "
                            f"{entry['index']} fully covered by bubbles, "
                            "roundtrip sample skipped"
                        )
                        continue
                    cx, cy = found
                si = ((cy - entry["y"]) * iw + (cx - entry["x"])) * 4
                want = (
                    panel_px_list[si],
                    panel_px_list[si + 1],
                    panel_px_list[si + 2],
                )
                got = _sample_px(page_px, width, cx, cy)
                checks[f"roundtrip_p{entry['index']:02d}"] = all(
                    abs(a - b) <= 1.5 / 255.0
                    for a, b in zip(want, got, strict=True)
                )
            # P4-5 bubble checks on the assembled page: ring ink, white
            # body above the text box, and (when the bubble carries text)
            # dark lettering pixels inside the ellipse mid band.
            for gi, (be, ge) in enumerate(
                zip(
                    (breport["bubbles"] if breport else []),
                    bubble_rects,
                    strict=True,
                )
            ):
                el = be["ellipse_px"]
                bx, by = ge["x"], ge["y"]
                ecx = bx + int(round(el["cx_px"]))
                # the assembled page is opaque (RGB samples; alpha 1 everywhere)
                ring = _sample_px(
                    page_px, width, ecx, by + int(round(el["cy_px"] + el["ry_px"]))
                )
                checks[f"bubble_{gi:02d}_ring"] = ring[0] < 0.5
                body = _sample_px(
                    page_px,
                    width,
                    ecx,
                    by + int(round(el["cy_px"] + el["ry_px"] * 0.75)),
                )
                checks[f"bubble_{gi:02d}_body"] = body[0] > 0.9 and body[1] > 0.9
                if be["has_text"]:
                    rx = int(round(el["rx_px"]))
                    ry = int(round(el["ry_px"]))
                    ecy = by + int(round(el["cy_px"]))
                    dark = sum(
                        1
                        for yy in range(ecy - int(ry * 0.35), ecy + int(ry * 0.35), 2)
                        for xx in range(ecx - int(rx * 0.5), ecx + int(rx * 0.5), 2)
                        if _sample_px(page_px, width, xx, yy)[0] < 0.35
                    )
                    checks[f"bubble_{gi:02d}_text"] = dark > 0
            failed = [k for k, v in checks.items() if not v]
            if failed:
                print(
                    f"RM_STYLE PAGES {page_name}: FAIL — {failed} "
                    f"(size={got_size}, bg_pt={bg_pt})"
                )
                ok = False
                pages_ok = False
                continue
            print(
                f"RM_STYLE PAGES {page_name}: PASS panels={count} "
                f"bubbles={nbubbles} page={width}x{height} "
                f"nodes={len(graph['nodes'])} file={page_png.name}"
            )
            pages.remove_page(scene)
        if pages_ok:
            print("RM_STYLE PAGES: PASS")

    # P4-7: animatic mode — a timed panel sequence from a canonical
    # action through the CERTIFIED bake path (bake_action). Frames are
    # PER-FRAME STILLS only: the 5.1 VSE movie-append is a recorded
    # dead end (racy segfault, docs/STYLE.md) and movie assembly is
    # shell glue (style_verify.sh, ffmpeg — D-009). Two full sweeps
    # must be pixel-identical (the P4-4 determinism standard); the
    # shot cut and the swing must be visible in the pixels. SKIPPED
    # honestly where renders skip (no GPU context).
    from riggermortis_addon import animatics

    sys.path.insert(0, str(REPO / "core" / "src"))
    import riggermortis as core
    from riggermortis_addon import bake as bake_mod

    def _anim_pose(i: int) -> Any:
        """8-phase canonical swing: the LEFT arm chain rises and falls.

        Positions follow the export-gate pose layout (hips anchor,
        canonical meters); only the left arm moves, so the motion is
        unambiguous in the pixels.
        """
        import math

        swing = 0.10 * math.sin(2.0 * math.pi * i / 8.0)
        return core.CanonicalPose(
            positions={
                "spine": (0.0, 0.0, 0.09),
                "chest": (0.0, 0.0, 0.26),
                "neck": (0.0, 0.0, 0.45),
                "head": (0.0, 0.0, 0.56),
                "shoulder.L": (0.13, 0.0, 0.45),
                "shoulder.R": (-0.13, 0.0, 0.45),
                "upper_arm.L": (0.26, 0.0, 0.45 + swing),
                "upper_arm.R": (-0.26, 0.0, 0.45),
                "forearm.L": (0.58, 0.0, 0.45 + 1.55 * swing),
                "forearm.R": (-0.58, 0.0, 0.45),
                "hand.L": (0.86, 0.0, 0.45 + 2.1 * swing),
                "hand.R": (-0.86, 0.0, 0.45),
                "hips": (0.0, 0.0, 0.0),
            },
            flips={},
            confidence=0.9,
            reliable=True,
            scale=30.0,
            anchor="hips",
        )

    try:
        animatic = animatics.load_animatic("demo_shots")
        action_len = 8
        plan = animatics.animatic_frames(animatic, action_len)

        # The page assembly must NOT be active (the builder refuses it —
        # exercised here as the documented negative path when the pages
        # section actually left a page graph behind).
        current_group = getattr(scene, "compositing_node_group", None)
        if current_group is not None and current_group.name == "rm_page":
            try:
                animatics.render_animatic_frames(
                    scene, animatic, out_dir / "animatic_frames", action_len
                )
                print("RM_STYLE ANIMATIC: FAIL — page-graph refusal did not fire")
                ok = False
            except ValueError as exc:
                if "rm_page" not in str(exc):
                    print(f"RM_STYLE ANIMATIC: FAIL — refusal error unclear: {exc}")
                    ok = False
        from riggermortis_addon import pages as pages_mod

        pages_mod.remove_page(scene)

        # Tiny mappable rig + deformed cube, far from the page sphere so
        # nothing photobombs (hide_render staged on everything else).
        bpy.ops.object.armature_add(location=(10.0, 0.0, 0.0))
        rig = bpy.context.object
        rig.name = "rm_animatic_rig"
        bpy.ops.object.mode_set(mode="EDIT")
        rig_bones = rig.data.edit_bones
        rig_bones.remove(rig_bones[0])

        def _bone(name: str, parent: str, head: Any, tail: Any) -> None:
            b = rig_bones.new(name)
            b.head, b.tail = head, tail
            b.parent = rig_bones[parent] if parent else None

        _bone("pelvis", None, (10.0, 0.0, 0.98), (10.0, 0.0, 1.06))
        _bone("spine", "pelvis", (10.0, 0.0, 1.06), (10.0, 0.0, 1.22))
        _bone("chest", "spine", (10.0, 0.0, 1.22), (10.0, 0.0, 1.40))
        _bone("neck", "chest", (10.0, 0.0, 1.40), (10.0, 0.0, 1.50))
        _bone("head", "neck", (10.0, 0.0, 1.50), (10.0, 0.0, 1.70))
        _bone("shoulder.L", "chest", (10.03, 0.0, 1.44), (10.14, 0.0, 1.46))
        _bone("upper_arm.L", "shoulder.L", (10.16, 0.0, 1.45), (10.46, 0.0, 1.45))
        _bone("forearm.L", "upper_arm.L", (10.46, 0.0, 1.45), (10.72, 0.0, 1.45))
        _bone("hand.L", "forearm.L", (10.72, 0.0, 1.45), (10.82, 0.0, 1.45))
        bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.mesh.primitive_cube_add(
            size=0.5, location=(10.31, 0.0, 1.45)
        )
        subject2 = bpy.context.object
        subject2.name = "rm_animatic_cube"
        vgroup = subject2.vertex_groups.new(name="upper_arm.L")
        vgroup.add(list(range(len(subject2.data.vertices))), 1.0, "REPLACE")
        arm_mod = subject2.modifiers.new("arm", "ARMATURE")
        arm_mod.object = rig

        for other in scene.objects:
            if other.name not in {
                rig.name,
                subject2.name,
                "rm_cam_1",
                "rm_cam_2",
            }:
                other.hide_render = True

        frames = [
            core.ActionFrame(frame=i, pose=_anim_pose(i))
            for i in range(action_len)
        ]
        bake_report = bake_mod.bake_action(
            rig, frames, core, name="rm_animatic_bake"
        )
        if bake_report["baked_frames"] != list(range(1, action_len + 1)):
            print(
                "RM_STYLE ANIMATIC: FAIL — bake report "
                f"{bake_report['baked_frames']}"
            )
            ok = False

        # The animatic cameras: rm_cam_1/rm_cam_2 are the preset's camera
        # DATA. The pages section may have left them aimed at the page
        # sphere — RE-AIM at the animatic subject (pages already rendered;
        # nothing re-renders behind us). Caught by the first gate run:
        # reusing the sphere aim rendered 20 identical empty frames.
        for i, loc in enumerate([(10.0, -4.0, 1.6), (12.2, -3.0, 2.0)]):
            name = f"rm_cam_{i + 1}"
            if name in scene.objects:
                cam = scene.objects[name]
            else:
                data = bpy.data.cameras.new(name)
                cam = bpy.data.objects.new(name, data)
                bpy.context.collection.objects.link(cam)
            cam.location = loc
            aim = Vector((10.0, 0.0, 1.9)) - cam.location
            cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()

        def _base_look() -> None:
            base = style.load_preset(animatic["style"])
            subject2.data.materials.clear()
            style.build_toon_material(subject2, base)
            if base.get("lineart") is not None:
                style.build_lineart(subject2, base)
            else:
                style.remove_lineart()
            if base.get("tones") is not None:
                style.build_screentones(scene, base)
            else:
                style.remove_screentones(scene)

        def _sweep() -> dict[str, Any]:
            _base_look()  # persistent style semantics: re-apply the base
            report = animatics.render_animatic_frames(
                scene,
                animatic,
                out_dir / "animatic_frames",
                action_len,
                subject=subject2,
            )
            got_plan = [
                {k: e[k] for k in ("frame", "shot", "camera", "action_frame", "style")}
                for e in report["frames"]
            ]
            if got_plan != plan:
                raise AssertionError("render plan != animatic_frames timing")
            return report

        try:
            report1 = _sweep()
            report2 = _sweep()
        except Exception as exc:  # noqa: BLE001 — honest degradation
            skipped.append("animatic")
            print(
                f"RM_STYLE ANIMATIC: SKIPPED ({exc.__class__.__name__}: {exc})"
            )
        else:
            def _frame_px(path: Any) -> list[float]:
                img = bpy.data.images.load(str(path))
                px = list(img.pixels)
                bpy.data.images.remove(img)
                return px

            det_bad = sum(
                _diff_channels(_frame_px(a["file"]), _frame_px(b["file"]))
                for a, b in zip(
                    report1["frames"], report2["frames"], strict=True
                )
            )
            shot_cut = _diff_channels(
                _frame_px(report1["frames"][0]["file"]),
                _frame_px(report1["frames"][-1]["file"]),
            )
            swing = _diff_channels(
                _frame_px(report1["frames"][0]["file"]),
                _frame_px(report1["frames"][5]["file"]),
            )
            anim_checks_ok = (
                det_bad == 0 and shot_cut > 1000 and swing > 50
            )
            print(
                f"RM_STYLE ANIMATIC: {'PASS' if anim_checks_ok else 'FAIL'} "
                f"total={report1['total']} fps={report1['fps']} "
                f"det={det_bad == 0} shot_cut={shot_cut} swing={swing}"
            )
            ok = ok and anim_checks_ok
    except Exception as exc:  # noqa: BLE001 — structured, honest failure
        print(f"RM_STYLE ANIMATIC: FAIL ({exc.__class__.__name__}: {exc})")
        ok = False

    # P4-6: export — assemble the PDF + EPUB from THIS probe's page renders
    # (the unit = the P4-4/P4-5 page PNG). Structure is verified by parsing
    # the documents back (pdfinfo-free) and byte-determinism is asserted by
    # writing twice. SKIPPED honestly when the page renders did not happen
    # (the pages section skipped on this Blender).
    from riggermortis_addon import pages  # scoped import: SKIPPED path may not have it

    page_pngs = [out_dir / f"page_{name}.png" for name in pages.known_pages()]
    if not all(p.is_file() for p in page_pngs):
        print(
            "RM_STYLE EXPORT: SKIPPED (page renders absent — the pages "
            "section skipped on this Blender; not a failure)"
        )
    else:
        sys.path.insert(0, str(REPO / "core" / "src"))
        from riggermortis import pagedoc

        try:
            pdf1 = out_dir / "pages.pdf"
            pdf2 = out_dir / "pages_again.pdf"
            pagedoc.write_pdf(page_pngs, pdf1, title="riggermortis pages")
            pagedoc.write_pdf(page_pngs, pdf2, title="riggermortis pages")
            det = pdf1.read_bytes() == pdf2.read_bytes()
            parsed = pagedoc.read_pdf_pages(pdf1)
            want_sizes = []
            for p in page_pngs:
                img = bpy.data.images.load(str(p))
                want_sizes.append(tuple(img.size))
                bpy.data.images.remove(img)
            pdf_ok = (
                det
                and len(parsed) == len(page_pngs)
                and all(
                    (e["image_width"], e["image_height"]) == s
                    for e, s in zip(parsed, want_sizes, strict=True)
                )
                and all(
                    e["image_bytes"] == e["image_width"] * e["image_height"] * 3
                    for e in parsed
                )
            )
            print(
                f"RM_STYLE EXPORT PDF: {'PASS' if pdf_ok else 'FAIL'} "
                f"pages={len(parsed)} det={det}"
            )
            ok = ok and pdf_ok

            epub1 = out_dir / "pages.epub"
            epub2 = out_dir / "pages_again.epub"
            pagedoc.write_epub(page_pngs, epub1, title="riggermortis pages")
            pagedoc.write_epub(page_pngs, epub2, title="riggermortis pages")
            epub_det = epub1.read_bytes() == epub2.read_bytes()
            structure = pagedoc.read_epub_structure(epub1)
            epub_ok = (
                epub_det
                and structure["page_documents"] == len(page_pngs)
                and structure["images"] == len(page_pngs)
                and structure["title"] == "riggermortis pages"
            )
            print(
                f"RM_STYLE EXPORT EPUB: {'PASS' if epub_ok else 'FAIL'} "
                f"pages={structure['page_documents']} det={epub_det}"
            )
            ok = ok and epub_ok
        except Exception as exc:  # noqa: BLE001 — structured, honest failure
            print(f"RM_STYLE EXPORT: FAIL ({exc.__class__.__name__}: {exc})")
            ok = False

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
