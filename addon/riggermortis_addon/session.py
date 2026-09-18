"""Agent session bridge — the Blender side of P3-5 (mcp/DESIGN.md).

A background thread dials the MCP server's loopback transport (127.0.0.1
ONLY — the add-on connects OUT; nothing ever listens inside Blender), says
``hello`` with the session token, and polls for enqueued actions. Actions are
executed on Blender's MAIN thread (a ``bpy.app.timers`` pump, or
``pump_once()`` driven directly by headless probes) through the add-on's REAL
machinery — ``apply_pose`` runs the same payload path as the Apply Pose
operator (D-009). Results travel back as structured reports; executor errors
are structured and actionable, never tracebacks over the socket.

The thread itself NEVER touches ``bpy``: it only moves dicts between the
socket and the inbound/outbound queues. Connection settings (port + token)
live on WindowManager properties — session-only state, never saved to disk.

Lifecycle honesty: a dropped connection backs off and reconnects (0.5 s
doubling, 5 s cap) until stopped; ``auth_failed`` STOPS the client (retrying
a wrong token is pointless — fix the token and reconnect). Dispatched
actions that die with a connection are marked stale SERVER-side; the client
never replays them on its own (idempotency is the enqueuer's concern).
"""
from __future__ import annotations

import contextlib
import importlib
import json
import queue
import socket
import threading
from typing import Any

from . import bpy_bridge, pose_apply, tails

PROTOCOL_VERSION = 1
LOOPBACK_HOST = "127.0.0.1"
POLL_INTERVAL = 0.5
POLL_MAX = 8
RECONNECT_MIN = 0.5
RECONNECT_MAX = 5.0
#: Known action kinds — mirrors mcp/session_bridge.KNOWN_ACTION_KINDS v1.
KNOWN_ACTION_KINDS = (
    "inspect_scene", "apply_pose", "bake_action", "render_turntable",
    "apply_style",
)

_STATE: dict[str, Any] = {}


class SessionClient:
    """Background poll/result loop. Socket-only; never touches bpy."""

    def __init__(self, host: str, port: int, token: str, agent_info: dict[str, Any]) -> None:
        self.host = host
        self.port = port
        self.token = token
        self._agent_info = dict(agent_info)
        self.inbound: queue.Queue[dict[str, Any]] = queue.Queue()
        self.outbound: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stop = threading.Event()
        self._state_lock = threading.Lock()
        self._state: dict[str, Any] = {
            "state": "starting", "detail": "", "port": port,
            "connects": 0, "results_sent": 0,
        }
        self.thread: threading.Thread | None = None
        self._sock: socket.socket | None = None
        self._sockfile: Any = None  # readline handle for the live connection

    # -- control ------------------------------------------------------------

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self._run, name="rm-session-client", daemon=True,
        )
        self.thread.start()

    def running(self) -> bool:
        return not self._stop.is_set()

    def stop(self) -> None:
        self._stop.set()
        with self._state_lock:
            sock, self._sock = self._sock, None
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.close()

    def snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return dict(self._state)

    # -- state (thread-safe) -------------------------------------------------

    def _set_state(self, state: str, detail: str = "", **extra: Any) -> None:
        with self._state_lock:
            self._state["state"] = state
            self._state["detail"] = detail
            self._state.update(extra)

    # -- the loop ------------------------------------------------------------

    def _run(self) -> None:
        backoff = RECONNECT_MIN
        while not self._stop.is_set():
            self._set_state("connecting")
            try:
                sock = socket.create_connection((self.host, self.port), timeout=3.0)
            except OSError as exc:
                if self._stop.is_set():
                    break
                self._set_state("reconnecting", str(exc))
                self._stop.wait(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX)
                continue
            backoff = RECONNECT_MIN
            sock.settimeout(5.0)
            with self._state_lock:
                self._sock = sock
            try:
                if not self._session_loop(sock):
                    break  # hard stop (auth rejected or asked to stop)
            except (OSError, json.JSONDecodeError) as exc:
                if not self._stop.is_set():
                    self._set_state("reconnecting", str(exc))
            finally:
                sockfile = self._sockfile
                self._sockfile = None
                if sockfile is not None:
                    with contextlib.suppress(OSError):
                        sockfile.close()
                with contextlib.suppress(OSError):
                    sock.close()
                with self._state_lock:
                    self._sock = None
        self._set_state("stopped")

    def _session_loop(self, sock: socket.socket) -> bool:
        """One authenticated connection. False = stop the client entirely."""
        self._sockfile = sock.makefile("r", encoding="utf-8", newline="\n")
        self._send(sock, {"v": PROTOCOL_VERSION, "op": "hello", "token": self.token,
                          **self._agent_info})
        reply = self._recv(sock)
        op = reply.get("op")
        if op == "error" and reply.get("code") == "auth_failed":
            self._set_state("auth_failed", str(reply.get("message", "")))
            self._stop.set()
            return False
        if op != "welcome":
            self._set_state("reconnecting", f"handshake: {reply.get('op')!r}")
            return True
        with self._state_lock:
            self._state["connects"] += 1
            connects = self._state["connects"]
        self._set_state("connected", f"connection #{connects}")
        while not self._stop.is_set():
            while True:  # results first, so the queue drains before the poll
                try:
                    result = self.outbound.get_nowait()
                except queue.Empty:
                    break
                self._send(sock, {"v": PROTOCOL_VERSION, "op": "result", **result})
                with self._state_lock:
                    self._state["results_sent"] += 1
            self._send(sock, {"v": PROTOCOL_VERSION, "op": "poll", "max": POLL_MAX})
            while True:  # acks may precede the actions frame — read through
                reply = self._recv(sock)
                reply_op = reply.get("op")
                if reply_op == "actions":
                    for action in reply.get("actions") or []:
                        self.inbound.put(action)
                    break
                if reply_op == "error":
                    self._set_state("reconnecting", str(reply.get("message", "")))
                    return True
                # ack: result accepted — keep reading
            self._stop.wait(POLL_INTERVAL)
        return False

    # -- framing (same shapes as mcp/session_bridge.py) -----------------------

    def _send(self, sock: socket.socket, message: dict[str, Any]) -> None:
        sock.sendall((json.dumps(message, sort_keys=True) + "\n").encode("utf-8"))

    def _recv(self, sock: socket.socket) -> dict[str, Any]:
        del sock  # the readline handle lives on the client, not the socket
        sockfile = self._sockfile
        if sockfile is None:
            raise OSError("no live connection")
        raw = sockfile.readline()
        if not raw:
            raise OSError("connection closed by the server")
        message = json.loads(raw)
        if not isinstance(message, dict):
            return {"op": None}
        return message


