#!/usr/bin/env bash
# P5-2/P5-3 live-consumer gate: a REAL `rigpose live` side process + a REAL
# Blender running the add-on's stream driver (xtask/live_gate.py inside).
#
# 1. starts headless Blender with the gate rig registered and the add-on's
#    live driver ARMED on stream A (run A: poses, smoothing OFF — the
#    P5-2 control)
# 2. waits for the RM_LIVE READY handshake, then spawns the REAL producer —
#    the production spawn path, from shell glue, never from a .py (D-009)
# 3. run A asserts: every replay frame applies through the REAL P1-6 path at
#    the 0.5-deg bar class, zero misses; per-line RM_LIVE BUDGET rows
#    (age_ms + poll lag + apply cost = the REPLAY end-to-end number)
# 4. the producer exits after the replay dir is exhausted; the driver must
#    flip to STALE and say so (RM_LIVE STALE)
# 5. run B (RM_LIVE READY-B handshake): a forced-all-miss stream
#    (--conf-floor above any real body conf) must apply NOTHING and leave
#    the pose bones byte-unchanged (RM_LIVE MISS-KEEP)
# 6. runs J1/J2 (gate-fed, no producer): the P5-3 smoothing sweep — a
#    synthetic stream built from run A's first REAL payload line with
#    deterministic two-tone jitter; OFF is the control curve, ON must cut
#    the applied-curve variance >= 4x (the P2-2 bar), track the mean within
#    the amplitude, and hold the 0.5-deg bar per line (RM_LIVE SMOOTH)
# 7. run F (gate-fed): sustained silence fires the failsafe EDGE, the rig
#    lands byte-at-REST, the readout says FAILSAFE; a continuation line
#    applies, clears the latch, and passes the reset smoother exactly
#    (RM_LIVE FAILSAFE / FAILSAFE-RECOVERY)
#
# Honest scope: REPLAY frames + a SYNTHETIC jitter fixture, not a camera —
# /dev/video0 delivered no frames in S17/S18/S19 (DroidCam silent); the live
# capture->apply number and the Phase-5 <100 ms mid-laptop gate stay
# UNCLAIMED, and the smoothing defaults are untuned D-008 starting points.
# Missing prereqs (models/frames/rig/CLI) answer
# `RM_LIVE GATE: SKIPPED (...)` — grep-tested like every gate, never a
# silent pass.
#
# Run: make live-verify   (or: BLENDER=... PY=... RIGPOSE=... bash xtask/live_verify.sh)
set -euo pipefail

