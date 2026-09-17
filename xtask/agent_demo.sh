#!/usr/bin/env bash
# P3-7 E2E agent demo — the Phase-3 launch asset.
#
# A deterministic scripted AGENT (shell JSON-RPC over the MCP server's stdio
# — the session_verify glue pattern, a real MCP client) drives a LIVE
# Blender through the whole Phase-3 loop with zero human interaction:
#
#   inspect (rig + scene) -> pose (real photo payload) -> animate (fixture
#   walk job, progress streamed) -> bake (the REAL add-on path) ->
#   render turntable -> collected via action_result.
#
# Honest inputs, stated everywhere they matter: the rig is the real local
# metarig, the pose payload is real pipeline output, and the MOTION is the
# labeled SYNTHETIC walk fixture (xtask/walk_job.py; real-clip NEEDS-HUMAN,
# out/video_smoke/SOURCES.md). The GIF + transcript land in docs/ with the
# media-guard allowlist extended in the same commit.
#
# Run: make agent-demo   (or: BLENDER=... PY=... bash xtask/agent_demo.sh)
set -euo pipefail

BLENDER=${BLENDER:-blender}
PY=${PY:-python3}
REPO=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

METARIG="$REPO/out/real_rigs/metarig.blend"
METARIG_RIG="$REPO/out/real_rigs/metarig.rig.json"
PAYLOAD="$REPO/out/payloads/metarig_payload.json"
for f in "$METARIG" "$METARIG_RIG" "$PAYLOAD"; do
  if [ ! -s "$f" ]; then
    echo "missing $f — the demo needs the local rigs/payloads (see docs/BENCHMARKS.md reproduce block)" >&2
    exit 1
  fi
done

PORT=$("$PY" -c 'import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()')
TOKEN=$("$PY" -c 'import secrets; print(secrets.token_hex(16))')
TRANSCRIPT="$TMP/transcript.txt"
: > "$TRANSCRIPT"

echo "== 1/6 starting the MCP server with the session bridge on 127.0.0.1:$PORT"
mkfifo "$TMP/server.in"
"$PY" "$REPO/mcp/riggermortis_mcp.py" \
  --session-port "$PORT" --session-token "$TOKEN" \
  < "$TMP/server.in" > "$TMP/server.out.log" 2> "$TMP/server.err.log" &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; }
trap 'cleanup; rm -rf "$TMP"' EXIT
exec 3>"$TMP/server.in"
sleep 0.3
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "error: server exited at startup:" >&2
  cat "$TMP/server.err.log" >&2
  exit 1
fi

C_FILE="$TMP/consumed"  # consumed-line counter lives in a FILE: the helpers
echo 0 > "$C_FILE"      # run in command-substitution subshells, vars die

read_C() { cat "$C_FILE"; }

wait_new() { # wait for stdout to grow past the consumed count; print count
  local base c i
  base=$(read_C)
  for i in $(seq 1 600); do
    c=$(wc -l < "$TMP/server.out.log")
    if [ "$c" -gt "$base" ]; then
      echo "$c"
      return 0
    fi
    sleep 0.2
  done
  echo "error: timed out waiting for the server" >&2
  exit 1
}

capture() { # shared body; echoes the FINAL (last new) response line
  local req new base
  req="$1"
  printf '>>> %s\n' "$req" >> "$TRANSCRIPT"
  printf '%s\n' "$req" >&3
  new=$(wait_new)
  base=$(read_C)
  sed -n "$((base + 1)),${new}p" "$TMP/server.out.log" | sed 's/^/<<< /' >> "$TRANSCRIPT"
  echo "$new" > "$C_FILE"
  sed -n "${new}p" "$TMP/server.out.log"
}

raw_rpc() { # ID METHOD PARAMS_JSON — one protocol-level request (initialize…)
  capture "$(printf '{"jsonrpc":"2.0","id":%s,"method":"%s","params":%s}' "$1" "$2" "$3")"
}

call_tool() { # ID TOOL ARGS_JSON — one tools/call
  capture "$(printf '{"jsonrpc":"2.0","id":%s,"method":"tools/call","params":{"name":"%s","arguments":%s}}' "$1" "$2" "$3")"
}

