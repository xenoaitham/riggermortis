"""P4-3 capability probe: does background-mode compositing actually process,
and what can build a deterministic halftone dot-screen in THIS Blender?

The S11/S12 lesson twice over: probe the Blender capability before designing.
Findings so far (probe v1-v3, recorded honestly):
- Background compositing WORKS in 5.1 via ``scene.compositing_node_group``
  (a node group; ``scene.node_tree`` is GONE; the sink is the group-output
  interface — BrightContrast changed 230,400 channels headless).
- There is NO UV pass under 5.1's EEVEE (RL node lists only Image/Alpha;
  ``use_pass_uv`` enablement changes nothing visible to the node).
This version probes the fallback design: a SECOND VIEW LAYER with a
material override whose shader emits Generated coordinates — the
coordinate map arrives as an ordinary Image from that layer's RenderLayers
node, so the dot grid needs no UV pass. Also construct-tests candidate
compositor node types (the Python-subclass enumeration returns nothing in
5.1 — recorded).

Prints ``RM_TONE`` lines; exit 0 = compositing works here.
Usage: blender -b --python xtask/tone_probe.py -- OUT_DIR
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _make_scene() -> tuple[Any, Any]:
    import bpy
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(0, 0, 1))
    sphere = bpy.context.object
    cam_data = bpy.data.cameras.new("tone_cam")
    cam = bpy.data.objects.new("tone_cam", cam_data)
    cam.location = (0.0, -4.0, 1.2)
    aim = Vector((0.0, 0.0, 1.0)) - cam.location
    cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
    bpy.context.collection.objects.link(cam)
    world = bpy.data.worlds.new("tone_world")
    world.use_nodes = False
    # Dim on purpose: a bright world pushes the grey sphere to luminance
    # ~0.99, darkness -> 0 and the tone dots never fire (bisect-caught).
    world.color = (0.35, 0.35, 0.35)
    scene = bpy.context.scene
    scene.world = world
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 320, 240
    scene.render.image_settings.file_format = "PNG"
    return scene, sphere


def _render_pixels(scene: Any, path: Path) -> list[float]:
    import bpy

    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path))
    px = list(img.pixels)
    bpy.data.images.remove(img)
    return px


def _wire_group_sink(tree: Any, source: Any) -> Any:
    """Ensure an ``Image`` output socket and link ``source`` into a FRESH
    Group Output node.

    5.1 quirk (probe-recorded): the compositor group's interface gets
    rewritten behind the scenes (probe found stray 'X'/'Y'/'Z' sockets), and
    an EXISTING Group Output node never refreshes after an interface change —
    so the node is (re)created after any socket creation. Stale outputs are
    removed first: multiple Group Output nodes are undefined behavior.
    """
    for node in list(tree.nodes):
        if node.type == "GROUP_OUTPUT":
            tree.nodes.remove(node)
    out = tree.nodes.new("NodeGroupOutput")
    if "Image" not in out.inputs:
        tree.interface.new_socket(
            name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
        )
        out = tree.nodes.new("NodeGroupOutput")
    tree.links.new(source, out.inputs["Image"])
    return out


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("RM_TONE FAIL: expected -- OUT_DIR")
        return 2
    out_dir = Path(argv[argv.index("--") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)

    import bpy

    print(f"RM_TONE BLENDER: {bpy.app.version_string}")
    scene, sphere = _make_scene()
    engines = [
        e.identifier
        for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    ]
    scene.render.engine = (
        "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    )
    scene.frame_set(1)

    # Flat-lit grey sphere: luminance bands give the tone screen something
    # to encode (no lamps — the world IS the light).
    mat = bpy.data.materials.new("tone_grey")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1.0)
    sphere.data.materials.clear()
    sphere.data.materials.append(mat)

    base_px = _render_pixels(scene, out_dir / "plain.png")
    print(f"RM_TONE PLAIN RENDER: {len(base_px)} channels")

    # ---- candidate compositor node types (construct-test; the subclass
    # enumeration returns NOTHING in 5.1 — recorded) -----------------------
    candidates = [
        "CompositorNodeMath", "CompositorNodeSepXYZ", "CompositorNodeMix",
        "CompositorNodeRGBToBW", "CompositorNodeRLayers", "CompositorNodeComposite",
        "CompositorNodeTexture", "CompositorNodeTexCoord", "CompositorNodeGradient",
        "CompositorNodePosterize", "CompositorNodeDither", "CompositorNodeWhiteNoise",
        "CompositorNodeImage", "CompositorNodeBlur", "NodeGroupOutput",
        # 5.x unified-node guesses: the compositor may accept the shared
        # shader/generic node classes directly.
        "ShaderNodeMath", "ShaderNodeMix", "ShaderNodeSeparateXYZ",
        "ShaderNodeCombineColor", "ShaderNodeSeparateColor", "ShaderNodeValToRGB",
        "ShaderNodeVectorMath", "ShaderNodeRGBCurve", "FunctionNodeMath",
        "FunctionNodeSeparateColor", "NodeMath",
    ]
    tree = bpy.data.node_groups.new("rm_tone_probe", "CompositorNodeTree")
    available = []
    for node_type in candidates:
        try:
            node = tree.nodes.new(node_type)
            tree.nodes.remove(node)
            available.append(node_type)
        except Exception:  # noqa: BLE001 — absence is data, not an error
            pass
    print(f"RM_TONE AVAILABLE NODES: {available}")

    # ---- compositing processes in background? ----------------------------
    scene.use_nodes = True
    scene.compositing_node_group = tree
    tree.nodes.clear()
    rl = tree.nodes.new("CompositorNodeRLayers")
    bright = tree.nodes.new("CompositorNodeBrightContrast")
    bright.inputs["Contrast"].default_value = 5.0
    tree.links.new(rl.outputs["Image"], bright.inputs["Image"])
    if "CompositorNodeComposite" in available:
        comp = tree.nodes.new("CompositorNodeComposite")
        tree.links.new(bright.outputs["Image"], comp.inputs["Image"])
        print("RM_TONE GRAPH SINK: legacy Composite node")
    else:
        _wire_group_sink(tree, bright.outputs["Image"])
        print("RM_TONE GRAPH SINK: group output interface")

    tone_px = _render_pixels(scene, out_dir / "composited.png")
    changed = sum(
        1
        for a, b in zip(base_px, tone_px, strict=True)
        if abs(a - b) > 0.02
    )
    print(f"RM_TONE COMPOSITOR: changed_channels={changed}")
    compositing_works = changed > 0

    # ---- the coordinate source: view layer 2 with an emissive-UV override -
    uv_mat = bpy.data.materials.new("rm_probe_uvmap")
    uv_mat.use_nodes = True
    nodes = uv_mat.node_tree.nodes
    links = uv_mat.node_tree.links
    nodes.clear()
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 1.0
    coord = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    comb = nodes.new("ShaderNodeCombineColor")
    links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    links.new(sep.outputs["X"], comb.inputs["Red"])
    links.new(sep.outputs["Y"], comb.inputs["Green"])
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    links.new(comb.outputs["Color"], emit.inputs["Color"])

    vl2 = scene.view_layers.new("ToneUV")
    vl2.material_override = uv_mat

    # Diagnostic: render the coordinate map alone — per-channel min/max
    # proves whether the sphere + override actually produced a UV gradient.
    tree.nodes.clear()
    coords_only = tree.nodes.new("CompositorNodeRLayers")
    coords_only.layer = "ToneUV"
    _wire_group_sink(tree, coords_only.outputs["Image"])
    coord_px = _render_pixels(scene, out_dir / "coords.png")
    r_vals = coord_px[0::4]
    g_vals = coord_px[1::4]
    print(
        f"RM_TONE COORDS: r=[{min(r_vals):.3f},{max(r_vals):.3f}] "
        f"g=[{min(g_vals):.3f},{max(g_vals):.3f}]"
    )

    # ---- full halftone: dot grid from VL2 coords, radius from luminance ---
    tree.nodes.clear()
    beauty = tree.nodes.new("CompositorNodeRLayers")
    coords = tree.nodes.new("CompositorNodeRLayers")
    coords.layer = "ToneUV"
    print(
        f"RM_TONE HALFTONE LAYERS: beauty={beauty.layer!r} "
        f"coords={coords.layer!r}"
    )

    def math(op: str, x: Any = None, y: Any = None, value: Any = None) -> Any:
        node = tree.nodes.new("ShaderNodeMath")
        node.operation = op
        if x is not None:
            tree.links.new(x, node.inputs[0])
        if value is not None:
            node.inputs[1].default_value = value
        if y is not None:
            tree.links.new(y, node.inputs[1])
        return node.outputs["Value"]

    csep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(coords.outputs["Image"], csep.inputs["Vector"])
    cells = 40.0
    fx = math("MULTIPLY", csep.outputs["X"], value=cells)
    fy = math("MULTIPLY", csep.outputs["Y"], value=cells)
    frx = math("SUBTRACT", fx, math("FLOOR", fx))
    fry = math("SUBTRACT", fy, math("FLOOR", fy))
    dx = math("SUBTRACT", frx, value=0.5)
    dy = math("SUBTRACT", fry, value=0.5)
    d2 = math("ADD", math("MULTIPLY", dx, dx), math("MULTIPLY", dy, dy))
    dist = math("POWER", d2, value=0.5)

    bw = tree.nodes.new("CompositorNodeRGBToBW")
    tree.links.new(beauty.outputs["Image"], bw.inputs["Image"])
    # darkness = 1 - luminance: the CONSTANT goes in input 0, the linked
    # luminance in input 1 (the v14 bisect caught the operands swapped —
    # bw - 1.0 is negative, dots never fire, whatever the lighting).
    darkness_node = tree.nodes.new("ShaderNodeMath")
    darkness_node.operation = "SUBTRACT"
    darkness_node.inputs[0].default_value = 1.0
    tree.links.new(bw.outputs[0], darkness_node.inputs[1])
    radius = math("MULTIPLY", darkness_node.outputs["Value"], value=0.42)

    mask = math("LESS_THAN", dist, y=radius)

    # BISECT: the compositor has NO combine node (construct-test proved it),
    # so each intermediate goes through a ColorRamp (float -> greyscale) and
    # its own render. The default ramp maps 0->black, 1->white linearly.
    def _render_value(tag: str, socket: Any) -> None:
        ramp = tree.nodes.new("ShaderNodeValToRGB")
        tree.links.new(socket, ramp.inputs["Fac"])
        _wire_group_sink(tree, ramp.outputs["Color"])
        px = _render_pixels(scene, out_dir / f"val_{tag}.png")
        vals = px[0::4]
        print(f"RM_TONE VALUE {tag}: [{min(vals):.3f},{max(vals):.3f}]")
        tree.nodes.remove(ramp)

    _render_value("dist", dist)
    _render_value("radius", radius)
    _render_value("mask", mask)

    # Unified ShaderNodeMix inside the compositor tree — sockets by
    # IDENTIFIER (the P4-1 lesson: name lookup grabs the float socket).
    paper = tree.nodes.new("ShaderNodeMix")
    paper.data_type = "RGBA"
    paper.blend_type = "MIX"
    paper_a = next(s for s in paper.inputs if s.identifier == "A_Color")
    paper_b = next(s for s in paper.inputs if s.identifier == "B_Color")
    paper_fac = next(s for s in paper.inputs if s.identifier == "Factor_Float")
    paper_result = next(s for s in paper.outputs if s.identifier == "Result_Color")
    paper_a.default_value = (0.95, 0.95, 0.93, 1.0)  # paper
    paper_b.default_value = (0.06, 0.06, 0.06, 1.0)  # ink dot
    tree.links.new(mask, paper_fac)
    _wire_group_sink(tree, paper_result)

    tone_px = _render_pixels(scene, out_dir / "halftone.png")
    dark_pixels = sum(1 for i in range(0, len(tone_px), 4) if tone_px[i] < 0.3)
    light_pixels = sum(1 for i in range(0, len(tone_px), 4) if tone_px[i] > 0.7)
    tones_rendered = dark_pixels > 0 and light_pixels > 0
    print(
        f"RM_TONE HALFTONE: dark_px={dark_pixels} light_px={light_pixels} "
        f"{'TONES RENDER' if tones_rendered else 'no visible tones'}"
    )

    usable = {"compositing": compositing_works, "coords_via_view_layer":
              tones_rendered}
    print(f"RM_TONE PROBE RESULT: {usable}")
    return 0 if compositing_works else 1


if __name__ == "__main__":
    sys.exit(main())
