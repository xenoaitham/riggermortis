"""In-Blender probe for P4-4 page assembly (headless) — probe BEFORE builder.

Answers the three open questions docs/STYLE.md P4-4 records, with raw API
evidence (no pages.py involved — the builder is written only after this
passes, the S12 discipline):

1. Q-COMPOSE: does ``CompositorNodeImage`` (file-loaded PNG) + ``Translate``
   + ``AlphaOver`` + ``RGB`` work inside the 5.1 scene compositor node
   group (P4-3 only proved ``RLayers``/``RGBToBW`` in there)?
2. Q-PANELS: does per-render ``scene.camera`` + ``resolution_x/y`` +
   ``filepath`` swapping yield one PNG per panel at the expected pixel
   size, headless EEVEE?
3. Q-FIDELITY: does a panel PNG survive the compositor round-trip
   BYTE-FAITHFUL? The verified trick: load panel images with the DEFAULT
   sRGB colorspace and write the page with view transform ``Standard``
   (dither OFF) — Standard's write encode is the same curve the loader
   decodes with, so decode(encode(bytes)) is the byte-identity (the
   first attempt, ``Non-Color`` loads, FAILED: Standard still encodes,
   lifting every value by the sRGB curve — bisect-recorded).
   (The style look of the pixels themselves was produced by the panel
   render and its own transform — the page stage must be a no-op.)

Also bisect-proven and baked in here (the first page render shipped a
top sliver + black page — two stacked findings):
- the compositor CENTERS images smaller than the render buffer before
  ``Translate`` applies, so every offset is corrected:
  ``t = desired - (page - img) // 2`` per axis;
- a bare ``RGB`` node background does not work: OUTSIDE any image's
  footprint the chain carries no data and goes transparent-black — the
  page background is a FULL-PAGE solid generated image instead.

Positioning is proven with computed pixel samples: a white gutter point
between the two panels and a border-ring point of a generated under-rect.

Usage: blender -b --python xtask/page_probe.py -- OUT_DIR
"""
from __future__ import annotations

import array
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addon"))

# The manga_koma3 layout numbers from docs/STYLE.md (real px math, not a
# toy): a wide top panel and a bottom-right panel with a 6 px ink border.
PAGE_W, PAGE_H = 1200, 1800
A_X, A_Y, A_W, A_H = 0, 1116, 1200, 684      # [0.0, 0.62, 1.0, 0.38]
B_X, B_Y, B_W, B_H = 612, 558, 588, 522      # [0.51, 0.31, 0.49, 0.29]
BORDER = 6
INK = (16 / 255.0, 16 / 255.0, 16 / 255.0, 1.0)  # #101010 as raw float


