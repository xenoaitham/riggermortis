#!/usr/bin/env bash
# P7-6 launch cut (partial): the 60-second video assembled ONLY from footage
# the pipeline generates today — docs/LAUNCH.md § 5 is the source of record
# for every shot's timing, VO intent, and footage mapping.
#
#   bash xtask/launch_cut.sh [--recapture-gate]
#
# Output: docs/media/launch_cut.mp4 (1280x720 @ 30fps, H.264, silent — the
# VO is the author's read at publish time, music the author's choice; LAUNCH.md
# production notes put neither on the pipeline's claim surface).
#
# Honesty rules honored here:
# - NO live-camera footage exists and the cut does not pretend otherwise
#   (LAUNCH.md: live mode appears only after P5-4 ships — the reserved 8th
#   shot; until then shot 6's lower-third carries the pending label verbatim).
# - Shot 6 typesets the REAL tail of a REAL `make gate` run (cached at
#   out/launch_cut/gate_capture.log; --recapture-gate re-runs the battery).
#   The text comes from the log file — never hand-typed, never edited.
# - Nothing staged: every image/GIF is a committed pipeline output the
#   media-guard pins; ui_screenshot.png is the genuine S16 windowed capture.
# - Assembly is shell-glue ffmpeg (D-009: spawns live in xtask/*.sh); the
#   ffprobe parse-back gates duration/resolution/fps/frames before the media
#   ships, and per-shot stills are extracted for the human visual check.
# - Overlay text goes through drawtext textfile= (no shell/ffmpeg escaping
#   surface); fonts are the box's DejaVu (the cut is a LOCAL pipeline output
#   like the manga media — CI pins the committed mp4 via media-guard).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO/out/launch_cut"
FINAL="$REPO/docs/media/launch_cut.mp4"
FONT_MONO="/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W=1280; H=720; FPS=30
RECAPTURE=0
[ "${1:-}" = "--recapture-gate" ] && RECAPTURE=1

mkdir -p "$OUT"
cd "$REPO"

for f in docs/media/ui_screenshot.png docs/media/boom.gif docs/media/walk_3rigs.gif \
         docs/media/walk_lock_metarig.gif docs/media/agent_turntable.gif \
         docs/manga/hero_3styles.png docs/manga/page_01.png docs/manga/page_02.png \
         docs/manga/page_03.png; do
  [ -f "$f" ] || { echo "missing shot asset: $f (regen per LAUNCH.md production notes)" >&2; exit 1; }
done
[ -f "$FONT_MONO" ] && [ -f "$FONT_BOLD" ] || { echo "missing DejaVu fonts for the text overlays" >&2; exit 1; }
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || { echo "ffmpeg/ffprobe required" >&2; exit 1; }

# -- shot 6 source text: the real tail of a real gate run ---------------------
GATE_LOG="$OUT/gate_capture.log"
if [ "$RECAPTURE" -eq 1 ] || [ ! -s "$GATE_LOG" ]; then
  echo "== capturing a REAL gate run for shot 6 (full battery; ~5 min)"
  make gate > "$GATE_LOG" 2>&1
fi
grep -q "PHASE 0 GATE: PASS" "$GATE_LOG" || {
  echo "gate log has no PHASE 0 GATE: PASS — re-run with --recapture-gate" >&2
  exit 1
}
# page 1 = the run's own step lines (real output), page 2 = the closing PASS
grep -E "PHASE 0 (BLENDER GATE|GATE): PASS|passed|All checks passed" "$GATE_LOG" \
  | tail -n 4 > "$OUT/gate_page1.txt"
printf 'PHASE 0 GATE: PASS' > "$OUT/gate_page2.txt"

# -- helpers -------------------------------------------------------------------
# still_segment SRC SECS OUT [TEXTFILE] [ZOOM_TARGET]
# - no zoom: loop the still, scale/pad to 720p, optional textfile overlay
# - zoom: single-frame input, 2x upscale then zoompan push-in 1.0->Z (the
#   LAUNCH.md shot-3 note: a crop/zoom of the committed capture, not a re-render)
still_segment () {
  local src="$1" secs="$2" out="$3" textfile="${4:-}" zoom="${5:-1.0}"
  local base="scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x101014,setsar=1,fps=${FPS}"
  local text=""
  [ -n "$textfile" ] && text=",drawtext=fontfile=${FONT_MONO}:textfile=${textfile}:fontsize=24:fontcolor=white:box=1:boxcolor=0x101014B4:boxborderw=10:x=24:y=h-text_h-24"
  if [ "$zoom" = "1.0" ]; then
    ffmpeg -hide_banner -loglevel error -y -loop 1 -t "$secs" -i "$src" \
      -vf "$base$text" -r "$FPS" -t "$secs" \
      -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$out"
  else
    local frames=$(( secs * FPS ))
    ffmpeg -hide_banner -loglevel error -y -i "$src" \
      -vf "scale=${W}*2:${H}*2:force_original_aspect_ratio=decrease,pad=${W}*2:${H}*2:(ow-iw)/2:(oh-ih)/2:color=0x101014,zoompan=z='1+(${zoom}-1)*on/${frames}':x='(iw-ow/2)/2':y='(ih-oh/2)/2':d=${frames}:s=${W}x${H}:fps=${FPS},setsar=1$text" \
      -r "$FPS" -t "$secs" \
      -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$out"
  fi
}

