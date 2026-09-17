"""P3-5 session-bridge tests: queue semantics, real loopback, honest states.

Two layers, like any tool surface:

- ``SessionHub`` (queue + ledger) and the ``LoopbackTransport`` wire protocol
  are exercised against a REAL 127.0.0.1 socket with an inline fake add-on
  client speaking the DESIGN.md protocol — loopback is still "no external
  network", and a genuine socket beats a mocked pair for the framing rules.
- The MCP tool layer (``session_status`` / ``enqueue_action`` /
  ``action_result``) is tested in-process, enabled AND disabled: a server
  started without the bridge answers ``session_disabled`` honestly instead
  of pretending.

The default-path zero-sockets guarantee is extended to the server itself:
``serve_stdin_stdout`` under an audit hook records NO socket events, with a
positive control proving the hook sees the opt-in bind.
"""
from __future__ import annotations

import io
import json
import socket
import sys
import time
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[2] / "mcp"
sys.path.insert(0, str(MCP_DIR))

import pytest  # noqa: E402
import riggermortis_mcp as server  # noqa: E402
import session_bridge as bridge  # noqa: E402

TOKEN = "unit-test-token-0123456789abcdef"


# ---------------------------------------------------------------------------
# queue semantics (hub only, no sockets)
# ---------------------------------------------------------------------------

def test_enqueue_lifecycle_without_any_addon_is_honest() -> None:
    hub = bridge.SessionHub(TOKEN)
    record = hub.enqueue("inspect_scene", {})
    assert record["action_id"] == "a-0001"
    assert record["status"] == "queued"
    status = hub.status()
    assert status["counts"]["queued"] == 1
    assert hub.authenticated_connections() == 0
    assert any(event["event"] == "enqueue a-0001 inspect_scene"
               for event in status["recent"])


def test_action_ids_are_deterministic_for_a_request_order() -> None:
    first = bridge.SessionHub(TOKEN)
    second = bridge.SessionHub(TOKEN)
    for hub in (first, second):
        hub.enqueue("inspect_scene", {})
        hub.enqueue("apply_pose", {"payload_path": "p.json"})
    assert [a["action_id"] for a in (
        first.result("a-0001"), first.result("a-0002"),
    )] == ["a-0001", "a-0002"]
    assert second.result("a-0002")["kind"] == "apply_pose"


def test_dispatched_actions_go_stale_on_disconnect_and_never_re_deliver() -> None:
    hub = bridge.SessionHub(TOKEN)
    hub.enqueue("apply_pose", {"payload_path": "p.json"})
    cid = hub.connection_opened()
    claimed = hub.claim(8, cid)
    assert len(claimed) == 1
    hub.connection_closed(cid)
    record = hub.result("a-0001")
    assert record["status"] == "dispatched"
    assert record["stale"] is True
    # No silent re-delivery: a new connection claims NOTHING stale.
    cid2 = hub.connection_opened()
    assert hub.claim(8, cid2) == []
    assert any(event["event"] == "stale a-0001" for event in hub.status()["recent"])


def test_complete_rejects_foreign_or_unknown_dispatches() -> None:
    hub = bridge.SessionHub(TOKEN)
    hub.enqueue("inspect_scene", {})
    stranger = hub.connection_opened()
    assert hub.complete("a-0001", True, {"report": {}}, stranger) is None
    assert hub.complete("a-9999", True, {"report": {}}, stranger) is None
    owner = hub.connection_opened()
    hub.claim(8, owner)
    assert hub.complete("a-0001", True, {"x": 1}, stranger) is None
    done = hub.complete("a-0001", True, {"x": 1}, owner)
    assert done is not None
    assert done["status"] == "done"
    assert done["report"] == {"x": 1}


def test_failure_path_completes_with_the_structured_error() -> None:
    hub = bridge.SessionHub(TOKEN)
    hub.enqueue("apply_pose", {"payload_path": "missing.json"})
    cid = hub.connection_opened()
    hub.claim(8, cid)
    error = {"code": "executor_error", "message": "payload not found", "retryable": False}
    record = hub.complete("a-0001", False, error, cid)
    assert record is not None and record["status"] == "failed"
    assert record["error"] == error
    assert "report" not in record