json_field() { # JSON PYEXPR — print a scalar
  "$PY" -c 'import json, sys
value = json.loads(sys.argv[1])
print(eval(sys.argv[2], {"v": value}))' "$1" "$2"
}

json_value() { # JSON PYEXPR OUT — print the evaluated value AS JSON
  "$PY" -c 'import json, sys
value = json.loads(sys.argv[1])
print(json.dumps(eval(sys.argv[2], {"v": value}), sort_keys=True))' "$1" "$2" > "$3"
}

collect() { # ID ACTION_ID — poll action_result until done/failed
  local id="$1" aid="$2" tries=0 resp status
  while [ "$tries" -lt 240 ]; do
    resp=$(call_tool "$id" action_result "{\"action_id\":\"$aid\"}")
    status=$(json_field "$resp" "v['result']['content'][0]['json']['status']")
    case "$status" in
      done|failed) printf '%s' "$resp"; return 0 ;;
    esac
    tries=$((tries + 1))
    sleep 2
  done
  echo "error: timed out collecting $aid" >&2
  return 1
}

echo "== 2/6 the agent inspects (server-side rig map + live scene inventory)"
RESP=$(raw_rpc 1 initialize '{}')
json_field "$RESP" "v['result']['serverInfo']['name']" > /dev/null
RESP=$(call_tool 2 inspect_rig "{\"path\":\"$METARIG_RIG\"}")
ROLES=$(json_field "$RESP" "len(v['result']['content'][0]['json']['assignments'])")
CONF=$(json_field "$RESP" "min(a['confidence'] for a in v['result']['content'][0]['json']['assignments'])")
echo "   inspect_rig: $ROLES roles (min conf $CONF)"

"$PY" "$REPO/xtask/walk_job.py" "$TMP/walkjob" | sed 's/^/   fixture job: /'

echo "== 3/6 the agent enqueues the live-Blender actions + animates the job"
RESP=$(call_tool 3 session_status '{}')
json_field "$RESP" "v['result']['content'][0]['json']['enabled']" > /dev/null
RESP=$(call_tool 4 enqueue_action '{"kind":"inspect_scene","params":{}}')
A1=$(json_field "$RESP" "v['result']['content'][0]['json']['action_id']")
RESP=$(call_tool 5 enqueue_action "{\"kind\":\"apply_pose\",\"params\":{\"payload_path\":\"$PAYLOAD\",\"armature_name\":\"metarig\"}}")
A2=$(json_field "$RESP" "v['result']['content'][0]['json']['action_id']")
RESP=$(call_tool 6 animate_from_video "{\"rig\":\"$METARIG_RIG\",\"job_dir\":\"$TMP/walkjob\",\"hip_stabilize\":0.7}")
CANON_FRAMES=$(json_field "$RESP" "v['result']['content'][0]['json']['canonical']['frames']")
SLIDE_BEFORE=$(json_field "$RESP" "v['result']['content'][0]['json']['canonical']['foot_slide_u_before']")
SLIDE_AFTER=$(json_field "$RESP" "v['result']['content'][0]['json']['canonical']['foot_slide_u_after']")
BAKE_STATUS=$(json_field "$RESP" "v['result']['content'][0]['json']['bake']['status']")
echo "   animate_from_video: $CANON_FRAMES frames, slide $SLIDE_BEFORE -> $SLIDE_AFTER u (bake: $BAKE_STATUS)"
RESP=$(call_tool 7 enqueue_action "{\"kind\":\"bake_action\",\"params\":{\"job_dir\":\"$TMP/walkjob\",\"armature_name\":\"metarig\"}}")
A3=$(json_field "$RESP" "v['result']['content'][0]['json']['action_id']")
RESP=$(call_tool 8 enqueue_action "{\"kind\":\"render_turntable\",\"params\":{\"out_dir\":\"$TMP/turntable\",\"armature_name\":\"metarig\",\"frames\":35,\"width\":640,\"height\":480,\"prefix\":\"agent\"}}")
A4=$(json_field "$RESP" "v['result']['content'][0]['json']['action_id']")

echo "== 4/6 live Blender (headless) connects and executes everything"
"$BLENDER" -b --python "$REPO/xtask/agent_demo_blender.py" -- "$PORT" "$TOKEN" "$METARIG" \
  > "$TMP/blender.log" 2>&1 || { cat "$TMP/blender.log" >&2; exit 1; }
