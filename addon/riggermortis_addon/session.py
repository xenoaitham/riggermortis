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

from . import pose_apply, tails

PROTOCOL_VERSION = 1
LOOPBACK_HOST = "127.0.0.1"
POLL_INTERVAL = 0.5
POLL_MAX = 8
RECONNECT_MIN = 0.5
RECONNECT_MAX = 5.0
#: Known action kinds — mirrors mcp/session_bridge.KNOWN_ACTION_KINDS v1.
KNOWN_ACTION_KINDS = ("inspect_scene", "apply_pose", "bake_action")

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
            return {"ok": False, "error": {
                "code": "not_implemented",
                "message": "bake_action is declared but not implemented "
                           "(lands with P3-7; meanwhile bake via the add-on "
                           "bake path or make export-verify)",
                "retryable": False,
            }}
        return {"ok": False, "error": {
            "code": "unknown_action_kind",
            "message": f"unknown action kind: {kind!r}",
            "retryable": False,
            "hint": "known kinds: " + ", ".join(KNOWN_ACTION_KINDS),
        }}
    except (ValueError, ImportError, OSError) as exc:
        return {"ok": False, "error": {
            "code": "executor_error",
            "message": str(exc),
            "retryable": False,
        }}


def _exec_apply_pose(params: dict[str, Any]) -> dict[str, Any]:
    """The REAL payload-apply path (D-009) — same machinery as Apply Pose."""
    import bpy

    root = importlib.import_module(__package__)
    payload = root._load_payload(str(params.get("payload_path") or ""))
    name = params.get("armature_name")
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