# gif_segment SRC.SECS OUT [TEXTFILE] — loop the gif to fill the shot
gif_segment () {
  local src="$1" secs="$2" out="$3" textfile="${4:-}"
  local text=""
  [ -n "$textfile" ] && text=",drawtext=fontfile=${FONT_MONO}:textfile=${textfile}:fontsize=24:fontcolor=white:box=1:boxcolor=0x101014B4:boxborderw=10:x=24:y=h-text_h-24"
  ffmpeg -hide_banner -loglevel error -y -stream_loop -1 -t "$secs" -i "$src" \
    -vf "scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x101014,setsar=1,fps=${FPS}$text" \
    -r "$FPS" -t "$secs" \
    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$out"
}

# centered text segment (title/end cards): TEXTFILE SIZE Y
card_segment () {
  local src="$1" secs="$2" out="$3" textfile="$4" size="$5" y="$6"
  ffmpeg -hide_banner -loglevel error -y -loop 1 -t "$secs" -i "$src" \
    -vf "scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x101014,setsar=1,fps=${FPS},drawtext=fontfile=${FONT_BOLD}:textfile=${textfile}:fontsize=${size}:fontcolor=white:x=(w-text_w)/2:y=${y}:box=1:boxcolor=0x101014D0:boxborderw=18" \
    -r "$FPS" -t "$secs" \
    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$out"
}

echo "== shot text files (overlay copy comes verbatim from the LAUNCH.md script)"
cat > "$OUT/t1_title.txt" << 'EOF'
riggermortis
EOF
cat > "$OUT/t1_sub.txt" << 'EOF'
local, rig-agnostic posing + animation — no cloud, no uploads
EOF
cat > "$OUT/t2.txt" << 'EOF'
a photo becomes a pose — on your rig (<=0.5 deg self-check gates this)
EOF
cat > "$OUT/t3a.txt" << 'EOF'
single-view solve: documented limits
EOF
cat > "$OUT/t3b.txt" << 'EOF'
arms get a one-click flip review — benchmark published 0/10 auto-usable
EOF
cat > "$OUT/t4a.txt" << 'EOF'
video -> animation on three rigs — SYNTHETIC test motion (labeled honestly)
EOF
cat > "$OUT/t4b.txt" << 'EOF'
foot-slide inside a plant: >20x reduction on the test rigs
EOF
cat > "$OUT/t5.txt" << 'EOF'
your coding agent drives real Blender via MCP — transcript committed (SYNTHETIC)
EOF
cat > "$OUT/t6_lower.txt" << 'EOF'
live mode: measured on replayed frames — real-camera number pending
EOF
cat > "$OUT/t7_flip.txt" << 'EOF'
toon styles + wordless manga — MIT, all local
EOF
cat > "$OUT/t7_end.txt" << 'EOF'
github.com/xenoaitham/riggermortis
EOF

echo "== shot 1: title card over the genuine S16 windowed capture (0:00-0:06) 6s"
still_segment docs/media/ui_screenshot.png 6 "$OUT/s1_base.mp4"
ffmpeg -hide_banner -loglevel error -y -i "$OUT/s1_base.mp4" -vf "
drawtext=fontfile=${FONT_BOLD}:textfile=$OUT/t1_title.txt:fontsize=72:x=(w-text_w)/2:y=110:box=1:boxcolor=0x101014CC:boxborderw=18,
drawtext=fontfile=${FONT_MONO}:textfile=$OUT/t1_sub.txt:fontsize=26:x=(w-text_w)/2:y=220:box=1:boxcolor=0x101014B4:boxborderw=10" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$OUT/s1.mp4"

echo "== shot 2: the BOOM turntable, rest -> posed (0:06-0:14) 8s"
gif_segment docs/media/boom.gif 8 "$OUT/s2.mp4" "$OUT/t2.txt"

echo "== shot 3: honest limits — slow push-in on the review overlay (0:14-0:24) 10s"
still_segment docs/media/ui_screenshot.png 10 "$OUT/s3_base.mp4" "" 1.15
# captions live TOP-left: the zoomed capture's bottom band is Blender UI chrome
ffmpeg -hide_banner -loglevel error -y -i "$OUT/s3_base.mp4" -vf "
drawtext=fontfile=${FONT_MONO}:textfile=$OUT/t3a.txt:fontsize=26:x=24:y=24:box=1:boxcolor=0x101014B4:boxborderw=10,
drawtext=fontfile=${FONT_MONO}:textfile=$OUT/t3b.txt:fontsize=21:x=24:y=80:box=1:boxcolor=0x101014B4:boxborderw=10" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$OUT/s3.mp4"