def test_empty_token_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="token"):
        bridge.SessionHub("")


# ---------------------------------------------------------------------------
# wire protocol over a REAL loopback socket
# ---------------------------------------------------------------------------

class _InlineAddon:
    """Minimal synchronous add-on client for protocol tests."""

    def __init__(self, port: int, token: str) -> None:
        self.token = token
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=3.0)
        self.sockfile = self.sock.makefile("r", encoding="utf-8", newline="\n")

    def send(self, **message: object) -> None:
        frame = json.dumps({"v": bridge.PROTOCOL_VERSION, **message}, sort_keys=True)
        self.sock.sendall((frame + "\n").encode("utf-8"))

    def recv(self) -> dict:
        raw = self.sockfile.readline()
        assert raw, "server closed the connection unexpectedly"
        return json.loads(raw)

    def hello(self) -> dict:
        self.send(op="hello", token=self.token, addon="fake-addon",
                  version="0.0.0", blender="none")
        return self.recv()

    def poll(self, max_n: int = 8) -> list[dict]:
        self.send(op="poll", max=max_n)
        while True:  # acks may precede the actions frame
            message = self.recv()
            if message["op"] == "actions":
                return message["actions"]

    def result(self, action_id: str, ok: bool, **payload: object) -> dict:
        self.send(op="result", action_id=action_id, ok=ok, **payload)
        return self.recv()

    def close(self) -> None:
        try:
            self.sockfile.close()
        finally:
            self.sock.close()


@pytest.fixture()
def transport():
    hub = bridge.SessionHub(TOKEN)
    tp = bridge.LoopbackTransport(hub, 0)
    port = tp.start()
    yield hub, tp, port
    tp.stop()


def test_wrong_token_is_rejected_and_counted(transport) -> None:
    hub, _tp, port = transport
    client = _InlineAddon(port, "wrong-token")
    reply = client.hello()
    assert reply["op"] == "error" and reply["code"] == "auth_failed"
    client.close()
    assert hub.status()["auth_failures"] == 1
    assert hub.authenticated_connections() == 0


def test_full_round_trip_over_a_real_loopback_socket(transport) -> None:
    hub, _tp, port = transport
    client = _InlineAddon(port, TOKEN)
    welcome = client.hello()
    assert welcome["op"] == "welcome"
    assert client.poll() == []  # empty queue answers an empty actions frame

    enqueued = hub.enqueue("apply_pose", {"payload_path": "pose.json", "mirror": True})
    actions = client.poll()
    assert [a["action_id"] for a in actions] == [enqueued["action_id"]]
    assert actions[0]["kind"] == "apply_pose"
    assert actions[0]["params"] == {"payload_path": "pose.json", "mirror": True}
    assert hub.result(enqueued["action_id"])["status"] == "dispatched"
    assert client.poll() == []  # dispatch is one-shot: no re-delivery

    ack = client.result(enqueued["action_id"], True, report={"applied": 12})
    assert ack["op"] == "ack"
    record = hub.result(enqueued["action_id"])
    assert record["status"] == "done"
    assert record["report"] == {"applied": 12}
    assert "stale" not in record  # stale is a dispatched-only marker
    client.close()


def test_failed_action_travels_back_as_a_structured_error(transport) -> None:
    hub, _tp, port = transport
    client = _InlineAddon(port, TOKEN)
    client.hello()
    enqueued = hub.enqueue("apply_pose", {"payload_path": "missing.json"})
    (action,) = client.poll()
    error = {"code": "executor_error", "message": "payload not found: missing.json",
             "retryable": False}
    client.result(action["action_id"], False, error=error)
    record = hub.result(enqueued["action_id"])
    assert record["status"] == "failed"
    assert record["error"] == error
    client.close()


