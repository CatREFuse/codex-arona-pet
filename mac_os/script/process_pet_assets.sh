#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
CHARACTER_DIR="$REPO_ROOT/shared/Characters/plana"
MAGICK="${MAGICK:-$(command -v magick || command -v /opt/homebrew/bin/magick || command -v /usr/local/bin/magick || true)}"
TARGET_WIDTH=256
TARGET_HEIGHT=256
CONTENT_WIDTH=240
CONTENT_HEIGHT=240
FRAME_COUNT=12
FRAME_DURATION="0.1666666667"

require_magick() {
  if ! command -v "$MAGICK" >/dev/null 2>&1; then
    echo "ImageMagick not found: $MAGICK" >&2
    exit 1
  fi
}

image_size() {
  "$MAGICK" identify -format '%[width]x%[height]' "$1"
}

frame_count_for_dir() {
  find "$1" -maxdepth 1 -type f -name '[0-9][0-9].png' | wc -l | tr -d ' '
}

source_guard_width_for_state() {
  case "$1" in
    edge-pinched-left|edge-pinched-right)
      echo 12
      ;;
    edge-*-left|edge-*-right)
      echo 8
      ;;
    *)
      echo 0
      ;;
  esac
}

source_guard_fill_for_key() {
  case "$1" in
    magenta)
      echo '#ff00ff'
      ;;
    *)
      echo '#00ff00'
      ;;
  esac
}

crop_source_strip() {
  local source="$1"
  local frame_count="$2"
  local output_dir="$3"
  local state_name="$4"
  local key_color="${5:-green}"
  local guard_width
  guard_width="$(source_guard_width_for_state "$state_name")"

  local source_size source_width source_height
  source_size="$(image_size "$source")"
  source_width="${source_size%x*}"
  source_height="${source_size#*x}"

  local guard_fill
  guard_fill="$(source_guard_fill_for_key "$key_color")"

  local index
  for ((index = 0; index < frame_count; index++)); do
    local left right crop_width output
    left=$((source_width * index / frame_count))
    right=$((source_width * (index + 1) / frame_count))
    crop_width=$((right - left))
    output="$output_dir/frame-$(printf '%02d.png' "$index")"

    "$MAGICK" "$source" -crop "${crop_width}x${source_height}+${left}+0" +repage "$output"

    if [ "$guard_width" -gt 0 ]; then
      case "$state_name" in
        edge-*-right)
          if [ "$index" -gt 0 ]; then
            "$MAGICK" "$output" -fill "$guard_fill" -draw "rectangle 0,0 $((guard_width - 1)),$((source_height - 1))" "$output"
          fi
          ;;
        edge-*-left)
          if [ "$index" -lt $((frame_count - 1)) ]; then
            "$MAGICK" "$output" -fill "$guard_fill" -draw "rectangle $((crop_width - guard_width)),0 $((crop_width - 1)),$((source_height - 1))" "$output"
          fi
          ;;
      esac
    fi
  done
}

base_frame_count_for_state() {
  echo "$FRAME_COUNT"
}

edge_line_shift() {
  local frame="$1"
  local side="$2"
  local width="${3:-$TARGET_WIDTH}"
  local height="${4:-$TARGET_HEIGHT}"
  "$MAGICK" "$frame" -depth 8 RGBA:- | python3 -c '
import sys

w = int(sys.argv[1])
h = int(sys.argv[2])
side = sys.argv[3]
raw = sys.stdin.buffer.read()

if len(raw) < w * h * 4:
    print(0)
    raise SystemExit

if side == "left":
    search_range = range(0, int(w * 0.35))
    target_x = 0
else:
    search_range = range(int(w * 0.65), w)
    target_x = w - 1

best_x = None
best_count = -1
for x in search_range:
    count = 0
    for y in range(h):
        i = (y * w + x) * 4
        r, g, b, a = raw[i], raw[i + 1], raw[i + 2], raw[i + 3]
        if a > 128 and r < 35 and g < 35 and b < 35:
            count += 1
    if count > best_count:
        best_x = x
        best_count = count

if best_x is None or best_count < h * 0.35:
    print(0)
    raise SystemExit

shift = target_x - best_x
limit = max(32, int(w * 0.085))
print(shift if abs(shift) <= limit else 0)
' "$width" "$height" "$side"
}