echo "== shot 4: video retarget + foot lock, synthetic label verbatim (0:24-0:34) 10s"
gif_segment docs/media/walk_3rigs.gif 5 "$OUT/s4a.mp4" "$OUT/t4a.txt"
gif_segment docs/media/walk_lock_metarig.gif 5 "$OUT/s4b.mp4" "$OUT/t4b.txt"

echo "== shot 5: the MCP agent demo (0:34-0:44) 10s"
gif_segment docs/media/agent_turntable.gif 10 "$OUT/s5.mp4" "$OUT/t5.txt"

echo "== shot 6: the REAL gate tail + the pending-live lower-third (0:44-0:52) 8s"
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=c=0x0C0C10:s=${W}x${H}:d=8:r=${FPS}" -vf "
drawtext=fontfile=${FONT_MONO}:textfile=$OUT/gate_page1.txt:fontsize=20:x=40:y=110:fontcolor=0x9FE39F:line_spacing=14,
drawtext=fontfile=${FONT_MONO}:textfile=$OUT/gate_page2.txt:fontsize=26:x=40:y=330:fontcolor=0x4FE34F,
drawtext=fontfile=${FONT_MONO}:text='CI audit hook: zero network calls in default use':fontsize=24:x=40:y=60:fontcolor=white,
drawtext=fontfile=${FONT_MONO}:textfile=$OUT/t6_lower.txt:fontsize=22:x=(w-text_w)/2:y=h-64:fontcolor=white:box=1:boxcolor=0x101014D0:boxborderw=12,
format=yuv420p" -t 8 -r "$FPS" -c:v libx264 -preset medium -crf 20 "$OUT/s6.mp4"

echo "== shot 7: styles + manga flip + end card (0:52-1:00) 8s"
still_segment docs/manga/hero_3styles.png 2 "$OUT/s7a_base.mp4"
ffmpeg -hide_banner -loglevel error -y -i "$OUT/s7a_base.mp4" -vf "
drawtext=fontfile=${FONT_MONO}:textfile=$OUT/t7_flip.txt:fontsize=24:x=24:y=h-text_h-24:box=1:boxcolor=0x101014B4:boxborderw=10" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$OUT/s7a.mp4"
still_segment docs/manga/page_01.png 1 "$OUT/s7b.mp4"
still_segment docs/manga/page_02.png 1 "$OUT/s7c.mp4"
still_segment docs/manga/page_03.png 1 "$OUT/s7d.mp4"
card_segment docs/manga/hero_3styles.png 3 "$OUT/s7e.mp4" "$OUT/t7_end.txt" 34 "(h-text_h)/2"

echo "== concat + parse-back"
: > "$OUT/concat.txt"
for s in s1 s2 s3 s4a s4b s5 s6 s7a s7b s7c s7d s7e; do
  echo "file '$OUT/$s.mp4'" >> "$OUT/concat.txt"
done
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$OUT/concat.txt" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -movflags +faststart "$FINAL"

DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$FINAL")
RES=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$FINAL")
FPS_GOT=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=nw=1:nk=1 "$FINAL")
FRAMES=$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of default=nw=1:nk=1 "$FINAL")
echo "RM_LAUNCH CUT: duration=${DUR}s res=${RES} fps=${FPS_GOT} frames=${FRAMES} (expect 60.0s 1280x720 30fps 1800 frames)"

export DUR RES FPS_GOT FRAMES
python3 - << 'PYEOF'
import os, sys
dur = float(os.environ["DUR"]); res = os.environ["RES"]
fps = os.environ["FPS_GOT"]; frames = int(os.environ["FRAMES"])
ok = abs(dur - 60.0) <= 0.5 and res == "1280,720" and fps == "30/1" and frames == 1800
print(f"RM_LAUNCH PARSE: {'PASS' if ok else 'FAIL'} (60.0s +/-0.5, 1280x720, 30fps, 1800 frames)")
sys.exit(0 if ok else 1)
PYEOF

echo "== visual-check stills (one per shot) at $OUT/check_*.png"
ffmpeg -hide_banner -loglevel error -y -ss 3  -i "$FINAL" -frames:v 1 "$OUT/check_shot1.png"
ffmpeg -hide_banner -loglevel error -y -ss 10 -i "$FINAL" -frames:v 1 "$OUT/check_shot2.png"
ffmpeg -hide_banner -loglevel error -y -ss 19 -i "$FINAL" -frames:v 1 "$OUT/check_shot3.png"
ffmpeg -hide_banner -loglevel error -y -ss 31 -i "$FINAL" -frames:v 1 "$OUT/check_shot4.png"
ffmpeg -hide_banner -loglevel error -y -ss 40 -i "$FINAL" -frames:v 1 "$OUT/check_shot5.png"
ffmpeg -hide_banner -loglevel error -y -ss 48 -i "$FINAL" -frames:v 1 "$OUT/check_shot6.png"
ffmpeg -hide_banner -loglevel error -y -ss 58 -i "$FINAL" -frames:v 1 "$OUT/check_shot7.png"
echo "RM_LAUNCH CUT: WROTE $FINAL ($(stat -c%s "$FINAL") bytes) — run the visual check on out/launch_cut/check_*.png before shipping"
