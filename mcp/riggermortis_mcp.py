"""riggermortis MCP server (P3-1..P3-4) — stdio JSON-RPC 2.0.

Local-only by construction: stdio transport, no sockets opened here yet (the
loopback session bridge is P3-5), no telemetry, no spawns (D-003/D-009: the
server CONSUMES payloads and core APIs; it never launches processes).

Protocol: newline-delimited JSON-RPC 2.0 over stdin/stdout, per the MCP
conventions. Implemented methods:

- ``initialize``            -> server_info (contract version, capabilities)
- ``tools/list``            -> schema v1 for the Phase-0/1 tool subset
- ``tools/call``            -> ``inspect_rig``, ``policy_status``,
                               ``policy_check`` and ``animate_from_video``
                               (canonical half) are LIVE; ``pose_from_image``
                               returns a structured ``not_implemented`` result
                               (honest, still schema-listed so agents can
                               plan against it)
- ``ping``                  -> {}

Progress streaming (P3-4): long tools emit ``notifications/progress``
(``progressToken``/``progress`` 0..1/``phase``/``message`` per
mcp/DESIGN.md) while they run, when the request carries
``params._meta.progressToken`` and the client owns the stdio channel.
Without a token every tool runs identically and silently.

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
SERVER_VERSION = "0.2.0"

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
        "status": "live",
        "description": "Per-frame payloads -> canonical action -> cleanup "
                       "(stabilize -> detect -> lock, the certified "
                       "composition) with progress notifications; returns the "
                       "action summary + foot-slide metrics. The rig-space "
                       "BAKE stays not_implemented (it needs the Blender "
                       "add-on path, D-009)",
        "input_schema": {
            "type": "object",
            "properties": {
                "rig": {"type": "string"},
                "job_dir": {"type": "string"},
                "hip_stabilize": {
                    "type": "number",
                    "description": "0..1, None disables; default 0.7",
                },
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
        "capabilities": {"tools": True, "progress_streaming": True},
        "tool_schema_version": 1,
    }


class ProgressReporter:
    """Emits ``notifications/progress`` for one tools/call (P3-4).

    Created only when the request carries ``params._meta.progressToken`` and
    the transport owns an output channel; tools must run identically (and
    silently) without one. ``progress`` is clamped to 0..1 and rounded to 3
    decimals so re-runs emit byte-identical lines.
    """

    def __init__(self, token, emit) -> None:
        self._token = token
        self._emit = emit

    def report(self, phase: str, fraction: float, message: str) -> None:
        clamped = max(0.0, min(1.0, float(fraction)))
        self._emit(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/progress",
            "params": {
                "progressToken": self._token,
                "progress": round(clamped, 3),
                "phase": str(phase),
                "message": str(message),
            },
        }, sort_keys=True))


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


def animate_from_video(arguments: dict, progress=None) -> dict:
    """Canonical half of the video pipeline (P3-4): load a job's payloads
    through the payload contract, run the certified cleanup composition
    (stabilize -> detect -> lock), and report the honest metrics. The
    rig-space BAKE needs the Blender add-on path (D-009) and stays
    not_implemented — declared in the result, never swallowed.
    """
    job_dir = arguments.get("job_dir")
    rig = arguments.get("rig")
    if not isinstance(job_dir, str) or not job_dir or not Path(job_dir).is_dir():
        return {
            "error": {
                "code": "invalid_request",
                "message": f"job_dir not found: {job_dir!r}",
                "retryable": False,
            }
        }
    if not isinstance(rig, str) or not rig or not Path(rig).is_file():
        return {
            "error": {
                "code": "invalid_request",
                "message": f"rig file not found: {rig!r}",
                "retryable": False,
            }
        }
    strength = arguments.get("hip_stabilize", 0.7)
    if strength is not None and not isinstance(strength, (int, float)):
        return {
            "error": {
                "code": "invalid_request",
                "message": "hip_stabilize must be a number in [0, 1] or null",
                "retryable": False,
            }
        }
    try:
        action = core.load_action(Path(job_dir))
        if progress is not None:
            progress.report(
                "load", 0.15,
                f"loaded {len(action.frames)} frame(s), "
                f"{len(action.failed)} failed and carried",
            )
        conditioned = core.condition_action(
            action, hip_stabilize=strength, min_cutoff=None, tolerance=None,
        )
        if progress is not None:
            progress.report(
                "condition", 0.4,
                f"stabilize({strength}) -> {len(conditioned.frames)} frame(s)",
            )
        report = core.detect_contacts(conditioned.frames)
        if progress is not None:
            progress.report(
                "contacts", 0.65,
                f"{len(report.intervals)} contact interval(s) detected",
            )
        _locked, lock = core.lock_feet(conditioned, report)
        if progress is not None:
            progress.report(
                "lock", 0.9,
                f"foot lock: slide {lock.slide_before.total:.4f}u -> "
                f"{lock.slide_after.total:.4f}u",
            )
    except core.RiggermortisError as exc:
        return {
            "error": {"code": "invalid_request", "message": str(exc),
                      "retryable": False}
        }
    planned = len(action.frames) + len(action.failed)
    coverage = round(len(conditioned.frames) / planned, 4) if planned else 0.0
    if progress is not None:
        progress.report("done", 1.0, "canonical action ready")
    return {
        "canonical": {
            "frames": len(conditioned.frames),
            "planned": planned,
            "failed_carried": len(action.failed),
            "coverage": coverage,
            "foot_slide_u_before": round(lock.slide_before.total, 4),
            "foot_slide_u_after": round(lock.slide_after.total, 4),
            "unit": "canonical u (single-view, scale-normalized; not cm)",
            "notes": list(action.notes) + list(conditioned.notes)[-2:],
        },
        "bake": {
            "status": "not_implemented",
            "message": "rig-space baking runs in the Blender add-on (D-009); "
                       "load this job there, or export via the make "
                       "export-verify path",
            "retryable": False,
        },
    }


def call_tool(name: str, arguments: dict, progress=None) -> dict:
    if name == "inspect_rig":
        return inspect_rig(arguments)
    if name == "policy_status":
        return policy_status()
    if name == "policy_check":
        return policy_check(arguments)
    if name == "animate_from_video":
        return animate_from_video(arguments, progress)
    return {
        "error": {
            "code": "not_implemented",
            "message": f"tool {name!r} is declared in schema v1 but not implemented yet",
            "retryable": False,
        }
    }


def handle(request: dict, emit=None) -> dict | None:
    """One JSON-RPC request -> response dict (or None for notifications).

    ``emit`` (optional) receives one string per notification LINE while the
    request is being served — the stdio loop writes+flushes it so progress
    notifications reach the client before the final response. Without an
    output channel, progress emission is suppressed and tools run silently.
    """
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
        meta = params.get("_meta") or {}
        token = meta.get("progressToken") if isinstance(meta, dict) else None
        progress = (
            ProgressReporter(token, emit)
            if token is not None and emit is not None
            else None
        )
        try:
            value = call_tool(name, params.get("arguments") or {}, progress)
        except Exception as exc:  # noqa: BLE001 — JSON-RPC surface, never a traceback
            return error(-32603, f"internal error in {name}: {exc}")
        if "error" in value:
            return result({"content": [{"type": "json", "json": value}], "isError": True})
        return result({"content": [{"type": "json", "json": value}], "isError": False})
    return error(-32601, f"method not found: {method}")


def serve_stdin_stdout() -> int:
    """Newline-delimited JSON-RPC loop over stdin/stdout."""

    def emit(line: str) -> None:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

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
            response = handle(request, emit=emit)
        if response is not None:
            sys.stdout.write(json.dumps(response, sort_keys=True) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(serve_stdin_stdout())