BLENDER=${BLENDER:-blender}
PY=${PY:-python3}
RIGPOSE=${RIGPOSE:-rigpose}
REPO=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
PROD_A=""
PROD_B=""
BL_PID=""
cleanup() {
  [ -n "$BL_PID" ] && kill "$BL_PID" 2>/dev/null || true
  [ -n "$PROD_A" ] && kill "$PROD_A" 2>/dev/null || true
  [ -n "$PROD_B" ] && kill "$PROD_B" 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

FRAMES=${RM_LIVE_FRAMES:-$REPO/out/live_probe/smoke_frames}
RIG=${RM_LIVE_RIG:-$REPO/out/real_rigs/metarig.rig.json}

skip() { echo "RM_LIVE GATE: SKIPPED ($1)"; exit 0; }

command -v "$BLENDER" > /dev/null 2>&1 || skip "Blender not found (hint: BLENDER=/path/to/blender)"
command -v "$RIGPOSE" > /dev/null 2>&1 || skip "rigpose CLI not found (hint: pip install -e core[inference])"
[ -d "$FRAMES" ] || skip "replay frames dir missing: $FRAMES (git-ignored; see docs/LIVE.md)"
ls "$FRAMES" | grep -qiE '\.(png|jpg|jpeg|webp|bmp)$' || skip "no frame images in $FRAMES"
[ -f "$RIG" ] || skip "rig JSON missing: $RIG (hint: bash xtask/export_fixture_rigs.py)"
RM_REPO="$REPO" "$PY" -c "
import os, sys
sys.path.insert(0, os.path.join(os.environ['RM_REPO'], 'core', 'src'))
from riggermortis.inference import models
from riggermortis.inference.dwpose import DET_MODEL, POSE_MODEL
for m in (DET_MODEL, POSE_MODEL):
    models.verify_model(m)
" || skip "pinned models missing (hint: rigpose models download all)"

STREAM_A="$TMP/stream_a.jsonl"
STREAM_B="$TMP/stream_b.jsonl"

echo "== 1/4 starting headless Blender (gate rig + armed live driver)"
"$BLENDER" -b --python "$REPO/xtask/live_gate.py" -- "$STREAM_A" "$STREAM_B" "$FRAMES" \
  > "$TMP/blender.log" 2>&1 &
BL_PID=$!

wait_for() { # GREP LOG TIMEOUT_S — Blender-side handshake with an early-exit check
  local ticks=$(( $3 * 10 ))
  local i=0
  while [ "$i" -lt "$ticks" ]; do
    grep -q "$1" "$2" && return 0
    kill -0 "$BL_PID" 2>/dev/null || {
      echo "error: Blender exited while waiting for '$1':" >&2
      tail -40 "$2" >&2
      exit 1
    }
    sleep 0.1
    i=$((i + 1))
  done
  echo "error: timed out waiting for '$1'" >&2
  tail -40 "$2" >&2
  exit 1
}
wait_for "RM_LIVE READY" "$TMP/blender.log" 60

echo "== 2/4 spawning the REAL side process (run A: tracked cadence, poses)"
# --idle-timeout: a replay dir exhausts; the producer ends like a stream going
# quiet (the live default waits forever, the right behavior for a camera)
"$RIGPOSE" live "$FRAMES" "$RIG" --out "$STREAM_A" --detect-every 3 --idle-timeout 2 \
  > "$TMP/prod_a.log" 2>&1 &
PROD_A=$!
# the side process exhausts the replay dir and exits on its own (idle timeout
# would be the live-mode behavior; a list of files just ends)
ticks=0
until ! kill -0 "$PROD_A" 2>/dev/null; do
  if [ "$ticks" -ge 1200 ]; then
    echo "error: producer A did not exit in 120 s" >&2
    tail -20 "$TMP/prod_a.log" >&2
    exit 1
  fi
  sleep 0.1
  ticks=$((ticks + 1))
done
grep -q "RM_LIVE STALE" "$TMP/blender.log" || wait_for "RM_LIVE STALE" "$TMP/blender.log" 30

wait_for "RM_LIVE READY-B" "$TMP/blender.log" 30
echo "== 3/4 spawning the REAL side process (run B: forced all-miss stream)"
"$RIGPOSE" live "$FRAMES" "$RIG" --out "$STREAM_B" --detect-every 1 --conf-floor 0.95 --idle-timeout 2 \
  > "$TMP/prod_b.log" 2>&1 &
PROD_B=$!

echo "== 4/4 collecting the gate verdict (sweep + failsafe runs are gate-fed, inside Blender)"
BL_RC=0
wait "$BL_PID" 2> /dev/null || BL_RC=$?
BL_PID=""
# the second producer ends on its own; give it a moment, then the trap reaps it
ticks=0
while kill -0 "$PROD_B" 2>/dev/null && [ "$ticks" -lt 1200 ]; do
  sleep 0.1
  ticks=$((ticks + 1))
done

grep "RM_LIVE" "$TMP/blender.log" || true
if [ "$BL_RC" -ne 0 ]; then
  echo "error: gate Blender exited $BL_RC" >&2
  tail -40 "$TMP/blender.log" >&2
  exit "$BL_RC"
fi
grep -q "RM_LIVE GATE: PASS" "$TMP/blender.log" || {
  echo "error: gate did not reach PASS" >&2
  tail -40 "$TMP/blender.log" >&2
  exit 1
}
grep -q "RM_LIVE SMOOTH PASS" "$TMP/blender.log" || {
  echo "error: smoothing sweep did not pass" >&2
  exit 1
}
grep -q "RM_LIVE FAILSAFE-RECOVERY" "$TMP/blender.log" || {
  echo "error: failsafe/recovery run did not complete" >&2
  exit 1
}
echo ""
echo "P5-3 LIVE CONSUMER GATE: PASS (replay/synthetic-labeled; the live number stays unclaimed)"