# ---------------------------------------------------------------------------
# main-thread executor
# ---------------------------------------------------------------------------

def execute_action(action: dict[str, Any]) -> dict[str, Any]:
    """Run ONE action on Blender's main thread. Never raises: every failure
    is a structured, actionable error (the socket contract)."""
    try:
        kind = action.get("kind")
        params = action.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError("action params must be an object")
        if kind == "apply_pose":
            return {"ok": True, "report": _exec_apply_pose(params)}
        if kind == "inspect_scene":
            return {"ok": True, "report": _exec_inspect_scene(params)}
        if kind == "bake_action":
            return {"ok": True, "report": _exec_bake_action(params)}
        if kind == "render_turntable":
            return {"ok": True, "report": _exec_render_turntable(params)}
        if kind == "apply_style":
            return {"ok": True, "report": _exec_apply_style(params)}
        return {"ok": False, "error": {
            "code": "unknown_action_kind",
            "message": f"unknown action kind: {kind!r}",
            "retryable": False,
            "hint": "known kinds: " + ", ".join(KNOWN_ACTION_KINDS),
        }}
    except Exception as exc:  # noqa: BLE001 — the socket contract: an executor
        # failure is ALWAYS a structured error, never a raised exception (the
        # S13 CI catch: a 4.0.2 ops-enum TypeError escaped the old narrow
        # tuple and crashed the main-thread pump).
        return {"ok": False, "error": {
            "code": "executor_error",
            "message": f"{exc.__class__.__name__}: {exc}",
            "retryable": False,
        }}


def _resolve_armature(name: Any):
    """The named (or active) armature — the shared executor resolution."""
    import bpy

    if name:
        obj = bpy.data.objects.get(str(name))
    else:
        obj = bpy.context.active_object
    if obj is None or obj.type != "ARMATURE":
        raise ValueError(
            f"armature {name!r} not found" if name
            else "no armature selected (hint: pass armature_name, or set the "
                 "active object to the rig first)"
        )
    return obj


def _import_core():
    """The core package inside Blender (pip-installed or on sys.path)."""
    try:
        return importlib.import_module("riggermortis")
    except ImportError as exc:
        raise ImportError(bpy_bridge.CORE_MISSING_HINT) from exc


