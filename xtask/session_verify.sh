#!/usr/bin/env bash
# P3-5/P3-7 session-bridge gate: the FULL loop with a real Blender as the add-on.
#
# 1. starts the MCP server with the loopback bridge (--session-port/--session-token)
# 2. acts as the agent over the server's stdio: enqueues inspect_scene,
#    apply_pose (valid payload), apply_pose (deliberately missing payload),
#    bake_action (P3-7: a contract-valid walk fixture job through the REAL
#    add-on bake path under the certified composition), render_turntable
#    (P3-7), apply_style (S13: the P4 style builders on a shaded object)
# 3. runs xtask/session_probe.py headlessly in Blender: registers the add-on,
#    builds rig + sphere + payload + fixture job, connects the REAL session
#    client, executes all six actions through the real main-thread executor
# 4. collects the structured results via action_result and validates them:
#    the bake's re-evaluated fcurves must land <= 0.5 deg (RM_BAKE instrument,
#    unlocked roles; the locked-chain deviation is reported separately), the
#    turntable must render its frames to disk, the style report must name
#    the built material/lineart/tones datablocks
#
# Honest scope: self-contained (no models, no local assets); the walk fixture
# job is SYNTHETIC (generator-cited, xtask/walk_job.py) — labeled, never
# relabeled. Exits non-zero on the first failure.
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

echo "== 1/6 starting MCP server with the session bridge on 127.0.0.1:$PORT"
sleep 0.3
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "error: server exited at startup:" >&2
  cat "$TMP/server.err.log" >&2
  exit 1
fi

echo "== 2/6 enqueueing six actions as the agent (stdio JSON-RPC)"
rpc 1 enqueue_action '{"kind":"inspect_scene","params":{}}'
rpc 2 enqueue_action '{"kind":"apply_pose","params":{"payload_path":"'"$TMP"'/stand.json","armature_name":"RM_SessionRig"}}'
rpc 3 enqueue_action '{"kind":"apply_pose","params":{"payload_path":"'"$TMP"'/missing.json","armature_name":"RM_SessionRig"}}'
rpc 4 enqueue_action '{"kind":"bake_action","params":{"job_dir":"'"$TMP"'/walkjob","armature_name":"RM_SessionRig"}}'
rpc 5 enqueue_action '{"kind":"render_turntable","params":{"out_dir":"'"$TMP"'/turntable","armature_name":"RM_SessionRig","frames":4,"width":320,"height":240,"prefix":"gate"}}'
rpc 6 enqueue_action '{"kind":"apply_style","params":{"style":"manga","object":"RM_StyleSphere"}}'
A1=$(json_field "$(wait_line 1)" "v['result']['content'][0]['json']['action_id']")
A2=$(json_field "$(wait_line 2)" "v['result']['content'][0]['json']['action_id']")
A3=$(json_field "$(wait_line 3)" "v['result']['content'][0]['json']['action_id']")
A4=$(json_field "$(wait_line 4)" "v['result']['content'][0]['json']['action_id']")
A5=$(json_field "$(wait_line 5)" "v['result']['content'][0]['json']['action_id']")
A6=$(json_field "$(wait_line 6)" "v['result']['content'][0]['json']['action_id']")
echo "   enqueued: $A1 $A2 $A3 $A4 $A5 $A6"

echo "== 3/6 running the real add-on client inside Blender (headless)"
RM_SESSION_LOG="$TMP/blender.log"
"$BLENDER" -b --python "$REPO/xtask/session_probe.py" -- "$PORT" "$TOKEN" "$TMP/stand.json" "$TMP/walkjob" \
  > "$RM_SESSION_LOG" 2>&1 || { cat "$RM_SESSION_LOG" >&2; exit 1; }
grep -q "RM_SESSION_PROBE OK" "$RM_SESSION_LOG" || { cat "$RM_SESSION_LOG" >&2; exit 1; }
grep "RM_SESSION_PROBE OK" "$RM_SESSION_LOG"

echo "== 4/6 collecting the structured results (the agent half)"
rpc 7 action_result "{\"action_id\":\"$A1\"}"
rpc 8 action_result "{\"action_id\":\"$A2\"}"
rpc 9 action_result "{\"action_id\":\"$A3\"}"
rpc 10 action_result "{\"action_id\":\"$A4\"}"
rpc 11 action_result "{\"action_id\":\"$A5\"}"
rpc 12 action_result "{\"action_id\":\"$A6\"}"
R1=$(wait_line 7)
R2=$(wait_line 8)
R3=$(wait_line 9)
R4=$(wait_line 10)
R5=$(wait_line 11)
R6=$(wait_line 12)

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

