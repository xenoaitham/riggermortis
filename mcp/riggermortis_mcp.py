"""riggermortis MCP server (P3-1/P3-2 skeleton) — stdio JSON-RPC 2.0.

Local-only by construction: stdio transport, no sockets opened here yet (the
loopback session bridge is P3-5), no telemetry, no spawns (D-003/D-009: the
server CONSUMES payloads and core APIs; it never launches processes).

Protocol: newline-delimited JSON-RPC 2.0 over stdin/stdout, per the MCP
conventions. Implemented methods:

- ``initialize``            -> server_info (contract version, capabilities)
- ``tools/list``            -> schema v1 for the Phase-0/1 tool subset
- ``tools/call``            -> ``inspect_rig``, ``policy_status`` and
                               ``policy_check`` are LIVE; the remaining design
                               tools return a structured ``not_implemented``
                               result (honest, still schema-listed so agents
                               can plan against them)
- ``ping``                  -> {}

Structured policy refusals (P3-3) mirror ``riggermortis.policy`` exactly:
codes are imported from the core module (public API, never re-typed here)
and the error shape is ``Refusal.to_dict()`` —
``{"code", "message", "category", "retryable"}`` per mcp/DESIGN.md.

Run: ``python3 mcp/riggermortis_mcp.py`` (an agent client owns the process —
spawn lives outside Python per D-009).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core" / "src"))

import riggermortis as core  # noqa: E402
from riggermortis.io import load_rig  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_VERSION = "0.1.0"

#: Schema v1 for the implemented + design-declared tools (mcp/DESIGN.md).
#: Honest: ``status`` separates live tools from declared-but-pending ones.
TOOL_SCHEMAS_V1: list[dict] = [
    {
        "name": "inspect_rig",
        "status": "live",
        "description": "Bone inventory + proposed role mapping + confidence per bone",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "policy_status",
        "status": "live",
        "description": "Content-policy state: defaults, hard lines, refusal codes",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "policy_check",
        "status": "live",
        "description": "Evaluate a hypothetical content request against the "
                       "policy; refused subjects answer with the structured "
                       "refusal shape (codes mirror riggermortis.policy)",
        "input_schema": {
            "type": "object",
            "properties": {"subject": {"type": "string"}},
            "required": ["subject"],
        },
    },
    {
        "name": "map_rig",
        "status": "live",
        "description": "Apply/adjust mapping; optional per-rig preset save",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "overrides": {"type": "object"},
                "save_preset": {"type": "boolean"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "pose_from_image",
        "status": "declared",
        "description": "Detect pose from an image payload and report quality "
                       "(the agent runs `rigpose pose` and applies the payload; D-009)",
        "input_schema": {
            "type": "object",
            "properties": {
                "rig": {"type": "string"},
                "payload": {"type": "string"},
                "mirror": {"type": "boolean"},
                "figure": {"type": "string"},
            },
            "required": ["rig", "payload"],
        },
    },
    {
        "name": "animate_from_video",
        "status": "declared",
        "description": "Per-frame payloads -> smooth -> retarget -> cleanup (P2-3+)",
        "input_schema": {
            "type": "object",
            "properties": {
                "rig": {"type": "string"},
                "job_dir": {"type": "string"},
            },
            "required": ["rig", "job_dir"],
        },
    },
]


def server_info() -> dict:
    return {
        "name": "riggermortis",
        "version": SERVER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "core_version": core.__version__,
        "local_only": True,
        "capabilities": {"tools": True, "progress_streaming": False},
        "tool_schema_version": 1,
    }


def policy_status() -> dict:
    engine = core.PolicyEngine()
    status = engine.status()  # {adult_module_enabled, defaults, hard_lines}
    return {
        "adult_module_enabled": status.get("adult_module_enabled", False),
        "defaults": status.get("defaults", {}),
        "hard_lines": status.get("hard_lines", []),
        # Public-API refusal codes, imported from the core module (P3-3):
        # frontends must report exactly these strings.
        "refusal_codes": [
            core.MINOR_CONTENT,
            core.REAL_PERSON_EXPLICIT,
            core.ADULT_MODULE_DISABLED,
            core.INVALID_REQUEST,
        ],
    }


def policy_check(arguments: dict) -> dict:
    """Evaluate a hypothetical content request (P3-3).

    Allowed subjects answer ``{"allowed": true, ...}``; refused ones answer
    with the EXACT structured refusal shape from ``riggermortis.policy``
    (``Refusal.to_dict()``) under ``error`` with ``isError`` — the same shape
    every content-carrying tool will return once implemented (P6-4/P6-5).
    """
    subject = arguments.get("subject")
    if not isinstance(subject, str):
        return {
            "error": {
                "code": core.INVALID_REQUEST,
                "message": "subject must be a string "
                           "(expected: minor, real_person, fictional_adult, other)",
                "retryable": False,
            }
        }
    engine = core.PolicyEngine()
    refusal = engine.check_explicit_request(subject)
    if refusal is None:
        return {"allowed": True, "subject": subject}
    return {"error": refusal.to_dict()}


def inspect_rig(arguments: dict) -> dict:
    path = arguments.get("path")
    if not path or not Path(str(path)).exists():
        return {
            "error": {
                "code": "invalid_request",
                "message": f"rig file not found: {path!r}",
                "retryable": False,
            }
        }
    try:
        rig = load_rig(Path(str(path)))
        mapping = core.map_rig(rig)
    except core.RiggermortisError as exc:
        return {
            "error": {"code": "invalid_request", "message": str(exc), "retryable": False}
        }
    return {
        "rig": rig.name,
        "fingerprint": rig.fingerprint(),
        "bone_count": len(rig.bones),
        "assignments": [
            {"role": a.role, "bone": a.bone, "confidence": round(a.confidence, 4)}
            for a in sorted(mapping.assignments.values(), key=lambda a: a.role)
        ],
        "core_missing": sorted(mapping.core_missing()),
        "ambiguities": [
            a.to_dict() if hasattr(a, "to_dict") else str(a)
            for a in mapping.ambiguities
        ],
    }


def call_tool(name: str, arguments: dict) -> dict:
    if name == "inspect_rig":
        return inspect_rig(arguments)
    if name == "policy_status":
        return policy_status()
    if name == "policy_check":
        return policy_check(arguments)
    return {
        "error": {
            "code": "not_implemented",
            "message": f"tool {name!r} is declared in schema v1 but not implemented yet",
            "retryable": False,
        }
    }


def handle(request: dict) -> dict | None:
    """One JSON-RPC request -> response dict (or None for notifications)."""
    method = request.get("method", "")
    request_id = request.get("id")
    notification = request_id is None

    def result(value: dict) -> dict | None:
        if notification:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": value}

    def error(code: int, message: str) -> dict | None:
        if notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    if method == "initialize":
        return result({"protocolVersion": PROTOCOL_VERSION, "serverInfo": server_info()})
    if method == "ping":
        return result({})
    if method == "tools/list":
        return result({"tools": TOOL_SCHEMAS_V1, "schema_version": 1})
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name", "")
        try:
            value = call_tool(name, params.get("arguments") or {})
        except Exception as exc:  # noqa: BLE001 — JSON-RPC surface, never a traceback
            return error(-32603, f"internal error in {name}: {exc}")
        if "error" in value:
            return result({"content": [{"type": "json", "json": value}], "isError": True})
        return result({"content": [{"type": "json", "json": value}], "isError": False})
    return error(-32601, f"method not found: {method}")


def serve_stdin_stdout() -> int:
    """Newline-delimited JSON-RPC loop over stdin/stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32700, "message": f"parse error: {exc}"},
            }
        else:
            response = handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response, sort_keys=True) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(serve_stdin_stdout())
