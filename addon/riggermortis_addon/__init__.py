"""Riggermortis — local, rig-agnostic posing & animation for Blender.

Phase 1 pose UX: the N-panel consumes ``rigpose pose`` payload JSON (D-009 —
inference runs outside Blender; spawn lives in the user's shell / agent /
shell glue). Apply Pose rebuilds the pose in-process from the payload (stdlib
core) and writes pose-bone rotations; Clear Pose restores rest. Every unfinished
action still says so instead of pretending.

Thin by architecture: all engine logic lives in ``riggermortis-core``.
"""
from __future__ import annotations

import json

bl_info = {
    "name": "Riggermortis",
    "author": "Riggermortis contributors",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "3D Viewport > N-panel > Riggermortis",
    "description": "Local rig-agnostic posing: image->pose, video->animation, agent-drivable via MCP",
    "doc_url": "https://github.com/riggermortis/riggermortis",
    "category": "Animation",
}

import bpy  # noqa: E402
from bpy.props import (  # noqa: E402
    BoolProperty,
    EnumProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup  # noqa: E402
from typing import Any  # noqa: E402

from . import bpy_bridge, pose_apply  # noqa: E402

POLICY_NOTICE = (
    "Default build is SFW. An opt-in adult module (off by default, requires "
    "explicit confirmation) permits explicit content of fictional adult "
    "characters only, processed 100% locally. Hard lines never toggle: no "
    "minors, no explicit content of real identifiable people, nothing illegal. "
    "See docs/POLICY.md."
)

PAYLOAD_HINT = (
    "Generate a payload first (terminal): rigpose pose <image> <rig.json> --out payload.json"
)


# ---------------------------------------------------------------------------
# scene settings
# ---------------------------------------------------------------------------

def _figure_rows(payload: dict) -> list[dict]:
    """Per-figure {label, confidence, reliable} rows for the panel dropdown.

    Uses the core payload contract when importable (the one implementation of
    the D-009 rules); falls back to a minimal shape walk at draw time so the
    panel still renders usefully when core is missing (Apply then shows the
    real install error). Never raises.
    """
    try:
        import riggermortis.payload as payload_mod  # noqa: PLC0415
        entries = payload_mod.figure_entries(payload)
        return [
            {
                "label": str(e.get("label", "?")),
                "confidence": float((e.get("pose") or {}).get("confidence", 0.0)),
                "reliable": bool((e.get("pose") or {}).get("reliable", False)),
            }
            for e in entries if isinstance(e, dict)
        ]
    except Exception:  # noqa: BLE001 — draw-time best effort; apply reports precisely
        fmt = payload.get("format", 1)
        if fmt == 2 and isinstance(payload.get("figures"), list):
            rows = []
            for e in payload["figures"]:
                if isinstance(e, dict):
                    pose = e.get("pose") or {}
                    rows.append({
                        "label": str(e.get("label", "?")),
                        "confidence": float(pose.get("confidence", 0.0)),
                        "reliable": bool(pose.get("reliable", False)),
                    })
            return rows
        pose = payload.get("pose") or {}
        figure = payload.get("figure") or {}
        if pose:
            return [{
                "label": str(figure.get("label", "figure 0")),
                "confidence": float(pose.get("confidence", 0.0)),
                "reliable": bool(pose.get("reliable", False)),
            }]
        return []


def _figure_enum_items(self: Any, context: Any) -> list[tuple[str, str, str]]:
    """Dynamic EnumProperty items: the figures embedded in the current payload."""
    del self  # PropertyGroup instance — the payload lives on the scene settings
    settings = context.scene.rm_settings
    payload = _payload_summary(settings.payload_path)
    if not payload:
        return [("", "(no payload)", "Load a pose payload JSON first")]
    rows = _figure_rows(payload)
    if not rows:
        return [("", "(no figures)", "Payload carries no figures")]
    return [
        (row["label"], row["label"],
         f"confidence {row['confidence']:.2f} — "
         + ("reliable" if row["reliable"] else "low confidence, review"))
        for row in rows
    ]


class RM_SceneSettings(PropertyGroup):
    rig_object: StringProperty(  # type: ignore[valid-type]
        name="Rig",
        description="Armature object to map and pose",
    )
    image_path: StringProperty(  # type: ignore[valid-type]
        name="Reference image",
        description="Pose reference image (shown in the review overlay, P1-7)",
        subtype="FILE_PATH",
    )
    payload_path: StringProperty(  # type: ignore[valid-type]
        name="Pose payload",
        description="JSON written by 'rigpose pose' (D-009: the add-on consumes payloads)",
        subtype="FILE_PATH",
    )
    figure: EnumProperty(  # type: ignore[valid-type]
        name="Figure",
        description="Which detected figure to apply (switch in-process when the "
                    "payload embeds several, i.e. written with --all-figures)",
        items=_figure_enum_items,
    )
    mirror: BoolProperty(  # type: ignore[valid-type]
        name="Mirror",
        description="Apply the mirrored pose (x -> -x, sides swapped)",
        default=False,
    )
    overlay_enabled: BoolProperty(  # type: ignore[valid-type]
        name="Pose review overlay",
        description="Draw the canonical ghost skeleton with per-joint confidence colors",
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


def _load_payload(path: str) -> dict:
    """Read a pose payload with actionable errors (no tracebacks at users)."""
    if not path:
        raise ValueError(PAYLOAD_HINT)
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise ValueError(f"payload not found: {path} ({PAYLOAD_HINT})") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"payload is not valid JSON: {path}: {exc}") from exc


class RM_OT_apply_pose(Operator):
    """Apply a 'rigpose pose' payload to the active armature"""

    bl_idname = "rm.apply_pose"
    bl_label = "Apply Pose"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        return obj is not None and obj.type == "ARMATURE"

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rm_settings
        try:
            payload = _load_payload(settings.payload_path)
            report = pose_apply.apply_payload(
                context.active_object, payload, mirror=settings.mirror
            )
        except (ValueError, ImportError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        pose_apply.push_undo()

        lines = [
            f"applied {len(report['applied'])} bone(s) "
            f"[{report['mapping_source']}]"
            + (" (mirrored)" if report["mirrored"] else ""),
            f"pose confidence {report['confidence']:.2f}"
            + ("" if report["reliable"] else " — BELOW the reliable bar, review"),
        ]
        if report["missing_pose_bones"]:
            lines.append(f"missing pose bones: {', '.join(report['missing_pose_bones'])}")
        for note in report["notes"][:4]:
            lines.append(f"note: {note}")
        lines.append(f"self-check: worst {report['worst_deg']:.3f} deg on {report['worst_role']}")
        if report["core_missing"]:
            lines.append(f"core roles unmapped: {report['core_missing']}")
        settings.last_report = "\n".join(lines)
        settings.rig_object = context.active_object.name

        if not report["reliable"] or report["missing_pose_bones"]:
            self.report({"WARNING"}, lines[0] + " — see Last Report")
        else:
            self.report({"INFO"}, lines[0] + f", worst {report['worst_deg']:.3f} deg")
        return {"REGISTER"}


class RM_OT_clear_pose(Operator):
    """Restore every pose bone on the active armature to rest"""

    bl_idname = "rm.clear_pose"
    bl_label = "Clear Pose"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        return obj is not None and obj.type == "ARMATURE"

    def execute(self, context: bpy.types.Context) -> set[str]:
        message = pose_apply.clear_pose(context.active_object)
        pose_apply.push_undo()
        self.report({"INFO"}, message)
        return {"REGISTER"}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def _payload_summary(path: str) -> dict | None:
    """Small (path, mtime)-cached payload read for panel labels; None if unreadable."""
    import os

    if not path or not os.path.isfile(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        cache = getattr(_payload_summary, "_cache", None)
        if cache and cache[0] == path and cache[1] == mtime:
            return cache[2]
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        _payload_summary._cache = (path, mtime, data)  # type: ignore[attr-defined]
        return data
    except (OSError, json.JSONDecodeError):
        return None


def _selected_row(rows: list[dict], label: str) -> dict | None:
    """The dropdown's chosen figure row; falls back to the first row."""
    for row in rows:
        if row["label"] == label:
            return row
    return rows[0] if rows else None


def _conf_icon(conf: float) -> str:
    if conf < 0.55:
        return "ERROR"
    if conf < 0.75:
        return "QUESTION"
    return "CHECKMARK"


class RM_PT_main_panel(Panel):
    bl_label = "Riggermortis"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Riggermortis"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = context.scene.rm_settings
        col = layout.column()
        col.prop_search(settings, "rig_object", context.scene, "objects", text="Rig")
        col.operator("rm.inspect_and_map", icon="ARMATURE_DATA")
        col.operator("rm.show_report", icon="TEXT")

        box = layout.box()
        box.label(text="Pose from image", icon="POSE_HLT")
        box.prop(settings, "payload_path")
        payload = _payload_summary(settings.payload_path)
        if payload is None:
            for chunk in (PAYLOAD_HINT[:64], PAYLOAD_HINT[64:]):
                if chunk:
                    box.label(text=chunk, icon="INFO")
        else:
            rows = _figure_rows(payload)
            box.prop(settings, "figure")
            row = _selected_row(rows, settings.figure)
            if row is not None:
                state = "reliable" if row["reliable"] else "low confidence — review"
                box.label(
                    text=f"{row['label']}  conf {row['confidence']:.2f} ({state})",
                    icon=_conf_icon(row["confidence"]),
                )
                if len(rows) > 1 and not (payload.get("figures") and len(payload["figures"]) > 1):
                    box.label(text="switch figures: regenerate with --all-figures", icon="INFO")
            pose = payload.get("pose") or {}
            joint_conf = pose.get("joint_confidence", {})
            shown = 0
            for role, conf in sorted(joint_conf.items()):
                if shown >= 8:
                    box.label(text=f"… and {len(joint_conf) - shown} more")
                    break
                box.label(text=f"{role:<14} {conf:.2f}", icon=_conf_icon(conf))
                shown += 1
        row = box.row()
        row.prop(settings, "mirror")
        row.operator("rm.apply_pose", icon="PLAY")
        box.operator("rm.clear_pose", icon="X")

        box = layout.box()
        box.label(text="Review overlay", icon="HIDE_OFF")
        box.prop(settings, "image_path")
        box.prop(settings, "overlay_enabled")

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
    RM_OT_apply_pose,
    RM_OT_clear_pose,
    RM_PT_main_panel,
    RM_AddonPreferences,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rm_settings = PointerProperty(type=RM_SceneSettings)
    from . import overlay

    overlay.register()


def unregister() -> None:
    from . import overlay

    overlay.unregister()
    del bpy.types.Scene.rm_settings
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
