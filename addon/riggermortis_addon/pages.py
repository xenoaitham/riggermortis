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

_BUBBLE_TAILS = ("n", "ne", "e", "se", "s", "sw", "w", "nw", "none")


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
        panel_unknown = set(panel) - {"rect", "camera", "style", "bubbles", "frame"}
        if panel_unknown:
            raise ValueError(
                f"{source}: unknown panel {index} fields: {sorted(panel_unknown)}"
            )
        frame = panel.get("frame")
        if frame is not None and (
            not isinstance(frame, int) or isinstance(frame, bool) or frame < 0
        ):
            raise ValueError(
                f"{source}: panel {index}.frame must be a non-negative int "
                f"(the scene frame to render this panel at; got {frame!r})"
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
        bubbles = panel.get("bubbles")
        if bubbles is not None:
            if not isinstance(bubbles, list):
                raise ValueError(
                    f"{source}: panel {index}.bubbles must be a list"
                )
            for b_index, bubble in enumerate(bubbles):
                _validate_bubble(
                    page, index, b_index, bubble, source, bleed
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


def _validate_bubble(
    page: dict[str, Any],
    panel_index: int,
    bubble_index: int,
    bubble: Any,
    source: str,
    bleed: float,
) -> None:
    """Validate one bubble of panel ``panel_index`` (P4-5, loud failures)."""
    where = f"{source}: panel {panel_index} bubble {bubble_index}"
    if not isinstance(bubble, dict):
        raise ValueError(f"{where} must be an object")
    unknown = set(bubble) - {"pos", "size", "tail", "text"}
    if unknown:
        raise ValueError(f"{where}: unknown bubble fields: {sorted(unknown)}")
    pos = bubble.get("pos")
    if (
        not isinstance(pos, list)
        or len(pos) != 2
        or not all(_is_num(v) for v in pos)
    ):
        raise ValueError(f"{where}.pos must be [x, y] numbers (panel fractions)")
    size = bubble.get("size")
    if (
        not isinstance(size, list)
        or len(size) != 2
        or not all(_is_num(v) for v in size)
    ):
        raise ValueError(f"{where}.size must be [w, h] numbers (panel fractions)")
    if float(size[0]) <= 0 or float(size[1]) <= 0:
        raise ValueError(f"{where}.size must be positive")
    tail = bubble.get("tail", "none")
    if tail not in _BUBBLE_TAILS:
        raise ValueError(
            f"{where}.tail {tail!r} is not one of: {', '.join(_BUBBLE_TAILS)}"
        )
    if not isinstance(bubble.get("text"), str):
        raise ValueError(f"{where}.text must be a string ('' = wordless)")
    # geometry: the FULL footprint (ellipse + tail band) in page fractions
    # must stay inside the bleed-extended page — same rule as panels.
    panel = page["panels"][panel_index]
    px_, py_, pw_, ph_ = (float(v) for v in panel["rect"])
    pos_x, pos_y = float(pos[0]), float(pos[1])
    size_x, size_y = float(size[0]), float(size[1])
    fx = px_ + (pos_x - size_x / 2) * pw_
    fy = py_ + (pos_y - size_y / 2) * ph_
    limit = 1.0 + bleed
    if not (
        -bleed <= fx
        and fx + size_x * pw_ <= limit
        and -bleed <= fy
        and fy + size_y * ph_ <= limit
    ):
        raise ValueError(
            f"{where} footprint leaves the page "
            f"(bleed allows [{-bleed}, {limit}])"
        )


def bubble_px(
    page: dict[str, Any], panel_index: int, bubble_index: int
) -> tuple[int, int, int, int]:
    """Bubble footprint in PAGE pixels (x, y, w, h), origin bottom-left.

    The bubble's ``pos`` is its CENTER and ``size`` its extents, both as
    PANEL fractions; edge-based rounding like ``panel_px``.
    """
    px_, py_, pw_, ph_ = panel_px(page, panel_index)
    bubble = page["panels"][panel_index]["bubbles"][bubble_index]
    pos_x, pos_y = (float(v) for v in bubble["pos"])
    size_x, size_y = (float(v) for v in bubble["size"])
    x0 = round(px_ + (pos_x - size_x / 2) * pw_)
    x1 = round(px_ + (pos_x + size_x / 2) * pw_)
    y0 = round(py_ + (pos_y - size_y / 2) * ph_)
    y1 = round(py_ + (pos_y + size_y / 2) * ph_)
    return (x0, y0, x1 - x0, y1 - y0)


def page_bubble_count(page: dict[str, Any]) -> int:
    """Total bubbles on the page (reading order: panel order, then index)."""
    return sum(len(p.get("bubbles") or []) for p in page["panels"])


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
    (camera/resolution/percentage/filepath + the scene frame) is restored;
    the view transform is deliberately NOT staged: panel pixels carry
    whatever the scene's transform does (the style look), while the page
    assembly's byte-identity contract is independent of it (module
    docstring).

    P4-8: a panel may carry ``frame`` (non-negative int) — the scene frame
    that panel renders at (``frame_set`` before its render). All motion
    data stays in the SCENE (keyed actions built by the caller); the page
    preset references a moment, it never contains motion. Panels without
    ``frame`` render at the scene frame as found — frame-less pages
    behave exactly as before this field existed.
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
        scene.frame_current,
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
            if panel.get("frame") is not None:
                scene.frame_set(int(panel["frame"]))
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
                "frame": panel.get("frame"),
            }
    finally:
        (
            scene.camera,
            render.resolution_x,
            render.resolution_y,
            render.resolution_percentage,
            render.filepath,
            scene.frame_current,
        ) = staged
    return {
        "panels": [entries[i] for i in sorted(entries)],
        "out_dir": str(out),
    }


