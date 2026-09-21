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

from typing import Any, ClassVar

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup

from . import bpy_bridge, live_driver, overlay, pose_apply, session, tails

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
        import riggermortis.payload as payload_mod
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
    manual_flips: StringProperty(  # type: ignore[valid-type]
        name="Manual flips",
        description="Flip keys toggled in review this session (comma-separated). "
                    "Session state: the payload file itself stays untouched.",
        default="",
    )


class RM_WM_Session(PropertyGroup):
    """Agent-session settings (P3-5). Lives on the WindowManager: session-only
    state, never saved to disk or into .blend files — the token especially."""

    port: IntProperty(  # type: ignore[valid-type]
        name="Port",
        description="TCP port of the MCP server's session bridge "
                    "(always 127.0.0.1 — the add-on dials out, nothing listens here)",
        default=8765,
        min=1,
        max=65535,
    )
    token: StringProperty(  # type: ignore[valid-type]
        name="Token",
        description="Session token the MCP server was started with "
                    "(--session-token). Session-only: never saved to disk.",
        subtype="PASSWORD",
        default="",
    )


class RM_WM_Live(PropertyGroup):
    """Live stream consumer settings (P5-2, extended by P5-3).
    WindowManager like the session state: session-only, never saved into
    .blend files."""

    stream_path: StringProperty(  # type: ignore[valid-type]
        name="Stream",
        description="live stream file written by 'rigpose live' (spawn the "
                    "side process from your shell or xtask/live_capture.sh)",
        subtype="FILE_PATH",
        default="",
    )
    stale_after: FloatProperty(  # type: ignore[valid-type]
        name="Stale after (s)",
        description="Seconds without a new stream line before the panel "
                    "reports STALE (the last pose is kept). Order-of-magnitude "
                    "default, not a tuned threshold.",
        default=2.0,
        min=0.1,
        max=30.0,
    )
    failsafe_after: FloatProperty(  # type: ignore[valid-type]
        name="Failsafe after (s)",
        description="SUSTAINED stream silence before the driver clears the "
                    "rig to rest (docs/LIVE.md P5-3): a frozen mid-gesture "
                    "pose is the stale-puppet trap; rest is the safe state. "
                    "Fires strictly after the STALE readout, never before. "
                    "Order-of-magnitude default, not tuned.",
        default=10.0,
        min=0.5,
        max=120.0,
    )
    smoothing: BoolProperty(  # type: ignore[valid-type]
        name="Smooth (1€)",
        description="Filter the stream's canonical poses through the P2-2 "
                    "one-euro filter before apply (docs/LIVE.md P5-3); read "
                    "fresh per tick, effective on the next line. Defaults "
                    "are order-of-magnitude starting points, never tuned "
                    "(D-008).",
        default=True,
    )


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

class RM_OT_inspect_and_map(Operator):
    """Inspect the active armature and map it to canonical roles"""

    bl_idname = "rm.inspect_and_map"
    bl_label = "Inspect & Map Rig"
    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

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
        # P2-8a (D-015): conditional glTF/VRM tail repair BEFORE mapping or
        # posing — garbage tails break Blender's evaluated placement. Sane
        # rigs are a bit-for-bit no-op; the count is reported, never silent.
        repaired = tails.normalize_imported_tails(obj)
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
        if repaired:
            unit = "tail" if repaired == 1 else "tails"
            self.report({"INFO"}, f"normalized {repaired} imported bone {unit} (D-015)")
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
    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

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