def test_protocol_violations_answer_bad_request_and_close(transport) -> None:
    _hub, _tp, port = transport

    # wrong protocol version
    sock = socket.create_connection(("127.0.0.1", port), timeout=3.0)
    sock.sendall(b'{"v": 99, "op": "hello"}\n')
    reply = json.loads(sock.makefile("r", encoding="utf-8").readline())
    assert reply["op"] == "error" and reply["code"] == "bad_request"
    sock.close()

    # first message is not hello
    client = _InlineAddon(port, TOKEN)
    client.send(op="poll")
    assert client.recv()["code"] == "bad_request"
    client.close()

    # invalid JSON
    sock = socket.create_connection(("127.0.0.1", port), timeout=3.0)
    sock.sendall(b"this is not json\n")
    reply = json.loads(sock.makefile("r", encoding="utf-8").readline())
    assert reply["op"] == "error" and reply["code"] == "bad_request"
    sock.close()

    # result for an action this connection never held
    client = _InlineAddon(port, TOKEN)
    client.hello()
    reply = client.result("a-0001", True, report={})
    assert reply["op"] == "error" and reply["code"] == "bad_request"
    client.close()

    # poll.max outside 1..64
    client = _InlineAddon(port, TOKEN)
    client.hello()
    client.send(op="poll", max=0)
    assert client.recv()["code"] == "bad_request"
    client.close()


def test_transport_never_binds_anything_but_loopback(transport) -> None:
    _hub, tp, port = transport
    info = tp.info()
    assert info["listening"] is True
    assert info["port"] == port
    client = _InlineAddon(port, TOKEN)
    assert client.hello()["op"] == "welcome"  # registration happens post-auth
    deadline = time.monotonic() + 2.0
    while tp.info()["connections"] == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert tp.info()["connections"] == 1
    client.close()


def test_transport_stop_is_idempotent(transport) -> None:
    _hub, tp, _port = transport
    tp.stop()
    tp.stop()
    assert tp.info()["listening"] is False


# ---------------------------------------------------------------------------
# MCP tool layer (in-process)
# ---------------------------------------------------------------------------

@pytest.fixture()
def runtime():
    hub = bridge.SessionHub(TOKEN)
    rt = server.SessionRuntime(hub, 0)  # hub-only: the transport stays stopped
    server.set_session_runtime(rt)
    yield hub, rt
    server.set_session_runtime(None)


def _rpc(method: str, request_id: int = 1, **params: object) -> dict:
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    request.update(params)
    return server.handle(request)


def _call(name: str, arguments: dict) -> tuple[dict, dict]:
    response = _rpc("tools/call", params={"name": name, "arguments": arguments})
    return (
        response["result"]["content"][0]["json"],
        {"isError": response["result"]["isError"]},
    )


def test_disabled_bridge_answers_honestly() -> None:
    assert server.get_session_runtime() is None
    info = _rpc("initialize")["result"]["serverInfo"]
    assert info["capabilities"]["session_bridge"] is False
    value, _meta = _call("session_status", {})
    assert value["enabled"] is False and "hint" in value["note"]
    value, meta = _call("enqueue_action", {"kind": "inspect_scene"})
    assert meta["isError"] is True and value["error"]["code"] == "session_disabled"
    value, meta = _call("action_result", {"action_id": "a-0001"})
    assert meta["isError"] is True and value["error"]["code"] == "session_disabled"


def test_enabled_bridge_tools_round_trip(runtime) -> None:
    hub, _rt = runtime
    value, meta = _call("enqueue_action", {
        "kind": "apply_pose", "params": {"payload_path": "pose.json"},
    })
    assert meta["isError"] is False
    assert value["action_id"] == "a-0001" and value["status"] == "queued"
    assert hub.result("a-0001")["kind"] == "apply_pose"

    value, _meta = _call("action_result", {"action_id": "a-0001"})
    assert value["status"] == "queued"

    value, _meta = _call("session_status", {})
    assert value["enabled"] is True
    assert value["counts"]["queued"] == 1
    assert value["addon_connected"] is False  # no transport started


