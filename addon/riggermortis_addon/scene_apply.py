"""Scene apply (P8-1 apply, P8-2 coupling): ONE payload -> N armatures.

Composes the REAL per-figure apply path (``pose_apply.apply_payload`` — the
D-009 recompute, mirror-aware, tails-repaired, reporting verbatim) over a
validated casting. Nothing here forks the single-apply machinery: the scene
is a NEW consumer of the SAME primitives, which is why per-figure fidelity
inherits the 0.5 deg family bar.

P8-2: after the first apply (which positions the rigs per the solved
figures), placements are MEASURED from the posed rigs — never guessed —
and the core coupling pass (``core.couple_scene``) enforces AUTHORED pins
by moving the canonical figures; the coupled positions are written back
into the in-memory payload entries and the figures RE-APPLY (the apply is
idempotent and order-insensitive, probe-proven S26). Enforcement is
core-owned and honesty-gated: suggested / below-floor / unplaced pins are
REPORTED LOUD and move nothing (docs/SCENES.md § Contact coupling).

Ordering + honesty rules (docs/SCENES.md):
- figures apply in SORTED-LABEL order; the report rows come out in that
  order; the apply is order-insensitive and idempotent;
- casting is validated in core (``validate_casting``) BEFORE any pose is
  written — an uncast or double-cast figure refuses without touching rigs;
- scenes without pins never enter the coupling path (byte-identical
  behavior).
"""
from __future__ import annotations

from typing import Any

from . import bpy_bridge, pose_apply, tails

#: Canonical torso span (the placement scale denominator; canonical units).
_TORSO_SPAN = 0.09 + 0.17 + 0.19


def scene_armatures() -> list[str]:
    """Armature object names in the scene, sorted (deterministic)."""
    import bpy

    return sorted(o.name for o in bpy.data.objects if o.type == "ARMATURE")


def apply_scene_payload(
    payload: dict[str, Any],
    assignments: dict[str, str],
    core: Any = None,
    mirror: bool = False,
    couple: bool = True,
) -> dict[str, Any]:
    """Apply every figure of ``payload`` to its cast armature (one action).

    ``assignments``: figure label -> armature name, validated by
    ``core.validate_casting`` first — refusals happen before any pose is
    written. With ``couple`` (default) and authored pins in the payload,
    the coupling pass runs between the first apply and the re-apply.
    Returns an aggregated structured report; raises ``ValueError`` with an
    actionable message on malformed payloads or bad castings.
    """
    import bpy

    if core is None:
        core = bpy_bridge.import_core()

    scene = core.scene_from_payload(payload)
    assignments = core.validate_casting(
        scene, {str(k): str(v) for k, v in assignments.items()},
        scene_armatures(),
    )
    uncast = sorted(f.label for f in scene.figures if f.label not in assignments)

    def _apply_all() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for label in sorted(assignments):  # sorted-label order (the contract)
            figure = next(f for f in scene.figures if f.label == label)
            obj = bpy.data.objects[assignments[label]]
            # D-016 order: tail repair BEFORE posing (idempotent; the second
            # pass re-repairs nothing)
            repaired = tails.normalize_imported_tails(obj)
            report = pose_apply.apply_payload(
                obj, payload, mirror=mirror, core=core, figure=figure.label,
            )
            report["armature"] = obj.name
            report["tails_repaired"] = repaired
            rows.append(report)
        return rows

    per_figure = _apply_all()

    couple_block: dict[str, Any] | None = None
    if couple and scene.pins:
        # the placements read POSED joints — stale until the depsgraph runs
        # (the S26 lesson: place, UPDATE, then measure)
        bpy.context.view_layer.update()
        placements = _measure_placements(scene, assignments, core)
        coupled, couple_report = core.couple_scene(scene, placements)
        entries = {
            str(e.get("label")): e for e in core.payload.figure_entries(payload)
        }
        for fig in coupled.figures:
            entry = entries.get(fig.label)
            if entry is not None and isinstance(entry.get("pose"), dict):
                # FULL precision (not the file's 4 dp): riding roles keep
                # byte-exact segment directions, so their derived rotations
                # are untouched. The file format is never written here.
                entry["pose"]["positions"] = {
                    r: list(p) for r, p in fig.pose.positions.items()
                }
        per_figure = _apply_all()  # the coupled poses (idempotent path)
        couple_block = couple_report.to_dict()

    worst_deg, worst_label = 0.0, ""
    for row, label in zip(per_figure, sorted(assignments), strict=True):
        if row["worst_deg"] > worst_deg:
            worst_deg, worst_label = row["worst_deg"], label

    pose_apply.push_undo()  # one undo step for the whole scene
    return {
        "figures_applied": len(per_figure),
        "figures_uncast": uncast,  # reported, never silently skipped
        "per_figure": per_figure,
        "pins": [p.to_dict() for p in scene.pins],  # carried + reported
        "couple": couple,
        "coupling": couple_block,  # the P8-2 enforcement report (None: no pins)
        "mirror": mirror,
        "worst_deg": worst_deg,
        "worst_figure": worst_label,
    }


