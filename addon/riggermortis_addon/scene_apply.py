"""Scene apply (P8-1): ONE multi-figure payload -> N armatures in one call.

Composes the REAL per-figure apply path (``pose_apply.apply_payload`` — the
D-009 recompute, mirror-aware, tails-repaired, reporting verbatim) over a
validated casting. Nothing here forks the single-apply machinery: the scene
is a NEW consumer of the SAME primitives, which is why per-figure fidelity
inherits the 0.5 deg family bar.

Ordering + honesty rules (docs/SCENES.md):
- figures apply in SORTED-LABEL order; the report rows come out in that
  order; the apply is order-insensitive and idempotent (probe-proven:
  byte-identical rotations either way, second apply identical);
- pins are CARRIED AND REPORTED, never enforced (P8-2 owns enforcement);
- casting is validated in core (``validate_casting``) BEFORE any pose is
  written — an uncast or double-cast figure refuses without touching rigs.
"""
from __future__ import annotations

from typing import Any

from . import bpy_bridge, pose_apply, tails


def scene_armatures() -> list[str]:
    """Armature object names in the scene, sorted (deterministic)."""
    import bpy

    return sorted(o.name for o in bpy.data.objects if o.type == "ARMATURE")


def apply_scene_payload(
    payload: dict[str, Any],
    assignments: dict[str, str],
    core: Any = None,
    mirror: bool = False,
) -> dict[str, Any]:
    """Apply every figure of ``payload`` to its cast armature (one action).

    ``assignments``: figure label -> armature name, validated by
    ``core.validate_casting`` first — refusals happen before any pose is
    written. Returns an aggregated structured report; raises ``ValueError``
    with an actionable message on malformed payloads or bad castings.
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

    per_figure: list[dict[str, Any]] = []
    worst_deg, worst_label = 0.0, ""
    for label in sorted(assignments):  # sorted-label order (the contract)
        figure = next(f for f in scene.figures if f.label == label)
        obj = bpy.data.objects[assignments[label]]
        # D-016 order: tail repair BEFORE posing (rest tails feed the FK math)
        repaired = tails.normalize_imported_tails(obj)
        report = pose_apply.apply_payload(
            obj, payload, mirror=mirror, core=core, figure=figure.label,
        )
        report["armature"] = obj.name
        report["tails_repaired"] = repaired
        per_figure.append(report)
        if report["worst_deg"] > worst_deg:
            worst_deg, worst_label = report["worst_deg"], figure.label

    pose_apply.push_undo()  # one undo step for the whole scene
    return {
        "figures_applied": len(per_figure),
        "figures_uncast": uncast,  # reported, never silently skipped
        "per_figure": per_figure,
        "pins": [p.to_dict() for p in scene.pins],  # carried + reported, NOT enforced
        "mirror": mirror,
        "worst_deg": worst_deg,
        "worst_figure": worst_label,
    }