def build_page_graph(
    scene: Any,
    page: dict[str, Any],
    panel_files: list[Any],
    bubble_files: list[Any] | None = None,
) -> dict[str, Any]:
    """Assemble the page as the scene's compositor node group (``rm_page``).

    REPLACES the scene's compositor group — with the tones graph this is
    a sequential stage: panels render styled+toned FIRST, then the page
    graph assembles. The replaced group (e.g. ``rm_tones``) is unlinked,
    not removed — its own remover owns that. Remove-first determinism:
    the ``rm_page`` group and ``rm_page_*`` images are removed before
    creation; node/image names are fixed. The sink follows the P4-3 rule
    (interface socket first, then EXACTLY ONE Group Output node).

    P4-5: bubbles (optional ``bubble_files``, one RGBA PNG per bubble in
    the deterministic global order — panel order, then bubble index; the
    order ``render_bubbles`` returns) composite AFTER the panels — a
    bubble overlays its panel and may cross gutters; borders stay under
    panels. A page with bubbles but no files, the wrong count, or files
    without bubbles = actionable errors. Bubble-less pages build
    byte-identical graphs to the pre-P4-5 builder (the report grows no
    key).
    """
    import bpy

    _validate_page(page, f"{page.get('name', 'page')}.json")
    if len(panel_files) != len(page["panels"]):
        raise ValueError(
            f"expected {len(page['panels'])} panel files, got "
            f"{len(panel_files)} (hint: render_panels returns exactly one "
            "PNG per panel in reading order)"
        )
    bubble_total = page_bubble_count(page)
    if bubble_total and bubble_files is None:
        raise ValueError(
            f"the page carries {bubble_total} bubble(s) but no bubble files "
            "(hint: call bubbles.render_bubbles and pass its file list)"
        )
    if bubble_files is not None and len(bubble_files) != bubble_total:
        raise ValueError(
            f"expected {bubble_total} bubble files, got {len(bubble_files)} "
            "(hint: render_bubbles returns one PNG per bubble in reading "
            "order)"
        )
    if not bubble_total and bubble_files:
        raise ValueError(
            f"got {len(bubble_files)} bubble files but the page carries no "
            "bubbles (hint: add a 'bubbles' list to a panel, or drop the "
            "argument)"
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

    bubble_entries = []
    if bubble_total:
        g_index = 0
        for p_index, panel in enumerate(page["panels"]):
            for b_index, bubble in enumerate(panel.get("bubbles") or []):
                x, y, w, h = bubble_px(page, p_index, b_index)
                expected = f"{PAGE_IMAGE_PREFIX}bubble_{g_index:02d}"
                bubble_img = bpy.data.images.load(str(bubble_files[g_index]))
                bubble_img.name = expected
                if bubble_img.name != expected:
                    raise ValueError(
                        f"page image name collision: {expected!r} is owned "
                        "by a user datablock (hint: clear or rename it first)"
                    )
                images.append(bubble_img.name)
                chain = over(
                    f"BB{g_index:02d}Over",
                    chain,
                    placed(f"BB{g_index:02d}Img", bubble_img, x, y),
                )
                bubble_entries.append(
                    {
                        "panel": p_index,
                        "bubble": b_index,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "tail": bubble.get("tail", "none"),
                        "text": bubble.get("text", ""),
                    }
                )
                g_index += 1

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
        **({"bubbles": bubble_entries} if bubble_total else {}),
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
