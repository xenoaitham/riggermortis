"""bpy-side bridge: build riggermortis rig data from a live armature.

Pure ``bpy`` -> plain dict; the core package is imported lazily by operators so
the add-on still loads (and can report an actionable error) when
``riggermortis-core`` is not installed in Blender's Python.
"""
from __future__ import annotations

from typing import Any

CORE_MISSING_HINT = (
    "install the engine into Blender's Python: "
    "'<blender>/4.x/python/bin/python3.11 -m pip install riggermortis-core' "
    "(or use the bundled rigpose CLI for headless work)"
)


def rig_data_from_armature(armature_object: Any) -> dict[str, Any]:
    """Serialize an armature object into the riggermortis rig-dict format."""
    if armature_object.type != "ARMATURE":
        raise TypeError(f"{armature_object.name!r} is not an armature")
    bones: list[dict[str, Any]] = []
    for bone in armature_object.data.bones:
        bones.append(
            {
                "name": bone.name,
                "parent": bone.parent.name if bone.parent is not None else None,
                "head": [round(v, 6) for v in bone.head_local],
                "tail": [round(v, 6) for v in bone.tail_local],
            }
        )
    return {
        "format": 1,
        "name": armature_object.name,
        "source": "blender-addon",
        "bones": bones,
    }


def import_core():
    """Import riggermortis-core or raise with an actionable message."""
    try:
        import riggermortis
    except ImportError as exc:
        raise ImportError(CORE_MISSING_HINT) from exc
    return riggermortis