align_edge_frame() {
  local frame="$1"
  local side="$2"
  [ -n "$side" ] || return 0

  local frame_size width height
  frame_size="$(image_size "$frame")"
  width="${frame_size%x*}"
  height="${frame_size#*x}"

  local shift
  shift="$(edge_line_shift "$frame" "$side" "$width" "$height")"
  [[ "$shift" =~ ^-?[0-9]+$ ]] || return 0
  [ "$shift" -ne 0 ] || return 0

  local geometry
  if [ "$shift" -gt 0 ]; then
    geometry="+${shift}+0"
  else
    geometry="${shift}+0"
  fi

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  "$MAGICK" -size "${width}x${height}" xc:none "$frame" \
    -geometry "$geometry" -compose over -composite \
    -define png:color-type=6 \
    "$tmp_dir/frame.png"
  mv "$tmp_dir/frame.png" "$frame"
  rm -rf "$tmp_dir"
}

remove_small_alpha_components() {
  local frame="$1"
  local width="$2"
  local height="$3"
  local min_area="$4"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  "$MAGICK" "$frame" -depth 8 RGBA:- | python3 -c '
import sys

w = int(sys.argv[1])
h = int(sys.argv[2])
min_area = int(sys.argv[3])
raw = bytearray(sys.stdin.buffer.read())
if len(raw) < w * h * 4:
    sys.stdout.buffer.write(raw)
    raise SystemExit

alpha = raw[3::4]
seen = bytearray(w * h)

for start, a in enumerate(alpha):
    if a <= 10 or seen[start]:
        continue
    queue = [start]
    seen[start] = 1
    component = []
    while queue:
        current = queue.pop()
        component.append(current)
        x = current % w
        y = current // w
        for ny in (y - 1, y, y + 1):
            if ny < 0 or ny >= h:
                continue
            row = ny * w
            for nx in (x - 1, x, x + 1):
                if nx < 0 or nx >= w or (nx == x and ny == y):
                    continue
                nxt = row + nx
                if not seen[nxt] and alpha[nxt] > 10:
                    seen[nxt] = 1
                    queue.append(nxt)
    if len(component) < min_area:
        for pixel in component:
            raw[pixel * 4 + 3] = 0

sys.stdout.buffer.write(raw)
' "$width" "$height" "$min_area" | "$MAGICK" -depth 8 -size "${width}x${height}" RGBA:- -define png:color-type=6 "$tmp_dir/frame.png"
  mv "$tmp_dir/frame.png" "$frame"
  rm -rf "$tmp_dir"
}

remove_pinched_strip_artifacts() {
  local frame="$1"
  local width="$2"
  local height="$3"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  "$MAGICK" "$frame" -depth 8 RGBA:- | python3 -c '
import sys

w = int(sys.argv[1])
h = int(sys.argv[2])
raw = bytearray(sys.stdin.buffer.read())
if len(raw) < w * h * 4:
    sys.stdout.buffer.write(raw)
    raise SystemExit

alpha = raw[3::4]
seen = bytearray(w * h)

for start, a in enumerate(alpha):
    if a <= 10 or seen[start]:
        continue
    queue = [start]
    seen[start] = 1
    component = []
    min_x = w
    max_x = 0
    min_y = h
    max_y = 0
    while queue:
        current = queue.pop()
        component.append(current)
        x = current % w
        y = current // w
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        for ny in (y - 1, y, y + 1):
            if ny < 0 or ny >= h:
                continue
            row = ny * w
            for nx in (x - 1, x, x + 1):
                if nx < 0 or nx >= w or (nx == x and ny == y):
                    continue
                nxt = row + nx
                if not seen[nxt] and alpha[nxt] > 10:
                    seen[nxt] = 1
                    queue.append(nxt)

    is_left_strip = (
        min_x < int(w * 0.16)
        and max_x < int(w * 0.23)
        and min_y > int(h * 0.35)
        and len(component) < 20000
    )
    if is_left_strip:
        for pixel in component:
            raw[pixel * 4 + 3] = 0

sys.stdout.buffer.write(raw)
' "$width" "$height" | "$MAGICK" -depth 8 -size "${width}x${height}" RGBA:- -define png:color-type=6 "$tmp_dir/frame.png"
  mv "$tmp_dir/frame.png" "$frame"
  rm -rf "$tmp_dir"
}

