"""P3-1/P3-2 golden tests: MCP server framing, schemas, and tool behavior."""
from __future__ import annotations

import io
import json
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
    """Golden-schema test: the v1 tool table is pinned (name, status, required)."""
    response = _rpc("tools/list")
    tools = response["result"]["tools"]
    by_name = {t["name"]: t for t in tools}
    assert set(by_name) == {
        "inspect_rig", "policy_status", "policy_check", "map_rig",
        "pose_from_image", "animate_from_video",
    }
    assert by_name["inspect_rig"]["status"] == "live"
    assert by_name["inspect_rig"]["input_schema"]["required"] == ["path"]
    assert by_name["pose_from_image"]["status"] == "declared"
    assert by_name["policy_status"]["input_schema"]["properties"] == {}
    assert by_name["policy_check"]["status"] == "live"
    assert by_name["policy_check"]["input_schema"]["required"] == ["subject"]
    assert tools == server.TOOL_SCHEMAS_V1  # deterministic output


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
        "name": "animate_from_video",
        "arguments": {"rig": "r", "job_dir": "j"},
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
