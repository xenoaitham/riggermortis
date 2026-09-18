"""P4-4 panel pages — layout presets as DATA, deterministic page assembly.

A page preset (``presets/pages/*.json``) is N panel rectangles over a page
size, each bound to a SCENE camera (the layout is scene-independent data;
``reading_direction`` is data for panel order and export, never a code
fork). The builder renders one PNG per panel (per-render camera +
resolution + filepath swap) and assembles the page as a compositor node
group rendered once at page resolution.

The assembly mechanics were probe-verified on 5.1 headless
(``xtask/page_probe.py``, ``RM_PAGE`` lines; findings in docs/STYLE.md):

- the compositor CENTERS images smaller than the render buffer before
  ``Translate`` applies — every offset is corrected:
  ``t = desired - (page - img) // 2`` per axis (uncorrected offsets
  overshoot by exactly the centering term);
- the page background must be a FULL-PAGE solid image (a bare ``RGB``
  node has no spatial extent — outside image footprints the chain goes
  transparent-black);
- 5.1 ``Translate`` takes SEPARATE ``X``/``Y`` value sockets (the single
  ``Vector`` input is gone); ``AlphaOver``'s inputs are named
  ``Background``/``Foreground``;
- panel PNGs survive the compositor round-trip BYTE-FAITHFUL when loaded
  with the DEFAULT sRGB colorspace and the page renders with view
  transform ``Standard`` + dither 0 — decode(encode(bytes)) is the
  identity (``Non-Color`` loads FAIL: Standard still encodes).

Deterministic by remove-first + fixed node/image names (the ``style.py``
discipline). Every render entry point stages and RESTORES the render
state it touches. Panels are SINGLE FRAMES; borders are generated
under-rects, never hand-drawn frames.

This module imports WITHOUT bpy (validation + pixel math are pure) so the
CI suite exercises the preset contract; everything engine-facing
lazy-imports bpy like ``style.py``.
"""
from __future__ import annotations

import array
import json
from pathlib import Path
from typing import Any

PAGES_DIR = Path(__file__).resolve().parent / "presets" / "pages"
PAGE_GROUP = "rm_page"
PAGE_IMAGE_PREFIX = "rm_page_"
PANEL_FILE_TEMPLATE = "rm_panel_{:02d}.png"

_ALLOWED = {
    "format",
    "name",
    "reading_direction",
    "style",
    "page",
    "gutter",
    "panels",
    "notes",
}


def known_pages() -> list[str]:
    """Shipped page presets, sorted (deterministic)."""
    return sorted(p.stem for p in PAGES_DIR.glob("*.json"))


def _known_style_names() -> list[str]:
    """Shipped STYLE preset names (for panel ``style`` validation).

    A local re-glob of the presets dir rather than an import of
    ``style``: this module must stay importable without bpy and the
    package ``__init__`` pulls bpy at module level.
    """
    return sorted(p.stem for p in PAGES_DIR.parent.glob("*.json"))


def _hex_to_rgba(raw: Any) -> tuple[float, float, float, float]:
    text = str(raw).strip()
    if not text.startswith("#") or len(text) != 7:
        raise ValueError(f"page color must be #rrggbb (got {raw!r})")
    return (
        int(text[1:3], 16) / 255.0,
        int(text[3:5], 16) / 255.0,
        int(text[5:7], 16) / 255.0,
        1.0,
    )


