"""Per-defect fix operators (P8-9): the authored corrections behind the
review overlay's defect items.

The casting_desk pattern — the operators LIVE HERE (their bodies need the
payload read + the core affordances); ``__init__.py`` only imports the
classes into its registration table and draws the panel buttons. Each
operator is the scripted click-through's real interactive form: load the
payload, run the CORE affordance (docs/REVIEW_UX.md — pure functions,
confidence 1.0, provenance note), re-apply through the REAL apply path,
push one undo step, report.

- rm.finger_fix  — click a finger, drag the direction (author_finger)
- rm.face_trim   — per-param expression trim (trim_face)
- rm.figure_flip — per-figure flip, pins ride (flip_figure; scene payloads)
- rm.pin_retarget / rm.pin_confirm — the pin nudge (scene payloads)

Pose-level ops re-apply through pose_apply.apply_payload (the P1-6 path);
scene-level ops re-apply through scene_apply.apply_scene_payload (the P8-1
path) with the desk's cast_slots pairings. Nothing here re-solves anything.
"""
from __future__ import annotations

import json
from typing import Any, ClassVar

import bpy
from bpy.props import (
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import Operator

from . import bpy_bridge, pose_apply, scene_apply


def _load_payload(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _core_and_catch() -> tuple[Any, tuple[type[BaseException], ...]]:
    """The lazy core import (the bpy_bridge seam — addon modules stay
    bpy-importable without the core installed, the P0-13 contract) plus the
    exception tuple the operators render as error reports: the core's
    RiggermortisError base beside the payload/IO classes."""
    core = bpy_bridge.import_core()
    return core, (ValueError, OSError, KeyError, core.RiggermortisError)


def _desk_assignments(settings: Any) -> dict[str, str]:
    """The Casting Desk's label -> armature pairings (assigned rows only)."""
    return {
        slot.figure_label: slot.armature
        for slot in settings.cast_slots
        if slot.armature
    }


def _report_op(op: Operator, settings: Any, message: str) -> set[str]:
    settings.last_report = message
    op.report({"INFO"}, message)
    return {"FINISHED"}


class RM_OT_finger_fix(Operator):
    """Click a finger, drag the direction: author one finger chain (P8-9)"""

    bl_idname = "rm.finger_fix"
    bl_label = "Fix Finger"
    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

    hand: StringProperty(  # type: ignore[valid-type]
        name="Hand", description="hand.L / hand.R", default="hand.L",
    )
    finger: StringProperty(  # type: ignore[valid-type]
        name="Finger", description="thumb / index / middle / ring / pinky",
        default="index",
    )
    direction: FloatVectorProperty(  # type: ignore[valid-type]
        name="Drag direction", size=3, default=(0.0, 0.0, -1.0),
        description="Canonical-space direction the finger points along",
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        return (
            obj is not None and obj.type == "ARMATURE"
            and bool(context.scene.rm_settings.payload_path)
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rm_settings
        try:
            core, catch = _core_and_catch()
        except ImportError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        try:
            payload = _load_payload(str(settings.payload_path))
            pose = core.CanonicalPose.from_dict(
                pose_apply.payload_module().pose_for_figure(
                    payload, settings.figure or None)
            )
            if settings.mirror:
                pose = pose.mirrored()
            fixed = core.author_finger(
                pose, self.hand.strip(), self.finger.strip(),
                tuple(self.direction),
            )
            report = pose_apply.apply_pose_object(context.active_object, fixed, core)
        except catch as exc:
            self.report({"ERROR"}, f"finger fix refused: {exc}")
            return {"CANCELLED"}
        pose_apply.push_undo()
        return _report_op(
            self, settings,
            f"{self.hand.strip()}.{self.finger.strip()}: authored in review — "
            f"{len(report['applied'])} bone(s) re-applied, worst "
            f"{report['worst_deg']:.3f} deg (finger targets: see the preset's "
            f"hands bindings; a rig without them reports the capability line)",
        )


class RM_OT_face_trim(Operator):
    """Author one expression param, overriding the solver gate (P8-9)"""

    bl_idname = "rm.face_trim"
    bl_label = "Trim Face Param"
    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

    param: StringProperty(  # type: ignore[valid-type]
        name="Param", description="a D-022 param, e.g. smile.L",
        default="smile.L",
    )
    value: FloatProperty(  # type: ignore[valid-type]
        name="Value", min=0.0, max=1.0, default=0.5,
        description="Authored param value (clamped to [0, 1])",
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        return (
            obj is not None and obj.type == "ARMATURE"
            and bool(context.scene.rm_settings.payload_path)
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rm_settings
        try:
            core, catch = _core_and_catch()
        except ImportError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        try:
            payload = _load_payload(str(settings.payload_path))
            pose = core.CanonicalPose.from_dict(
                pose_apply.payload_module().pose_for_figure(
                    payload, settings.figure or None)
            )
            if settings.mirror:
                pose = pose.mirrored()
            fixed = core.trim_face(pose, self.param.strip(), float(self.value))
            report = pose_apply.apply_pose_object(context.active_object, fixed, core)
        except catch as exc:
            self.report({"ERROR"}, f"face trim refused: {exc}")
            return {"CANCELLED"}
        pose_apply.push_undo()
        return _report_op(
            self, settings,
            f"{self.param.strip()}: authored in review (trim {self.value:.2f}) — "
            f"{len(report['applied'])} bone(s) re-applied, worst "
            f"{report['worst_deg']:.3f} deg (facial targets: preset face_bones "
            f"bindings or shape keys by convention)",
        )


class _SceneFixOp(Operator):
    """Shared body for the scene-level fixes: mutate the payload dict
    in-memory through a core affordance, re-apply the WHOLE scene through
    the desk's pairings (the P8-1 one-action apply, coupling included)."""

    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

    def _affordance(self, core: Any, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        settings = context.scene.rm_settings
        return bool(settings.payload_path) and len(settings.cast_slots) > 0

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rm_settings
        try:
            core, catch = _core_and_catch()
        except ImportError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        try:
            payload = _load_payload(str(settings.payload_path))
            note = self._affordance(core, payload)
            assignments = _desk_assignments(settings)
            if not assignments:
                self.report({"ERROR"},
                            "no Casting Desk pairings — pair figures first")
                return {"CANCELLED"}
            report = scene_apply.apply_scene_payload(payload, assignments, core=core)
        except catch as exc:
            self.report({"ERROR"}, f"{self.bl_label} refused: {exc}")
            return {"CANCELLED"}
        return _report_op(
            self, settings,
            f"{note} — scene re-applied: {report['figures_applied']} figure(s), "
            f"worst {report['worst_deg']:.3f} deg"
            + (f", {len(report['figures_uncast'])} uncast"
               if report.get("figures_uncast") else ""),
        )


class RM_OT_figure_flip(_SceneFixOp):
    """Flip one figure of the scene (mirrored in place; its pins ride)"""

    bl_idname = "rm.figure_flip"
    bl_label = "Flip Figure"

    label: StringProperty(  # type: ignore[valid-type]
        name="Figure label", description="the scene figure to mirror",
        default="",
    )

    def _affordance(self, core: Any, payload: dict[str, Any]) -> str:
        scene = core.scene_from_payload(payload)
        flipped = core.flip_figure(scene, self.label.strip())
        entries = {str(e.get("label")): e for e in payload.get("figures", [])}
        for fig in flipped.figures:
            entry = entries.get(fig.label)
            if entry is not None and isinstance(entry.get("pose"), dict):
                entry["pose"] = fig.pose.to_dict()  # full replacement: the
                # mirror moves flips/hands/face/roll + positions together
        if payload.get("figure", {}).get("label") == self.label.strip() \
                and isinstance(payload.get("pose"), dict):
            fig = next(f for f in flipped.figures
                       if f.label == self.label.strip())
            payload["pose"] = fig.pose.to_dict()
        return f"figure {self.label.strip()} flipped"


class RM_OT_pin_retarget(_SceneFixOp):
    """Pin nudge: re-target one endpoint of a pin to an adjacent role"""

    bl_idname = "rm.pin_retarget"
    bl_label = "Retarget Pin"

    index: IntProperty(  # type: ignore[valid-type]
        name="Pin index", min=0, default=0,
        description="The pin's authored-order index",
    )
    endpoint: StringProperty(  # type: ignore[valid-type]
        name="Endpoint", default="a", description="'a' or 'b'",
    )
    new_role: StringProperty(  # type: ignore[valid-type]
        name="New role", default="hand.L",
        description="The canonical role this endpoint re-targets",
    )

    def _affordance(self, core: Any, payload: dict[str, Any]) -> str:
        scene = core.scene_from_payload(payload)
        retargeted = core.retarget_pin(
            scene, int(self.index), self.endpoint.strip(), self.new_role.strip())
        payload["pins"] = [p.to_dict() for p in retargeted.pins]
        return (f"pin {self.index} endpoint {self.endpoint.strip()} -> "
                f"{self.new_role.strip()}")


class RM_OT_pin_confirm(_SceneFixOp):
    """Confirm a suggested pin into an authored one (confidence 1.0)"""

    bl_idname = "rm.pin_confirm"
    bl_label = "Confirm Pin"

    index: IntProperty(  # type: ignore[valid-type]
        name="Pin index", min=0, default=0,
        description="The pin's authored-order index",
    )

    def _affordance(self, core: Any, payload: dict[str, Any]) -> str:
        scene = core.scene_from_payload(payload)
        confirmed = core.confirm_pin(scene, int(self.index))
        payload["pins"] = [p.to_dict() for p in confirmed.pins]
        return f"pin {self.index} confirmed"


CLASSES = (
    RM_OT_finger_fix,
    RM_OT_face_trim,
    RM_OT_figure_flip,
    RM_OT_pin_retarget,
    RM_OT_pin_confirm,
)
