"""P9-2 volume apply — the add-on half of the selected mechanism.

Design of record: docs/VOLUME.md (the AUTO_SCULPT.md sibling, amendments
A1–A3). The mechanism is ``shape_key_inflate`` (the probe's pre-declared
selection, measured at the A.1 binding bar — worst exact-alpha IoU
0.8838 vs 0.85 over 8 cases on both rig classes): engine-authored
convention shape keys — key DATA = the unit band warp (radial in the
plane perpendicular to the hips→neck axis, skin-gated via the mapped
roles' vertex groups; the thigh band warps each leg about its OWN
center), key VALUE = the solved delta (absolute-target — a re-solve
OVERWRITES, never composes; the artist dial IS the volume param, the
P8-4 pattern).

This module is bpy-side only and imports bpy inside functions (the
conftest shim pattern) so CI can pin its pure seams headlessly. Joints
are NEVER touched (the skeleton-invariance contract — the probe's
byte-wise instrument); the certified FK/pose-apply path is untouched
(the sculpt edits mesh data only).
"""
from __future__ import annotations

from typing import Any

from riggermortis.volume import (
    BAND_PARAMS,
    CAPABILITY_NO_MESH,
    VolumeReport,
    value_of_factor,
)

# Band extents in T-fractions along the hips→neck axis (declared,
# docs/VOLUME.md; T = signed distance from the hips head, normalized by
# the torso span). The thigh band is negative (below the hips head).
BAND_TFRAC: dict[str, tuple[float, float]] = {
    "vol.thigh_w": (-0.98, -0.41),
    "vol.hip_w": (-0.41, 0.09),
    "vol.waist_w": (0.09, 0.45),
    "vol.chest_w": (0.45, 0.91),
}
BAND_TENT_T = 0.05  # the linear transition half-width (declared, untuned)
BAND_ROLES: dict[str, tuple[str, ...]] = {
    "vol.thigh_w": ("upper_leg.L", "upper_leg.R"),
    "vol.hip_w": ("hips",),
    "vol.waist_w": ("spine",),
    "vol.chest_w": ("chest",),
}


def _tent(zt: float, b0: float, b1: float) -> float:
    t = BAND_TENT_T
    if zt < b0 - t or zt > b1 + t:
        return 0.0
    if zt < b0 + t:
        return (zt - (b0 - t)) / (2 * t)
    if zt > b1 - t:
        return ((b1 + t) - zt) / (2 * t)
    return 1.0