remove_success_strip_artifacts() {
  local frame="$1"
  local width="$2"
  local height="$3"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  "$MAGICK" "$frame" -depth 8 RGBA:- | python3 -c '
import sys

w = int(sys.argv[1])
h = int(sys.argv[2])
raw = bytearray(sys.stdin.buffer.read())
if len(raw) < w * h * 4:
    sys.stdout.buffer.write(raw)
    raise SystemExit

alpha = raw[3::4]
seen = bytearray(w * h)

for start, a in enumerate(alpha):
    if a <= 10 or seen[start]:
        continue
    queue = [start]
    seen[start] = 1
    component = []
    min_x = w
    max_x = 0
    min_y = h
    max_y = 0
    while queue:
        current = queue.pop()
        component.append(current)
        x = current % w
        y = current // w
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        for ny in (y - 1, y, y + 1):
            if ny < 0 or ny >= h:
                continue
            row = ny * w
            for nx in (x - 1, x, x + 1):
                if nx < 0 or nx >= w or (nx == x and ny == y):
                    continue
                nxt = row + nx
                if not seen[nxt] and alpha[nxt] > 10:
                    seen[nxt] = 1
                    queue.append(nxt)

    is_left_strip = (
        min_x < int(w * 0.24)
        and max_x < int(w * 0.24)
        and min_y > int(h * 0.35)
        and len(component) < 20000
    )
    if is_left_strip:
        for pixel in component:
            raw[pixel * 4 + 3] = 0

sys.stdout.buffer.write(raw)
' "$width" "$height" | "$MAGICK" -depth 8 -size "${width}x${height}" RGBA:- -define png:color-type=6 "$tmp_dir/frame.png"
  mv "$tmp_dir/frame.png" "$frame"
  rm -rf "$tmp_dir"
}

remove_edge_stray_components() {
  local frame="$1"
  local width="$2"
  local height="$3"
  local side="$4"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  "$MAGICK" "$frame" -depth 8 RGBA:- | python3 -c '
import sys

w = int(sys.argv[1])
h = int(sys.argv[2])
side = sys.argv[3]
raw = bytearray(sys.stdin.buffer.read())
if len(raw) < w * h * 4:
    sys.stdout.buffer.write(raw)
    raise SystemExit

alpha = raw[3::4]
seen = bytearray(w * h)
components = []

for start, a in enumerate(alpha):
    if a <= 10 or seen[start]:
        continue
    queue = [start]
    seen[start] = 1
    component = []
    min_x = w
    max_x = 0
    min_y = h
    max_y = 0
    while queue:
        current = queue.pop()
        component.append(current)
        x = current % w
        y = current // w
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        for ny in (y - 1, y, y + 1):
            if ny < 0 or ny >= h:
                continue
            row = ny * w
            for nx in (x - 1, x, x + 1):
                if nx < 0 or nx >= w or (nx == x and ny == y):
                    continue
                nxt = row + nx
                if not seen[nxt] and alpha[nxt] > 10:
                    seen[nxt] = 1
                    queue.append(nxt)
    components.append((component, min_x, max_x, min_y, max_y))

if not components:
    sys.stdout.buffer.write(raw)
    raise SystemExit

largest = max(len(component) for component, *_ in components)
edge_band = max(6, int(w * 0.015))

for component, min_x, max_x, min_y, max_y in components:
    touches_expected_edge = min_x <= edge_band if side == "left" else max_x >= w - 1 - edge_band
    is_primary = len(component) == largest
    if is_primary or touches_expected_edge:
        continue
    for pixel in component:
        raw[pixel * 4 + 3] = 0

sys.stdout.buffer.write(raw)
' "$width" "$height" "$side" | "$MAGICK" -depth 8 -size "${width}x${height}" RGBA:- -define png:color-type=6 "$tmp_dir/frame.png"
  mv "$tmp_dir/frame.png" "$frame"
  rm -rf "$tmp_dir"
}