def _measure_placements(
    scene: Any, assignments: dict[str, str], core: Any,
) -> dict[str, Any]:
    """Placement per CAST figure, measured from the posed rigs (APPROXIMATE
    class, the same assumption the camera v0 staging makes: the rig's rest
    axes align with canonical axes after apply — measured, never constant).

    t maps the pose's canonical ORIGIN: ``t = world(anchor joint) −
    s·R·canonical(anchor joint)``. Detector-solved poses anchor the solve AT
    the origin (hips sits at (0,0,0)), so the second term is zero and t is
    simply the posed anchor joint's world position (hips, or neck for
    neck-anchored solves); engine-built fixture poses that carry the anchor
    off-origin (rest-skeleton-based) stay correct through the same formula.
    R = the armature object's world rotation, scale-stripped (uniform-scale
    assumption, the camera-v0 class); s = posed world torso span
    (hips -> neck) / 0.45. Figures whose mapping cannot resolve the needed
    roles get NO placement — their pins report ``no placement`` instead of
    being guessed.
    """
    import bpy
    from mathutils import Matrix, Vector

    placements: dict[str, Any] = {}

    def world_head(obj: Any, mapping: Any, role: str) -> Any:
        assignment = mapping.assignments.get(role)
        if assignment is None:
            return None
        pb = obj.pose.bones.get(assignment.bone)
        if pb is None:
            return None
        return obj.matrix_world @ Vector(pb.head)

    def anchor_role(pose: Any) -> str:
        return pose.anchor if pose.anchor in ("hips", "neck") else "hips"

    for label in sorted(assignments):
        figure = next(f for f in scene.figures if f.label == label)
        obj = bpy.data.objects[assignments[label]]
        mapping = pose_apply.mapping_from_props(obj, core)
        if mapping is None:
            rig = core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
            mapping = core.map_rig(rig)

        anchor = world_head(obj, mapping, anchor_role(figure.pose))
        anchor_canonical = figure.pose.positions.get(anchor_role(figure.pose))
        hips = world_head(obj, mapping, "hips")
        neck = world_head(obj, mapping, "neck")
        if anchor is None or hips is None or neck is None or anchor_canonical is None:
            continue  # core reports the pin as unplaced — never guessed
        span = (hips - neck).length
        if span <= 1e-9:
            continue
        s = span / _TORSO_SPAN
        rot = obj.matrix_world.to_3x3()
        stripped = Matrix((
            tuple(rot.row[0].normalized()),
            tuple(rot.row[1].normalized()),
            tuple(rot.row[2].normalized()),
        ))
        quat = stripped.to_quaternion()
        offset = (quat @ Vector(anchor_canonical)) * s
        t = Vector(anchor) - offset
        placements[label] = core.Placement(
            quat=(quat.w, quat.x, quat.y, quat.z),
            t=(t.x, t.y, t.z),
            s=s,
        )
    return placements
