"""Riggermortis — local, rig-agnostic posing & animation for Blender.

Phase 0 skeleton: N-panel, rig inspection, canonical role mapping persisted as
custom properties on the armature, content-policy preferences. Image posing
arrives in Phase 1; this panel keeps every unfinished action honest — it says
so instead of pretending.

Thin by architecture: all engine logic lives in ``riggermortis-core``.
"""
from __future__ import annotations

bl_info = {
    "name": "Riggermortis",
    "author": "Riggermortis contributors",
    "version": (0, 0, 1),
    "blender": (4, 0, 0),
    "location": "3D Viewport > N-panel > Riggermortis",
    "description": "Local rig-agnostic posing: image->pose, video->animation, agent-drivable via MCP",
    "doc_url": "https://github.com/riggermortis/riggermortis",
    "category": "Animation",
}

import bpy  # noqa: E402
from bpy.props import (  # noqa: E402
    BoolProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, Object, Operator, Panel, PropertyGroup  # noqa: E402

from . import bpy_bridge  # noqa: E402

POLICY_NOTICE = (
    "Default build is SFW. An opt-in adult module (off by default, requires "
    "explicit confirmation) permits explicit content of fictional adult "
    "characters only, processed 100% locally. Hard lines never toggle: no "
    "minors, no explicit content of real identifiable people, nothing illegal. "
    "See docs/POLICY.md."
)


# ---------------------------------------------------------------------------
# scene settings
# ---------------------------------------------------------------------------

class RM_SceneSettings(PropertyGroup):
    rig_object: StringProperty(  # type: ignore[valid-type]
        name="Rig",
        description="Armature object to map and pose",
    )
    image_path: StringProperty(  # type: ignore[valid-type]
        name="Reference image",
        description="Pose reference image (photo or anime art); Phase 1",
        subtype="FILE_PATH",
    )
    figure_index: IntProperty(  # type: ignore[valid-type]
        name="Figure",
        description="Which detected figure to pose (multi-figure images)",
        default=0,
        min=0,
    )
    mirror: BoolProperty(  # type: ignore[valid-type]
        name="Mirror",
        description="Mirror the detected pose left/right",
        default=False,
    )
    last_report: StringProperty(  # type: ignore[valid-type]
        name="Last report",
        description="Output of the most recent rig operation",
        default="",
    )


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

class RM_OT_inspect_and_map(Operator):
    """Inspect the active armature and map it to canonical roles"""

    bl_idname = "rm.inspect_and_map"
    bl_label = "Inspect & Map Rig"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        return obj is not None and obj.type == "ARMATURE"

    def execute(self, context: bpy.types.Context) -> set[str]:
        obj = context.active_object
        try:
            core = bpy_bridge.import_core()
        except ImportError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        rig_dict = bpy_bridge.rig_data_from_armature(obj)
        rig = core.RigData.from_dict(rig_dict)
        mapping = core.map_rig(rig)
        for role, assignment in mapping.assignments.items():
            obj[f"rm_role_{role}"] = assignment.bone
        settings = context.scene.rm_settings
        settings.last_report = mapping.summary()
        settings.rig_object = obj.name
        missing = mapping.core_missing()
        if missing:
            self.report(
                {"WARNING"},
                f"mapped {len(mapping.assignments)} roles; unresolved core roles: "
                f"{', '.join(missing)} — review flagged bones",
            )
        else:
            self.report(
                {"INFO"},
                f"mapped {len(mapping.assignments)} roles cleanly; "
                f"{len(mapping.ambiguities)} item(s) flagged for review",
            )
        return {"REGISTER"}


class RM_OT_show_report(Operator):
    """Show the last mapping report"""

    bl_idname = "rm.show_report"
    bl_label = "Show Last Report"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(context.scene.rm_settings.last_report)

    def execute(self, context: bpy.types.Context) -> set[str]:
        self.report({"INFO"}, context.scene.rm_settings.last_report)
        return {"FINISHED"}


class RM_OT_pose_from_image(Operator):
    """Apply a pose from a reference image (arrives in Phase 1)"""

    bl_idname = "rm.pose_from_image"
    bl_label = "Pose from Image (Phase 1)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        return obj is not None and obj.type == "ARMATURE"

    def execute(self, context: bpy.types.Context) -> set[str]:
        self.report(
            {"ERROR"},
            "Image posing is not implemented yet (Phase 1). "
            "The mapping pipeline above already works — see STATE/NEXT.md for the roadmap.",
        )
        return {"CANCELLED"}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class RM_PT_main_panel(Panel):
    bl_label = "Riggermortis"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Riggermortis"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = context.scene.rm_settings
        col = layout.column()
        col.prop_search(
            settings, "rig_object", context.scene, "objects", text="Rig"
        )
        col.operator("rm.inspect_and_map", icon="ARMATURE_DATA")
        col.operator("rm.show_report", icon="TEXT")

        box = layout.box()
        box.label(text="Pose from image", icon="POSE_HLT")
        box.prop(settings, "image_path")
        box.prop(settings, "figure_index")
        box.prop(settings, "mirror")
        box.operator("rm.pose_from_image")

        if settings.last_report:
            box = layout.box()
            for line in settings.last_report.splitlines()[:12]:
                box.label(text=line[:80])


class RM_AddonPreferences(AddonPreferences):
    bl_idname = __package__

    adult_module_enabled: BoolProperty(  # type: ignore[valid-type]
        name="Enable 18+ module",
        description=(
            "Permits explicit content of fictional adult characters only, "
            "rendered 100% locally. Off by default. See docs/POLICY.md."
        ),
        default=False,
    )
    adult_module_confirm: BoolProperty(  # type: ignore[valid-type]
        name="I understand the policy",
        description="Explicit confirmation required before the module can be enabled",
        default=False,
    )

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        box = layout.box()
        box.label(text="Content policy", icon="INFO")
        for chunk in (POLICY_NOTICE[:72], POLICY_NOTICE[72:144], POLICY_NOTICE[144:]):
            if chunk:
                box.label(text=chunk)
        col = box.column()
        col.prop(self, "adult_module_enabled")
        if self.adult_module_enabled:
            col.prop(self, "adult_module_confirm")
            if not self.adult_module_confirm:
                col.label(text="Confirmation required", icon="ERROR")


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

_CLASSES = (
    RM_SceneSettings,
    RM_OT_inspect_and_map,
    RM_OT_show_report,
    RM_OT_pose_from_image,
    RM_PT_main_panel,
    RM_AddonPreferences,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rm_settings = PointerProperty(type=RM_SceneSettings)


def unregister() -> None:
    del bpy.types.Scene.rm_settings
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