def load_page(name: str) -> dict[str, Any]:
    """Load a shipped page preset by name (or an explicit page .json path)."""
    if name.endswith(".json"):
        path = Path(name)
    else:
        path = PAGES_DIR / f"{name}.json"
    if not path.is_file():
        raise ValueError(
            f"unknown page preset: {name!r} (hint: known pages: "
            + ", ".join(known_pages())
            + " — or pass an explicit page .json path)"
        )
    page = json.loads(path.read_text(encoding="utf-8"))
    _validate_page(page, path.name)
    return page


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_page(page: dict[str, Any], source: str) -> None:
    unknown = set(page) - _ALLOWED
    if unknown:
        raise ValueError(f"{source}: unknown page fields: {sorted(unknown)}")
    if page.get("format") != 1:
        raise ValueError(f"{source}: page format must be 1")
    direction = page.get("reading_direction")
    if direction not in {"rtl", "ltr"}:
        raise ValueError(
            f"{source}: reading_direction must be 'rtl' or 'ltr' "
            f"(got {direction!r})"
        )
    styles = _known_style_names()
    page_style = page.get("style")
    if page_style is not None and page_style not in styles:
        raise ValueError(
            f"{source}: page style {page_style!r} is not a shipped style "
            f"preset (hint: known styles: {', '.join(styles)})"
        )
    pg = page.get("page")
    if not isinstance(pg, dict):
        raise ValueError(f"{source}: 'page' section is required")
    page_unknown = set(pg) - {"width_px", "height_px", "background", "bleed", "border"}
    if page_unknown:
        raise ValueError(f"{source}: unknown page.page fields: {sorted(page_unknown)}")
    for key in ("width_px", "height_px"):
        value = pg.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{source}: page.{key} must be a positive int")
    _hex_to_rgba(pg.get("background", ""))
    bleed = pg.get("bleed", 0.0)
    if not _is_num(bleed) or bleed < 0:
        raise ValueError(f"{source}: page.bleed must be a number >= 0")
    border = pg.get("border")
    if border is not None:
        if not isinstance(border, dict):
            raise ValueError(f"{source}: page.border must be an object")
        border_unknown = set(border) - {"width_px", "color"}
        if border_unknown:
            raise ValueError(
                f"{source}: unknown page.border fields: {sorted(border_unknown)}"
            )
        width = border.get("width_px")
        if not isinstance(width, int) or isinstance(width, bool) or width < 0:
            raise ValueError(f"{source}: page.border.width_px must be an int >= 0")
        _hex_to_rgba(border.get("color", ""))
    gutter = page.get("gutter", 0.0)
    if not _is_num(gutter) or gutter < 0:
        raise ValueError(f"{source}: gutter must be a number >= 0")

    panels = page.get("panels")
    if not isinstance(panels, list) or not panels:
        raise ValueError(f"{source}: panels must be a non-empty list")
    rects: list[tuple[float, float, float, float]] = []
    for index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            raise ValueError(f"{source}: panel {index} must be an object")
        panel_unknown = set(panel) - {"rect", "camera", "style"}
        if panel_unknown:
            raise ValueError(
                f"{source}: unknown panel {index} fields: {sorted(panel_unknown)}"
            )
        rect = panel.get("rect")
        if (
            not isinstance(rect, list)
            or len(rect) != 4
            or not all(_is_num(v) for v in rect)
        ):
            raise ValueError(
                f"{source}: panel {index}.rect must be [x, y, w, h] numbers"
            )
        x, y, w, h = (float(v) for v in rect)
        if w <= 0 or h <= 0:
            raise ValueError(f"{source}: panel {index} rect must have positive w/h")
        limit = 1.0 + bleed
        if not (-bleed <= x and x + w <= limit and -bleed <= y and y + h <= limit):
            raise ValueError(
                f"{source}: panel {index} rect {rect} leaves the page "
                f"(bleed allows [{-bleed}, {limit}])"
            )
        camera = panel.get("camera")
        if not isinstance(camera, str) or not camera:
            raise ValueError(
                f"{source}: panel {index}.camera must be a scene object name"
            )
        style_name = panel.get("style")
        if style_name is not None and style_name not in styles:
            raise ValueError(
                f"{source}: panel {index}.style {style_name!r} is not a "
                f"shipped style preset (hint: known styles: "
                f"{', '.join(styles)})"
            )
        rects.append((x, y, w, h))

    # Geometry: pairwise overlaps are always an error; axis-aligned
    # neighbors must keep >= gutter on the separating axis (checked in
    # pixels — gutter is a fraction of the respective page axis; a
    # half-pixel slack absorbs float representation error so a layout
    # EXACTLY at the gutter validates, e.g. 0.57 - 0.55 lands a hair
    # under 0.02 in binary floats). Reading direction is DATA and is
    # never validated.
    width, height = int(pg["width_px"]), int(pg["height_px"])
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            ax, ay, aw, ah = rects[i]
            bx, by, bw, bh = rects[j]
            overlap_x = min(ax + aw, bx + bw) - max(ax, bx)
            overlap_y = min(ay + ah, by + bh) - max(ay, by)
            if overlap_x > 0 and overlap_y > 0:
                raise ValueError(f"{source}: panels {i} and {j} overlap")
            gap_x = max(ax, bx) - min(ax + aw, bx + bw)
            gap_y = max(ay, by) - min(ay + ah, by + bh)
            if overlap_y > 0 and gap_x * width + 0.5 < gutter * width:
                raise ValueError(
                    f"{source}: panels {i} and {j} horizontal gap "
                    f"{gap_x * width:.1f}px < gutter {gutter * width:.1f}px"
                )
            if overlap_x > 0 and gap_y * height + 0.5 < gutter * height:
                raise ValueError(
                    f"{source}: panels {i} and {j} vertical gap "
                    f"{gap_y * height:.1f}px < gutter {gutter * height:.1f}px"
                )


