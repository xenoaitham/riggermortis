#!/usr/bin/env bash
# P2-1: extract numbered still frames from a video (the DECODE side of the
# video pipeline — lives in shell glue per D-009; core never spawns).
# Output paths are confined: <out_dir> must already exist or be created under
# the current directory; ".." and empty names are refused.
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "usage: $0 <video> <out_dir> [fps]" >&2
  echo "  extracts PNG frames named frame_000001.png ... at [fps] (default: source fps)" >&2
  exit 64
fi

VIDEO=$1
OUT_DIR=$2
FPS=${3:-}

case "$OUT_DIR" in
  ""|..|*..*|/*) echo "refusing out_dir '$OUT_DIR' (must be a relative, existing-or-creatable subdir)" >&2; exit 64 ;;
esac
if [ ! -f "$VIDEO" ]; then
  echo "video not found: $VIDEO" >&2
  exit 66
fi

mkdir -p "$OUT_DIR"

if [ -n "$FPS" ]; then
  ffmpeg -hide_banner -loglevel error -i "$VIDEO" -vf "fps=$FPS" "$OUT_DIR/frame_%06d.png"
else
  ffmpeg -hide_banner -loglevel error -i "$VIDEO" "$OUT_DIR/frame_%06d.png"
fi

COUNT=$(find "$OUT_DIR" -maxdepth 1 -name 'frame_*.png' | wc -l)
echo "extracted $COUNT frame(s) into $OUT_DIR"
