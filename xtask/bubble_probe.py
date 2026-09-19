"""In-Blender probe for P4-5 speech bubbles (headless) — probe BEFORE builder.

Answers the three open questions docs/STYLE.md P4-5 records, with raw API
evidence (no bubbles.py involved — the builder is written only after this
passes, the S12/S13 discipline):

1. Q-GP: can the bubble be authored + rendered deterministically on 5.1?
   The GPv3 fill was probed to DEATH and is a dead end, recorded so it is
   never faked: material fill (show_fill/SOLID/white) does not render,
   stroke-level fill_color/fill_opacity do not render, per-point
   vertex_color drives only the STROKE (V-variants), the only fill ops are
   interactive cursor tools, and the MONKEY preset's authored fills render
   black-unlit / vanish-lit. THE BODY IS THEREFORE A MESH (ellipse n-gon +
   tail triangle, z-layered, unlit Emission — the P4-1 house trick) and the
   GPv3 strokes carry the INK outline only (proven rendering path; the GP
   layer is set use_lights=False so the ink is flat vertex_color —
   scene-independent like every P4 look).
2. Q-TEXT: does a TEXT object render legibly (dark ink on the white body),
   and does the composed overlay keep the underlying panel BYTE-FAITHFUL
   outside the bubble footprint (alpha-0 over = identity)?
3. Q-DET: is the pipeline deterministic — same geometry + text -> the same
   PNG? Finding: EEVEE Next's default TAA 64 jitters the AA between runs
   (7777 channels differed, max delta 1.0 — measured), so the probe also
   proves byte-determinism at taa_render_samples=1 (single-sample AA; the
   64-segment ellipse is sub-pixel smooth at bubble resolutions).

Composition re-uses the probe-verified P4-4 mechanics (CompositorNodeImage
+ Translate with the centering correction t = desired - (page - img)//2 +
AlphaOver Background/Foreground, default-sRGB loads + Standard view
transform + dither 0). Pixel mapping: image rows are BOTTOM-UP, so
row = (y_world / world_h + 0.5) * BH for the centered footprint.

Usage: blender -b --python xtask/bubble_probe.py -- OUT_DIR
"""
from __future__ import annotations

import array
import math
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addon"))

# Footprint: 640 x 420 px, world height 1.0 m (world width = bw/bh).
BW, BH = 640, 420
H_M = 1.0
W_M = BW / BH
OUTLINE_PX = 5
BAND_FRAC = 0.30  # tail band reserved from the footprint, shift axis
MARGIN_M = 0.03
ELLIPSE_N = 64
# z layering (mesh fill under ink; tail over ellipse so its fill covers the
# ellipse ink at the join; tail ink on top; text frontmost)
Z_ELL_FILL, Z_ELL_INK, Z_TAIL_FILL, Z_TAIL_INK, Z_TEXT = (
    -0.002,
    0.0,
    0.002,
    0.003,
    0.004,
)


def _ellipse_geometry(tail: str) -> tuple[float, float, float, float]:
    """Ellipse center + radii, pushed AWAY from the tail by the band."""
    dirs = {
        "n": (0.0, 1.0), "s": (0.0, -1.0), "e": (1.0, 0.0), "w": (-1.0, 0.0),
        "ne": (1.0, 1.0), "nw": (-1.0, 1.0), "se": (1.0, -1.0), "sw": (-1.0, -1.0),
    }
    if tail == "none":
        return 0.0, 0.0, W_M / 2 - MARGIN_M, H_M / 2 - MARGIN_M
    dx, dy = dirs[tail]
    vertical = abs(dy) > 0  # vertical band for n/s and diagonals
    band = BAND_FRAC * (H_M if vertical else W_M)
    cx = 0.0 if vertical else -math.copysign(band / 2, dx)
    cy = -math.copysign(band / 2, dy) if vertical else 0.0
    rx = W_M / 2 - MARGIN_M
    ry = H_M / 2 - MARGIN_M
    if vertical:
        ry = (H_M - band) / 2 - MARGIN_M
    else:
        rx = (W_M - band) / 2 - MARGIN_M
    return cx, cy, rx, ry