def panel_px(page: dict[str, Any], index: int) -> tuple[int, int, int, int]:
    """Panel rect in PIXELS (x, y, w, h), origin bottom-left.

    Edge-based rounding (each edge rounded independently, w/h from the
    edge difference) so gutters stay exact in pixels.
    """
    pg = page["page"]
    width, height = int(pg["width_px"]), int(pg["height_px"])
    x, y, w, h = (float(v) for v in page["panels"][index]["rect"])
    x0, x1 = round(x * width), round((x + w) * width)
    y0, y1 = round(y * height), round((y + h) * height)
    return (x0, y0, x1 - x0, y1 - y0)


def render_panels(
    scene: Any,
    page: dict[str, Any],
    out_dir: Any,
    subject: Any = None,
) -> dict[str, Any]:
    """Render one PNG per panel (``rm_panel_XX.png`` names, index = the
    preset's reading order).

    Style semantics: an optional page-level ``style`` is the BASE look for
    unstyled panels (apply it to ``subject`` before calling); a per-panel
    ``style`` restyles ``subject`` through the P4-1/2/3 builders for that
    panel's render only. Style application is PERSISTENT in the scene, so
    the render order is: UNSTYLED panels first (index order — they carry
    the base look), then styled panels (index order — each restyles for
    its own render; the last styled look persists afterward). The report
    is in reading order regardless. Missing camera / unknown style /
    styled panel without a ``subject`` = actionable errors. Render staging
    (camera/resolution/percentage/filepath) is restored; the view
    transform is deliberately NOT staged: panel pixels carry whatever the
    scene's transform does (the style look), while the page assembly's
    byte-identity contract is independent of it (module docstring).
    """
    import bpy

    from riggermortis_addon import style

    _validate_page(page, f"{page.get('name', 'page')}.json")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cameras = {o.name: o for o in scene.objects if o.type == "CAMERA"}
    render = scene.render
    staged = (
        scene.camera,
        render.resolution_x,
        render.resolution_y,
        render.resolution_percentage,
        render.filepath,
    )
    try:
        entries: dict[int, dict[str, Any]] = {}
        # Unstyled first, then styled — style changes must not leak into
        # unstyled panels rendered later (persistent-scene semantics).
        ordered = [i for i, p in enumerate(page["panels"]) if p.get("style") is None]
        ordered += [i for i, p in enumerate(page["panels"]) if p.get("style") is not None]
        for index in ordered:
            panel = page["panels"][index]
            cam = cameras.get(panel["camera"])
            if cam is None:
                available = ", ".join(sorted(cameras)) or "none"
                raise ValueError(
                    f"panel {index} camera {panel['camera']!r} is not a "
                    f"camera in this scene (hint: scene cameras: {available})"
                )
            style_name = panel.get("style")
            if style_name is not None:
                if subject is None:
                    raise ValueError(
                        f"panel {index} has style {style_name!r} but no "
                        "subject was given (hint: pass the object the "
                        "style builders should restyle)"
                    )
                preset = style.load_preset(style_name)
                style.build_toon_material(subject, preset)
                if preset.get("lineart") is not None:
                    style.build_lineart(subject, preset)
                else:
                    style.remove_lineart()
                if preset.get("tones") is not None:
                    style.build_screentones(scene, preset)
                else:
                    style.remove_screentones(scene)
            x, y, w, h = panel_px(page, index)
            path = out / PANEL_FILE_TEMPLATE.format(index)
            scene.camera = cam
            render.resolution_x, render.resolution_y = w, h
            render.resolution_percentage = 100
            render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            entries[index] = {
                "index": index,
                "camera": panel["camera"],
                "file": str(path),
                "width_px": w,
                "height_px": h,
                "style": style_name,
            }
    finally:
        (
            scene.camera,
            render.resolution_x,
            render.resolution_y,
            render.resolution_percentage,
            render.filepath,
        ) = staged
    return {
        "panels": [entries[i] for i in sorted(entries)],
        "out_dir": str(out),
    }


