"""Server-side session bridge (P3-5): the action queue + loopback transport.

This is the mcp/DESIGN.md "Session bridge" section made executable. It lives
in mcp/ — NOT core (D-003: core stays process-free AND socket-free) — and is
pure stdlib, importable without bpy (the add-on speaks the same protocol from
``addon/riggermortis_addon/session.py``).

Topology: the MCP server binds ``127.0.0.1`` and NOTHING else (hardcoded);
the Blender add-on dials IN. The agent (owner of the server's stdio) enqueues
actions; an authenticated add-on claims them by polling and posts structured
results. Dispatched actions are never silently re-sent: a connection drop
marks them STALE in the ledger, and the agent decides whether to re-enqueue.

Threading: one RLock guards the ledger; the transport runs an accept thread
plus one handler thread per connection (daemon threads). The stdio loop owns
start/stop.
"""
from __future__ import annotations

import hmac
import json
import socket
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

PROTOCOL_VERSION = 1
#: Hardcoded host — the bridge never binds anything but IPv4 loopback.
LOOPBACK_HOST = "127.0.0.1"
#: Frames larger than this are a protocol violation (defensive bound).
MAX_LINE_BYTES = 8 * 1024 * 1024
LEDGER_SIZE = 256
MAX_CLAIM = 64
POLL_MAX_DEFAULT = 8