remove_opposite_edge_intrusions() {
  local frame="$1"
  local width="$2"
  local height="$3"
  local side="$4"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  "$MAGICK" "$frame" -depth 8 RGBA:- | python3 -c '
import sys

w = int(sys.argv[1])
h = int(sys.argv[2])
side = sys.argv[3]
raw = bytearray(sys.stdin.buffer.read())
if len(raw) < w * h * 4:
    sys.stdout.buffer.write(raw)
    raise SystemExit

alpha = raw[3::4]
seen = bytearray(w * h)
components = []

for start, a in enumerate(alpha):
    if a <= 10 or seen[start]:
        continue
    queue = [start]
    seen[start] = 1
    component = []
    min_x = w
    max_x = 0
    min_y = h
    max_y = 0
    while queue:
        current = queue.pop()
        component.append(current)
        x = current % w
        y = current // w
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        for ny in (y - 1, y, y + 1):
            if ny < 0 or ny >= h:
                continue
            row = ny * w
            for nx in (x - 1, x, x + 1):
                if nx < 0 or nx >= w or (nx == x and ny == y):
                    continue
                nxt = row + nx
                if not seen[nxt] and alpha[nxt] > 10:
                    seen[nxt] = 1
                    queue.append(nxt)
    components.append((component, min_x, max_x, min_y, max_y))

if not components:
    sys.stdout.buffer.write(raw)
    raise SystemExit

largest = max(len(component) for component, *_ in components)
area_limit = int(w * h * 0.018)

for component, min_x, max_x, min_y, max_y in components:
    if len(component) == largest:
        continue
    if side == "right":
        intrudes = max_x < int(w * 0.43) and len(component) < area_limit
    else:
        intrudes = min_x > int(w * 0.57) and len(component) < area_limit
    if not intrudes:
        continue
    for pixel in component:
        raw[pixel * 4 + 3] = 0

sys.stdout.buffer.write(raw)
' "$width" "$height" "$side" | "$MAGICK" -depth 8 -size "${width}x${height}" RGBA:- -define png:color-type=6 "$tmp_dir/frame.png"
  mv "$tmp_dir/frame.png" "$frame"
  rm -rf "$tmp_dir"
}

apply_edge_boundary_line() {
  local frame="$1"
  local side="$2"
  [ -n "$side" ] || return 0

  local draw
  if [ "$side" = "left" ]; then
    draw="rectangle 0,0 3,255"
  else
    draw="rectangle 252,0 255,255"
  fi

  "$MAGICK" "$frame" \
    -fill '#111111' -draw "$draw" \
    -define png:color-type=6 \
    "$frame"
}

key_source_strip() {
  local state_dir="$1"
  local source="${2:-$state_dir/source-strip-chroma.png}"
  local key_color="${3:-green}"
  local state_name
  state_name="$(basename "$state_dir")"
  local frame_count
  frame_count="$(base_frame_count_for_state "$state_name")"
  [ "$frame_count" -gt 0 ] || return 0

  local extent_gravity="Center"
  local edge_side=""
  local output_width="$TARGET_WIDTH"
  local output_height="$TARGET_HEIGHT"
  local resize_geometry="${CONTENT_WIDTH}x${CONTENT_HEIGHT}"
  case "$state_name" in
    edge-*-left)
      extent_gravity="West"
      edge_side="left"
      ;;
    edge-*-right)
      extent_gravity="East"
      edge_side="right"
      ;;
  esac

  local tmp_dir
  tmp_dir="$(mktemp -d)"

  rm -f "$state_dir"/[0-9][0-9].png
  crop_source_strip "$source" "$frame_count" "$tmp_dir" "$state_name" "$key_color"

  local index=0
  local crop
  for crop in "$tmp_dir"/frame-*.png; do
    local output
    local input="$crop"
    output="$state_dir/$(printf '%02d.png' "$index")"
    if [ "$(basename "$state_dir")" = "carried" ]; then
      input="$tmp_dir/shaved-$(printf '%02d.png' "$index")"
      "$MAGICK" "$crop" -shave 26x0 "$input"
    fi
    if [ "$key_color" = "magenta" ]; then
      "$MAGICK" "$input" \
        -alpha set \
        -channel A -fx '((r>0.35)*(b>0.35)*(g<0.55)) ? 1-min(1,max(0,(((r<b?r:b)-g-0.08)/0.18))) : 1' +channel \
        -channel A -morphology Close Disk:1 -blur 0x0.35 -level 4%,98% +channel \
        -channel R -fx '((r>0.45)*(b>0.45)*(g<0.55)) ? min(r,(g+b)/2+0.02) : r' +channel \
        -channel B -fx '((r>0.45)*(b>0.45)*(g<0.55)) ? min(b,(r+g)/2+0.02) : b' +channel \
        -trim +repage \
        -filter Lanczos -resize "$resize_geometry" \
        -background none -gravity "$extent_gravity" -extent "${output_width}x${output_height}" \
        -define png:color-type=6 \
        "$output"
    else
      "$MAGICK" "$input" \
        -alpha set \
        -channel A -fx 'g>0.25 ? 1-min(1,max(0,(g-(r>b?r:b)-0.03)/0.15)) : 1' +channel \
        -channel A -morphology Close Disk:1 -blur 0x0.35 -level 4%,98% +channel \
        -channel G -fx 'g>(r>b?r:b)+0.02 ? min(g,(r+b)/2+0.02) : g' +channel \
        -trim +repage \
        -filter Lanczos -resize "$resize_geometry" \
        -background none -gravity "$extent_gravity" -extent "${output_width}x${output_height}" \
        -define png:color-type=6 \
        "$output"
    fi
    case "$state_name" in
      coding)
        remove_small_alpha_components "$output" "$output_width" "$output_height" 5000
        ;;
      pinched|edge-pinched-left|edge-pinched-right)
        remove_small_alpha_components "$output" "$output_width" "$output_height" 1000
        ;;
    esac
    if [ "$state_name" = "pinched" ] || [ "$state_name" = "edge-pinched-right" ]; then
      remove_pinched_strip_artifacts "$output" "$output_width" "$output_height"
    fi
    if [ "$state_name" = "success" ]; then
      remove_small_alpha_components "$output" "$output_width" "$output_height" 1000
      remove_success_strip_artifacts "$output" "$output_width" "$output_height"
    fi
    case "$state_name" in
      edge-success-left)
        remove_edge_stray_components "$output" "$output_width" "$output_height" left
        ;;
      edge-success-right)
        remove_edge_stray_components "$output" "$output_width" "$output_height" right
        ;;
      edge-pinched-left)
        remove_opposite_edge_intrusions "$output" "$output_width" "$output_height" left
        ;;
      edge-pinched-right)
        remove_opposite_edge_intrusions "$output" "$output_width" "$output_height" right
        ;;
    esac
    align_edge_frame "$output" "$edge_side"
    apply_edge_boundary_line "$output" "$edge_side"
    index=$((index + 1))
  done
  rm -rf "$tmp_dir"
}

