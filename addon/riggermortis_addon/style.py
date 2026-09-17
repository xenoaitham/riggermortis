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
    allowed = {"format", "name", "light_direction", "bands", "rim", "notes"}
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
