#!/usr/bin/env bash
# P3-5 session-bridge gate: the FULL loop with a real Blender as the add-on.
#
# 1. starts the MCP server with the loopback bridge (--session-port/--session-token)
# 2. acts as the agent over the server's stdio: enqueues inspect_scene,
#    apply_pose (valid payload), apply_pose (deliberately missing payload)
# 3. runs xtask/session_probe.py headlessly in Blender: registers the add-on,
#    connects the REAL session client, executes all three actions through the
#    real main-thread executor (payload apply = the D-009 path)
# 4. collects the structured results via action_result and validates them
#
# Honest scope: the apply action must SUCCEED structurally (report with
# applied bones + self-check numbers); pose-FIDELITY bars stay in
# verify_pose_apply.sh (real payloads, real rigs). Self-contained: no models,
# no local assets. Exits non-zero on the first failure.
#
# Run: make session-verify   (or: BLENDER=... PY=... bash xtask/session_verify.sh)
set -euo pipefail

BLENDER=${BLENDER:-blender}
PY=${PY:-python3}
REPO=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

PORT=$("$PY" -c 'import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()')
TOKEN=$("$PY" -c 'import secrets; print(secrets.token_hex(16))')

mkfifo "$TMP/server.in"
"$PY" "$REPO/mcp/riggermortis_mcp.py" \
  --session-port "$PORT" --session-token "$TOKEN" \
  < "$TMP/server.in" > "$TMP/server.out.log" 2> "$TMP/server.err.log" &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; }
trap 'cleanup; rm -rf "$TMP"' EXIT
exec 3>"$TMP/server.in"   # hold the server's stdin open

rpc() { # RPC_ID TOOL_NAME ARGUMENTS_JSON
  printf '{"jsonrpc":"2.0","id":%s,"method":"tools/call","params":{"name":"%s","arguments":%s}}\n' \
    "$1" "$2" "$3" >&3
}

wait_line() { # N — wait for the Nth response line on the server's stdout
  local n="$1" i
  for i in $(seq 1 150); do
    if [ "$(wc -l < "$TMP/server.out.log")" -ge "$n" ]; then
      sed -n "${n}p" "$TMP/server.out.log"
      return 0
    fi
    sleep 0.1
  done
  echo "error: timed out waiting for response $n" >&2
  exit 1
}

json_field() { # JSON PYEXPR — evaluate a json path expression
  "$PY" -c 'import json, sys
value = json.loads(sys.argv[1])
print(eval(sys.argv[2], {"v": value}))' "$1" "$2"
}

echo "== 1/4 starting MCP server with the session bridge on 127.0.0.1:$PORT"
sleep 0.3
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "error: server exited at startup:" >&2
  cat "$TMP/server.err.log" >&2
  exit 1
fi

echo "== 2/4 enqueueing three actions as the agent (stdio JSON-RPC)"
rpc 1 enqueue_action '{"kind":"inspect_scene","params":{}}'
rpc 2 enqueue_action '{"kind":"apply_pose","params":{"payload_path":"'"$TMP"'/stand.json","armature_name":"RM_SessionRig"}}'
rpc 3 enqueue_action '{"kind":"apply_pose","params":{"payload_path":"'"$TMP"'/missing.json","armature_name":"RM_SessionRig"}}'
A1=$(json_field "$(wait_line 1)" "v['result']['content'][0]['json']['action_id']")
A2=$(json_field "$(wait_line 2)" "v['result']['content'][0]['json']['action_id']")
A3=$(json_field "$(wait_line 3)" "v['result']['content'][0]['json']['action_id']")
echo "   enqueued: $A1 $A2 $A3"

echo "== 3/4 running the real add-on client inside Blender (headless)"
RM_SESSION_LOG="$TMP/blender.log"
"$BLENDER" -b --python "$REPO/xtask/session_probe.py" -- "$PORT" "$TOKEN" "$TMP/stand.json" \
  > "$RM_SESSION_LOG" 2>&1 || { cat "$RM_SESSION_LOG" >&2; exit 1; }
grep -q "RM_SESSION_PROBE OK" "$RM_SESSION_LOG" || { cat "$RM_SESSION_LOG" >&2; exit 1; }
grep "RM_SESSION_PROBE OK" "$RM_SESSION_LOG"

echo "== 4/4 collecting the structured results (the agent half)"
rpc 4 action_result "{\"action_id\":\"$A1\"}"
rpc 5 action_result "{\"action_id\":\"$A2\"}"
rpc 6 action_result "{\"action_id\":\"$A3\"}"
R1=$(wait_line 4)
R2=$(wait_line 5)
R3=$(wait_line 6)

check() { # RESPONSE PYEXPR DESCRIPTION
  local got
  got=$(json_field "$1" "$2")
  if [ "$got" != "True" ]; then
    echo "error: $3 FAILED (got: $got)" >&2
    echo "$1" | head -c 2000 >&2
    echo >&2
    exit 1
  fi
  echo "   ok: $3"
}

check "$R1" "v['result']['content'][0]['json']['status'] == 'done'" \
  "inspect_scene completed"
check "$R1" "v['result']['content'][0]['json']['report']['count'] >= 1" \
  "inspect_scene sees the gate rig"
check "$R2" "v['result']['content'][0]['json']['status'] == 'done'" \
  "apply_pose completed"
check "$R2" "len(v['result']['content'][0]['json']['report']['applied']) > 0" \
  "apply_pose applied bones through the real D-009 path"
check "$R2" "isinstance(v['result']['content'][0]['json']['report']['worst_deg'], float)" \
  "apply_pose self-check numbers round-tripped"
check "$R3" "v['result']['content'][0]['json']['status'] == 'failed'" \
  "missing-payload apply FAILED honestly (not silently)"
check "$R3" "v['result']['content'][0]['json']['error']['code'] == 'executor_error'" \
  "failure carries the structured error code"
check "$R3" "'hint' in v['result']['content'][0]['json']['error']['message'] or 'payload' in v['result']['content'][0]['json']['error']['message']" \
  "failure message is actionable"

# unknown action_id -> structured invalid_request, isError flagged
rpc 9 action_result "{\"action_id\":\"a-9999\"}"
R9=$(wait_line 7)
check "$R9" "v['result']['isError'] is True" "unknown action_id is a structured error"
check "$R9" "v['result']['content'][0]['json']['error']['code'] == 'invalid_request'" \
  "unknown action_id answers invalid_request"

if [ -s "$TMP/server.err.log" ]; then
  echo "error: server wrote to stderr:" >&2
  cat "$TMP/server.err.log" >&2
  exit 1
fi

echo ""
echo "P3-5 SESSION GATE: PASS"