def _add_camera(name: str, loc: tuple[float, float, float]) -> Any:
    import bpy
    from mathutils import Vector

    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    aim = Vector((0.0, 0.0, 1.0)) - obj.location
    obj.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
    bpy.context.collection.objects.link(obj)
    return obj


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("RM_PAGE FAIL: expected -- OUT_DIR")
        return 2
    out_dir = Path(argv[argv.index("--") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)

    import bpy
    from riggermortis_addon import style

    print(f"RM_PAGE BLENDER: {bpy.app.version_string}")
    print(f"RM_PAGE VIEW_TRANSFORM: {bpy.context.scene.view_settings.view_transform}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(0, 0, 1))
    sphere = bpy.context.object
    cam1 = _add_camera("rm_cam_1", (0.0, -4.0, 1.2))
    cam2 = _add_camera("rm_cam_2", (2.2, -2.6, 0.55))
    _add_camera("rm_cam_3", (4.0, -0.5, 1.6))
    world = bpy.data.worlds.new("rm_page_world")
    world.use_nodes = False
    world.color = (0.08, 0.08, 0.09)
    bpy.context.scene.world = world
    scene = bpy.context.scene
    scene.camera = cam1
    scene.render.engine = "BLENDER_EEVEE_NEXT" if any(
        e.identifier == "BLENDER_EEVEE_NEXT"
        for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    ) else "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.use_border = False
    scene.render.resolution_percentage = 100
    scene.render.dither_intensity = 0.0

    # A styled subject: manga bands + ink + tones — panels must carry the
    # full look, and the tones graph exercises the "sequential stages"
    # contract (tones first, page graph replaces it for assembly).
    preset = style.load_preset("manga")
    style.build_toon_material(sphere, preset)
    style.build_lineart(sphere, preset)
    style.build_screentones(scene, preset)

    # Q2 — per-panel render swap: camera + resolution + filepath per panel.
    panel_paths = {}
    for tag, cam, w, h in (
        ("a", cam1, A_W, A_H),
        ("b", cam2, B_W, B_H),
    ):
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = w, h
        path = out_dir / f"probe_panel_{tag}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(path))
        got = tuple(img.size)
        bpy.data.images.remove(img)
        if got != (w, h):
            print(f"RM_PAGE FAIL: panel {tag} rendered {got}, expected {(w, h)}")
            return 1
        panel_paths[tag] = path
        print(f"RM_PAGE PANEL RENDER: {tag} {w}x{h} ok ({path.name})")

    img_a = bpy.data.images.load(str(panel_paths["a"]))
    img_b = bpy.data.images.load(str(panel_paths["b"]))
    px_a, px_b = list(img_a.pixels), list(img_b.pixels)
    stride = 4 * 37  # every 37th pixel — plenty for a difference test
    diffs = [
        abs(p - q)
        for p, q in zip(px_a[::stride], px_b[::stride], strict=False)
    ]
    spread_a = max(px_a[::stride]) - min(px_a[::stride])
    mean_diff = sum(diffs) / len(diffs)
    bpy.data.images.remove(img_a)
    bpy.data.images.remove(img_b)
    if spread_a <= 0.0 or mean_diff <= 0.01:
        print(
            f"RM_PAGE FAIL: panels do not prove distinct cameras "
            f"(spread_a={spread_a:.4f}, mean_diff={mean_diff:.4f})"
        )
        return 1
    print(
        f"RM_PAGE PANELS DIFFER: mean={mean_diff:.4f} spread_a={spread_a:.4f} "
        "(two cameras, two different frames)"
    )

    # Q1 — the assembly graph inside the 5.1 scene node group. This
    # REPLACES the tones group on the scene (sequential stages, the
    # documented contract). Bisect-proven mechanics baked in: a FULL-PAGE
    # solid background image (a bare RGB node has no spatial extent —
    # outside image footprints the chain goes transparent-black), and
    # Translate offsets corrected for the compositor's centering.
    group = bpy.data.node_groups.new("rm_page_probe", "CompositorNodeTree")
    scene.compositing_node_group = group

    def solid(name: str, w: int, h: int, rgba) -> Any:
        img = bpy.data.images.new(name, w, h, alpha=True)
        fill = array.array("f", rgba) * (w * h)
        img.pixels.foreach_set(fill)
        return img

    def over(name: str, base: Any, top: Any) -> Any:
        node = group.nodes.new("CompositorNodeAlphaOver")
        node.name = name
        node.inputs["Factor"].default_value = 1.0
        group.links.new(base, node.inputs["Background"])
        group.links.new(top, node.inputs["Foreground"])
        return node.outputs["Image"]

    def placed(name: str, image: Any, x: int, y: int) -> Any:
        img_node = group.nodes.new("CompositorNodeImage")
        img_node.name = name
        img_node.image = image
        tr = group.nodes.new("CompositorNodeTranslate")
        tr.name = name + "Pos"
        # 5.1: the translate is TWO value sockets (X, Y) — the old single
        # 'Vector' input is gone (probe-recorded). The offset corrects for
        # the compositor CENTERING images smaller than the render buffer
        # before translating: t = desired - (page - img) // 2 (bisect-
        # caught: uncorrected offsets overshot by exactly the centering
        # term and the page shipped a top sliver + black).
        tx = x - (PAGE_W - image.size[0]) // 2
        ty = y - (PAGE_H - image.size[1]) // 2
        tr.inputs["X"].default_value = float(tx)
        tr.inputs["Y"].default_value = float(ty)
        group.links.new(img_node.outputs["Image"], tr.inputs["Image"])
        print(
            f"RM_PAGE PLACE: {name} img={tuple(image.size)} "
            f"desired=({x},{y}) translate=({tx},{ty})"
        )
        return tr.outputs["Image"]

    bg_img = solid("rm_probe_bg", PAGE_W, PAGE_H, (1.0, 1.0, 1.0, 1.0))
    chain = placed("BgImg", bg_img, 0, 0)

    img_a = bpy.data.images.load(str(panel_paths["a"]))
    img_a.name = "rm_probe_panel_a"
    # DEFAULT sRGB colorspace (no override): Standard's write encode is the
    # same curve the loader decodes with — decode(encode(bytes)) is the
    # byte-identity round-trip (Non-Color loads were the FIRST attempt and
    # FAIL: Standard still encodes, lifting every value by the sRGB curve).
    chain = over("PanelAOver", chain, placed("PanelAImg", img_a, A_X, A_Y))

    # The border under-rect: a solid generated image behind panel B —
    # the mechanism the builder uses for panel frames (no hand-drawing).
    # Fill via foreach_set (generated_color is unreliable on buffer images).
    bw, bh = B_W + 2 * BORDER, B_H + 2 * BORDER
    border = bpy.data.images.new("rm_probe_border_b", bw, bh, alpha=True)
    fill = array.array("f", INK) * (bw * bh)
    border.pixels.foreach_set(fill)
    chain = over(
        "BorderBOver", chain, placed("BorderBImg", border, B_X - BORDER, B_Y - BORDER)
    )

    img_b = bpy.data.images.load(str(panel_paths["b"]))
    img_b.name = "rm_probe_panel_b"
    chain = over("PanelBOver", chain, placed("PanelBImg", img_b, B_X, B_Y))

    # The P4-3 sink rule: interface socket FIRST, then EXACTLY ONE
    # Group Output.
    group.interface.new_socket(
        name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
    )
    sink = group.nodes.new("NodeGroupOutput")
    sink.name = "Sink"
    group.links.new(chain, sink.inputs["Image"])
    print(
        "RM_PAGE GRAPH: nodes="
        + ",".join(n.name for n in group.nodes)
        + f" links={len(group.links)}"
    )

    # The page render: beauty output ignored; Standard + dither 0 = the
    # raw-write path under test for Q3.
    scene.render.resolution_x, scene.render.resolution_y = PAGE_W, PAGE_H
    scene.view_settings.view_transform = "Standard"
    page_path = out_dir / "probe_page.png"
    scene.render.filepath = str(page_path)
    bpy.ops.render.render(write_still=True)

    page = bpy.data.images.load(str(page_path))
    got = tuple(page.size)
    if got != (PAGE_W, PAGE_H):
        print(f"RM_PAGE FAIL: page rendered {got}, expected {(PAGE_W, PAGE_H)}")
        return 1
    print(f"RM_PAGE PAGE RENDER: {PAGE_W}x{PAGE_H} ok")

    px = list(page.pixels)

    def sample(x: int, y: int) -> tuple[float, float, float]:
        i = (y * PAGE_W + x) * 4
        return px[i], px[i + 1], px[i + 2]

    # Q3 — byte-faithful round-trip: page pixels inside a panel must EQUAL
    # that panel's own pixels at the same position (integer placement, no
    # scale, raw in / raw out).
    src_a = bpy.data.images.load(str(panel_paths["a"]))
    px_a = list(src_a.pixels)
    bpy.data.images.remove(src_a)
    src_b = bpy.data.images.load(str(panel_paths["b"]))
    px_b = list(src_b.pixels)
    bpy.data.images.remove(src_b)
    checks_a = [(100, 1300), (600, 1500), (1100, 1700)]  # inside panel A
    checks_b = [(700, 700), (900, 1000)]  # inside panel B
    bad = 0
    for x, y in checks_a + checks_b:
        if y >= A_Y:
            si = ((y - A_Y) * A_W + x) * 4
            want = (px_a[si], px_a[si + 1], px_a[si + 2])
        else:
            si = ((y - B_Y) * B_W + (x - B_X)) * 4
            want = (px_b[si], px_b[si + 1], px_b[si + 2])
        got_px = sample(x, y)
        if max(abs(a - b) for a, b in zip(want, got_px, strict=True)) > 1.5 / 255.0:
            bad += 1
            print(
                f"RM_PAGE ROUNDTRIP MISS: ({x},{y}) page={got_px} "
                f"panel={want}"
            )
    if bad:
        print(f"RM_PAGE FAIL: {bad}/{len(checks_a + checks_b)} roundtrip samples drifted")
        return 1
    print(
        f"RM_PAGE ROUNDTRIP: {len(checks_a + checks_b)}/"
        f"{len(checks_a + checks_b)} samples byte-faithful "
        "(sRGB loads in, Standard+dither0 out)"
    )

    # Positioning: the white gutter point (between A and B, clear of both
    # borders), the border ring left of panel B, and a page-corner point
    # (the full-page background must reach everywhere, not just image
    # footprints — the bare-RGB-node regression).
    gutter = sample(600, 1101)
    ring = sample(609, 819)
    corner = sample(5, 5)
    if min(gutter) < 0.95:
        print(f"RM_PAGE FAIL: gutter not white at (600,1101): {gutter}")
        return 1
    if max(ring) > 0.2:
        print(f"RM_PAGE FAIL: border ring not ink at (609,819): {ring}")
        return 1
    if min(corner) < 0.95:
        print(f"RM_PAGE FAIL: page corner not white at (5,5): {corner}")
        return 1
    print(
        f"RM_PAGE POSITION: gutter{tuple(round(v, 3) for v in gutter)} "
        f"ring{tuple(round(v, 3) for v in ring)} "
        f"corner{tuple(round(v, 3) for v in corner)} — panels sit at the "
        "preset's computed pixel offsets, background covers the page"
    )

    (out_dir / "probe_ok.txt").write_text("ok\n", encoding="utf-8")
    print("RM_PAGE PROBE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