class RM_OT_flip_toggle(Operator):
    """Toggle one distal flip (elbow/knee bend) and re-apply in-process — the D-008 rescue"""

    bl_idname = "rm.flip_toggle"
    bl_label = "Toggle Flip"
    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

    flip_key: StringProperty(  # type: ignore[valid-type]
        name="Flip key",
        description="Distal flip to override (e.g. forearm.L, lower_leg.R)",
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
        key = self.flip_key.strip()
        try:
            core = bpy_bridge.import_core()
            payload = _load_payload(settings.payload_path)
            pose = core.CanonicalPose.from_dict(
                pose_apply.payload_module().pose_for_figure(payload, settings.figure or None)
            )
            if settings.mirror:
                pose = pose.mirrored()
            toggled = pose.toggled(key)
            if toggled is pose:
                self.report(
                    {"WARNING"},
                    f"{key}: nothing to toggle (unknown key, or the distal joint "
                    "is not in this figure's pose)",
                )
                return {"CANCELLED"}
            report = pose_apply.apply_pose_object(context.active_object, toggled, core)
        except (ValueError, ImportError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        pose_apply.push_undo()

        flips = [f for f in settings.manual_flips.split(",") if f]
        if key in flips:
            flips.remove(key)
        else:
            flips.append(key)
        flips.sort()
        settings.manual_flips = ",".join(flips)
        settings.last_report = (
            f"flip {key} {'ON' if key in flips else 'OFF (back to solver choice)'} — "
            f"{len(report['applied'])} bone(s) re-applied, "
            f"self-check worst {report['worst_deg']:.3f} deg on {report['worst_role']}"
        )
        self.report({"INFO"}, settings.last_report)
        return {"REGISTER"}


class RM_OT_pick_joint(Operator):
    """Click a joint in the viewport to pick it; flip keys toggle, others report confidence"""

    bl_idname = "rm.pick_joint"
    bl_label = "Pick Joint (click in viewport)"
    bl_options: ClassVar[set[str]] = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        return (
            obj is not None and obj.type == "ARMATURE"
            and context.scene.rm_settings.overlay_enabled
        )

    def invoke(self, context: bpy.types.Context, _event: bpy.types.Event) -> set[str]:
        if context.area and context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "run from the 3D viewport")
            return {"CANCELLED"}
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        if event.type == "RIGHTMOUSE" or event.type in {"ESC", "RET"}:
            return {"FINISHED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS":
            return {"PASS_THROUGH"}
        from bpy_extras import view3d_utils

        region = context.region
        rv3d = context.region_data
        if region is None or rv3d is None:
            return {"PASS_THROUGH"}
        try:
            core = bpy_bridge.import_core()
        except ImportError as exc:
            self.report({"ERROR"}, str(exc))
            return {"FINISHED"}
        settings = context.scene.rm_settings
        pose = overlay.effective_pose(settings, core)
        if pose is None:
            self.report({"WARNING"}, "no pose to pick (load a payload, enable the overlay)")
            return {"FINISHED"}
        coord = (event.mouse_region_x, event.mouse_region_y)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        ray_dir = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        scale_origin = overlay._anchor(context)
        points = core.joint_points(pose, origin=scale_origin[0], scale=scale_origin[1])
        role = core.pick_joint(points, ray_origin, ray_dir, radius=scale_origin[1] * 0.06)
        if role is None:
            self.report({"INFO"}, "no joint under the click")
            return {"RUNNING_MODAL"}
        conf = pose.joint_confidence.get(role)
        is_flip = role in ("forearm.L", "forearm.R", "lower_leg.L", "lower_leg.R")
        if is_flip:
            bpy.ops.rm.flip_toggle("INVOKE_DEFAULT", flip_key=role)
        else:
            self.report(
                {"INFO"},
                f"{role}: confidence {conf:.2f}" if conf is not None else f"{role}",
            )
        return {"RUNNING_MODAL"}


class RM_OT_flip_reset(Operator):
    """Reset all manual flips back to the solver's choices and re-apply"""

    bl_idname = "rm.flip_reset"
    bl_label = "Reset Manual Flips"
    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(context.scene.rm_settings.manual_flips)

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rm_settings
        settings.manual_flips = ""
        flipped = context.scene.rm_settings.payload_path
        try:
            core = bpy_bridge.import_core()
            payload = _load_payload(flipped)
            pose = core.CanonicalPose.from_dict(
                pose_apply.payload_module().pose_for_figure(
                    payload, settings.figure or None
                )
            )
            if settings.mirror:
                pose = pose.mirrored()
            report = pose_apply.apply_pose_object(context.active_object, pose, core)
        except (ValueError, ImportError, AttributeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        pose_apply.push_undo()
        self.report({"INFO"}, f"solver flips restored ({len(report['applied'])} bones)")
        return {"REGISTER"}


class RM_OT_clear_pose(Operator):
    """Restore every pose bone on the active armature to rest"""

    bl_idname = "rm.clear_pose"
    bl_label = "Clear Pose"
    bl_options: ClassVar[set[str]] = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = context.active_object
        return obj is not None and obj.type == "ARMATURE"

    def execute(self, context: bpy.types.Context) -> set[str]:
        message = pose_apply.clear_pose(context.active_object)
        context.scene.rm_settings.manual_flips = ""  # review state is session-only
        pose_apply.push_undo()
        self.report({"INFO"}, message)
        return {"REGISTER"}


class RM_OT_session_connect(Operator):
    """Connect to the MCP server's session bridge (127.0.0.1, opt-in)"""

    bl_idname = "rm.session_connect"
    bl_label = "Connect Agent Session"
    bl_options: ClassVar[set[str]] = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return not session.running()

    def execute(self, context: bpy.types.Context) -> set[str]:
        wm_session = context.window_manager.rm_session
        error = session.start_session(wm_session.port, wm_session.token)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, f"session connecting on 127.0.0.1:{wm_session.port}")
        return {"FINISHED"}


class RM_OT_session_disconnect(Operator):
    """Disconnect the agent session (stop polling for actions)"""

    bl_idname = "rm.session_disconnect"
    bl_label = "Disconnect Agent Session"
    bl_options: ClassVar[set[str]] = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return session.running()

    def execute(self, context: bpy.types.Context) -> set[str]:
        session.stop_session()
        self.report({"INFO"}, "agent session disconnected")
        return {"FINISHED"}


class RM_OT_live_start(Operator):
    """Start the live stream consumer (P5-2): tail the 'rigpose live'
    stream file and puppeteer the rig through the real apply path"""

    bl_idname = "rm.live_start"
    bl_label = "Start Live"
    bl_options: ClassVar[set[str]] = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return not live_driver.running()

    def execute(self, context: bpy.types.Context) -> set[str]:
        settings = context.scene.rm_settings
        obj = bpy.data.objects.get(settings.rig_object)
        if obj is None or obj.type != "ARMATURE":
            obj = context.active_object
        if obj is None or obj.type != "ARMATURE":
            self.report(
                {"ERROR"},
                "no rig selected (hint: pick the rig in the panel or set it "
                "active, then Start Live)",
            )
            return {"CANCELLED"}
        wm_live = context.window_manager.rm_live
        error = live_driver.start_live(
            wm_live.stream_path,
            obj.name,
            stale_after=wm_live.stale_after,
            failsafe_after=wm_live.failsafe_after,
            mirror=settings.mirror,
            smoothing=wm_live.smoothing,
        )
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report(
            {"INFO"},
            f"live driver running on {obj.name} (hint: spawn the side "
            "process: rigpose live <frames_dir> <rig.json> --out live.jsonl)",
        )
        return {"FINISHED"}


class RM_OT_live_stop(Operator):
    """Stop the live stream consumer (the last applied pose stays)"""

    bl_idname = "rm.live_stop"
    bl_label = "Stop Live"
    bl_options: ClassVar[set[str]] = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        del context
        return live_driver.running()

    def execute(self, context: bpy.types.Context) -> set[str]:
        del context
        live_driver.stop_live()
        self.report({"INFO"}, "live driver stopped (the last pose stays)")
        return {"FINISHED"}


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
            joint_items = sorted(joint_conf.items())
            for shown, (role, conf) in enumerate(joint_items):
                if shown >= 8:
                    box.label(text=f"… and {len(joint_items) - shown} more")
                    break
                box.label(text=f"{role:<14} {conf:.2f}", icon=_conf_icon(conf))
        row = box.row()
        row.prop(settings, "mirror")
        row.operator("rm.apply_pose", icon="PLAY")
        box.operator("rm.clear_pose", icon="X")

        box = layout.box()
        box.label(text="Agent session (MCP)", icon="LINKED")
        wm_session = context.window_manager.rm_session
        box.prop(wm_session, "port")
        box.prop(wm_session, "token")
        if session.running():
            box.operator("rm.session_disconnect", icon="UNCHECKED")
        else:
            box.operator("rm.session_connect", icon="CHECKMARK")
        for line in session.ui_status().splitlines():
            box.label(text=line)

        box = layout.box()
        box.label(text="Live driver (P5-2)", icon="TIME")
        wm_live = context.window_manager.rm_live
        box.prop(wm_live, "stream_path")
        row = box.row(align=True)
        row.prop(wm_live, "stale_after")
        row.prop(wm_live, "failsafe_after")
        box.prop(wm_live, "smoothing")
        if live_driver.running():
            box.operator("rm.live_stop", icon="PAUSE")
            driver = live_driver.driver()
            if driver is not None:
                for line in driver.ui_status().splitlines():
                    box.label(text=line)
        else:
            box.operator("rm.live_start", icon="PLAY")
            box.label(text="spawn the side process from a terminal:", icon="INFO")
            box.label(text="rigpose live <frames_dir> <rig.json> \\", icon="INFO")
            box.label(text="    --out live.jsonl --detect-every 5", icon="INFO")

        box = layout.box()
        box.label(text="Review overlay", icon="HIDE_OFF")
        box.prop(settings, "image_path")
        box.prop(settings, "overlay_enabled")
        box.operator("rm.pick_joint", icon="RESTRICT_SELECT_OFF")
        if settings.manual_flips:
            box.label(text=f"manual flips: {settings.manual_flips}", icon="FLIP")
            box.operator("rm.flip_reset", icon="LOOP_BACK")

        payload_obj = _payload_summary(settings.payload_path)
        if payload_obj is not None:
            try:
                core = bpy_bridge.import_core()
                pose = overlay.effective_pose(settings, core)
                items = core.review_items(pose) if pose is not None else []
                flagged = [i for i in items if i.kind == "flip"]
                if flagged:
                    box = layout.box()
                    box.label(text="Flagged flips (D-008 rescue)", icon="ERROR")
                    for item in flagged:
                        row = box.row(align=True)
                        row.label(text=item.role, icon=_conf_icon(1.0 - item.severity))
                        row.operator(
                            "rm.flip_toggle", text="Toggle", icon="FLIP"
                        ).flip_key = item.role
            except ImportError:
                pass

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
    RM_WM_Session,
    RM_WM_Live,
    RM_OT_inspect_and_map,
    RM_OT_show_report,
    RM_OT_apply_pose,
    RM_OT_flip_toggle,
    RM_OT_pick_joint,
    RM_OT_flip_reset,
    RM_OT_clear_pose,
    RM_OT_session_connect,
    RM_OT_session_disconnect,
    RM_OT_live_start,
    RM_OT_live_stop,
    RM_PT_main_panel,
    RM_AddonPreferences,
)


def register() -> None:
    session.stop_session()  # addon reload: never carry a stale client over
    live_driver.stop_live()  # ...nor a stale stream pump
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rm_settings = PointerProperty(type=RM_SceneSettings)
    bpy.types.WindowManager.rm_session = PointerProperty(type=RM_WM_Session)
    bpy.types.WindowManager.rm_live = PointerProperty(type=RM_WM_Live)
    from . import overlay

    overlay.register()


def unregister() -> None:
    session.stop_session()  # kills the client thread + pump, if any
    live_driver.stop_live()  # kills the stream pump, if any
    from . import overlay

    overlay.unregister()
    del bpy.types.WindowManager.rm_live
    del bpy.types.WindowManager.rm_session
    del bpy.types.Scene.rm_settings
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
