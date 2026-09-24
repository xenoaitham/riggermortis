"""Casting Desk (P8-1): figures x armatures, one action applies all.

The operators LIVE HERE (their bodies need the payload read, and this
module owns it); ``__init__.py`` only imports the classes into its
registration table and draws the panel. Every helper returns
``(report_lines, error_message)`` with an empty ``error_message`` on
success — the operator's contract is a report and a return code, never a
traceback.

The scene apply is ``scene_apply.apply_scene_payload`` (the REAL per-figure
apply path composed over a validated casting); the camera is
``scene_camera.stage_scene_camera`` (stage-or-refuse per the IoU floor).
Pins are carried + reported here, never enforced (P8-2 owns enforcement).
"""
from __future__ import annotations

import json
from typing import Any, ClassVar

import bpy
from bpy.types import Operator

from . import scene_apply, scene_camera


def desk_read(path: str) -> Any:
    """JSON reader for the desk (errors are ValueError subclasses with text)."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def refresh_desk(settings: Any) -> tuple[str, str]:
    """Sync desk rows with the payload's figures (append missing, keep every
    existing pairing; unknown labels refuse at apply time).
    Returns (message, error)."""
    try:
        payload = desk_read(str(settings.payload_path or ""))
    except FileNotFoundError:
        return "", f"payload not found: {settings.payload_path}"
    except json.JSONDecodeError as exc:
        return "", f"payload is not valid JSON: {exc}"
    labels = _payload_figure_labels(payload)
    if not labels:
        return "", "payload carries no figures to pair"
    known = {slot.figure_label for slot in settings.cast_slots}
    added = 0
    for label in labels:  # payload order (stable detector output)
        if label in known:
            continue
        slot = settings.cast_slots.add()
        slot.figure_label = label
        added += 1
    total = len(settings.cast_slots)
    return f"desk synced: {added} new figure(s), {total} total", ""


def apply_scene_from_desk(settings: Any) -> tuple[list[str], str]:
    """The Apply Scene operator's body: validate + apply + report lines.
    Returns (report_lines, error)."""
    try:
        core = _core()
        payload = desk_read(str(settings.payload_path or ""))
        report = scene_apply.apply_scene_payload(
            payload, _desk_assignments(settings), core=core,
            mirror=bool(settings.mirror),
        )
    except (ValueError, ImportError, json.JSONDecodeError) as exc:
        return [], str(exc)
    return _scene_report_lines(report), ""


def stage_camera_from_desk(settings: Any) -> tuple[list[str], str]:
    """The Stage Scene Camera operator's body: stage-or-refuse per the floor.
    Returns (report_lines, error); error == "REFUSED" is the below-floor
    refusal (a WARNING at the operator, never a staged camera)."""
    try:
        core = _core()
        payload = desk_read(str(settings.payload_path or ""))
        report = scene_camera.stage_scene_camera(
            payload, _desk_assignments(settings), core=core,
        )
    except (ValueError, ImportError, json.JSONDecodeError) as exc:
        return [], str(exc)
    if not report["staged"]:
        return [
            f"camera v0 REFUSED to stage: {report['reason']} "
            f"(IoU {report['iou']:.3f} < floor {report['floor']:.2f})",
            "hint: " + report["hint"],
        ], "REFUSED"
    cam = report["camera"]
    created = " (created)" if report["created"] else ""
    return [
        f"camera v0 staged: {cam}{created}, lens {report['lens_mm']:.0f} mm, "
        f"subject-bbox IoU {report['iou']:.3f} (floor {report['floor']:.2f})",
        report["label"],
    ], ""


# -- operators (registered from __init__) --------------------------------------

class RM_OT_cast_refresh(Operator):
    """Sync the Casting Desk rows with the payload's figures (append missing,
    keep every existing pairing; unknown labels refuse at apply time)"""

    bl_idname = "rm.cast_refresh"
    bl_label = "Refresh Desk"
    bl_options: ClassVar[set[str]] = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(context.scene.rm_settings.payload_path)

    def execute(self, context: bpy.types.Context) -> set[str]:
        message, error = refresh_desk(context.scene.rm_settings)
        if error:
            self.report({"WARNING"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}


class RM_OT_apply_scene(Operator):
    """Apply every paired figure of the payload to its armature in ONE action (P8-1)"""

    bl_idname = "rm.apply_scene"
    bl_label = "Apply Scene"
    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        settings = context.scene.rm_settings
        return bool(settings.payload_path) and len(settings.cast_slots) > 0

    def execute(self, context: bpy.types.Context) -> set[str]:
        lines, error = apply_scene_from_desk(context.scene.rm_settings)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        context.scene.rm_settings.last_report = "\n".join(lines)
        self.report({"INFO"}, lines[0])
        return {"REGISTER"}


class RM_OT_stage_scene_camera(Operator):
    """Stage the APPROXIMATE scene camera from the reference framing (P8-1);
    refuses to stage below the subject-bbox IoU 0.75 floor"""

    bl_idname = "rm.stage_scene_camera"
    bl_label = "Stage Scene Camera (~APPROXIMATE~)"
    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        settings = context.scene.rm_settings
        return bool(settings.payload_path) and len(settings.cast_slots) > 0

    def execute(self, context: bpy.types.Context) -> set[str]:
        lines, error = stage_camera_from_desk(context.scene.rm_settings)
        if error and error != "REFUSED":
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        context.scene.rm_settings.last_report = "\n".join(lines)
        if error == "REFUSED":
            # the floor refused: loud, scene untouched (nothing was staged)
            self.report({"WARNING"}, lines[0])
            return {"CANCELLED"}
        self.report({"INFO"}, lines[0])
        return {"REGISTER"}


# -- internals ----------------------------------------------------------------

def _core() -> Any:
    from . import bpy_bridge

    return bpy_bridge.import_core()


def _desk_assignments(settings: Any) -> dict[str, str]:
    """The desk rows as a label -> armature map (unassigned rows dropped;
    the apply validates completeness in core)."""
    return {
        slot.figure_label: slot.armature
        for slot in settings.cast_slots
        if slot.figure_label and slot.armature
    }


def _payload_figure_labels(payload: dict) -> list[str]:
    """Figure labels from the payload via the core contract when importable,
    else the minimal shape walk (the panel fallback rule). Never raises."""
    try:
        core = _core()
        return [
            str(e.get("label") or f"figure {i}")
            for i, e in enumerate(core.payload.figure_entries(payload))
        ]
    except ImportError:
        figures = payload.get("figures")
        if isinstance(figures, list) and figures:
            return [
                str(e.get("label") or f"figure {i}")
                for i, e in enumerate(figures)
                if isinstance(e, dict)
            ]
        pose = payload.get("pose")
        return ["figure 0"] if isinstance(pose, dict) else []


def _scene_report_lines(report: dict) -> list[str]:
    """The apply report as panel lines (pins carried + reported, NOT enforced)."""
    mirrored = " (mirrored)" if report["mirror"] else ""
    summary = (
        f"scene applied: {report['figures_applied']} figure(s), "
        f"worst {report['worst_deg']:.3f} deg on {report['worst_figure']}"
        + mirrored
    )
    lines = [summary]
    pins = report["pins"]
    if pins:
        parts = []
        for p in pins:
            unconfirmed = "" if p["origin"] == "authored" else " — unconfirmed"
            parts.append(
                f"{p['figure_a']}.{p['role_a']} <-> "
                f"{p['figure_b']}.{p['role_b']} [{p['origin']}{unconfirmed}]"
            )
        lines.append("pins carried (NOT enforced until P8-2): " + ", ".join(parts))
    for fig in report["per_figure"]:
        if fig["notes"]:
            lines.append(f"{fig['figure']}: {fig['notes'][0]}")
    return lines
