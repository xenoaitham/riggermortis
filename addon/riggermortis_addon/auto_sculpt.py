"""P9-1 proportion auto-sculpt — the add-on apply half (the selected
mechanism).

Design of record: docs/AUTO_SCULPT.md (the probe-earned amendments A1/A2
included). The mechanism is ``armature_scale_correctives`` delivered as
POSE-bone locations: per-joint offsets as rigid offsets in parent frames —
they persist without an action, FK rotations compose over them, and the
skinned mesh follows via real LBS (the rest-edit delivery is REFUTED —
armature skinning re-binds to the new rest, so the mesh would stay behind;
amendment A1).

The pure math (ratios, target construction, validation, capability lines)
lives in core (``riggermortis.auto_sculpt``); this module owns the bpy
surface only: the pose-location solve (the head response to a location is
linear and is MEASURED per bone with three axis perturbations — no
API-semantics betting), the loud capability refusals (the P8-4 verbatim
pattern), and the apply report. ``bpy`` is imported INSIDE the functions
(the add-on convention, clip_sample.py's pattern) so the module imports
cleanly outside Blender.

Rigs without viable targets report the capability line VERBATIM and touch
nothing; a below-bar apply is REPORTED (worst frac + role), never silently
accepted as "sculpted".
"""
from __future__ import annotations

import math
from typing import Any

Vec3 = tuple[float, float, float]

# real-follow threshold x space_scale (float32 noise stays ~1e-7 local
# units below it — the probe-earned instrument constant, amendment A1)
FOLLOW_EPS = 1e-6
POSE_RESPONSE_H = 1e-4  # probe-step for the linear response, x space_scale


def _bone_table_roles(arm_obj: Any) -> list[str]:
    """Roles mapped on this rig via the rm_role_* props, sorted (keyed)."""
    roles = sorted(
        k[len("rm_role_") :] for k in arm_obj.keys() if k.startswith("rm_role_")
    )
    return roles