def build_page_graph(
    scene: Any,
    page: dict[str, Any],
    panel_files: list[Any],
) -> dict[str, Any]:
    """Assemble the page as the scene's compositor node group (``rm_page``).

    REPLACES the scene's compositor group — with the tones graph this is
    a sequential stage: panels render styled+toned FIRST, then the page
    graph assembles. The replaced group (e.g. ``rm_tones``) is unlinked,
    not removed — its own remover owns that. Remove-first determinism:
    the ``rm_page`` group and ``rm_page_*`` images are removed before
    creation; node/image names are fixed. The sink follows the P4-3 rule
    (interface socket first, then EXACTLY ONE Group Output node).
    """
    import bpy

    _validate_page(page, f"{page.get('name', 'page')}.json")
    if len(panel_files) != len(page["panels"]):
        raise ValueError(
            f"expected {len(page['panels'])} panel files, got "
            f"{len(panel_files)} (hint: render_panels returns exactly one "
            "PNG per panel in reading order)"
        )
    remove_page(scene)
    pg = page["page"]
    width, height = int(pg["width_px"]), int(pg["height_px"])
    border = pg.get("border") or {}
    border_px = int(border.get("width_px", 0) or 0)
    border_rgba = _hex_to_rgba(border.get("color", "#000000"))
    bg_rgba = _hex_to_rgba(pg.get("background", "#ffffff"))

    group = bpy.data.node_groups.new(PAGE_GROUP, "CompositorNodeTree")
    scene.use_nodes = True
    scene.compositing_node_group = group

    def solid_image(name: str, w: int, h: int, rgba: tuple[float, ...]) -> Any:
        img = bpy.data.images.new(name, w, h, alpha=True)
        img.pixels.foreach_set(array.array("f", rgba) * (w * h))
        return img

    def placed(name: str, image: Any, x: int, y: int) -> Any:
        node = group.nodes.new("CompositorNodeImage")
        node.name = name
        node.image = image
        tr = group.nodes.new("CompositorNodeTranslate")
        tr.name = name + "Pos"
        # Centering correction (probe-recorded): the compositor centers
        # images smaller than the buffer before translating.
        tr.inputs["X"].default_value = float(x - (width - image.size[0]) // 2)
        tr.inputs["Y"].default_value = float(y - (height - image.size[1]) // 2)
        group.links.new(node.outputs["Image"], tr.inputs["Image"])
        return tr.outputs["Image"]

    def over(name: str, base: Any, top: Any) -> Any:
        node = group.nodes.new("CompositorNodeAlphaOver")
        node.name = name
        node.inputs["Factor"].default_value = 1.0
        group.links.new(base, node.inputs["Background"])
        group.links.new(top, node.inputs["Foreground"])
        return node.outputs["Image"]

    chain = placed(
        "BGImg",
        solid_image(f"{PAGE_IMAGE_PREFIX}bg", width, height, bg_rgba),
        0,
        0,
    )
    images = [f"{PAGE_IMAGE_PREFIX}bg"]
    entries = []
    for index, panel in enumerate(page["panels"]):
        x, y, w, h = panel_px(page, index)
        if border_px > 0:
            border_img = solid_image(
                f"{PAGE_IMAGE_PREFIX}border_{index:02d}",
                w + 2 * border_px,
                h + 2 * border_px,
                border_rgba,
            )
            images.append(border_img.name)
            chain = over(
                f"B{index:02d}Over",
                chain,
                placed(
                    f"B{index:02d}Img", border_img, x - border_px, y - border_px
                ),
            )
        expected = f"{PAGE_IMAGE_PREFIX}panel_{index:02d}"
        # DEFAULT sRGB colorspace (no override) — the byte-identity
        # contract with the Standard view transform (module docstring).
        panel_img = bpy.data.images.load(str(panel_files[index]))
        panel_img.name = expected
        if panel_img.name != expected:
            raise ValueError(
                f"page image name collision: {expected!r} is owned by a "
                "user datablock (hint: clear or rename it first)"
            )
        images.append(panel_img.name)
        chain = over(
            f"P{index:02d}Over", chain, placed(f"P{index:02d}Img", panel_img, x, y)
        )
        entries.append(
            {
                "index": index,
                "camera": panel["camera"],
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "style": panel.get("style"),
            }
        )

    group.interface.new_socket(
        name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
    )
    sink = group.nodes.new("NodeGroupOutput")
    sink.name = "Sink"
    group.links.new(chain, sink.inputs["Image"])

    return {
        "group": group.name,
        "images": images,
        "nodes": [node.name for node in group.nodes],
        "panels": entries,
        "background": pg.get("background", "#ffffff"),
        "size": [width, height],
    }


def render_page(scene: Any, page: dict[str, Any], out_path: Any) -> dict[str, Any]:
    """Render the assembled page (call ``build_page_graph`` first).

    Stages page resolution + ``Standard`` view transform + dither 0 +
    filepath (the byte-identity contract), renders, RESTORES everything.
    """
    import bpy

    _validate_page(page, f"{page.get('name', 'page')}.json")
    group = getattr(scene, "compositing_node_group", None)
    if group is None or group.name != PAGE_GROUP:
        raise ValueError(
            "the scene's compositor graph is not the page assembly (hint: "
            "call build_page_graph before render_page)"
        )
    pg = page["page"]
    width, height = int(pg["width_px"]), int(pg["height_px"])
    render = scene.render
    staged = (
        render.resolution_x,
        render.resolution_y,
        render.resolution_percentage,
        render.filepath,
        scene.view_settings.view_transform,
        render.dither_intensity,
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        render.resolution_x, render.resolution_y = width, height
        render.resolution_percentage = 100
        render.filepath = str(out)
        scene.view_settings.view_transform = "Standard"
        render.dither_intensity = 0.0
        bpy.ops.render.render(write_still=True)
    finally:
        (
            render.resolution_x,
            render.resolution_y,
            render.resolution_percentage,
            render.filepath,
            scene.view_settings.view_transform,
            render.dither_intensity,
        ) = staged
    return {"file": str(out), "size": [width, height]}


def remove_page(scene: Any) -> bool:
    """Remove the page machinery (compositor group + ``rm_page_*`` images).

    An unrelated compositor group is never touched (the
    ``remove_screentones`` rule). Returns True when our group was removed.
    """
    import bpy

    removed = False
    current = getattr(scene, "compositing_node_group", None)
    if current is not None and current.name == PAGE_GROUP:
        scene.compositing_node_group = None
        bpy.data.node_groups.remove(current)
        removed = True
    elif PAGE_GROUP in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[PAGE_GROUP])
    for img in list(bpy.data.images):
        if img.name.startswith(PAGE_IMAGE_PREFIX):
            bpy.data.images.remove(img)
    return removed