process_alpha_source_strip() {
  local state_dir="$1"
  local source="$state_dir/source-strip-alpha.png"
  local state_name
  state_name="$(basename "$state_dir")"
  local frame_count
  frame_count="$(base_frame_count_for_state "$state_name")"
  [ "$frame_count" -gt 0 ] || return 0
  local edge_side=""
  case "$state_name" in
    edge-*-left)
      edge_side="left"
      ;;
    edge-*-right)
      edge_side="right"
      ;;
  esac

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  rm -f "$state_dir"/[0-9][0-9].png
  crop_source_strip "$source" "$frame_count" "$tmp_dir" "$state_name" none

  local index=0
  local crop
  for crop in "$tmp_dir"/frame-*.png; do
    local output
    output="$state_dir/$(printf '%02d.png' "$index")"
    "$MAGICK" "$crop" \
      -alpha on \
      -filter LanczosSharp -resize "${CONTENT_WIDTH}x${CONTENT_HEIGHT}" \
      -background none -gravity center -extent "${TARGET_WIDTH}x${TARGET_HEIGHT}" \
      -unsharp 0x0.9+0.85+0.015 \
      -define png:color-type=6 \
      "$output"
    apply_edge_boundary_line "$output" "$edge_side"
    index=$((index + 1))
  done
  rm -rf "$tmp_dir"
}

replace_frame() {
  local state="$1"
  local source_index="$2"
  local target_index="$3"
  local state_dir="$CHARACTER_DIR/extra/$state"
  local source="$state_dir/$(printf '%02d.png' "$source_index")"
  local target="$state_dir/$(printf '%02d.png' "$target_index")"

  [ -f "$source" ] && [ -f "$target" ] || return 0
  cp "$source" "$target"
}

remove_blink_frames() {
  replace_frame edge-idle-read-left 0 1
  replace_frame edge-idle-read-left 2 3
  replace_frame edge-idle-read-left 4 5
  replace_frame edge-idle-read-right 0 1
  replace_frame edge-idle-read-right 2 3
  replace_frame edge-idle-read-right 4 5

  replace_frame edge-coding-left 0 1
  replace_frame edge-coding-left 0 2
  replace_frame edge-coding-right 0 1
  replace_frame edge-coding-right 0 2

  replace_frame edge-peek-left 3 4
  replace_frame edge-peek-right 3 4

  replace_frame edge-pinched-left 1 0
  replace_frame edge-pinched-left 2 3
  replace_frame edge-pinched-left 3 4
  replace_frame edge-pinched-left 3 5
  replace_frame edge-pinched-right 2 3
  replace_frame edge-pinched-right 4 5

  replace_frame edge-success-right 6 7
}