def _exec_apply_pose(params: dict[str, Any]) -> dict[str, Any]:
    """The REAL payload-apply path (D-009) — same machinery as Apply Pose."""
    import bpy

    payload = importlib.import_module(__package__)._load_payload(
        str(params.get("payload_path") or "")
    )
    obj = _resolve_armature(params.get("armature_name"))
    report = pose_apply.apply_payload(
        obj, payload,
        mirror=bool(params.get("mirror", False)),
        figure=params.get("figure") or None,
    )
    # P2-8a (D-015): same conditional tail repair the Inspect & Map operator
    # runs — an agent-driven apply on a garbage-tail imported rig must not
    # leave the evaluated placement broken. Count is reported, never silent.
    report["tails_repaired"] = tails.normalize_imported_tails(obj)
    pose_apply.push_undo()
    with contextlib.suppress(Exception):  # background mode has no scene UI
        settings = bpy.context.scene.rm_settings
        settings.last_report = (
            f"session apply: {len(report['applied'])} bone(s), "
            f"worst {report['worst_deg']:.3f} deg on {report['worst_role']}"
        )
        settings.rig_object = obj.name
    return report


def _exec_inspect_scene(_params: dict[str, Any]) -> dict[str, Any]:
    """Read-only armature inventory: name, bone count, mapped-role count."""
    import bpy

    armatures = []
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        armatures.append({
            "name": obj.name,
            "bone_count": len(obj.data.bones),
            "mapped_roles": sum(
                1 for key in obj.keys() if str(key).startswith("rm_role_")
            ),
        })
    armatures.sort(key=lambda a: a["name"])  # deterministic for a given scene
    return {"armatures": armatures, "count": len(armatures)}


def _exec_bake_action(params: dict[str, Any]) -> dict[str, Any]:
    """The REAL bake path (P2-3/P2-5) over a video job (P3-7).

    Certified composition (stabilize -> detect -> lock, min_cutoff=None) —
    the same composition the CI gate and the MCP animate tool run — then the
    add-on bake with the contact lock, then the RM_BAKE instrument: every
    baked frame is re-set and the fcurve evaluation re-measured against the
    frame's canonical targets. FK fidelity (<= 0.5 deg bar, gate-asserted)
    is reported over the UNLOCKED roles; locked-chain roles on contact
    frames deviate BY DESIGN (the plant pin) and are reported separately as
    ``reeval_lock_dev_deg`` — the evaluated twin of the bake's lock_dev_deg.
    """
    from pathlib import Path

    core = _import_core()
    from . import bake as bake_mod

    obj = _resolve_armature(params.get("armature_name"))
    job_dir = str(params.get("job_dir") or "")
    if not job_dir or not Path(job_dir).is_dir():
        raise ValueError(
            f"job_dir not found: {job_dir!r} (hint: pass the video job "
            "directory written by rigpose pose-video — it contains job.json)"
        )
    strength = params.get("hip_stabilize", 0.7)
    if strength is not None and (
        isinstance(strength, bool) or not isinstance(strength, (int, float))
        or not 0.0 <= float(strength) <= 1.0
    ):
        raise ValueError(
            "hip_stabilize must be a number in [0, 1] or null "
            f"(got {strength!r})"
        )
    action_name = str(params.get("action_name") or "rm_bake")

    # D-016 order: tail repair BEFORE any posing — the repair edits rest
    # tails, which invalidates stored rotations if done afterwards.
    tails_repaired = tails.normalize_imported_tails(obj)

    action = core.load_action(Path(job_dir))
    if not action.frames:
        raise ValueError(
            f"the job produced no usable frames ({len(action.failed)} failed; "
            "hint: check job.json's failure ledger — failed frames are never "
            "fabricated)"
        )
    conditioned = core.condition_action(
        action, hip_stabilize=strength, min_cutoff=None, tolerance=None,
    )
    contacts = core.detect_contacts(conditioned.frames)
    locked, lock = core.lock_feet(conditioned, contacts)
    baked = bake_mod.bake_action(
        obj, locked.frames, core, name=action_name, contacts=contacts,
    )

    # Frames x side of the plant pins — the re-eval's honest classifier.
    lock_at: set[tuple[int, str]] = set()
    for interval in contacts.intervals:
        for f in range(interval.start, interval.end + 1):
            lock_at.add((f, interval.foot[-2:]))

    import math

    import bpy
    from mathutils import Vector

    mapping = pose_apply.mapping_from_props(obj, core) or core.map_rig(
        core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    )
    scene = bpy.context.scene
    worst_role, worst_deg = "", 0.0
    lock_role, lock_deg = "", 0.0
    checks = 0
    for af in locked.frames:
        scene.frame_set(af.frame + 1)  # the bake's default frame_offset
        bpy.context.view_layer.update()
        for role, assignment in sorted(mapping.assignments.items()):
            target = core.bone_target_direction(af.pose, role)
            if target is None:
                continue
            pb = obj.pose.bones.get(assignment.bone)
            if pb is None:
                continue
            d = pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))
            d.normalize()
            dot = max(-1.0, min(1.0, d.dot(Vector(target))))
            deg = math.degrees(math.acos(dot))
            base = role.rsplit(".", 1)[0]
            side = role[-2:] if role.endswith((".L", ".R")) else ""
            is_locked = (
                (af.frame, side) in lock_at and base in core.LOCK_CHAIN_BASES
            )
            checks += 1
            if is_locked:
                if deg > lock_deg:
                    lock_role, lock_deg = role, deg
            elif deg > worst_deg:
                worst_role, worst_deg = role, deg

    return {
        **baked,
        "job_dir": job_dir,
        "hip_stabilize": strength,
        "tails_repaired": tails_repaired,
        "contacts": {
            "intervals": len(contacts.intervals),
            "slide_before_u": round(lock.slide_before.total, 4),
            "slide_after_u": round(lock.slide_after.total, 4),
            "unit": "canonical u (single-view, scale-normalized)",
        },
        "reeval_worst_deg": worst_deg,
        "reeval_worst_role": worst_role,
        "reeval_lock_dev_deg": lock_deg,
        "reeval_lock_role": lock_role,
        "reeval_checks": checks,
        "reeval_frames": len(locked.frames),
    }