def apply_proportion_sculpt(
    arm_obj: Any,
    target: dict[str, Vec3],
    base: dict[str, Vec3],
    space_scale: float = 1.0,
) -> dict[str, Any]:
    """Apply the proportion target as POSE-translation correctives.

    ``target``/``base`` are role -> armature-space joint positions (the
    pure core builds them). Returns a structured report: applied roles,
    worst frac vs the Annex A.1 bar, the loud capability lines, and the
    pose locations written (deterministic bytes for the twin gates).
    Raises nothing for a refused rig — the refusal IS the report."""
    import bpy

    roles_present = set(_bone_table_roles(arm_obj))
    from riggermortis.auto_sculpt import sculpt_capability_lines

    lines = sculpt_capability_lines(roles_present)
    if lines:
        return {
            "applied": False,
            "capability_lines": lines,
            "worst_frac": None,
            "worst_role": None,
            "pose_locations": {},
            "notes": ["refused loud — nothing applied"],
        }

    from riggermortis.auto_sculpt import validate_sculpt

    view_layer = bpy.context.view_layer
    view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")

    def head_of(bone_name: str) -> Vec3:
        t = arm_obj.pose.bones[bone_name].matrix.to_translation()
        return (t.x, t.y, t.z)

    role_to_bone = {
        k[len("rm_role_") :]: arm_obj[k] for k in sorted(arm_obj.keys()) if k.startswith("rm_role_")
    }
    # PARENT-FIRST keyed order (the probe's BONE_TABLE discipline): a child
    # solved before its parent would ride the parent's later delta and
    # overshoot. Depth from the rig's OWN bone topology, ties by bone name.
    def bone_depth(bone_name: str) -> int:
        d = 0
        b = arm_obj.data.bones[bone_name]
        while b.parent is not None:
            d += 1
            b = b.parent
        return d

    solve_order = sorted(
        (role for role in role_to_bone if role in target),
        key=lambda r: (bone_depth(role_to_bone[r]), role_to_bone[r]),
    )
    solved: dict[str, Vec3] = {}
    for role in solve_order:
        bone_name = role_to_bone[role]
        pb = arm_obj.pose.bones[bone_name]
        # ABSOLUTE-TARGET solve: zero THIS bone's location first — a
        # re-sculpt on an already-sculpted rig must land the target, never
        # compose with the previous offset (the gate's sequential-sculpt
        # class caught the draft's relative solve: head(L) = base + R@L, so
        # solving against a posed c0 leaked R@L_old into every re-run). The
        # parent chain is already solved (parent-first order); its offsets
        # are part of the frame this bone's location maps through.
        pb.location = (0.0, 0.0, 0.0)
        view_layer.update()
        c0 = head_of(bone_name)
        delta = (target[role][0] - c0[0], target[role][1] - c0[1], target[role][2] - c0[2])
        if math.sqrt(sum(c * c for c in delta)) <= 1e-12:
            solved[role] = c0
            continue
        cols: list[Vec3] = []
        for axis in range(3):
            h = POSE_RESPONSE_H * space_scale
            probe = [0.0, 0.0, 0.0]
            probe[axis] = h
            pb.location = probe
            view_layer.update()
            cp = head_of(bone_name)
            cols.append(
                (
                    (cp[0] - c0[0]) / h,
                    (cp[1] - c0[1]) / h,
                    (cp[2] - c0[2]) / h,
                )
            )
            pb.location = (0.0, 0.0, 0.0)
        view_layer.update()
        det = (
            cols[0][0] * (cols[1][1] * cols[2][2] - cols[1][2] * cols[2][1])
            - cols[1][0] * (cols[0][1] * cols[2][2] - cols[0][2] * cols[2][1])
            + cols[2][0] * (cols[0][1] * cols[1][2] - cols[0][2] * cols[1][1])
        )
        if abs(det) < 1e-12:
            raise ValueError(
                f"degenerate pose response for role {role} "
                "(hint: the bone's rest frame collapsed — check the rig)"
            )
        inv_det = 1.0 / det
        adj = [
            (
                cols[1][1] * cols[2][2] - cols[1][2] * cols[2][1],
                cols[0][2] * cols[2][1] - cols[0][1] * cols[2][2],
                cols[0][1] * cols[1][2] - cols[0][2] * cols[1][1],
            ),
            (
                cols[1][2] * cols[2][0] - cols[1][0] * cols[2][2],
                cols[0][0] * cols[2][2] - cols[0][2] * cols[2][0],
                cols[0][2] * cols[1][0] - cols[0][0] * cols[1][2],
            ),
            (
                cols[1][0] * cols[2][1] - cols[1][1] * cols[2][0],
                cols[0][1] * cols[2][0] - cols[0][0] * cols[2][1],
                cols[0][0] * cols[1][1] - cols[0][1] * cols[1][0],
            ),
        ]
        loc = (
            inv_det * (adj[0][0] * delta[0] + adj[1][0] * delta[1] + adj[2][0] * delta[2]),
            inv_det * (adj[0][1] * delta[0] + adj[1][1] * delta[1] + adj[2][1] * delta[2]),
            inv_det * (adj[0][2] * delta[0] + adj[1][2] * delta[1] + adj[2][2] * delta[2]),
        )
        pb.location = loc
        view_layer.update()
        solved[role] = head_of(bone_name)

    achieved = {role: head_of(bone_name) for role, bone_name in sorted(role_to_bone.items())}
    worst, fracs, worst_role, within_bar = validate_sculpt(achieved, target, base)
    pose_locations = {b.name: (float(b.location.x), float(b.location.y), float(b.location.z)) for b in arm_obj.pose.bones}
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except RuntimeError:
        pass
    notes = [
        f"auto-sculpt: {len(solved)} joint(s) re-placed as pose correctives;"
        f" worst {worst:.4f} at {worst_role} (bar 0.05)"
    ]
    if not within_bar:
        notes.append(
            f"auto-sculpt: bar MISSED ({worst:.4f} > 0.05) — reported, never silently accepted"
        )
    return {
        "applied": True,
        "capability_lines": [],
        "worst_frac": worst,
        "worst_role": worst_role,
        "within_bar": within_bar,
        "per_role_fracs": fracs,
        "pose_locations": pose_locations,
        "notes": notes,
    }


def measure_mesh_follow(mesh_obj: Any, space_scale: float = 1.0) -> float:
    """Fraction of vertices whose EVALUATED position really moved relative
    to their basis coordinates (the follow instrument; the threshold is
    FOLLOW_EPS x space_scale — float32 noise stays under it)."""
    import bpy

    pre = [tuple(v.co) for v in mesh_obj.data.vertices]
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh_obj.evaluated_get(deps)
    thr = FOLLOW_EPS * space_scale
    moved = 0
    for i in range(len(pre)):
        ev_co = ev.data.vertices[i].co
        d = math.sqrt(
            (ev_co.x - pre[i][0]) ** 2 + (ev_co.y - pre[i][1]) ** 2 + (ev_co.z - pre[i][2]) ** 2
        )
        if d > thr:
            moved += 1
    return moved / max(len(pre), 1)
