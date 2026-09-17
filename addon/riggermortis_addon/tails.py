"""Conditional glTF/VRM bone-tail normalization at add-on level (P2-8a, D-015).

glTF/VRM have no bone-tail concept; importers synthesize one, and on the
Mixamo glb (Xbot) the synthesized tails are ~100x the true joint spacing.
Garbage tails leave Blender's EVALUATED bone placement broken: posed children
ladder away from their parents (the core-side FK verifies 0.0000 deg while
the visible rig falls apart), which is exactly what an add-on user posing an
imported rig hits.

The rule is the SAME deterministic, conditional rule as
``xtask/walk_media.py::_repair_imported_tails`` (kept in lockstep on
purpose), keyed on an ABSURD-RATIO threshold: a tail is repaired only when
its length exceeds 10x the distance to the nearest child's head (chain
bones) or 10x the rig's median joint span (childless leaves). The threshold
is data-separated on the real rigs (S10 measurements): the Blender-native
metarig's worst artist-intended tails are ~5.1x (pelvis/breast flanks), the
glTF synthesizer's garbage starts at ~76x and sits at ~100x — so sane rigs
are a bit-for-bit no-op (asserted by the pose-apply gate) while the whole
garbage class is caught with order-of-magnitude margin.

Returns the number of bones repaired (0 = nothing touched) so callers can
REPORT the normalization instead of silently mutating a user's rig.
"""
from __future__ import annotations

from typing import Any

#: A tail is garbage only above this ratio (see module docstring: measured
#: sane max ~5.1x on the metarig, importer garbage >= ~76x on the Mixamo glb).
ABSURD_RATIO = 10.0
#: A child whose head is co-located with the bone's head (span <= 5% of the
#: median joint span) gives NO geometric evidence about the tail — skip it
#: (the metarig's spine/spine.006 have such children; treating span~0 as an
#: infinite ratio would snap artist tails to zero length).
COLOCATED_FRACTION = 0.05
#: Repaired leaf stubs are 0.3x the median joint span.
LEAF_STUB_FACTOR = 0.3


def normalize_imported_tails(armature: Any) -> int:
    """Repair garbage bone tails WHEN they disagree with the skeleton.

    Runs in EDIT mode on the armature (it is made active first). Deterministic
    for a given armature; 0 on sane rigs. Raises ValueError when the object is
    not an armature.
    """
    import bpy
    from mathutils import Vector

    if armature.type != "ARMATURE":
        raise ValueError(f"{armature.name!r} is not an armature")
    data = armature.data

    children: dict[str, list[Any]] = {}
    for bone in data.bones:
        if bone.parent is not None:
            children.setdefault(bone.parent.name, []).append(bone)

    def _nearest_child_span(bone: Any) -> float | None:
        kids = children.get(bone.name)
        if not kids:
            return None
        return min((k.head_local - bone.head_local).length for k in kids)

    spans = [s for s in (_nearest_child_span(b) for b in data.bones) if s]
    median_span = sorted(spans)[len(spans) // 2] if spans else 1.0
    leaf_stub = LEAF_STUB_FACTOR * median_span

    changed: list[str] = []
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        edit_bones = data.edit_bones
        for bone in data.bones:
            expected = _nearest_child_span(bone)
            if expected is not None:
                if expected <= COLOCATED_FRACTION * median_span:
                    continue  # co-located child — no tail evidence, untouched
                if bone.length <= ABSURD_RATIO * expected:
                    continue  # plausible chain tail (sane rigs: <= ~5x) — untouched
                new_tail = min(
                    children[bone.name],
                    key=lambda k: (k.head_local - bone.head_local).length,
                ).head_local
            elif bone.parent is not None:
                if bone.length <= ABSURD_RATIO * median_span:
                    continue  # plausible leaf stub — untouched
                direction = Vector(bone.head_local) - Vector(bone.parent.head_local)
                if direction.length <= 1e-9:
                    continue
                new_tail = bone.head_local + direction.normalized() * leaf_stub
            else:
                continue  # parentless root — leave alone
            edit_bones[bone.name].tail = new_tail
            changed.append(bone.name)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    return len(changed)