def _exec_render_turntable(params: dict[str, Any]) -> dict[str, Any]:
    """The P3-7 turntable: bone-proxy staging (FLAT + explicit world) around
    the named (or active) armature; everything staged is restored."""
    from . import turntable

    core = _import_core()
    obj = _resolve_armature(params.get("armature_name"))
    raw_out = params.get("out_dir")
    if not isinstance(raw_out, str) or not raw_out.strip():
        raise ValueError(
            "out_dir is required (hint: an absolute path inside the Blender "
            "process cwd or the system temp dir)"
        )
    out_dir = turntable.safe_out_dir(raw_out)

    def _int(key: str, default: int) -> int:
        value = params.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{key} must be an integer (got {value!r})")
        return value

    mapping = pose_apply.mapping_from_props(obj, core) or core.map_rig(
        core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    )
    bone_names = {a.bone for a in mapping.assignments.values()}
    return turntable.render_turntable(
        obj, bone_names, out_dir,
        frames=_int("frames", 24),
        width=_int("width", 640),
        height=_int("height", 480),
        play_action=bool(params.get("play_action", True)),
        prefix=str(params.get("prefix") or "turn"),
    )


def _exec_apply_style(params: dict[str, Any]) -> dict[str, Any]:
    """The P4 style builders as a session action (S13): apply a shipped
    style preset (bands + line art + tones, exactly what the preset file
    carries) to a SHADED object. Armatures have no shading — the bone
    proxy mesh is the visualizer to style (pass its name). Per-panel/per-
    action style application is PERSISTENT (like every Blender material
    assignment); the report says exactly what was built."""
    import bpy

    from . import style

    style_name = str(params.get("style") or "")
    if not style_name:
        raise ValueError(
            "params.style is required (hint: known styles: "
            + ", ".join(style.known_presets()) + ")"
        )
    preset = style.load_preset(style_name)
    target = params.get("object")
    if target:
        obj = bpy.data.objects.get(str(target))
        if obj is None:
            shaded = sorted(
                o.name for o in bpy.data.objects
                if o.type in {"MESH", "SURFACE", "META", "CURVE"}
            )
            raise ValueError(
                f"object {target!r} not found (hint: shaded objects in this "
                f"scene: {', '.join(shaded) or 'none'})"
            )
    else:
        obj = bpy.context.active_object
    if obj is None or obj.type not in {"MESH", "SURFACE", "META", "CURVE"}:
        kind = getattr(obj, "type", None)
        raise ValueError(
            f"apply_style needs a shaded object (got {kind!r} — hint: pass "
            "'object' with the mesh/proxy to restyle; armatures have no "
            "shading — the bone proxy mesh is the visualizer to style)"
        )
    report: dict[str, Any] = {"style": style_name, "object": obj.name}
    mat_report = style.build_toon_material(obj, preset)
    report["material"] = mat_report["material"]
    # Per-feature honest degradation (the style gate's SKIPPED semantics):
    # the material builds on every supported Blender; line art needs the
    # GPv3 API (4.3+) and tones the scene compositor node group (5.x). The
    # report says which happened — never a silent partial apply.
    if preset.get("lineart") is not None:
        if hasattr(bpy.types, "GreasePencilLineartModifier"):
            report["lineart"] = style.build_lineart(obj, preset)
        else:
            report["lineart"] = (
                "SKIPPED (this Blender has no GPv3 LineArt API — pre-4.3-class)"
            )
    else:
        style.remove_lineart()
        report["lineart"] = None
    if preset.get("tones") is not None:
        if hasattr(bpy.context.scene, "compositing_node_group"):
            report["tones"] = style.build_screentones(bpy.context.scene, preset)
        else:
            report["tones"] = (
                "SKIPPED (this Blender has no scene compositing node group — "
                "pre-5.x-class)"
            )
    else:
        style.remove_screentones(bpy.context.scene)
        report["tones"] = None
    return report


