"""P4-5 speech bubbles — generated geometry + typeset text as page DATA.

A bubble is a per-panel entry on a P4-4 page preset (``bubbles``: pos /
size / tail / text — schema in docs/STYLE.md). The builder renders one
RGBA PNG per bubble (deterministic global order: panel order, then bubble
index) which ``pages.build_page_graph`` composites over the panels —
placement is pure page-pixel math (``pages.bubble_px``), never scene state.

Mechanism, probe-verified on 5.1 headless (``xtask/bubble_probe.py``,
``RM_BUBBLE`` lines; findings in docs/STYLE.md):

- **The body is a MESH** (ellipse n-gon + tail triangle, z-layered, unlit
  Emission — the P4-1 house trick). The GPv3 FILL was probed to death and
  is a dead end on 5.1: lit fills vanish (the material fill only renders
  on ``use_lights=False`` layers), stroke fill_color/fill_opacity do not
  render, and the only fill ops are interactive cursor tools. A mesh body
  needs no fill-engine semantics and z-orders the tail join explicitly.
- **The ink is GPv3 strokes** (the proven path from P4-2): ops-created GP
  + canonical renames, layer ``use_lights=False`` so the ink is flat
  vertex_color (scene-independent), ellipse = closed 64-point stroke, tail
  = OPEN 3-point polyline (base1 -> tip -> base2 — no ink edge inside the
  body) drawn at a higher z so its white mesh fill covers the ellipse ink
  at the join.
- **The lettering is a TEXT object** (emission black, unlit), auto-fit
  deterministically: the font object's bounding box is measured and
  scaled into a fixed interior box — same string, same layout, always.
- **Film transparent + Standard + dither 0** renders the RGBA overlay;
  compositor UNSET during bubble renders (no tones dots on lettering, no
  stale page graph). Re-renders are pixel-identical (the only file-byte
  difference is Blender's ``tEXt RenderTime`` metadata stamp — measured).

Everything is canonically named ``rm_bubble*`` (remove-first discipline).
Bubbles are GENERATED GEOMETRY + TYPESET TEXT — no "hand-lettered" claims,
ever.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

BUBBLE_PREFIX = "rm_bubble"
BODY_OBJECT = "rm_bubble_body"
GP_OBJECT = "rm_bubble_gp"
TEXT_OBJECT = "rm_bubble_text"
CAM_OBJECT = "rm_bubble_cam"
FILL_MATERIAL = "rm_bubble_fill"
INK_MATERIAL = "rm_bubble_ink"
TEXT_MATERIAL = "rm_bubble_textmat"
FILE_TEMPLATE = "rm_bubble_{:02d}.png"

ELLIPSE_N = 64
OUTLINE_PX = 5.0  # ink stroke half-width at a 420 px-tall footprint
OUTLINE_REF_PX = 420.0
BAND_FRAC = 0.30  # tail band reserved from the footprint along the shift axis
MARGIN_M = 0.03  # body margin inside the footprint (world meters, height = 1.0)
TEXT_W_FRAC = 0.55  # auto-fit box as a fraction of the ellipse extents
TEXT_H_FRAC = 0.50
# z layering: mesh fill under ink; tail fill OVER the ellipse ink so the
# join reads open; tail ink on top; lettering frontmost.
Z_ELL_FILL = -0.002
Z_ELL_INK = 0.0
Z_TAIL_FILL = 0.002
Z_TAIL_INK = 0.003
Z_TEXT = 0.004

_TAIL_DIRS = {
    "n": (0.0, 1.0),
    "s": (0.0, -1.0),
    "e": (1.0, 0.0),
    "w": (-1.0, 0.0),
    "ne": (1.0, 1.0),
    "nw": (-1.0, 1.0),
    "se": (1.0, -1.0),
    "sw": (-1.0, -1.0),
}


def remove_bubbles() -> None:
    """Remove every ``rm_bubble*`` object/data/material (deterministic)."""
    import bpy

    for ob in list(bpy.data.objects):
        if ob.name.startswith(BUBBLE_PREFIX):
            bpy.data.objects.remove(ob)
    for coll in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.cameras,
        bpy.data.grease_pencils,
    ):
        for datablock in list(coll):
            if datablock.name.startswith(BUBBLE_PREFIX) and datablock.users == 0:
                coll.remove(datablock)
    for mat in list(bpy.data.materials):
        if mat.name.startswith(BUBBLE_PREFIX):
            bpy.data.materials.remove(mat)


def _ellipse_geometry(w_m: float, tail: str) -> dict[str, float]:
    """Ellipse center + radii, pushed AWAY from the tail by the band."""
    if tail == "none":
        return {"cx": 0.0, "cy": 0.0, "rx": w_m / 2 - MARGIN_M, "ry": 0.5 - MARGIN_M}
    dx, dy = _TAIL_DIRS[tail]
    vertical = abs(dy) > 0  # vertical band for n/s and diagonals
    band = BAND_FRAC * (1.0 if vertical else w_m)
    cx = 0.0 if vertical else -math.copysign(band / 2, dx)
    cy = -math.copysign(band / 2, dy) if vertical else 0.0
    return {
        "cx": cx,
        "cy": cy,
        "rx": w_m / 2 - MARGIN_M if vertical else (w_m - band) / 2 - MARGIN_M,
        "ry": (1.0 - band) / 2 - MARGIN_M if vertical else 0.5 - MARGIN_M,
    }


def _tail_geometry(
    tail: str, w_m: float, ell: dict[str, float]
) -> list[tuple[float, float]]:
    """Open tail polyline [base1, tip, base2] in footprint coordinates.

    The tip reaches the FOOTPRINT edge (corner for diagonals, edge midpoint
    for cardinals) — footprint coordinates, not ellipse coordinates.
    """
    if tail == "none":
        return []
    dx, dy = _TAIL_DIRS[tail]
    cx, cy = ell["cx"], ell["cy"]
    diag = abs(dx) > 0 and abs(dy) > 0
    mx, my = w_m / 2 - MARGIN_M, 0.5 - MARGIN_M
    if diag:
        tip = (math.copysign(mx, dx), math.copysign(my, dy))
    elif abs(dx) == 0:
        tip = (cx, math.copysign(my, dy))
    else:
        tip = (math.copysign(mx, dx), cy)
    theta = math.atan2(tip[1] - cy, tip[0] - cx)
    pull = 0.94
    b1 = (
        cx + math.cos(theta + 0.38) * ell["rx"] * pull,
        cy + math.sin(theta + 0.38) * ell["ry"] * pull,
    )
    b2 = (
        cx + math.cos(theta - 0.38) * ell["rx"] * pull,
        cy + math.sin(theta - 0.38) * ell["ry"] * pull,
    )
    return [b1, tip, b2]


def _unlit_material(name: str, rgba: tuple[float, float, float, float]) -> Any:
    """Emission strength 1 = unlit by construction (the P4-1 trick)."""
    import bpy

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    em = tree.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgba
    em.inputs["Strength"].default_value = 1.0
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    tree.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def build_bubble_objects(tail: str, text: str, bw: int, bh: int) -> dict[str, Any]:
    """Build the bubble stage for one footprint (remove-first).

    ``bw``/``bh`` are the footprint's pixel size — the world framing
    derives from them (world height 1.0 m, width ``bw/bh``; ortho camera
    with HORIZONTAL sensor fit maps the scale to the width, so any aspect
    is framed exactly). Returns the LOCAL geometry the gate samples from
    (ellipse center/radii in bubble-local pixels, +Y = up) — deterministic
    from the same inputs by construction.
    """
    import bpy

    if not hasattr(bpy.types, "GreasePencilDrawing"):
        raise ValueError(
            "this Blender has no GPv3 drawings API (pre-4.3-class — hint: "
            "bubbles need a 4.3+/5.x Blender; see docs/STYLE.md)"
        )
    if bw <= 0 or bh <= 0:
        raise ValueError(f"bubble footprint must be positive px (got {bw}x{bh})")
    remove_bubbles()
    w_m = bw / bh
    ell = _ellipse_geometry(w_m, tail)
    tri = _tail_geometry(tail, w_m, ell)
    outline_w = OUTLINE_PX / OUTLINE_REF_PX

    # body mesh: ellipse n-gon (under) + tail triangle (over the ellipse ink)
    verts = [
        (
            ell["cx"] + ell["rx"] * math.cos(2.0 * math.pi * i / ELLIPSE_N),
            ell["cy"] + ell["ry"] * math.sin(2.0 * math.pi * i / ELLIPSE_N),
            Z_ELL_FILL,
        )
        for i in range(ELLIPSE_N)
    ]
    faces = [list(range(ELLIPSE_N))]
    if tri:
        base = len(verts)
        verts += [(x, y, Z_TAIL_FILL) for x, y in tri]
        faces.append([base, base + 1, base + 2])
    mesh = bpy.data.meshes.new(BODY_OBJECT)
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(_unlit_material(FILL_MATERIAL, (1.0, 1.0, 1.0, 1.0)))
    body_obj = bpy.data.objects.new(BODY_OBJECT, mesh)
    bpy.context.collection.objects.link(body_obj)

    # GP ink overlay: ops-create (the proven path) + canonical renames
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    body_obj.select_set(True)
    view_layer.objects.active = body_obj
    known = set(bpy.data.objects.keys())
    try:
        bpy.ops.object.grease_pencil_add(type="EMPTY")
    finally:
        view_layer.objects.active = prev_active
    created = [
        o
        for o in bpy.data.objects
        if o.name not in known and o.type == "GREASEPENCIL"
    ]
    if len(created) != 1:
        raise ValueError(
            f"ops grease_pencil_add created {len(created)} Grease Pencil "
            "objects (expected exactly 1 — hint: re-check this Blender "
            "version against xtask/bubble_probe.py)"
        )
    gp_obj = created[0]
    gp_obj.name = GP_OBJECT
    gp = gp_obj.data
    gp.name = GP_OBJECT
    layer = gp.layers[0]
    layer.name = "Bubbles"
    layer.use_lights = False  # flat vertex_color ink, scene-independent
    ink = gp.materials[0]
    ink.name = INK_MATERIAL
    ink.grease_pencil.show_fill = False
    ink.grease_pencil.show_stroke = True
    ink.grease_pencil.stroke_style = "SOLID"
    ink.grease_pencil.color = (0.0, 0.0, 0.0, 1.0)
    drawing = layer.frames[0].drawing
    drawing.add_strokes([ELLIPSE_N] + ([3] if tri else []))
    ell_pts = [
        (
            ell["cx"] + ell["rx"] * math.cos(2.0 * math.pi * i / ELLIPSE_N),
            ell["cy"] + ell["ry"] * math.sin(2.0 * math.pi * i / ELLIPSE_N),
            Z_ELL_INK,
        )
        for i in range(ELLIPSE_N)
    ]
    tails_pts = [[(x, y, Z_TAIL_INK) for x, y in tri]] if tri else []
    for stroke, pts, closed in zip(
        list(drawing.strokes), [ell_pts] + tails_pts, [True] + [False] * len(tails_pts),
        strict=True,
    ):
        stroke.cyclic = closed
        for p, (x, y, z) in zip(stroke.points, pts, strict=True):
            p.position = (x, y, z)
            p.radius = outline_w
            p.opacity = 1.0
            p.vertex_color = (0.0, 0.0, 0.0, 1.0)

    # lettering: TEXT object, auto-fit into a fixed interior box
    has_text = bool(text)
    if has_text:
        font = bpy.data.curves.new(TEXT_OBJECT, type="FONT")
        font.body = text
        font.size = 1.0
        font.align_x = "CENTER"
        font.align_y = "CENTER"
        text_obj = bpy.data.objects.new(TEXT_OBJECT, font)
        bpy.context.collection.objects.link(text_obj)
        font.materials.append(
            _unlit_material(TEXT_MATERIAL, (0.0, 0.0, 0.0, 1.0))
        )
        bpy.context.view_layer.update()
        dims = text_obj.dimensions
        if min(dims.x, dims.y) <= 0:
            raise ValueError(
                f"bubble text {text!r} measured zero dimensions (hint: the "
                "font evaluation failed — see xtask/bubble_probe.py)"
            )
        target_w, target_h = (
            TEXT_W_FRAC * 2 * ell["rx"],
            TEXT_H_FRAC * 2 * ell["ry"],
        )
        s = min(target_w / dims.x, target_h / dims.y)
        text_obj.scale = (s, s, s)
        text_obj.location = (ell["cx"], ell["cy"], Z_TEXT)

    cam_data = bpy.data.cameras.new(CAM_OBJECT)
    cam_data.type = "ORTHO"
    cam_data.sensor_fit = "HORIZONTAL"  # ortho_scale maps the width axis
    cam_data.ortho_scale = w_m
    cam = bpy.data.objects.new(CAM_OBJECT, cam_data)
    cam.location = (0.0, 0.0, 5.0)
    bpy.context.collection.objects.link(cam)

    return {
        "tail": tail,
        "text": text,
        "footprint_px": [bw, bh],
        "world": [w_m, 1.0],
        "ellipse": {
            "cx_px": (ell["cx"] / w_m + 0.5) * bw,
            "cy_px": (ell["cy"] + 0.5) * bh,
            "rx_px": ell["rx"] / w_m * bw,
            "ry_px": ell["ry"] * bh,
        },
        "has_text": has_text,
        "objects": [BODY_OBJECT, GP_OBJECT] + ([TEXT_OBJECT] if has_text else []),
    }


def render_bubbles(
    scene: Any,
    page: dict[str, Any],
    out_dir: Any,
) -> dict[str, Any]:
    """Render one RGBA PNG per bubble in deterministic global order.

    Stages + RESTORES: camera, resolution, filepath, film_transparent,
    view transform (``Standard`` + dither 0 — the ink/white identity
    transform), color mode RGBA, the compositor group (UNSET — no tones
    dots on the lettering, no stale page graph compositing the overlay),
    and ``hide_render`` on every non-bubble object. The stage objects are
    removed afterwards (the scene is left as it was found, plus the PNGs).
    """
    import bpy

    from riggermortis_addon import pages as _pages

    _pages._validate_page(page, f"{page.get('name', 'page')}.json")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    total = _pages.page_bubble_count(page)
    if total == 0:
        return {"bubbles": [], "out_dir": str(out)}

    render = scene.render
    staged = (
        scene.camera,
        render.resolution_x,
        render.resolution_y,
        render.resolution_percentage,
        render.filepath,
        render.film_transparent,
        scene.view_settings.view_transform,
        render.dither_intensity,
        render.image_settings.color_mode,
        render.image_settings.color_depth,
        scene.compositing_node_group,
    )
    entries: list[dict[str, Any]] = []
    g_index = 0
    try:
        scene.render.film_transparent = True
        scene.view_settings.view_transform = "Standard"
        render.dither_intensity = 0.0
        render.image_settings.color_mode = "RGBA"
        render.image_settings.color_depth = "8"
        scene.compositing_node_group = None
        for p_index, panel in enumerate(page["panels"]):
            for b_index, bubble in enumerate(panel.get("bubbles") or []):
                x, y, bw, bh = _pages.bubble_px(page, p_index, b_index)
                report = build_bubble_objects(
                    bubble.get("tail", "none"), bubble.get("text", ""), bw, bh
                )
                stage = set(report["objects"] + [CAM_OBJECT])
                hidden = [
                    (ob, ob.hide_render)
                    for ob in scene.objects
                    if ob.name not in stage
                ]
                for ob, _was in hidden:
                    ob.hide_render = True
                cam = bpy.data.objects[CAM_OBJECT]
                try:
                    scene.camera = cam
                    render.resolution_x, render.resolution_y = bw, bh
                    render.resolution_percentage = 100
                    path = out / FILE_TEMPLATE.format(g_index)
                    render.filepath = str(path)
                    bpy.ops.render.render(write_still=True)
                finally:
                    for ob, was in hidden:
                        ob.hide_render = was
                entries.append(
                    {
                        "panel": p_index,
                        "bubble": b_index,
                        "file": str(path),
                        "x": x,
                        "y": y,
                        "w": bw,
                        "h": bh,
                        "tail": report["tail"],
                        "text": report["text"],
                        "ellipse_px": report["ellipse"],
                        "has_text": report["has_text"],
                    }
                )
                g_index += 1
    finally:
        (
            scene.camera,
            render.resolution_x,
            render.resolution_y,
            render.resolution_percentage,
            render.filepath,
            render.film_transparent,
            scene.view_settings.view_transform,
            render.dither_intensity,
            render.image_settings.color_mode,
            render.image_settings.color_depth,
            scene.compositing_node_group,
        ) = staged
        remove_bubbles()
    return {"bubbles": entries, "out_dir": str(out)}
