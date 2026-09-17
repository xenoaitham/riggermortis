"""P3-1..P3-4 golden tests: MCP framing, schemas, streaming, tool behavior."""
from __future__ import annotations

import io
import json
import math
import sys
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[2] / "mcp"
sys.path.insert(0, str(MCP_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import riggermortis_mcp as server  # noqa: E402

import riggermortis as core  # noqa: E402
from rigs import rigify_rig  # noqa: E402


def _rpc(method: str, request_id: int = 1, **params) -> dict:
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    request.update(params)
    return server.handle(request)


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


def test_initialize_returns_server_info() -> None:
    response = _rpc("initialize", params={})
    assert response["result"]["serverInfo"]["name"] == "riggermortis"
    assert response["result"]["protocolVersion"] == server.PROTOCOL_VERSION
    assert response["result"]["serverInfo"]["local_only"] is True


def test_tools_list_matches_golden_schema() -> None:
    """Golden-schema test: the v1 tool table is pinned (name, status, required).
    P3-5 extends it additively with the three session tools (same-commit pin
    update, per the P3-3 precedent)."""
    response = _rpc("tools/list")
    tools = response["result"]["tools"]
    by_name = {t["name"]: t for t in tools}
    assert set(by_name) == {
        "inspect_rig", "policy_status", "policy_check", "map_rig",
        "pose_from_image", "animate_from_video",
        "session_status", "enqueue_action", "action_result",
    }
    assert by_name["inspect_rig"]["status"] == "live"
    assert by_name["inspect_rig"]["input_schema"]["required"] == ["path"]
    assert by_name["pose_from_image"]["status"] == "declared"
    assert by_name["policy_status"]["input_schema"]["properties"] == {}
    assert by_name["policy_check"]["status"] == "live"
    assert by_name["policy_check"]["input_schema"]["required"] == ["subject"]
    assert by_name["animate_from_video"]["status"] == "live"
    assert by_name["animate_from_video"]["input_schema"]["required"] == [
        "rig", "job_dir",
    ]
    assert by_name["session_status"]["status"] == "live"
    assert by_name["session_status"]["input_schema"]["properties"] == {}
    assert by_name["enqueue_action"]["status"] == "live"
    assert by_name["enqueue_action"]["input_schema"]["required"] == ["kind"]
    assert by_name["action_result"]["status"] == "live"
    assert by_name["action_result"]["input_schema"]["required"] == ["action_id"]
    assert tools == server.TOOL_SCHEMAS_V1  # deterministic output


def test_server_without_the_bridge_reports_the_capability_honestly() -> None:
    """P3-5: session_bridge capability is per-process — False on a server
    started without --session-port/--session-token (the full enabled path
    lives in test_mcp_session.py)."""
    info = _rpc("initialize")["result"]["serverInfo"]
    assert info["capabilities"]["session_bridge"] is False
    assert info["capabilities"]["progress_streaming"] is True


def test_server_declares_progress_streaming() -> None:
    """P3-4: the capability flag is ON now that long tools emit
    notifications/progress — flipped honestly, tested like any surface."""
    response = _rpc("initialize", params={})
    info = response["result"]["serverInfo"]
    assert info["capabilities"]["progress_streaming"] is True


# -- P3-4: progress streaming over a REAL canonical job --------------------------

def _fake_video_job(tmp_path: Path, planned: int, done: set[int]) -> Path:
    """A contract-valid video job (same shape test_action.py builds)."""

    def pose_dict(i: int) -> dict:
        z = 0.01 * (i % 5)
        positions = {
            "hips": (0.0, 0.0, z), "spine": (0.0, 0.02, z + 0.17),
            "chest": (0.0, 0.04, z + 0.34), "neck": (0.0, 0.06, z + 0.45),
            "head": (0.0, 0.08, z + 0.62),
            "upper_arm.L": (-0.18, 0.06, z + 0.42),
            "upper_arm.R": (0.18, 0.06, z + 0.42),
            "forearm.L": (-0.22, 0.04, z + 0.24),
            "forearm.R": (0.22, 0.04, z + 0.24),
            "upper_leg.L": (-0.09, 0.0, z), "upper_leg.R": (0.09, 0.0, z),
            "lower_leg.L": (-0.10, -0.02, z - 0.42),
            "lower_leg.R": (0.10, -0.02, z - 0.42),
            "foot.L": (-0.11, -0.04, z - 0.90),
            "foot.R": (0.11, -0.04, z - 0.90),
        }
        return {
            "positions": {r: list(p) for r, p in sorted(positions.items())},
            "flips": {}, "confidence": 0.8, "reliable": True,
            "scale": 30.0 + math.sin(i), "anchor": "hips", "notes": [],
            "joint_confidence": {},
        }

    def payload(i: int) -> dict:
        entry = {
            "label": "figure 0", "index": 0, "score": 0.9,
            "bbox": [0.0, 0.0, 10.0, 10.0], "pose": pose_dict(i),
            "rotations": [], "skipped": [], "notes": [],
        }
        return {
            "format": 2, "frame": i, "file": f"frame_{i:06d}.png",
            "figure": {k: entry[k] for k in ("label", "index", "score", "bbox")},
            "pose": entry["pose"], "rotations": [], "skipped": [], "notes": [],
            "figures": [entry], "rig": {"name": "rig", "fingerprint": "beef"},
        }

    job = tmp_path / "job"
    (job / "payloads").mkdir(parents=True)
    for i in range(planned):
        if i in done:
            p = job / "payloads" / f"frame_{i:06d}.json"
            p.write_text(json.dumps(payload(i)), encoding="utf-8")
    state = {
        "format": 1, "source": "frames", "rig": "rig.json", "stride": 1,
        "frames": [f"frame_{i:06d}.png" for i in range(planned)],
        "done": {str(i): f"payloads/frame_{i:06d}.json" for i in sorted(done)},
        "notes": [], "updated": "2026-09-17T00:00:00Z",
    }
    (job / "job.json").write_text(json.dumps(state), encoding="utf-8")
    return job


def test_animate_from_video_streams_progress_end_to_end(tmp_path: Path) -> None:
    """With params._meta.progressToken the stdio loop emits
    notifications/progress lines BEFORE the final response: monotonic
    0..1 progress, ordered phases, token echoed on every line."""
    rig_path = tmp_path / "rig.json"
    rigify_rig().to_json(rig_path)
    job = _fake_video_job(tmp_path, planned=6, done={0, 1, 2, 3, 4, 5})
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {
            "name": "animate_from_video",
            "arguments": {"rig": str(rig_path), "job_dir": str(job)},
            "_meta": {"progressToken": "tok-1"},
        }}),
    ]
    responses = _run_stdio(lines)
    assert len(responses) == 6  # 5 notifications + the final result
    notifications = responses[:5]
    result = responses[5]
    assert result["id"] == 11 and "method" not in result
    assert [n["method"] for n in notifications] == ["notifications/progress"] * 5
    assert all(n["params"]["progressToken"] == "tok-1" for n in notifications)
    progress_values = [n["params"]["progress"] for n in notifications]
    assert progress_values == sorted(progress_values)
    assert progress_values[0] > 0.0 and progress_values[-1] == 1.0
    assert [n["params"]["phase"] for n in notifications] == [
        "load", "condition", "contacts", "lock", "done",
    ]
    value = result["result"]["content"][0]["json"]
    assert result["result"]["isError"] is False
    assert value["canonical"]["frames"] == 6
    assert value["canonical"]["planned"] == 6
    assert value["canonical"]["coverage"] == 1.0
    # Streaming is what this fixture tests; the lock's >=5x guarantee lives
    # in the walk-fixture composition gate (test_denoise.py), not here.
    assert value["canonical"]["foot_slide_u_after"] <= value[
        "canonical"]["foot_slide_u_before"]
    assert value["bake"]["status"] == "not_implemented"