# -- P3-7: bake_action through the REAL add-on bake path -----------------------
check "$R4" "v['result']['content'][0]['json']['status'] == 'done'" \
  "bake_action completed through the real P2-3/P2-5 path"
check "$R4" "v['result']['content'][0]['json']['report']['reeval_worst_deg'] <= 0.5" \
  "baked frames re-evaluate <= 0.5 deg (RM_BAKE instrument, unlocked roles)"
check "$R4" "v['result']['content'][0]['json']['report']['locked_frames'] >= 1" \
  "the contact lock pinned at least one frame"
check "$R4" "v['result']['content'][0]['json']['report']['contacts']['intervals'] >= 1" \
  "contact detection found the fixture walk's contacts"
check "$R4" "v['result']['content'][0]['json']['report']['contacts']['slide_after_u'] <= v['result']['content'][0]['json']['report']['contacts']['slide_before_u']" \
  "foot-slide did not increase through the certified composition"
check "$R4" "v['result']['content'][0]['json']['report']['reeval_frames'] >= 2 and v['result']['content'][0]['json']['report']['reeval_checks'] > 0" \
  "re-evaluation measured the baked frames"
check "$R4" "'root motion' in ' '.join(v['result']['content'][0]['json']['report']['notes'])" \
  "honest no-root-motion note travels in the report"

# -- P3-7: render_turntable -----------------------------------------------------
check "$R5" "v['result']['content'][0]['json']['status'] == 'done'" \
  "render_turntable completed"
check "$R5" "v['result']['content'][0]['json']['report']['frames_rendered'] == 4" \
  "turntable rendered its four frames"
check "$R5" "v['result']['content'][0]['json']['report']['played_action'] is True" \
  "turntable played the baked action while orbiting"
check "$R5" "v['result']['content'][0]['json']['report']['bones_visualized'] >= 12" \
  "turntable visualized the mapped bone set"
TURN_PNG=$(json_field "$R5" "v['result']['content'][0]['json']['report']['frames'][0]['path']")
if [ ! -s "$TURN_PNG" ]; then
  echo "error: turntable frame missing on disk: $TURN_PNG" >&2
  exit 1
fi
echo "   ok: turntable frames on disk ($TURN_PNG)"

# -- S13: apply_style (the P4 style builders as a session action) ---------------
# Capability-tolerant like the style gate: a 5.x-class Blender builds the
# lineart overlay + tone compositor (manga carries both); a pre-5.x one
# reports SKIPPED honestly for those halves while the material still builds.
check "$R6" "v['result']['content'][0]['json']['status'] == 'done'" \
  "apply_style completed through the real P4 builders"
check "$R6" "v['result']['content'][0]['json']['report']['style'] == 'manga' and v['result']['content'][0]['json']['report']['object'] == 'RM_StyleSphere'" \
  "apply_style named the style and the styled object"
check "$R6" "v['result']['content'][0]['json']['report']['material'] == 'rm_style_manga'" \
  "apply_style built the deterministic toon material"
R6REP="v['result']['content'][0]['json']['report']"
check "$R6" "(isinstance($R6REP['lineart'], dict) and $R6REP['lineart']['object'] == 'rm_lineart' and isinstance($R6REP['tones'], dict) and $R6REP['tones']['group'] == 'rm_tones') or ('SKIPPED' in str($R6REP['lineart']) and 'SKIPPED' in str($R6REP['tones']))" \
  "apply_style built lineart+tones (5.x) or reported SKIPPED honestly (pre-5.x)"

# unknown action_id -> structured invalid_request, isError flagged
rpc 13 action_result "{\"action_id\":\"a-9999\"}"
R9=$(wait_line 13)
check "$R9" "v['result']['isError'] is True" "unknown action_id is a structured error"
check "$R9" "v['result']['content'][0]['json']['error']['code'] == 'invalid_request'" \
  "unknown action_id answers invalid_request"

if [ -s "$TMP/server.err.log" ]; then
  echo "error: server wrote to stderr:" >&2
  cat "$TMP/server.err.log" >&2
  exit 1
fi

echo ""
echo "P3-5/P3-7 SESSION GATE: PASS"