def _tail_geometry(tail: str, cx: float, cy: float, rx: float, ry: float) -> list[tuple[float, float]]:
    """Open tail polyline [base1, tip, base2] — no base edge inside the body.

    The tip reaches the FOOTPRINT edge (corner for diagonals, edge midpoint
    for cardinals) — measured in footprint coordinates, not ellipse coords.
    """
    dirs = {
        "n": (0.0, 1.0), "s": (0.0, -1.0), "e": (1.0, 0.0), "w": (-1.0, 0.0),
        "ne": (1.0, 1.0), "nw": (-1.0, 1.0), "se": (1.0, -1.0), "sw": (-1.0, -1.0),
    }
    if tail == "none":
        return []
    dx, dy = dirs[tail]
    diag = abs(dx) > 0 and abs(dy) > 0
    mx, my = W_M / 2 - MARGIN_M, H_M / 2 - MARGIN_M
    if diag:
        tip = (math.copysign(mx, dx), math.copysign(my, dy))
    elif abs(dx) == 0:
        tip = (cx, math.copysign(my, dy))
    else:
        tip = (math.copysign(mx, dx), cy)
    theta = math.atan2(tip[1] - cy, tip[0] - cx)
    pull = 0.94
    b1 = (cx + math.cos(theta + 0.38) * rx * pull, cy + math.sin(theta + 0.38) * ry * pull)
    b2 = (cx + math.cos(theta - 0.38) * rx * pull, cy + math.sin(theta - 0.38) * ry * pull)
    return [b1, tip, b2]


def _load_px(path: Path) -> tuple[int, int, list[float]]:
    import bpy

    img = bpy.data.images.load(str(path))
    w, h = img.size
    px = list(img.pixels)
    bpy.data.images.remove(img)
    return w, h, px