def test_animate_from_video_without_token_runs_silently(tmp_path: Path) -> None:
    """No progressToken -> identical result, zero notification lines."""
    rig_path = tmp_path / "rig.json"
    rigify_rig().to_json(rig_path)
    job = _fake_video_job(tmp_path, planned=4, done={0, 1, 3})
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {
            "name": "animate_from_video",
            "arguments": {"rig": str(rig_path), "job_dir": str(job)},
        }}),
    ]
    responses = _run_stdio(lines)
    assert len(responses) == 1
    value = responses[0]["result"]["content"][0]["json"]
    assert responses[0]["result"]["isError"] is False
    assert value["canonical"]["frames"] == 3
    assert value["canonical"]["failed_carried"] == 1
    assert value["canonical"]["coverage"] == 0.75


def test_animate_from_video_bake_field_points_at_the_session_action(
    tmp_path: Path,
) -> None:
    """P3-7: on a session-enabled server the bake field answers
    ``session_action`` with the enqueue recipe. The stdio-only path keeps
    the honest ``not_implemented`` (covered above — those tests run without
    a session runtime)."""
    import session_bridge as bridge

    server.set_session_runtime(
        server.SessionRuntime(bridge.SessionHub("unit-test-token"), 0)
    )
    try:
        rig_path = tmp_path / "rig.json"
        rigify_rig().to_json(rig_path)
        job = _fake_video_job(tmp_path, planned=2, done={0, 1})
        response = _rpc("tools/call", params={
            "name": "animate_from_video",
            "arguments": {"rig": str(rig_path), "job_dir": str(job)},
        })
        value = response["result"]["content"][0]["json"]
        assert response["result"]["isError"] is False
        assert value["bake"]["status"] == "session_action"
        assert "enqueue_action" in value["bake"]["message"]
        assert "bake_action" in value["bake"]["message"]
    finally:
        server.set_session_runtime(None)


def test_animate_from_video_missing_job_is_a_structured_error(
    tmp_path: Path,
) -> None:
    rig_path = tmp_path / "rig.json"
    rigify_rig().to_json(rig_path)
    response = _rpc("tools/call", params={
        "name": "animate_from_video",
        "arguments": {"rig": str(rig_path), "job_dir": str(tmp_path / "nope")},
    })
    value = response["result"]["content"][0]["json"]
    assert response["result"]["isError"] is True
    assert value["error"]["code"] == "invalid_request"