#: Action kinds the add-on executor understands (v1). All five are live:
#: ``bake_action`` (video job -> certified composition -> rig-space bake +
#: re-eval), ``render_turntable`` (bone-proxy turntable) and
#: ``apply_style`` (P4 style builders on a shaded object) execute in
#: Blender; see mcp/DESIGN.md "Action kinds".
KNOWN_ACTION_KINDS = (
    "inspect_scene", "apply_pose", "bake_action", "render_turntable",
    "apply_style",
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class SessionHub:
    """Action ledger + queue, shared by the stdio thread and the transport.

    Deterministic ids for a given request order (``a-0001``, ``a-0002``, …).
    Every transition appends to a bounded ledger — the honest failure ledger
    surfaced by ``status()``; nothing is swallowed.
    """

    def __init__(
        self,
        token: str,
        clock: Callable[[], str] = _now,
        ledger_size: int = LEDGER_SIZE,
    ) -> None:
        if not isinstance(token, str) or not token:
            raise ValueError(
                "session token must be a non-empty string "
                "(hint: generate one with: python3 -c "
                "'import secrets; print(secrets.token_hex(16))')"
            )
        self._token = token
        self._clock = clock
        self._lock = threading.RLock()
        self._seq = 0
        self._actions: dict[str, dict[str, Any]] = {}
        self._conn_seq = 0
        self._connections: set[str] = set()
        self._auth_failures = 0
        self._ledger: deque[dict[str, str]] = deque(maxlen=ledger_size)

    # -- auth ---------------------------------------------------------------

    def authenticate(self, token: Any) -> bool:
        ok = isinstance(token, str) and hmac.compare_digest(self._token, token)
        with self._lock:
            if not ok:
                self._auth_failures += 1
                self._ledger.append({"at": self._clock(), "event": "auth_failed"})
        return ok

    # -- connections --------------------------------------------------------

    def connection_opened(self) -> str:
        with self._lock:
            self._conn_seq += 1
            cid = f"c-{self._conn_seq:04d}"
            self._connections.add(cid)
            self._ledger.append({"at": self._clock(), "event": f"connected {cid}"})
            return cid

    def connection_closed(self, connection_id: str) -> None:
        """Drop a connection; dispatched-but-unanswered actions go stale."""
        with self._lock:
            self._connections.discard(connection_id)
            self._ledger.append({"at": self._clock(), "event": f"disconnected {connection_id}"})
            for record in self._actions.values():
                if (
                    record["status"] == "dispatched"
                    and record["connection"] == connection_id
                ):
                    record["stale"] = True
                    self._ledger.append({
                        "at": self._clock(),
                        "event": f"stale {record['action_id']}",
                    })

    def authenticated_connections(self) -> int:
        with self._lock:
            return len(self._connections)

    # -- queue ops ------------------------------------------------------------

    def enqueue(self, kind: str, params: dict[str, Any] | None) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            action_id = f"a-{self._seq:04d}"
            record = {
                "action_id": action_id,
                "kind": kind,
                "params": dict(params or {}),
                "status": "queued",
                "enqueued_at": self._clock(),
                "dispatched_at": None,
                "completed_at": None,
                "connection": None,
                "stale": False,
                "report": None,
                "error": None,
            }
            self._actions[action_id] = record
            self._ledger.append({
                "at": record["enqueued_at"],
                "event": f"enqueue {action_id} {kind}",
            })
            return self._snapshot(record)

    def claim(self, max_n: int, connection_id: str) -> list[dict[str, Any]]:
        """Claim up to ``max_n`` queued actions (queued -> dispatched)."""
        with self._lock:
            claimed: list[dict[str, Any]] = []
            for record in sorted(self._actions.values(), key=lambda r: r["action_id"]):
                if len(claimed) >= max_n:
                    break
                if record["status"] != "queued":
                    continue
                record["status"] = "dispatched"
                record["dispatched_at"] = self._clock()
                record["connection"] = connection_id
                self._ledger.append({
                    "at": record["dispatched_at"],
                    "event": f"dispatch {record['action_id']} -> {connection_id}",
                })
                claimed.append({
                    "action_id": record["action_id"],
                    "kind": record["kind"],
                    "params": dict(record["params"]),
                    "enqueued_at": record["enqueued_at"],
                })
            return claimed

    def complete(
        self, action_id: str, ok: bool, payload: dict[str, Any], connection_id: str,
    ) -> dict[str, Any] | None:
        """Complete a dispatched action (done/failed). Only the connection
        that holds the dispatch may complete it; None = no such dispatch."""
        with self._lock:
            record = self._actions.get(action_id)
            if (
                record is None
                or record["status"] != "dispatched"
                or record["connection"] != connection_id
            ):
                return None
            record["status"] = "done" if ok else "failed"
            record["completed_at"] = self._clock()
            if ok:
                record["report"] = payload
            else:
                record["error"] = payload
            self._ledger.append({
                "at": record["completed_at"],
                "event": f"{'done' if ok else 'failed'} {action_id}",
            })
            return self._snapshot(record)

    def result(self, action_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._actions.get(action_id)
            return None if record is None else self._snapshot(record)

    def status(self) -> dict[str, Any]:
        with self._lock:
            counts = {"queued": 0, "dispatched": 0, "done": 0, "failed": 0, "stale": 0}
            for record in self._actions.values():
                counts[record["status"]] += 1
                if record["stale"]:
                    counts["stale"] += 1
            return {
                "counts": counts,
                "total": len(self._actions),
                "auth_failures": self._auth_failures,
                "recent": list(self._ledger)[-8:],
            }

    # -- internals ----------------------------------------------------------

    def _snapshot(self, record: dict[str, Any]) -> dict[str, Any]:
        """Public view of one action: no connection identity, only states."""
        view: dict[str, Any] = {
            "action_id": record["action_id"],
            "kind": record["kind"],
            "status": record["status"],
            "enqueued_at": record["enqueued_at"],
        }
        if record["status"] in ("dispatched", "done", "failed"):
            view["dispatched_at"] = record["dispatched_at"]
        if record["status"] in ("done", "failed"):
            view["completed_at"] = record["completed_at"]
        if record["status"] == "dispatched":
            view["stale"] = record["stale"]
        if record["status"] == "done":
            view["report"] = record["report"]
        if record["status"] == "failed":
            view["error"] = record["error"]
        return view


class LoopbackTransport:
    """127.0.0.1-only TCP transport speaking the DESIGN.md wire protocol."""

    def __init__(
        self,
        hub: SessionHub,
        port: int,
        log: Callable[[str], None] | None = None,
    ) -> None:
        if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
            raise ValueError(
                f"session port out of range: {port!r} (hint: 1..65535; "
                "0 binds an ephemeral port — for tests/probes, read the "
                "actual port back from start())"
            )
        self._hub = hub
        self._port = port
        self._log = log or (lambda message: None)
        self._listener: socket.socket | None = None
        self._conns: dict[str, socket.socket] = {}
        self._sends: dict[str, threading.Lock] = {}
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._conn_lock = threading.Lock()

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> int:
        """Bind + listen; returns the ACTUAL port (construct with 0 for ephemeral)."""
        if self._listener is not None:
            raise RuntimeError("session transport already started")
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((LOOPBACK_HOST, self._port))
        srv.listen(4)
        srv.settimeout(0.2)  # so the accept loop observes stop()
        self._listener = srv
        self._port = srv.getsockname()[1]
        thread = threading.Thread(
            target=self._accept_loop, name="rm-session-accept", daemon=True,
        )
        self._threads.append(thread)
        thread.start()
        self._log(f"session bridge listening on {LOOPBACK_HOST}:{self._port}")
        return self._port

    def stop(self) -> None:
        """Close listener + connections and join threads. Idempotent."""
        self._stop.set()
        with self._conn_lock:
            listener, self._listener = self._listener, None
            conns = dict(self._conns)
            self._conns.clear()
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        for sock in conns.values():
            try:
                sock.close()
            except OSError:
                pass
        for thread in self._threads:
            thread.join(timeout=2.0)
        self._threads.clear()
        self._log("session bridge stopped")

    def info(self) -> dict[str, Any]:
        with self._conn_lock:
            return {
                "listening": self._listener is not None,
                "port": self._port if self._listener is not None else None,
                "connections": len(self._conns),
            }

    # -- wire handling --------------------------------------------------------

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                sock, _addr = self._listener.accept()  # type: ignore[union-attr]
            except TimeoutError:  # socket.timeout — accept() poll interval
                continue
            except OSError:
                break  # listener closed by stop()
            sock.settimeout(5.0)
            thread = threading.Thread(
                target=self._handle_connection, args=(sock,), daemon=True,
            )
            self._threads.append(thread)
            thread.start()

    def _handle_connection(self, sock: socket.socket) -> None:
        """One add-on connection: hello (auth) -> poll/result loop."""
        cid: str | None = None
        sockfile = sock.makefile("r", encoding="utf-8", newline="\n")
        try:
            hello = self._read_line(sock, sockfile)
            if hello is None:
                return
            if not self._is_hello(hello):
                self._send(sock, None, "error", {
                    "code": "bad_request",
                    "message": "first message must be hello",
                })
                return
            if not self._hub.authenticate(hello.get("token")):
                self._send(sock, None, "error", {
                    "code": "auth_failed",
                    "message": "session token rejected",
                })
                return
            cid = self._hub.connection_opened()
            with self._conn_lock:
                self._conns[cid] = sock
                self._sends[cid] = threading.Lock()
            self._send(sock, cid, "welcome", {
                "addon": str(hello.get("addon", "?")),
            })
            while not self._stop.is_set():
                line = self._read_line(sock, sockfile)
                if line is None:
                    break
                op = line.get("op")
                if op == "bye":
                    self._send(sock, cid, "ack", {"bye": True})
                    break
                if op == "poll":
                    if not self._dispatch_claim(sock, cid, line):
                        break
                elif op == "result":
                    if not self._accept_result(sock, cid, line):
                        break
                elif op == "hello":
                    self._send(sock, cid, "error", {
                        "code": "bad_request",
                        "message": "already authenticated on this connection",
                    })
                    break
                else:
                    self._send(sock, cid, "error", {
                        "code": "bad_request",
                        "message": f"unknown op: {op!r}",
                    })
                    break
        except (OSError, json.JSONDecodeError):
            pass  # dropped mid-line — the stale marking below is the record
        finally:
            try:
                sockfile.close()
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
            with self._conn_lock:
                self._conns.pop(cid or "", None)
                self._sends.pop(cid or "", None)
            if cid is not None:
                self._hub.connection_closed(cid)

    def _is_hello(self, message: dict[str, Any]) -> bool:
        return message.get("op") == "hello" and message.get("v") == PROTOCOL_VERSION

    def _dispatch_claim(self, sock: socket.socket, cid: str, line: dict[str, Any]) -> bool:
        max_n = line.get("max", POLL_MAX_DEFAULT)
        if isinstance(max_n, bool) or not isinstance(max_n, int) or not 1 <= max_n <= MAX_CLAIM:
            self._send(sock, cid, "error", {
                "code": "bad_request",
                "message": f"poll.max must be an integer in 1..{MAX_CLAIM}",
            })
            return False
        actions = self._hub.claim(max_n, cid)
        self._send(sock, cid, "actions", {"actions": actions})
        return True

    def _accept_result(self, sock: socket.socket, cid: str, line: dict[str, Any]) -> bool:
        action_id = line.get("action_id")
        ok = line.get("ok")
        if not isinstance(action_id, str) or not isinstance(ok, bool):
            self._send(sock, cid, "error", {
                "code": "bad_request",
                "message": "result needs action_id (string) and ok (bool)",
            })
            return False
        payload = line.get("report") if ok else line.get("error")
        if not isinstance(payload, dict):
            self._send(sock, cid, "error", {
                "code": "bad_request",
                "message": "result needs a report (ok) or error (not ok) object",
            })
            return False
        record = self._hub.complete(action_id, ok, payload, cid)
        if record is None:
            self._send(sock, cid, "error", {
                "code": "bad_request",
                "message": f"no dispatched action {action_id!r} on this connection",
            })
            return False
        self._send(sock, cid, "ack", {"action_id": action_id})
        return True

    # -- framing ------------------------------------------------------------

    def _read_line(
        self, sock: socket.socket, sockfile: Any,
    ) -> dict[str, Any] | None:
        """One protocol frame; None = connection over. Violations answer
        bad_request and end the connection (the server itself keeps running)."""
        raw = sockfile.readline(MAX_LINE_BYTES + 1)
        if not raw:
            return None
        if len(raw) > MAX_LINE_BYTES or not raw.endswith("\n"):
            self._send(sock, None, "error", {
                "code": "bad_request",
                "message": f"line exceeds {MAX_LINE_BYTES} bytes",
            })
            return None
        text = raw.strip()
        if not text:
            return {}  # blank line: ignored, keep the connection
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            self._send(sock, None, "error", {
                "code": "bad_request",
                "message": "line is not valid JSON",
            })
            return None
        if not isinstance(message, dict):
            return {}  # non-object lines are ignored (defensive)
        if message.get("v") != PROTOCOL_VERSION:
            self._send(sock, None, "error", {
                "code": "bad_request",
                "message": f"unsupported protocol version: {message.get('v')!r} "
                           f"(expected {PROTOCOL_VERSION})",
            })
            return None
        return message

    def _send(
        self, sock: socket.socket, cid: str | None, op: str, fields: dict[str, Any],
    ) -> None:
        message = {"v": PROTOCOL_VERSION, "op": op, **fields}
        line = json.dumps(message, sort_keys=True) + "\n"
        lock = self._sends.get(cid or "") if cid else None
        if lock is not None:
            with lock:
                sock.sendall(line.encode("utf-8"))
        else:
            sock.sendall(line.encode("utf-8"))
