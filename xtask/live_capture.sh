#!/usr/bin/env bash
# P5-1: capture-device frame source — ffmpeg v4l2 -> numbered PNG frames into
# a watched directory (the same contract extract_frames.sh feeds). Lives in
# shell glue per D-009: core never opens a device, never spawns.
#
# HONEST STATUS (S17): UNTESTED against a streaming device. This box's only
# capture node is a DroidCam v4l2loopback (/dev/video0) that delivered no
# frames while the phone side was not streaming (see docs/LIVE.md). The
# replay path (extract_frames.sh -> rigpose live) is the verified path.
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
  echo "usage: $0 <out_dir> [fps] [device]" >&2
  echo "  writes frame_%06d.png into <out_dir> from a v4l2 device" >&2
  echo "  (default fps 15, device /dev/video0; stop with Ctrl-C)" >&2
  exit 64
fi

OUT_DIR=$1
FPS=${2:-15}
DEVICE=${3:-/dev/video0}

case "$OUT_DIR" in
  ""|..|*..*|/*) echo "refusing out_dir '$OUT_DIR' (must be a relative, existing-or-creatable subdir)" >&2; exit 64 ;;
esac
if [ ! -e "$DEVICE" ]; then
  echo "capture device not found: $DEVICE" >&2
  echo "(hint: check the device node; for DroidCam the phone app must be streaming)" >&2
  exit 66
fi

mkdir -p "$OUT_DIR"

# -fflags nobuffer keeps the stream low-latency; frames are named to the
# exact contract DirectoryFrameSource + extract_frames.sh share.
ffmpeg -hide_banner -loglevel error \
  -fflags nobuffer -f v4l2 -video_size 640x480 -framerate "$FPS" -i "$DEVICE" \
  -vf "fps=$FPS" "$OUT_DIR/frame_%06d.png"

COUNT=$(find "$OUT_DIR" -maxdepth 1 -name 'frame_*.png' | wc -l)
echo "captured $COUNT frame(s) into $OUT_DIR"