def test_tools_call_inspect_rig_on_real_fixture(tmp_path: Path) -> None:
    rig_path = tmp_path / "rig.json"
    rigify_rig().to_json(rig_path)
    response = _rpc("tools/call", params={
        "name": "inspect_rig", "arguments": {"path": str(rig_path)},
    })
    value = response["result"]["content"][0]["json"]
    assert response["result"]["isError"] is False
    assert value["rig"] == rigify_rig().name
    assert value["assignments"], "the fixture rig must map to roles"
    assert {"role", "bone", "confidence"} <= set(value["assignments"][0])


def test_tools_call_missing_file_is_a_structured_error() -> None:
    response = _rpc("tools/call", params={
        "name": "inspect_rig", "arguments": {"path": "/nope/rig.json"},
    })
    value = response["result"]["content"][0]["json"]
    assert response["result"]["isError"] is True
    assert value["error"]["code"] == "invalid_request"


def test_declared_tool_answers_not_implemented_honestly() -> None:
    response = _rpc("tools/call", params={
        "name": "pose_from_image",
        "arguments": {"rig": "r", "payload": "p"},
    })
    value = response["result"]["content"][0]["json"]
    assert value["error"]["code"] == "not_implemented"


def test_policy_status_reports_defaults() -> None:
    response = _rpc("tools/call", params={"name": "policy_status", "arguments": {}})
    value = response["result"]["content"][0]["json"]
    assert value["adult_module_enabled"] is False
    assert isinstance(value["hard_lines"], list) and value["hard_lines"]


# -- P3-3: structured policy refusals through MCP -------------------------------

def _policy_check(subject: str) -> tuple[dict, dict]:
    response = _rpc("tools/call", params={
        "name": "policy_check", "arguments": {"subject": subject},
    })
    return (
        response["result"]["content"][0]["json"],
        {"isError": response["result"]["isError"]},
    )


def test_policy_check_refusals_mirror_the_core_engine_exactly() -> None:
    """The MCP refusal shape IS riggermortis.policy's Refusal.to_dict() —
    mirrored, byte for byte, from a fresh default engine (public API)."""
    engine = core.PolicyEngine()
    for subject in ("minor", "real_person", "fictional_adult", "bogus"):
        expected = engine.check_explicit_request(subject)
        assert expected is not None  # all four refuse on a default engine
        value, meta = _policy_check(subject)
        assert meta["isError"] is True
        assert value["error"] == expected.to_dict()
        assert set(value["error"]) == {"code", "message", "category", "retryable"}


def test_policy_check_refusal_codes_are_the_public_api() -> None:
    cases = {
        "minor": core.MINOR_CONTENT,
        "real_person": core.REAL_PERSON_EXPLICIT,
        "fictional_adult": core.ADULT_MODULE_DISABLED,
        "bogus": core.INVALID_REQUEST,
    }
    for subject, code in cases.items():
        value, _meta = _policy_check(subject)
        assert value["error"]["code"] == code


def test_policy_check_retryable_follows_the_policy() -> None:
    """adult_module_disabled is the ONLY retryable refusal (the user can
    enable the module with explicit confirmation); hard lines are not."""
    value, _meta = _policy_check("fictional_adult")
    assert value["error"]["retryable"] is True
    for subject in ("minor", "real_person"):
        value, _meta = _policy_check(subject)
        assert value["error"]["retryable"] is False


def test_policy_check_allowed_subject_answers_allowed() -> None:
    value, meta = _policy_check("other")
    assert meta["isError"] is False
    assert value == {"allowed": True, "subject": "other"}


def test_policy_check_non_string_subject_is_invalid_request() -> None:
    response = _rpc("tools/call", params={
        "name": "policy_check", "arguments": {"subject": 42},
    })
    value = response["result"]["content"][0]["json"]
    assert response["result"]["isError"] is True
    assert value["error"]["code"] == core.INVALID_REQUEST


def test_policy_status_lists_the_public_refusal_codes() -> None:
    response = _rpc("tools/call", params={"name": "policy_status", "arguments": {}})
    value = response["result"]["content"][0]["json"]
    assert value["refusal_codes"] == [
        core.MINOR_CONTENT,
        core.REAL_PERSON_EXPLICIT,
        core.ADULT_MODULE_DISABLED,
        core.INVALID_REQUEST,
    ]


def test_unknown_method_and_notifications() -> None:
    response = _rpc("no/such/method")
    assert response["error"]["code"] == -32601
    assert server.handle({"jsonrpc": "2.0", "method": "ping"}) is None


def test_stdio_loop_end_to_end() -> None:
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"}),
        json.dumps({"jsonrpc": "2.0", "id": 8, "method": "initialize"}),
        "not json at all",
        "",
    ]
    responses = _run_stdio(lines)
    assert [r["id"] for r in responses] == [7, 8, None]
    assert responses[0]["result"] == {}
    assert responses[1]["result"]["serverInfo"]["name"] == "riggermortis"
    assert responses[2]["error"]["code"] == -32700
