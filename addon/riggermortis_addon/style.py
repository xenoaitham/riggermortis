"""Toon style presets (P4-1) — banded shading + rim as an EEVEE node graph.

A preset is a DATA FILE (``presets/*.json``, shipped with the add-on) and the
material is a DETERMINISTIC node graph built from it — same preset in, same
graph out (CONVENTIONS determinism rule). The look:

- **Banded diffuse**: the dot product of the shaded normal with the preset's
  fixed light direction feeds a ColorRamp whose stops ARE the bands
  (shadow color below the first cut, one stop per cut). A fixed direction
  (not scene lights) keeps the look stylized, portable, and testable — the
  bands do not move when the scene's lamp rig moves.
- **Rim**: Layer Weight (Facing: 0 toward the camera, 1 at the silhouette)
  through a steep ColorRamp gives a black-to-rim-color mask starting at
  ``rim.start``; a Mix then swaps rim color in over the bands on the
  silhouette. Anime/western use a bright rim; the manga preset deliberately
  uses a DARK one (ink contour). Screentones/halftones are P4-3 and are NOT
  faked here.

**Unlit by construction**: the bands feed an EMISSION shader (strength 1),
not a light-dependent BSDF — the look is 100% determined by the preset, so
the same material renders identically with no lights, wrong lights, or any
scene (the black-render failure class caught by the visual check is
structural, not incidental). This is the standard EEVEE cel trick and needs
no Shader-to-RGB node; Cycles renders the same graph.

Unknown preset fields fail loudly (``_validate``) — typos never become
silent look changes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PRESETS_DIR = Path(__file__).resolve().parent / "presets"
MATERIAL_PREFIX = "rm_style_"
LINEART_OBJECT = "rm_lineart"
INK_PREFIX = "rm_ink_"
TONES_GROUP = "rm_tones"
TONES_UV_LAYER = "rm_tones_uv"
TONES_UV_MATERIAL = "rm_tones_uv"


def known_presets() -> list[str]:
    """Preset names shipped with the add-on, sorted (deterministic)."""
    return sorted(p.stem for p in PRESETS_DIR.glob("*.json"))


def load_preset(name: str) -> dict[str, Any]:
    """Load a shipped preset by name (or an explicit preset .json path)."""
    if name.endswith(".json"):
        path = Path(name)
    else:
        path = PRESETS_DIR / f"{name}.json"
    if not path.is_file():
        raise ValueError(
            f"unknown style preset: {name!r} (hint: known presets: "
            + ", ".join(known_presets())
            + " — or pass an explicit preset .json path)"
        )
    preset = json.loads(path.read_text(encoding="utf-8"))
    _validate(preset, path.name)
    return preset


def _hex_to_rgba(raw: Any) -> tuple[float, float, float, float]:
    text = str(raw).strip()
    if not text.startswith("#") or len(text) != 7:
        raise ValueError(f"preset color must be #rrggbb (got {raw!r})")
    return (
        int(text[1:3], 16) / 255.0,
        int(text[3:5], 16) / 255.0,
        int(text[5:7], 16) / 255.0,
        1.0,
    )


def _validate(preset: dict[str, Any], source: str) -> None:
    allowed = {
        "format",
        "name",
        "light_direction",
        "bands",
        "rim",
        "lineart",
        "tones",
        "notes",
    }
    unknown = set(preset) - allowed
    if unknown:
        raise ValueError(f"{source}: unknown preset fields: {sorted(unknown)}")
    if preset.get("format") != 1:
        raise ValueError(f"{source}: preset format must be 1")
    light = preset.get("light_direction")
    if (
        not isinstance(light, list)
        or len(light) != 3
        or not all(isinstance(v, (int, float)) for v in light)
    ):
        raise ValueError(f"{source}: light_direction must be [x, y, z] numbers")
    bands = preset.get("bands", {})
    positions, colors = bands.get("positions", []), bands.get("colors", [])
    if len(colors) < 2 or len(positions) != len(colors) - 1:
        raise ValueError(
            f"{source}: bands need len(colors) == len(positions) + 1 "
            "(N-1 cut positions between N colors)"
        )
    if any(not isinstance(p, (int, float)) or not 0 < p < 1 for p in positions):
        raise ValueError(f"{source}: band positions must be floats in (0, 1)")
    if sorted(positions) != list(positions):
        raise ValueError(f"{source}: band positions must be ascending")
    for color in colors:
        _hex_to_rgba(color)
    rim = preset.get("rim")
    if rim is not None:
        _hex_to_rgba(rim.get("color", ""))
        for key in ("facing", "start"):
            if not isinstance(rim.get(key), (int, float)) or not 0 <= rim[key] < 1:
                raise ValueError(f"{source}: rim.{key} must be a number in [0, 1)")
    line = preset.get("lineart")
    if line is not None:
        _hex_to_rgba(line.get("color", ""))
        for key in ("contour", "crease"):
            if not isinstance(line.get(key), bool):
                raise ValueError(f"{source}: lineart.{key} must be a boolean")
        for key in ("radius", "opacity", "crease_threshold"):
            if not isinstance(line.get(key), (int, float)):
                raise ValueError(f"{source}: lineart.{key} must be a number")
        if not line["radius"] > 0:
            raise ValueError(
                f"{source}: lineart.radius must be > 0 (WORLD METERS — a "
                "character rig at ~1.7 m wants ~0.002-0.004)"
            )
        if not 0 <= line["opacity"] <= 1:
            raise ValueError(f"{source}: lineart.opacity must be in [0, 1]")
        if not 0 < line["crease_threshold"] <= 3.1416:
            raise ValueError(
                f"{source}: lineart.crease_threshold must be in (0, pi] radians"
            )
    tones = preset.get("tones")
    if tones is not None:
        _hex_to_rgba(tones.get("ink", ""))
        cells = tones.get("cells")
        if not isinstance(cells, int) or isinstance(cells, bool) or not 1 <= cells <= 256:
            raise ValueError(f"{source}: tones.cells must be an int in [1, 256]")
        scale = tones.get("dot_scale")
        if not isinstance(scale, (int, float)) or not 0 < scale <= 1:
            raise ValueError(
                f"{source}: tones.dot_scale must be a number in (0, 1] "
                "(fraction of a cell; 0.71 reaches the cell corners)"
            )


def _rgba_to_hex(color: Any) -> str:
    """Blender RGBA (0..1 floats) back to the preset's #rrggbb form (gate
    assertion round-trip; alpha is 1.0 by construction)."""
    return (
        f"#{round(color[0] * 255):02x}"
        f"{round(color[1] * 255):02x}{round(color[2] * 255):02x}"
    )


def _socket(node: Any, identifier: str) -> Any:
    """The input socket with this IDENTIFIER.

    ShaderNodeMix has several sockets NAMED 'A'/'B'/'Factor' (one per data
    type) — name lookup grabs the float one first, and this Blender's
    bracket lookup does not resolve identifiers, so scan explicitly. The
    identifiers (``Factor_Float``/``A_Color``/``B_Color``/``Result_Color``)
    are the stable contract across 4.x -> 5.x.
    """
    for sock in node.inputs:
        if sock.identifier == identifier:
            return sock
    raise ValueError(
        f"{node.name!r} has no input socket with identifier {identifier!r} "
        "(hint: the ShaderNodeMix socket layout moved — re-check this "
        "Blender version's identifiers)"
    )


def _output_socket(node: Any, identifier: str) -> Any:
    for sock in node.outputs:
        if sock.identifier == identifier:
            return sock
    raise ValueError(f"{node.name!r} has no output socket {identifier!r}")


def build_toon_material(obj: Any, preset: dict[str, Any]) -> dict[str, Any]:
    """Build (or rebuild) the preset's toon material and assign it to ``obj``.

    Deterministic: fixed creation order, fixed node names, fixed grid
    positions. Rebuilding replaces the previous ``rm_style_*`` material on
    THIS object instead of stacking copies. Returns the graph report the
    gate asserts against.
    """
    import bpy

    if obj.type not in {"MESH", "SURFACE", "META", "CURVE"}:
        raise ValueError(
            f"{obj.name!r} is {obj.type!r} — toon materials need a shaded "
            "object (hint: the bone proxy is the visualizer for armatures)"
        )
    _validate(preset, f"{preset.get('name', 'preset')}.json")

    # Rebuild discipline: REMOVE the preset's old material BEFORE creating
    # the new one, keeping its slot. Creating first would suffix '.001' (the
    # old datablock owns the name), and clearing the slot would leave an
    # empty slot 0 whose default material hijacks faces with index 0 (both
    # caught by the determinism check / the visual check).
    target = f"{MATERIAL_PREFIX}{preset['name']}"
    replaced_slot = None
    for slot in obj.material_slots:
        if slot.material is not None and slot.material.name == target:
            bpy.data.materials.remove(slot.material)  # unlinks: slot goes None
            replaced_slot = slot
            break

    mat = bpy.data.materials.new(target)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Creation order is the graph's public shape; the gate asserts it.
    output = nodes.new("ShaderNodeOutputMaterial")  # (600, 0)
    output.location = (600.0, 0.0)
    output.name = "Output"

    emission = nodes.new("ShaderNodeEmission")  # (350, 0)
    emission.location = (350.0, 0.0)
    emission.name = "ToonEmission"
    emission.inputs["Strength"].default_value = 1.0

    bands = nodes.new("ShaderNodeValToRGB")  # (50, 0)
    bands.location = (50.0, 0.0)
    bands.name = "Bands"
    elements = bands.color_ramp.elements
    colors = preset["bands"]["colors"]
    positions = [float(p) for p in preset["bands"]["positions"]]
    # Hard band edges: each cut carries TWO stops at the same position
    # (band i's color ending, band i+1's color starting) — a single stop
    # per cut would give a soft gradient, not cel bands.
    elements[0].position = 0.0
    elements[0].color = _hex_to_rgba(colors[0])
    for index, position in enumerate(positions):
        lower = elements.new(position)
        lower.color = _hex_to_rgba(colors[index])
        upper = elements.new(position)
        upper.color = _hex_to_rgba(colors[index + 1])
    elements[-1].position = 1.0
    elements[-1].color = _hex_to_rgba(colors[-1])

    dot = nodes.new("ShaderNodeVectorMath")  # (-150, 0)
    dot.location = (-150.0, 0.0)
    dot.name = "BandLight"
    dot.operation = "DOT_PRODUCT"
    light = preset["light_direction"]
    dot.inputs[1].default_value = (float(light[0]), float(light[1]), float(light[2]))

    normal = nodes.new("ShaderNodeNewGeometry")  # (-350, 0)
    normal.location = (-350.0, 0.0)
    normal.name = "Normal"

    graph: dict[str, Any] = {
        "bands": len(colors),
        "band_cuts": positions,
        "band_colors": list(colors),
        "rim": None,
        "nodes": [node.name for node in nodes],
        "stops": [
            [round(e.position, 6), _rgba_to_hex(e.color)]
            for e in bands.color_ramp.elements
        ],
    }

    links.new(dot.outputs["Value"], bands.inputs["Fac"])
    links.new(normal.outputs["Normal"], dot.inputs[0])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])

    rim = preset.get("rim")
    if rim is not None:
        mix = nodes.new("ShaderNodeMix")  # (350, 200)
        mix.location = (350.0, 200.0)
        mix.name = "RimMix"
        mix.data_type = "RGBA"
        mix.blend_type = "MIX"
        mix_b = _socket(mix, "B_Color")
        mix_factor = _socket(mix, "Factor_Float")
        mix_a = _socket(mix, "A_Color")
        mix_result = _output_socket(mix, "Result_Color")
        mix_b.default_value = _hex_to_rgba(rim["color"])

        facing = nodes.new("ShaderNodeLayerWeight")  # (-350, 200)
        facing.location = (-350.0, 200.0)
        facing.name = "Facing"
        facing.inputs["Blend"].default_value = float(rim["facing"])

        rim_ramp = nodes.new("ShaderNodeValToRGB")  # (-150, 200)
        rim_ramp.location = (-150.0, 200.0)
        rim_ramp.name = "RimMask"
        rim_elements = rim_ramp.color_ramp.elements
        start = float(rim["start"])
        # The mask is black->WHITE (the swap factor); the rim COLOR itself
        # lives in RimMix.B — so a dark ink contour (manga) swaps in just as
        # a bright rim (anime) does.
        rim_elements[0].position = start
        rim_elements[0].color = (0.0, 0.0, 0.0, 1.0)
        rim_elements[1].position = min(start + 0.08, 1.0)
        rim_elements[1].color = (1.0, 1.0, 1.0, 1.0)

        links.new(facing.outputs["Facing"], rim_ramp.inputs["Fac"])
        links.new(rim_ramp.outputs["Color"], mix_factor)
        links.new(bands.outputs["Color"], mix_a)
        links.new(mix_result, emission.inputs["Color"])
        graph["rim"] = {
            "facing": float(rim["facing"]),
            "start": start,
            "color": rim["color"],
        }
        graph["nodes"] = [node.name for node in nodes]
    else:
        links.new(bands.outputs["Color"], emission.inputs["Color"])

    graph["nodes"] = [node.name for node in nodes]
    graph["material"] = mat.name

    if replaced_slot is not None:
        replaced_slot.material = mat
    else:
        obj.data.materials.append(mat)  # type: ignore[union-attr]
    return graph


def remove_lineart() -> bool:
    """Remove this module's LineArt overlay (object + data + ink materials).

    Returns True when an overlay object was removed. Ink materials are
    removed only when orphaned (a rebuild re-owns them by name anyway).
    """
    import bpy

    removed = False
    for obj in list(bpy.data.objects):
        if obj.type == "GREASEPENCIL" and obj.name == LINEART_OBJECT:
            data = obj.data
            bpy.data.objects.remove(obj)
            removed = True
            if data is not None and data.users == 0:
                bpy.data.grease_pencils.remove(data)
    for mat in list(bpy.data.materials):
        if mat.name.startswith(INK_PREFIX) and mat.users == 0:
            bpy.data.materials.remove(mat)
    return removed


def build_lineart(source_obj: Any, preset: dict[str, Any]) -> dict[str, Any]:
    """Build (or rebuild) the preset's LineArt ink overlay tracing
    ``source_obj``. Composes OVER ``build_toon_material`` — banded fill +
    ink lines in the same scene (the manga look).

    The GPv3 ``LINEART`` modifier only yields strokes through the ops
    ``LINEART_OBJECT`` preset wiring: a data-API build (own layer + frame +
    props) evaluates 0 strokes, and assigning ``target_material`` is
    Blender-blocked ("has to be used by the Grease Pencil object already")
    even when the material IS in the GP's list — probe-recorded in
    docs/STYLE.md. So this builder ops-creates, then RENAMES every datablock
    to the canonical names below; determinism comes from remove-first (same
    discipline as ``build_toon_material``). Returns the report the gate
    asserts; rebuilding must produce an equal report.
    """
    import bpy

    line = preset.get("lineart")
    if line is None:
        raise ValueError(
            f"preset {preset.get('name', '?')!r} has no 'lineart' section "
            "(hint: add one — schema in docs/STYLE.md)"
        )
    # Honest capability check: the GPv3 LINEART modifier needs a 4.3+-class
    # Blender (apt 4.0.2 has only the LRT_* ops enums — probe-recorded).
    if not hasattr(bpy.types, "GreasePencilLineartModifier"):
        raise ValueError(
            "this Blender has no GPv3 LineArt API (pre-4.3-class — hint: the "
            "'lineart' field needs a 4.3+/5.x Blender; see docs/STYLE.md)"
        )
    _validate(preset, f"{preset.get('name', 'preset')}.json")
    if source_obj is None or getattr(source_obj, "type", None) not in {
        "MESH",
        "SURFACE",
        "META",
        "CURVE",
    }:
        kind = getattr(source_obj, "type", None)
        raise ValueError(
            f"line art needs a shaded source object (got {kind!r} — hint: "
            "the bone proxy is the visualizer for armatures)"
        )

    remove_lineart()
    for mat in list(bpy.data.materials):
        if mat.name.startswith(INK_PREFIX):
            bpy.data.materials.remove(mat)
    ink_name = f"{INK_PREFIX}{preset['name']}"

    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    source_obj.select_set(True)
    view_layer.objects.active = source_obj
    known = set(bpy.data.objects.keys())
    try:
        bpy.ops.object.grease_pencil_add(type="LINEART_OBJECT")
    finally:
        view_layer.objects.active = prev_active
    # Context-independent capture: bpy.context.object is NOT reliable here
    # (after a render it still points at the previous active object), so
    # diff the datablocks the ops actually created.
    created = [
        o
        for o in bpy.data.objects
        if o.name not in known and o.type == "GREASEPENCIL"
    ]
    if len(created) != 1:
        raise ValueError(
            f"ops LINEART_OBJECT preset created {len(created)} Grease Pencil "
            "objects (expected exactly 1 — hint: re-check this Blender "
            "version against xtask/lineart_probe.py)"
        )
    gp = created[0]
    mod = next((m for m in gp.modifiers if m.type == "LINEART"), None)
    if mod is None:
        raise ValueError(
            "ops LINEART_OBJECT preset created no LINEART modifier (hint: "
            "re-check this Blender version against xtask/lineart_probe.py)"
        )
    if not len(gp.data.layers):
        raise ValueError(
            "ops LINEART_OBJECT preset created no layer (hint: the modifier "
            "writes strokes into a target layer — see docs/STYLE.md)"
        )
    ink = mod.target_material
    if ink is None and len(gp.data.materials):
        ink = gp.data.materials[0]
    if ink is None:
        raise ValueError(
            "ops LINEART_OBJECT preset left no ink material to re-own "
            "(hint: it normally creates a 'Black' material — see docs/STYLE.md)"
        )

    # Canonical renames — the names were freed by remove-first.
    gp.data.name = LINEART_OBJECT
    gp.name = LINEART_OBJECT
    mod.name = "rm_lineart"
    gp.data.layers[0].name = "Lines"
    ink.name = ink_name
    if gp.name != LINEART_OBJECT or ink.name != ink_name:
        raise ValueError(
            f"line-art rename collided (object={gp.name!r}, "
            f"material={ink.name!r} — hint: a user datablock owns the "
            "canonical rm_* name; clear it or rename it first)"
        )

    # The ink color must land where THIS Blender renders it from: the GP
    # material color AND the node surface (the ops preset's material uses
    # nodes; leaving Base Color black would pin every style's ink to black).
    ink_rgba = _hex_to_rgba(line["color"])
    if hasattr(ink, "grease_pencil") and hasattr(ink.grease_pencil, "color"):
        ink.grease_pencil.color = ink_rgba
    if ink.use_nodes:
        for node in ink.node_tree.nodes:  # type: ignore[union-attr]
            bsdf = getattr(node, "type", "")
            if bsdf == "BSDF_PRINCIPLED" and "Base Color" in node.inputs:
                node.inputs["Base Color"].default_value = ink_rgba

    mod.source_object = source_obj
    mod.use_contour = bool(line["contour"])
    mod.use_crease = bool(line["crease"])
    mod.crease_threshold = float(line["crease_threshold"])
    mod.radius = float(line["radius"])
    mod.opacity = float(line["opacity"])
    mod.target_layer = "Lines"
    mod.target_material = ink

    return {
        "object": gp.name,
        "data": gp.data.name,
        "layer": "Lines",
        "modifier": "rm_lineart",
        "source": source_obj.name,
        "material": ink.name,
        "color": line["color"],
        "radius": float(line["radius"]),
        "opacity": float(line["opacity"]),
        "contour": bool(line["contour"]),
        "crease": bool(line["crease"]),
        "crease_threshold": float(line["crease_threshold"]),
    }


def remove_screentones(scene: Any) -> bool:
    """Remove this module's tone machinery from ``scene`` (compositor group,
    UV view layer, override material). Returns True when a group was ours.

    Leaving an unrelated ``scene.compositing_node_group`` alone is the
    honest behavior — we never touch a graph we didn't build.
    """
    import bpy

    removed = False
    current = getattr(scene, "compositing_node_group", None)
    if current is not None and current.name == TONES_GROUP:
        scene.compositing_node_group = None
        bpy.data.node_groups.remove(current)
        removed = True
    elif TONES_GROUP in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[TONES_GROUP])
    for layer in list(scene.view_layers):
        if layer.name == TONES_UV_LAYER or layer.name.startswith(
            TONES_UV_LAYER + "."
        ):
            scene.view_layers.remove(layer)
    for mat in list(bpy.data.materials):
        if mat.name == TONES_UV_MATERIAL or mat.name.startswith(
            TONES_UV_MATERIAL + "."
        ):
            bpy.data.materials.remove(mat)
    return removed


def build_screentones(scene: Any, preset: dict[str, Any]) -> dict[str, Any]:
    """Build (or rebuild) the preset's halftone screentone pass over the
    rendered image: luminance -> dot radius, Generated coords (via a
    dedicated view layer whose override material emits them) -> tiled cell
    distance, ``dist < radius`` -> ink dots composited OVER the image.

    Everything here was probe-verified headless on 5.1 (docs/STYLE.md):
    the compositor graph lives in ``scene.compositing_node_group`` (the
    legacy ``scene.node_tree`` is gone), unified ``ShaderNode*`` classes
    work inside it, and there is NO UV pass — hence the second view layer.
    Deterministic by remove-first + fixed node names, same as the other
    builders; the report the gate asserts must be rebuild-equal.
    """
    import bpy

    tones = preset.get("tones")
    if tones is None:
        raise ValueError(
            f"preset {preset.get('name', '?')!r} has no 'tones' section "
            "(hint: add one — schema in docs/STYLE.md)"
        )
    # Honest capability check: the compositor graph lives in
    # scene.compositing_node_group only on 4.5+/5.x-class Blenders (the
    # legacy scene.node_tree is gone there and absent here).
    if not hasattr(scene, "compositing_node_group"):
        raise ValueError(
            "this Blender has no scene compositing node group (pre-5.x-class "
            "— hint: the 'tones' field needs a 5.x-class Blender; see "
            "docs/STYLE.md)"
        )
    _validate(preset, f"{preset.get('name', 'preset')}.json")
    cells = int(tones["cells"])
    dot_scale = float(tones["dot_scale"])
    ink_rgba = _hex_to_rgba(tones["ink"])

    remove_screentones(scene)

    # The coordinate source: a view layer whose override material emits
    # Generated coords as color (r = u, g = v). EEVEE renders it headless.
    uv_mat = bpy.data.materials.new(TONES_UV_MATERIAL)
    uv_mat.use_nodes = True
    nodes = uv_mat.node_tree.nodes
    links = uv_mat.node_tree.links
    nodes.clear()
    emit = nodes.new("ShaderNodeEmission")
    emit.name = "Emit"
    emit.inputs["Strength"].default_value = 1.0
    coord = nodes.new("ShaderNodeTexCoord")
    coord.name = "Coords"
    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.name = "UVSep"
    comb = nodes.new("ShaderNodeCombineColor")
    comb.name = "UVComb"
    links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    links.new(sep.outputs["X"], comb.inputs["Red"])
    links.new(sep.outputs["Y"], comb.inputs["Green"])
    out = nodes.new("ShaderNodeOutputMaterial")
    out.name = "Out"
    links.new(comb.outputs["Color"], emit.inputs["Color"])
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    vl = scene.view_layers.new(TONES_UV_LAYER)
    vl.use = True
    vl.material_override = uv_mat

    # The compositor graph: dots over the beauty image.
    group = bpy.data.node_groups.new(TONES_GROUP, "CompositorNodeTree")
    scene.use_nodes = True
    scene.compositing_node_group = group
    beauty = group.nodes.new("CompositorNodeRLayers")
    beauty.name = "BeautyRL"
    beauty.layer = scene.view_layers[0].name
    coords = group.nodes.new("CompositorNodeRLayers")
    coords.name = "CoordsRL"
    coords.layer = TONES_UV_LAYER

    def math(
        name: str, op: str, x: Any = None, value: Any = None, y: Any = None
    ) -> Any:
        node = group.nodes.new("ShaderNodeMath")
        node.name = name
        node.operation = op
        if x is not None:
            group.links.new(x, node.inputs[0])
        if y is not None:
            group.links.new(y, node.inputs[1])
        elif value is not None:
            node.inputs[1].default_value = value
        return node.outputs["Value"]

    csep = group.nodes.new("ShaderNodeSeparateXYZ")
    csep.name = "GridSep"
    group.links.new(coords.outputs["Image"], csep.inputs["Vector"])
    fx = math("GridX", "MULTIPLY", csep.outputs["X"], value=float(cells))
    fy = math("GridY", "MULTIPLY", csep.outputs["Y"], value=float(cells))
    frx = math("FracX", "SUBTRACT", fx, y=math("FloorX", "FLOOR", fx))
    fry = math("FracY", "SUBTRACT", fy, y=math("FloorY", "FLOOR", fy))
    dx = math("DX", "SUBTRACT", frx, value=0.5)
    dy = math("DY", "SUBTRACT", fry, value=0.5)
    d2 = math("D2", "ADD", y=math("DX2", "MULTIPLY", x=dx, y=dx),
              x=math("DY2", "MULTIPLY", x=dy, y=dy))
    dist = math("Dist", "POWER", d2, value=0.5)

    lum = group.nodes.new("CompositorNodeRGBToBW")
    lum.name = "Lum"
    group.links.new(beauty.outputs["Image"], lum.inputs[0])
    # darkness = 1 - luminance: CONSTANT in input 0, link in input 1
    # (operand order is load-bearing — probe-recorded).
    darkness = group.nodes.new("ShaderNodeMath")
    darkness.name = "Darkness"
    darkness.operation = "SUBTRACT"
    darkness.inputs[0].default_value = 1.0
    group.links.new(lum.outputs[0], darkness.inputs[1])
    radius = math("Radius", "MULTIPLY", darkness.outputs["Value"],
                  value=dot_scale)
    mask = math("Mask", "LESS_THAN", dist, y=radius)
    mix = group.nodes.new("ShaderNodeMix")
    mix.name = "ToneMix"
    mix.data_type = "RGBA"
    mix.blend_type = "MIX"
    mix_a = next(s for s in mix.inputs if s.identifier == "A_Color")
    mix_b = next(s for s in mix.inputs if s.identifier == "B_Color")
    mix_fac = next(s for s in mix.inputs if s.identifier == "Factor_Float")
    mix_result = next(s for s in mix.outputs if s.identifier == "Result_Color")
    mix_b.default_value = ink_rgba
    group.links.new(beauty.outputs["Image"], mix_a)
    group.links.new(mask, mix_fac)

    # EXACTLY ONE group-output node may exist, and it must be created AFTER
    # the interface socket (a stale unlinked first node renders black —
    # debug-caught: Blender reads the first output, not the linked one).
    for node in list(group.nodes):
        if node.type == "GROUP_OUTPUT":
            group.nodes.remove(node)
    sink = group.nodes.new("NodeGroupOutput")
    if "Image" not in sink.inputs:
        group.interface.new_socket(
            name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
        )
        group.nodes.remove(sink)
        sink = group.nodes.new("NodeGroupOutput")
    sink.name = "Sink"
    group.links.new(mix_result, sink.inputs["Image"])

    return {
        "group": group.name,
        "uv_layer": vl.name,
        "uv_material": uv_mat.name,
        "beauty_layer": beauty.layer,
        "cells": cells,
        "dot_scale": dot_scale,
        "ink": tones["ink"],
        "nodes": [node.name for node in group.nodes],
    }