def apply_volume_sculpt(
    arm_obj: Any,
    mesh_obj: Any,
    factors: dict[str, float],
    role_to_bone: dict[str, str],
) -> dict[str, Any]:
    """Apply the volume sculpt to a skinned mesh (the selected mechanism).

    factors: per-band ABSOLUTE-target factors (the solve's output; values
    are clamp(f-1) — a re-solve overwrites, never composes). The rig's
    mapped roles locate the bands (the hips/neck/spine/chest/upper_leg
    heads); the mesh's vertex groups of those roles gate the skin. Returns
    the structured report dict (applied / values / keys / capability_lines
    / notes); a starved rig is refused LOUD before anything is created.
    """
    lines: list[str] = []
    notes: list[str] = []
    if mesh_obj is None or mesh_obj.data is None:
        return {
            "applied": False,
            "values": {},
            "keys": [],
            "capability_lines": [CAPABILITY_NO_MESH],
            "notes": [],
        }

    import bpy  # noqa: PLC0415 — bpy stays inside functions (the shim pattern)

    missing = sorted(
        role
        for role in ("hips", "neck", *{r for roles in BAND_ROLES.values() for r in roles})
        if role not in role_to_bone
    )
    if missing:
        lines.append(
            "volume: rig has no viable volume targets for: " + ", ".join(missing) + " — volume not applied"
        )
        return {"applied": False, "values": {}, "keys": [], "capability_lines": lines, "notes": notes}

    if mesh_obj.data.shape_keys is None:
        mesh_obj.shape_key_add(name="Basis", from_mix=False)

    def head_world(role: str):
        bone = arm_obj.data.bones[role_to_bone[role]]
        return arm_obj.matrix_world @ bone.matrix_local.to_translation()

    def to_mesh_space(p_world):
        return mesh_obj.matrix_world.inverted() @ p_world

    # ALL geometry math happens in MESH-LOCAL space (one unit system: for a
    # Mixamo-class rig the mesh-local units are the armature's data units,
    # NOT world meters — mixing them makes every zt land outside the tents
    # and the apply becomes a silent no-op; the S37 mixamo-zero lesson).
    hips_m = to_mesh_space(head_world("hips"))
    neck_m = to_mesh_space(head_world("neck"))
    span = (neck_m - hips_m).length
    axis_m = (neck_m - hips_m).normalized() if span > 1e-12 else None
    if axis_m is None:
        lines.append("volume: torso ruler collapsed — volume not applied")
        return {"applied": False, "values": {}, "keys": [], "capability_lines": lines, "notes": notes}

    # skin membership per band (the mapped roles' vertex groups)
    groups: dict[str, set[int]] = {}
    for role in {r for roles in BAND_ROLES.values() for r in roles}:
        gname = role_to_bone[role]
        if gname in mesh_obj.vertex_groups:
            gi = mesh_obj.vertex_groups[gname].index
            groups[role] = {v.index for v in mesh_obj.data.vertices if any(g.group == gi and g.weight > 0.0 for g in v.groups)}
        else:
            groups[role] = set()

    legx = {
        "upper_leg.L": to_mesh_space(head_world("upper_leg.L")).x,
        "upper_leg.R": to_mesh_space(head_world("upper_leg.R")).x,
    }

    values: dict[str, float] = {}
    created: list[str] = []
    for param in BAND_PARAMS:
        b0, b1 = BAND_TFRAC[param]
        v = value_of_factor(factors[param])
        if abs(factors[param] - 1.0) <= 1e-9:
            notes.append(param + ": zero-delta target — key created at value 0 (the no-op contract)")
        if param not in [k.name for k in mesh_obj.data.shape_keys.key_blocks]:
            kb = mesh_obj.shape_key_add(name=param, from_mix=False)
            # the value law's range: negative values (slender references)
            # are DEAD at Blender's default slider_min of 0.0 — the S37
            # slender-zero lesson. Declared range: [CLAMP_LO-1, CLAMP_HI-1].
            kb.slider_min = -1.0
            kb.slider_max = 1.0
            created.append(param)
        else:
            kb = mesh_obj.data.shape_keys.key_blocks[param]
        roles = BAND_ROLES[param]
        for vert in mesh_obj.data.vertices:
            skin_ok = any(vert.index in groups.get(r, set()) for r in roles)
            if not skin_ok:
                continue
            rel = vert.co - hips_m
            zt = float(rel.dot(axis_m)) / span
            w = _tent(zt, b0, b1)
            if w <= 0.0:
                continue
            radial = rel - axis_m * float(rel.dot(axis_m))
            if len(roles) == 2:  # the thigh band: nearest leg axis is the center
                cx = legx[roles[0]] if abs(vert.co.x - legx[roles[0]]) <= abs(vert.co.x - legx[roles[1]]) else legx[roles[1]]
                rad_x = vert.co.x - cx
                rad_y = radial.y
            else:
                rad_x = radial.x
                rad_y = radial.y
            kb.data[vert.index].co = (vert.co.x + rad_x * w, vert.co.y + rad_y * w, vert.co.z)
        kb.value = v
        values[param] = v
    bpy.context.view_layer.update()
    report = VolumeReport(
        factors=dict(factors),
        values=values,
        capability_lines=[],
        notes=notes
        + (["clamped loudly: " + p for p, f in factors.items() if f < 0.5 or f > 2.0]),
    )
    return {
        "applied": True,
        "values": values,
        "keys": sorted(set(created) | {p for p in values if p not in created}),
        "capability_lines": report.capability_lines,
        "notes": report.notes,
    }


def measure_zero_restore(mesh_obj: Any) -> float:
    """The artist-exit instrument: zero every convention key, evaluate,
    return the worst vertex drift vs the Basis data (meters)."""
    import bpy  # noqa: PLC0415

    if mesh_obj is None or mesh_obj.data.shape_keys is None:
        return 0.0
    for k in mesh_obj.data.shape_keys.key_blocks:
        if k.name != "Basis":
            k.value = 0.0
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev_mesh = mesh_obj.evaluated_get(deps).data
    basis = mesh_obj.data.shape_keys.key_blocks[0].data
    worst = 0.0
    for bv, evv in zip(basis, ev_mesh.vertices, strict=False):
        d = (bv.co - evv.co).length
        if d > worst:
            worst = d
    return worst