def test_enqueue_validates_kind_and_params(runtime) -> None:
    value, meta = _call("enqueue_action", {"kind": "render_movie"})
    assert meta["isError"] is True
    assert value["error"]["code"] == "invalid_request"
    assert "inspect_scene" in value["error"]["hint"]
    value, meta = _call("enqueue_action", {"kind": "inspect_scene", "params": [1]})
    assert meta["isError"] is True
    assert value["error"]["message"] == "params must be an object"


def test_all_four_action_kinds_are_live_at_the_enqueue_layer(runtime) -> None:
    """P3-7: bake_action and render_turntable are LIVE kinds — the enqueue
    layer accepts them (execution itself is gate-verified in real Blender:
    make session-verify)."""
    for kind in ("inspect_scene", "apply_pose", "bake_action", "render_turntable"):
        value, meta = _call("enqueue_action", {"kind": kind, "params": {}})
        assert meta["isError"] is False, kind
        assert value["status"] == "queued", kind


def test_action_result_validates_the_id(runtime) -> None:
    value, meta = _call("action_result", {"action_id": 42})
    assert meta["isError"] is True
    assert value["error"]["code"] == "invalid_request"
    value, meta = _call("action_result", {"action_id": "a-404"})
    assert meta["isError"] is True
    assert value["error"]["code"] == "invalid_request"
    assert "enqueue_action" in value["error"]["hint"]


def test_session_tools_are_in_the_golden_schema() -> None:
    response = _rpc("tools/list")
    by_name = {t["name"]: t for t in response["result"]["tools"]}
    assert {"session_status", "enqueue_action", "action_result"} <= set(by_name)
    for name in ("session_status", "enqueue_action", "action_result"):
        assert by_name[name]["status"] == "live", name
    assert by_name["enqueue_action"]["input_schema"]["required"] == ["kind"]
    assert by_name["action_result"]["input_schema"]["required"] == ["action_id"]
    assert response["result"]["tools"] == server.TOOL_SCHEMAS_V1


# ---------------------------------------------------------------------------
# default path opens ZERO sockets (the guarantee extended to the server)
# ---------------------------------------------------------------------------

_socket_events: list[str] = []
_audit_installed = False


def _audit_hook(event: str, _args: tuple) -> None:
    if event.startswith("socket."):
        _socket_events.append(event)


@pytest.fixture()
def server_socket_audit() -> list[str]:
    global _audit_installed
    if not _audit_installed:
        sys.addaudithook(_audit_hook)
        _audit_installed = True
    _socket_events.clear()
    return _socket_events


def _run_stdio(lines: list[str]) -> list[dict]:
    buffer = io.StringIO()
    backup_in, backup_out = sys.stdin, sys.stdout
    sys.stdin = io.StringIO("\n".join(lines) + "\n")
    sys.stdout = buffer
    try:
        assert server.serve_stdin_stdout() == 0
    finally:
        sys.stdin, sys.stdout = backup_in, backup_out
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


def test_default_stdio_server_opens_zero_sockets(server_socket_audit) -> None:
    responses = _run_stdio([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "session_status", "arguments": {}}}),
        json.dumps({"jsonrpc": "2.0", "id": 4, "method": "ping"}),
    ])
    assert [r["id"] for r in responses] == [1, 2, 3, 4]
    assert responses[2]["result"]["content"][0]["json"]["enabled"] is False
    assert server_socket_audit == [], (
        "default stdio server opened sockets — the local-only guarantee "
        f"extends to the session bridge being OFF by default: {server_socket_audit}"
    )


def test_audit_hook_sees_the_optin_bind(server_socket_audit) -> None:
    """Positive control: the SAME hook records the bridge's bind — the zero
    above is a real property, not a blind hook."""
    hub = bridge.SessionHub(TOKEN)
    tp = bridge.LoopbackTransport(hub, 0)
    try:
        port = tp.start()
        assert port > 0
        assert "socket.bind" in server_socket_audit
    finally:
        tp.stop()
    _socket_events.clear()