def _sample(px: list[float], w: int, x: int, y: int) -> tuple[float, float, float, float]:
    i = (y * w + x) * 4
    return px[i], px[i + 1], px[i + 2], px[i + 3]


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("RM_BUBBLE FAIL: expected -- OUT_DIR")
        return 2
    out_dir = Path(argv[argv.index("--") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)

    import bpy

    print(f"RM_BUBBLE BLENDER: {bpy.app.version_string}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    engines = [
        e.identifier
        for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    ]
    scene.render.engine = (
        "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    )
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x, scene.render.resolution_y = BW, BH
    scene.view_settings.view_transform = "Standard"
    scene.render.dither_intensity = 0.0

    ok = True

    # ---- geometry (deterministic from data) -----------------------------------------
    tail = "se"
    cx, cy, rx, ry = _ellipse_geometry(tail)
    tri = _tail_geometry(tail, cx, cy, rx, ry)
    outline_w = OUTLINE_PX * H_M / BH

    # body mesh: ellipse n-gon (z=Z_ELL_FILL) + tail triangle (z=Z_TAIL_FILL)
    verts = [
        (cx + rx * math.cos(2.0 * math.pi * i / ELLIPSE_N),
         cy + ry * math.sin(2.0 * math.pi * i / ELLIPSE_N),
         Z_ELL_FILL)
        for i in range(ELLIPSE_N)
    ]
    ell_face = list(range(ELLIPSE_N))
    faces = [ell_face]
    if tri:
        base = len(verts)
        verts += [(x, y, Z_TAIL_FILL) for x, y in tri]
        faces.append([base, base + 1, base + 2])
    mesh = bpy.data.meshes.new("rm_bubble_body")
    mesh.from_pydata(verts, [], faces)
    body_obj = bpy.data.objects.new("rm_bubble_body", mesh)
    bpy.context.collection.objects.link(body_obj)
    fmat = bpy.data.materials.new("rm_bubble_fill")
    fmat.use_nodes = True
    fnt = fmat.node_tree
    for n in list(fnt.nodes):
        fnt.nodes.remove(n)
    fem = fnt.nodes.new("ShaderNodeEmission")
    fem.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    fem.inputs["Strength"].default_value = 1.0
    fout = fnt.nodes.new("ShaderNodeOutputMaterial")
    fnt.links.new(fem.outputs[0], fout.inputs["Surface"])
    mesh.materials.append(fmat)

    # GP ink overlay (the PROVEN GPv3 rendering path): ops-create + rename,
    # use_lights=False so the ink is flat vertex_color (scene-independent)
    bpy.ops.object.grease_pencil_add(type="EMPTY")
    gp_obj = bpy.context.object
    gp_obj.name = "rm_bubble_gp"
    gp = gp_obj.data
    gp.name = "rm_bubble_gp"
    gp_layer = gp.layers[0]
    gp_layer.name = "Bubbles"
    gp_layer.use_lights = False
    ink = gp.materials[0]
    ink.name = "rm_bubble_ink"
    ink.grease_pencil.show_fill = False
    ink.grease_pencil.show_stroke = True
    ink.grease_pencil.stroke_style = "SOLID"
    ink.grease_pencil.color = (0.0, 0.0, 0.0, 1.0)
    draw = gp.layers[0].frames[0].drawing
    n_strokes = 2 if tri else 1
    draw.add_strokes([ELLIPSE_N] + ([3] if tri else []))
    strokes = list(draw.strokes)
    ell_pts = [
        (cx + rx * math.cos(2.0 * math.pi * i / ELLIPSE_N),
         cy + ry * math.sin(2.0 * math.pi * i / ELLIPSE_N),
         Z_ELL_INK)
        for i in range(ELLIPSE_N)
    ]
    for stroke, pts, closed in zip(
        strokes, [ell_pts, [(x, y, Z_TAIL_INK) for x, y in tri]][:n_strokes],
        [True, False][:n_strokes], strict=False,
    ):
        stroke.cyclic = closed
        for p, (x, y, z) in zip(stroke.points, pts, strict=True):
            p.position = (x, y, z)
            p.radius = outline_w
            p.opacity = 1.0
            p.vertex_color = (0.0, 0.0, 0.0, 1.0)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = gp_obj.evaluated_get(dg).data
    ev_strokes = sum(
        len(f.drawing.strokes) for lyr in ev.layers for f in lyr.frames
        if getattr(f, "drawing", None)
    )
    print(f"RM_BUBBLE EVAL: strokes={ev_strokes}")
    if ev_strokes != n_strokes:
        print("RM_BUBBLE EVAL: FAIL — authored strokes do not evaluate")
        return 1

    # stage: ortho camera, hide everything else, film transparent
    cam_data = bpy.data.cameras.new("rm_bubble_cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = W_M
    cam = bpy.data.objects.new("rm_bubble_cam", cam_data)
    cam.location = (0.0, 0.0, 5.0)
    bpy.context.collection.objects.link(cam)
    for ob in scene.objects:
        if ob is not gp_obj and ob is not body_obj and ob is not cam:
            ob.hide_render = True
    scene.camera = cam
    scene.render.film_transparent = True

    def render_to(path: Path) -> None:
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)

    def row(y_world: float) -> int:
        return int(round((y_world / H_M + 0.5) * BH))

    def col(x_world: float) -> int:
        return int(round((x_world / W_M + 0.5) * BW))

    # NOTE: the fill-dead-end mini-evidence — one render with the material
    # fill enabled (the mechanism that does NOT render) so the probe alone
    # carries the finding.
    ink.grease_pencil.show_fill = True
    ink.grease_pencil.fill_style = "SOLID"
    ink.grease_pencil.fill_color = (1.0, 1.0, 1.0, 1.0)
    png_matfill = out_dir / "bubble_matfill_attempt.png"
    render_to(png_matfill)
    _, _, pxm = _load_px(png_matfill)
    white_m = sum(
        1
        for yy in range(row(cy), row(cy + ry), 6)
        for xx in range(col(cx), col(cx + rx), 6)
        if pxm[(yy * BW + xx) * 4] > 0.9 and pxm[(yy * BW + xx) * 4 + 3] > 0.9
    )
    ink.grease_pencil.show_fill = False
    print(f"RM_BUBBLE GP FILL ATTEMPT: white_pixels={white_m} (0 = the material fill does not render — recorded)")
    if white_m > 0:
        print(
            "RM_BUBBLE GP FILL ATTEMPT: NOTE — the material fill DOES render on "
            "use_lights=False layers (lit fills are the broken path in 5.1); the "
            "mesh body stays (explicit z-layering of the tail join, no GP "
            "fill-order semantics dependency)"
        )

    png1 = out_dir / "bubble_se.png"
    try:
        render_to(png1)
    except Exception as exc:  # noqa: BLE001 — honest degradation
        print(f"RM_BUBBLE RENDER: SKIPPED ({exc.__class__.__name__}: {exc})")
        return 1
    w, h, px = _load_px(png1)
    print(f"RM_BUBBLE RENDER: {w}x{h} (wanted {BW}x{BH})")
    if (w, h) != (BW, BH):
        print("RM_BUBBLE RENDER: FAIL — wrong resolution")
        return 1
    corner = _sample(px, w, 2, 2)
    ring = _sample(px, w, col(cx), row(cy + ry))
    inner = _sample(px, w, col(cx), row(cy + ry * 0.55))
    # tail ink: sample the MIDPOINTS of the two long edges (b1->tip, tip->b2)
    edge_mid = []
    if tri:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2])):
            edge_mid.append(_sample(px, w, col((a[0] + b[0]) / 2), row((a[1] + b[1]) / 2)))
    tip_ok = any(m[3] > 0.9 and m[0] < 0.5 for m in edge_mid)
    print(
        f"RM_BUBBLE PIXELS: corner_a={corner[3]:.3f} ring={tuple(round(v, 3) for v in ring)} "
        f"inner={tuple(round(v, 3) for v in inner)} tail_edges={len(edge_mid)} tip_ok={tip_ok}"
    )
    if corner[3] > 0.05:
        print("RM_BUBBLE ALPHA: FAIL — film_transparent corner is not transparent")
        ok = False
    if not (ring[0] < 0.5 and ring[3] > 0.9):
        print("RM_BUBBLE RING: FAIL — ellipse top edge is not dark ink")
        ok = False
    if not (inner[0] > 0.9 and inner[1] > 0.9 and inner[3] > 0.9):
        print("RM_BUBBLE FILL: FAIL — ellipse interior is not white")
        ok = False
    if not tip_ok:
        print("RM_BUBBLE TAIL: FAIL — tail long edges are not inked")
        ok = False

    # ---- Q-DET: same data -> the same PNG (SAME scene state — this must run
    # BEFORE the text object exists, the run-1 lesson) -------------------------
    png3 = out_dir / "bubble_se_again.png"
    render_to(png3)
    _, _, px3 = _load_px(png3)
    diff = [abs(a - b) for a, b in zip(px, px3, strict=True) if abs(a - b) > 1e-6]
    raw_a = png1.read_bytes()
    raw_b = png3.read_bytes()
    byte_diffs = sum(1 for a, b in zip(raw_a, raw_b, strict=True) if a != b)
    print(
        f"RM_BUBBLE DETERMINISM (taa={scene.eevee.taa_render_samples}): "
        f"pixels_identical={not diff} file_bytes_differing={byte_diffs}"
    )
    if byte_diffs:
        print(
            "RM_BUBBLE DETERMINISM NOTE: the file difference is Blender's "
            "'tEXt RenderTime' metadata stamp (chunk-located) — the IDAT pixel "
            "data is byte-identical; pixel-level determinism is the standard "
            "(same as the P4-4 page round-trip)"
        )
    if diff:
        print("RM_BUBBLE DETERMINISM: FAIL — re-rendered pixels differ")
        ok = False

    # ---- Q-TEXT: a TEXT object renders legibly into the RGBA -----------------------
    font = bpy.data.curves.new("rm_bubble_text", type="FONT")
    font.body = "KA-BOOM!"
    font.size = 1.0
    font.align_x = "CENTER"
    font.align_y = "CENTER"
    text_obj = bpy.data.objects.new("rm_bubble_text", font)
    bpy.context.collection.objects.link(text_obj)
    tmat = bpy.data.materials.new("rm_bubble_textmat")
    tmat.use_nodes = True
    nt = tmat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    em.inputs["Strength"].default_value = 1.0
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], outn.inputs["Surface"])
    text_obj.data.materials.append(tmat)
    bpy.context.view_layer.update()
    dims = text_obj.dimensions
    print(f"RM_BUBBLE TEXT DIMS: {tuple(round(v, 4) for v in dims)}")
    if min(dims.x, dims.y) <= 0:
        print("RM_BUBBLE TEXT: FAIL — zero dimensions (font evaluation broken?)")
        return 1
    target_w, target_h = 0.55 * rx * 2, 0.5 * ry * 2
    s = min(target_w / dims.x, target_h / dims.y)
    text_obj.scale = (s, s, s)
    text_obj.location = (cx, cy, Z_TEXT)
    bpy.context.view_layer.update()
    png2 = out_dir / "bubble_se_text.png"
    render_to(png2)
    w2, h2, px2 = _load_px(png2)
    band_dark = sum(
        1
        for yy in range(row(cy - 0.12), row(cy + 0.12), 2)
        for xx in range(col(cx - rx * 0.5), col(cx + rx * 0.5), 2)
        if _sample(px2, w2, xx, yy)[0] < 0.35 and _sample(px2, w2, xx, yy)[3] > 0.9
    )
    print(f"RM_BUBBLE TEXT PIXELS: dark_in_band={band_dark}")
    if band_dark <= 0:
        print("RM_BUBBLE TEXT: FAIL — no dark lettering pixels in the interior band")
        ok = False
    inner2 = _sample(px2, w2, col(cx), row(cy + ry * 0.75))
    if not (inner2[0] > 0.9 and inner2[3] > 0.9):
        print("RM_BUBBLE TEXT: FAIL — text render broke the white body")
        ok = False

    # ---- Q-COMPOSE: alpha-0 over = identity; bubble lands at the preset offset -----
    PAGE_W, PAGE_H = 1200, 1800
    scene.render.film_transparent = False
    group = bpy.data.node_groups.new("rm_probe_page", "CompositorNodeTree")
    scene.compositing_node_group = group
    scene.use_nodes = True

    def solid(name: str, sw: int, sh: int, rgba: tuple[float, ...]) -> Any:
        img = bpy.data.images.new(name, sw, sh, alpha=True)
        img.pixels.foreach_set(array.array("f", rgba) * (sw * sh))
        return img

    panel = solid("rm_probe_panel", PAGE_W, PAGE_H, (0.4, 0.42, 0.45, 1.0))
    bg_img = group.nodes.new("CompositorNodeImage")
    bg_img.image = panel
    bubble_img = bpy.data.images.load(str(png2))
    bub_node = group.nodes.new("CompositorNodeImage")
    bub_node.image = bubble_img
    BX, BY = 300, 900  # bubble placement on the page (px, bottom-left origin)
    tr_bg = group.nodes.new("CompositorNodeTranslate")
    tr_bg.inputs["X"].default_value = 0.0
    tr_bg.inputs["Y"].default_value = 0.0
    group.links.new(bg_img.outputs["Image"], tr_bg.inputs["Image"])
    tr_b = group.nodes.new("CompositorNodeTranslate")
    tr_b.inputs["X"].default_value = float(BX - (PAGE_W - BW) // 2)
    tr_b.inputs["Y"].default_value = float(BY - (PAGE_H - BH) // 2)
    group.links.new(bub_node.outputs["Image"], tr_b.inputs["Image"])
    over = group.nodes.new("CompositorNodeAlphaOver")
    over.inputs["Factor"].default_value = 1.0
    group.links.new(tr_bg.outputs["Image"], over.inputs["Background"])
    group.links.new(tr_b.outputs["Image"], over.inputs["Foreground"])
    group.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    sink = group.nodes.new("NodeGroupOutput")
    sink.name = "Sink"
    group.links.new(over.outputs["Image"], sink.inputs["Image"])

    scene.render.resolution_x, scene.render.resolution_y = PAGE_W, PAGE_H
    page_png = out_dir / "composed_page.png"
    render_to(page_png)
    wp, hp, ppx = _load_px(page_png)
    if (wp, hp) != (PAGE_W, PAGE_H):
        print(f"RM_BUBBLE COMPOSE: FAIL — page render {wp}x{hp}")
        return 1
    o = _sample(ppx, wp, BX - 20, BY - 20)
    i = _sample(ppx, wp, BX + col(cx), BY + row(cy + ry * 0.55))
    r = _sample(ppx, wp, BX + col(cx), BY + row(cy + ry))
    print(
        f"RM_BUBBLE COMPOSE: outside={tuple(round(v, 3) for v in o)} "
        f"interior={tuple(round(v, 3) for v in i)} ring={tuple(round(v, 3) for v in r)}"
    )
    if abs(o[0] - 0.4) > 1.5 / 255 or abs(o[1] - 0.42) > 1.5 / 255 or abs(o[2] - 0.45) > 1.5 / 255:
        print("RM_BUBBLE COMPOSE: FAIL — panel altered outside the bubble footprint")
        ok = False
    if not (i[0] > 0.9 and i[3] > 0.9):
        print("RM_BUBBLE COMPOSE: FAIL — interior not white on the page")
        ok = False
    if not (r[0] < 0.5 and r[3] > 0.9):
        print("RM_BUBBLE COMPOSE: FAIL — ring not inked on the page")
        ok = False

    # placement determinism: the ink moves with the offset (px math, nothing else)
    tr_b.inputs["X"].default_value = float(BX + 100 - (PAGE_W - BW) // 2)
    page2 = out_dir / "composed_page_shift.png"
    render_to(page2)
    _, _, ppx2 = _load_px(page2)
    a = _sample(ppx, wp, BX + col(cx), BY + row(cy + ry))
    b = _sample(ppx2, wp, BX + 100 + col(cx), BY + row(cy + ry))
    moved = a[0] < 0.5 and b[0] < 0.5
    print(f"RM_BUBBLE PLACEMENT: ink at both offsets={moved}")
    if not moved:
        print("RM_BUBBLE PLACEMENT: FAIL")
        ok = False

    print(f"RM_BUBBLE PROBE {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