grep "RM_AGENT_DEMO OK" "$TMP/blender.log" | sed 's/^/   /'
grep "RM_AGENT_DEMO OK" "$TMP/blender.log" > /dev/null

echo "== 5/6 the agent collects the structured results"
R1=$(collect 9 "$A1")
R2=$(collect 10 "$A2")
R3=$(collect 11 "$A3")
R4=$(collect 12 "$A4")
SCENE_N=$(json_field "$R1" "v['result']['content'][0]['json']['report']['count']")
APPLY_WORST=$(json_field "$R2" "v['result']['content'][0]['json']['report']['worst_deg']")
APPLY_N=$(json_field "$R2" "len(v['result']['content'][0]['json']['report']['applied'])")
REEVAL=$(json_field "$R3" "v['result']['content'][0]['json']['report']['reeval_worst_deg']")
LOCKED=$(json_field "$R3" "v['result']['content'][0]['json']['report']['locked_frames']")
KEYS=$(json_field "$R3" "v['result']['content'][0]['json']['report']['keys']")
LOCKDEV=$(json_field "$R3" "v['result']['content'][0]['json']['report']['reeval_lock_dev_deg']")
INTERVALS=$(json_field "$R3" "v['result']['content'][0]['json']['report']['contacts']['intervals']")
RENDERED=$(json_field "$R4" "v['result']['content'][0]['json']['report']['frames_rendered']")
PLAYED=$(json_field "$R4" "v['result']['content'][0]['json']['report']['played_action']")
json_value "$R4" "v['result']['content'][0]['json']['report']" "$TMP/turn_manifest.json"
if [ "$PLAYED" != "True" ] || [ "$RENDERED" != "35" ]; then
  printf 'error: turntable report unexpected, played=%s rendered=%s\n' "$PLAYED" "$RENDERED" >&2
  exit 1
fi
REEVAL_OK=$(json_field "$R3" "v['result']['content'][0]['json']['report']['reeval_worst_deg'] <= 0.5")
if [ "$REEVAL_OK" != "True" ]; then
  printf 'error: bake re-eval %s deg exceeds the 0.5 deg bar, refusing to ship media\n' "$REEVAL" >&2
  exit 1
fi
printf '   scene=%s armatures; apply worst %s deg over %s bones\n' "$SCENE_N" "$APPLY_WORST" "$APPLY_N"
printf '   bake: keys=%s locked=%s frames; re-eval %s deg; lock dev %s deg; %s contact intervals\n' "$KEYS" "$LOCKED" "$REEVAL" "$LOCKDEV" "$INTERVALS"

echo "== 6/6 assembling the launch GIF + writing the docs block"
# Values travel via environment (not argv interpolation); paths relative to
# the repo root.
export DEMO_ROLES="$ROLES" DEMO_MIN_CONF="$CONF"
export DEMO_CANON_FRAMES="$CANON_FRAMES" DEMO_SLIDE_BEFORE="$SLIDE_BEFORE"
export DEMO_SLIDE_AFTER="$SLIDE_AFTER" DEMO_APPLY_WORST="$APPLY_WORST"
export DEMO_APPLY_BONES="$APPLY_N" DEMO_BAKE_KEYS="$KEYS"
export DEMO_BAKE_LOCKED="$LOCKED" DEMO_BAKE_REEVAL="$REEVAL"
export DEMO_BAKE_LOCKDEV="$LOCKDEV" DEMO_BAKE_INTERVALS="$INTERVALS"
export DEMO_RENDERED="$RENDERED" DEMO_GIF="docs/media/agent_turntable.gif"
export DEMO_TRANSCRIPT_SRC="$TRANSCRIPT" DEMO_MANIFEST_SRC="$TMP/turn_manifest.json"
cd "$REPO"
"$PY" xtask/assemble_walk.py \
  --cell "agent-driven turntable (SYNTHETIC walk)=$TMP/turn_manifest.json" \
  --out docs/media/agent_turntable.gif \
  --fps 10 --cell-height 360
"$PY" xtask/agent_demo_docs.py

echo ""
echo "P3-7 AGENT DEMO: PASS — docs/media/agent_turntable.gif + docs/AGENT_DEMO.md"