smooth_edge_body_frames() {
  replace_frame edge-checking-right 1 0
  replace_frame edge-checking-right 4 5
  replace_frame edge-checking-right 7 6
  replace_frame edge-checking-right 10 11

  replace_frame edge-rejected-right 10 0
  replace_frame edge-rejected-right 4 5
  replace_frame edge-rejected-right 7 6
  replace_frame edge-rejected-right 10 11
}

update_manifest() {
  python3 - "$CHARACTER_DIR/openplana-character.json" "$FRAME_DURATION" <<'PY'
import json
import pathlib
import sys

manifest_path = pathlib.Path(sys.argv[1])
frame_duration = float(sys.argv[2])
non_loop_states = {
    "pinched",
    "edge-pinched-left",
    "edge-pinched-right",
    "edge-peek-left",
    "edge-peek-right",
}

data = json.loads(manifest_path.read_text(encoding="utf-8"))
for state, config in data.get("extraStates", {}).items():
    state_dir = pathlib.PurePosixPath("extra") / state
    config["framePaths"] = [str(state_dir / f"{index:02d}.png") for index in range(12)]
    config["frameDuration"] = frame_duration
    config["loop"] = state not in non_loop_states

manifest_path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
}

upscale_transparent_frame() {
  local frame="$1"
  local size
  size="$(image_size "$frame")"
  if [ "$size" = "${TARGET_WIDTH}x${TARGET_HEIGHT}" ]; then
    return 0
  fi

  "$MAGICK" "$frame" \
    -alpha on \
    -filter LanczosSharp -resize "${CONTENT_WIDTH}x${CONTENT_HEIGHT}" \
    -background none -gravity center -extent "${TARGET_WIDTH}x${TARGET_HEIGHT}" \
    -unsharp 0x0.8+0.65+0.012 \
    -background none -alpha background \
    -define png:color-type=6 \
    "$frame"
}

rebuild_contact_sheet() {
  local state_dir="$1"
  local frame_count
  frame_count="$(frame_count_for_dir "$state_dir")"
  [ "$frame_count" -gt 0 ] || return 0

  "$MAGICK" montage "$state_dir"/[0-9][0-9].png \
    -background '#2b2b2b' \
    -geometry "${TARGET_WIDTH}x${TARGET_HEIGHT}+8+8" \
    "$state_dir/contact-sheet.png"
}

prune_extra_frames() {
  local state_dir="$1"
  local state_name
  state_name="$(basename "$state_dir")"

  local base_count
  base_count="$(base_frame_count_for_state "$state_name")"
  [ "$base_count" -gt 0 ] || return 0

  find "$state_dir" -maxdepth 1 -type f -name '[0-9][0-9].png' | while IFS= read -r frame; do
    local stem
    stem="$(basename "$frame" .png)"
    if [ "$((10#$stem))" -ge "$base_count" ]; then
      rm -f "$frame"
    fi
  done
}

main() {
  require_magick

  while IFS= read -r source; do
    state_dir="$(dirname "$source")"
    [ -f "$state_dir/source-strip-magenta.png" ] && continue
    key_source_strip "$state_dir"
  done < <(find "$CHARACTER_DIR/extra" -type f -name 'source-strip-chroma.png' | sort)

  while IFS= read -r source; do
    key_source_strip "$(dirname "$source")" "$source" magenta
  done < <(find "$CHARACTER_DIR/extra" -type f -name 'source-strip-magenta.png' | sort)

  while IFS= read -r source; do
    process_alpha_source_strip "$(dirname "$source")"
  done < <(find "$CHARACTER_DIR/extra" -type f -name 'source-strip-alpha.png' | sort)

  while IFS= read -r frame; do
    upscale_transparent_frame "$frame"
  done < <(find "$CHARACTER_DIR/extra" -type f -name '[0-9][0-9].png' | sort)

  while IFS= read -r state_dir; do
    prune_extra_frames "$state_dir"
  done < <(find "$CHARACTER_DIR/extra" -mindepth 1 -maxdepth 1 -type d | sort)

  smooth_edge_body_frames

  update_manifest

  while IFS= read -r state_dir; do
    rebuild_contact_sheet "$state_dir"
  done < <(find "$CHARACTER_DIR/extra" -type d | sort)

  "$ROOT_DIR/script/validate_pet_assets.py"
}

main "$@"