# ---------------------------------------------------------------------------
# main-thread pump + session lifetime
# ---------------------------------------------------------------------------

def pump_once() -> int:
    """Drain inbound -> execute -> stage results. Runs on the MAIN thread
    (timer callback in interactive Blender; direct call in headless probes).
    Returns the number of actions executed."""
    client = _STATE.get("client")
    if client is None:
        return 0
    executed = 0
    while True:
        try:
            action = client.inbound.get_nowait()
        except queue.Empty:
            break
        result = execute_action(action)
        client.outbound.put({"action_id": action.get("action_id"), **result})
        executed += 1
    return executed


def _pump() -> float | None:
    """bpy.app.timers callback — keep running while the client lives."""
    if pump_once() and _STATE.get("client") is not None:
        pass  # status line is read fresh from the client at panel draw time
    client = _STATE.get("client")
    if client is not None and client.running():
        return 0.25
    _teardown_timer()
    return None


def _teardown_timer() -> None:
    import bpy

    if _STATE.get("timer"):
        with contextlib.suppress(ValueError):  # already unregistered
            bpy.app.timers.unregister(_pump)
        _STATE["timer"] = False


def start_session(port: int, token: str) -> str:
    """Start the background client + main-thread pump. Returns an error
    message, or "" on success (also used as the operator's contract)."""
    import bpy

    if not str(token or "").strip():
        return (
            "no session token (hint: the server was started with "
            "--session-token; paste it here — it is session-only, never saved)"
        )
    if not isinstance(port, int) or not 1 <= port <= 65535:
        return f"port out of range: {port!r} (hint: 1..65535)"
    if _STATE.get("client") is not None and _STATE["client"].running():
        return "session already running (hint: disconnect first)"
    stop_session()  # clear a stopped client + stale timer
    root = importlib.import_module(__package__)
    agent_info = {
        "addon": "riggermortis_addon",
        "version": ".".join(str(v) for v in root.bl_info.get("version", (0, 0, 0))),
        "blender": bpy.app.version_string,
    }
    client = SessionClient(LOOPBACK_HOST, int(port), str(token).strip(), agent_info)
    _STATE["client"] = client
    client.start()
    try:
        bpy.app.timers.register(_pump, first_interval=0.25, persistent=True)
        _STATE["timer"] = True
    except ValueError:
        _STATE["timer"] = True  # already registered from a previous session
    return ""


def stop_session() -> None:
    client = _STATE.get("client")
    if client is not None:
        client.stop()
    with contextlib.suppress(Exception):  # timer teardown needs bpy; probe-safe
        _teardown_timer()
    if client is not None and client.thread is not None:
        client.thread.join(timeout=2.0)
    _STATE.clear()


def running() -> bool:
    client = _STATE.get("client")
    return client is not None and client.running()


def ui_status() -> str:
    """Short multi-line status for the panel (read fresh at draw time)."""
    client = _STATE.get("client")
    if client is None:
        return "not running"
    snap = client.snapshot()
    lines = [f"{snap['state']}  127.0.0.1:{snap['port']}"]
    if snap.get("detail"):
        lines.append(str(snap["detail"])[:80])
    lines.append(
        f"pending actions: {client.inbound.qsize()}   "
        f"results queued: {client.outbound.qsize()}"
    )
    return "\n".join(lines)
