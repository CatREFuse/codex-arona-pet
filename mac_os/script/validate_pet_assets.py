#!/usr/bin/env python3
import argparse
import json
import pathlib
import re
import subprocess
import sys
from functools import lru_cache


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CHARACTER_ROOT = REPO_ROOT / "shared" / "Characters"
EXPECTED = (3072, 2304)
EXPECTED_EXTRA = (256, 256)
EXPECTED_VISIBLE_MARGIN = 8
EXPECTED_EDGE_GUIDE_WIDTH = 4
EXPECTED_EXTRA_FRAME_NAME = re.compile(r"^\d{2,}\.png$")
EXPECTED_LOOP_FRAME_COUNT = 12
EXPECTED_FRAME_DURATION = 1 / 6
EXPECTED_ATLAS_ROWS = 9
EXPECTED_ATLAS_COLUMNS = 12
EXPECTED_EDGE_MAX_VISIBLE_DELTA = 0.25
EXPECTED_EDGE_MAX_LOWER_DARK_DELTA = 0.35
EXPECTED_EDGE_MIN_LOWER_DARK_RATIO = 0.65
EXPECTED_EDGE_MIN_LOWER_DARK_VISIBLE_RATIO = 0.06
EXPECTED_EDGE_MAX_UPPER_WIDTH_DELTA = 18
EXPECTED_EDGE_MAX_UPPER_WIDTH_RANGE = 20
EXPECTED_EDGE_MIN_LINE_PIXELS = 900
EXPECTED_EDGE_MAX_OPPOSITE_LINE_PIXELS = 32
EXPECTED_EDGE_MAX_CONTENT_INSET = 20
EXPECTED_UPPER_MATERIAL_Y_RANGE = range(32, 156)
EXPECTED_MIN_SUCCESS_SIGN_AREA = 180
EXPECTED_MIN_REJECTED_SIGN_AREA = 350
EXPECTED_MIN_SIGN_FRAGMENT_AREA = 120


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", action="append")
    return parser.parse_args()


def _is_looping(config):
    return config.get("loop", True)


@lru_cache(maxsize=None)
def _dimensions(path):
    output = subprocess.check_output(
        ["magick", "identify", "-format", "%w %h", str(path)],
        text=True,
        stderr=subprocess.STDOUT,
    )
    width, height = (int(part) for part in output.strip().split()[:2])
    return width, height


@lru_cache(maxsize=None)
def _rgba_bytes(path):
    return subprocess.check_output(
        ["magick", str(path), "-depth", "8", "RGBA:-"],
        stderr=subprocess.STDOUT,
    )


def _canonical_rgba(raw):
    data = bytearray(raw)
    for offset in range(0, len(data), 4):
        if data[offset + 3] <= 16:
            data[offset] = 0
            data[offset + 1] = 0
            data[offset + 2] = 0
            data[offset + 3] = 0
    return bytes(data)


def _has_visible_pixels(path):
    raw = _rgba_bytes(path)
    return any(raw[index] > 0 for index in range(3, len(raw), 4))


def _allowed_edge_touch(state):
    if state.endswith("-left"):
        return "left"
    if state.endswith("-right"):
        return "right"
    return None


def _allowed_crop_sides(state):
    edge_touch = _allowed_edge_touch(state)
    allowed = set()
    if edge_touch is not None:
        allowed.add(edge_touch)
    if state == "carried":
        allowed.add("top")
    return allowed


def _visible_bounds(path, state):
    width, height = _dimensions(path)
    raw = _rgba_bytes(path)
    edge_touch = _allowed_edge_touch(state)
    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            offset = row + x * 4
            r, g, b, a = raw[offset], raw[offset + 1], raw[offset + 2], raw[offset + 3]
            if a <= 16:
                continue
            if edge_touch == "left" and x <= 3 and r < 35 and g < 35 and b < 35:
                continue
            if edge_touch == "right" and x >= width - 4 and r < 35 and g < 35 and b < 35:
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x < min_x or max_y < min_y:
        return None
    return min_x, min_y, max_x - min_x + 1, max_y - min_y + 1


def _edge_boundary_nonblack_pixels(path, state):
    edge_touch = _allowed_edge_touch(state)
    if edge_touch is None:
        return 0

    width, height = _dimensions(path)
    raw = _rgba_bytes(path)
    nonblack = 0
    for y in range(height):
        row = y * width * 4
        if edge_touch == "left":
            xs = range(EXPECTED_EDGE_GUIDE_WIDTH)
        else:
            xs = range(width - EXPECTED_EDGE_GUIDE_WIDTH, width)
        for x in xs:
            offset = row + x * 4
            r, g, b, a = raw[offset], raw[offset + 1], raw[offset + 2], raw[offset + 3]
            if a <= 16:
                continue
            if not (r < 35 and g < 35 and b < 35):
                nonblack += 1
    return nonblack


def _edge_boundary_black_pixels(path, state):
    edge_touch = _allowed_edge_touch(state)
    if edge_touch is None:
        return 0

    width, height = _dimensions(path)
    raw = _rgba_bytes(path)
    black = 0
    for y in range(height):
        row = y * width * 4
        if edge_touch == "left":
            xs = range(EXPECTED_EDGE_GUIDE_WIDTH)
        else:
            xs = range(width - EXPECTED_EDGE_GUIDE_WIDTH, width)
        for x in xs:
            offset = row + x * 4
            r, g, b, a = raw[offset], raw[offset + 1], raw[offset + 2], raw[offset + 3]
            if a > 16 and r < 35 and g < 35 and b < 35:
                black += 1
    return black


def _edge_opposite_boundary_black_pixels(path, state):
    edge_touch = _allowed_edge_touch(state)
    if edge_touch is None:
        return 0

    width, height = _dimensions(path)
    raw = _rgba_bytes(path)
    black = 0
    for y in range(height):
        row = y * width * 4
        if edge_touch == "left":
            xs = range(width - EXPECTED_EDGE_GUIDE_WIDTH, width)
        else:
            xs = range(EXPECTED_EDGE_GUIDE_WIDTH)
        for x in xs:
            offset = row + x * 4
            r, g, b, a = raw[offset], raw[offset + 1], raw[offset + 2], raw[offset + 3]
            if a > 16 and r < 35 and g < 35 and b < 35:
                black += 1
    return black


def _validate_edge_position(label, state, bounds, failures):
    edge_touch = _allowed_edge_touch(state)
    if edge_touch is None or bounds is None:
        return

    x, _, width, _ = bounds
    if edge_touch == "left":
        inset = x - EXPECTED_EDGE_GUIDE_WIDTH
        if inset > EXPECTED_EDGE_MAX_CONTENT_INSET:
            failures.append(
                f"{label}: expected left-edge character content to start within "
                f"{EXPECTED_EDGE_MAX_CONTENT_INSET}px of the left boundary line, got inset={inset}"
            )
    else:
        inset = (EXPECTED_EXTRA[0] - EXPECTED_EDGE_GUIDE_WIDTH) - (x + width)
        if inset > EXPECTED_EDGE_MAX_CONTENT_INSET:
            failures.append(
                f"{label}: expected right-edge character content to end within "
                f"{EXPECTED_EDGE_MAX_CONTENT_INSET}px of the right boundary line, got inset={inset}"
            )


def _edge_material_metrics(path, state):
    edge_touch = _allowed_edge_touch(state)
    if edge_touch is None:
        return None

    width, height = _dimensions(path)
    raw = _rgba_bytes(path)
    visible_pixels = 0
    lower_dark_pixels = 0
    upper_min_x = width
    upper_max_x = -1
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            offset = row + x * 4
            r, g, b, a = raw[offset], raw[offset + 1], raw[offset + 2], raw[offset + 3]
            if a <= 16:
                continue
            if edge_touch == "left" and x < EXPECTED_EDGE_GUIDE_WIDTH and r < 35 and g < 35 and b < 35:
                continue
            if edge_touch == "right" and x >= width - EXPECTED_EDGE_GUIDE_WIDTH and r < 35 and g < 35 and b < 35:
                continue
            visible_pixels += 1
            if y in EXPECTED_UPPER_MATERIAL_Y_RANGE:
                upper_min_x = min(upper_min_x, x)
                upper_max_x = max(upper_max_x, x)
            if y >= 110 and r < 92 and g < 96 and b < 122:
                lower_dark_pixels += 1
    upper_material_width = 0
    if upper_max_x >= upper_min_x:
        upper_material_width = upper_max_x - upper_min_x + 1
    return {
        "visible_pixels": visible_pixels,
        "lower_dark_pixels": lower_dark_pixels,
        "upper_material_width": upper_material_width,
    }


def _is_success_sign_pixel(r, g, b, a):
    return a > 16 and g > 125 and r < 100 and b < 130


def _is_rejected_sign_pixel(r, g, b, a):
    return a > 16 and r > 170 and g < 100 and b < 100


def _sign_color_components(path, state):
    if "success" in state:
        matcher = _is_success_sign_pixel
    elif "rejected" in state:
        matcher = _is_rejected_sign_pixel
    else:
        return []

    width, height = _dimensions(path)
    raw = _rgba_bytes(path)
    pixels = set()
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            offset = row + x * 4
            if matcher(raw[offset], raw[offset + 1], raw[offset + 2], raw[offset + 3]):
                pixels.add((x, y))

    components = []
    while pixels:
        start = pixels.pop()
        stack = [start]
        area = 0
        min_x = width
        min_y = height
        max_x = -1
        max_y = -1
        while stack:
            x, y = stack.pop()
            area += 1
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
            for next_y in range(y - 1, y + 2):
                for next_x in range(x - 1, x + 2):
                    point = (next_x, next_y)
                    if point in pixels:
                        pixels.remove(point)
                        stack.append(point)
        components.append((area, min_x, min_y, max_x, max_y))
    return sorted(components, reverse=True)


def _validate_sign_color(label, state, components, failures, allowed_crop_sides=None):
    if "success" not in state and "rejected" not in state:
        return
    allowed_crop_sides = allowed_crop_sides or set()

    expected_area = EXPECTED_MIN_SUCCESS_SIGN_AREA if "success" in state else EXPECTED_MIN_REJECTED_SIGN_AREA
    if not components or components[0][0] < expected_area:
        failures.append(f"{label}: expected visible sign color area >= {expected_area}px, got {components[:3]}")
        return

    for area, min_x, min_y, max_x, max_y in components:
        if area < EXPECTED_MIN_SIGN_FRAGMENT_AREA:
            continue
        left = min_x
        top = min_y
        right = EXPECTED_EXTRA[0] - max_x - 1
        bottom = EXPECTED_EXTRA[1] - max_y - 1
        side_margins = {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
        }
        tight_margins = {
            side: margin
            for side, margin in side_margins.items()
            if side not in allowed_crop_sides and margin < EXPECTED_VISIBLE_MARGIN
        }
        if tight_margins:
            failures.append(
                f"{label}: expected sign color component to stay inside {EXPECTED_VISIBLE_MARGIN}px padding, "
                f"got area={area} bounds={max_x - min_x + 1}x{max_y - min_y + 1}+{min_x}+{min_y} "
                f"with margins left={left}, top={top}, right={right}, bottom={bottom}"
            )

def _delta_ratio(left, right):
    return abs(left - right) / max(left, right, 1)


def _validate_edge_loop_continuity(label, metrics, failures):
    lower_dark_values = [item["lower_dark_pixels"] for item in metrics]
    median_lower_dark = sorted(lower_dark_values)[len(lower_dark_values) // 2]
    visible_values = [item["visible_pixels"] for item in metrics]
    median_visible = sorted(visible_values)[len(visible_values) // 2]
    dark_material_is_meaningful = (
        median_visible > 0
        and median_lower_dark / median_visible >= EXPECTED_EDGE_MIN_LOWER_DARK_VISIBLE_RATIO
    )
    upper_width_values = [item["upper_material_width"] for item in metrics]
    upper_width_range = max(upper_width_values) - min(upper_width_values)
    if upper_width_range > EXPECTED_EDGE_MAX_UPPER_WIDTH_RANGE:
        failures.append(
            f"{label}: expected edge upper-body width range <= {EXPECTED_EDGE_MAX_UPPER_WIDTH_RANGE}px, "
            f"got {upper_width_range}px from {upper_width_values}"
        )

    for index, current in enumerate(metrics):
        next_index = (index + 1) % len(metrics)
        next_item = metrics[next_index]
        visible_delta = _delta_ratio(current["visible_pixels"], next_item["visible_pixels"])
        if visible_delta > EXPECTED_EDGE_MAX_VISIBLE_DELTA:
            failures.append(
                f"{label}: expected edge frames {index:02d}->{next_index:02d} visible material delta <= "
                f"{EXPECTED_EDGE_MAX_VISIBLE_DELTA:.2f}, got {visible_delta:.2f}"
            )

        if dark_material_is_meaningful:
            lower_dark_delta = _delta_ratio(current["lower_dark_pixels"], next_item["lower_dark_pixels"])
            if lower_dark_delta > EXPECTED_EDGE_MAX_LOWER_DARK_DELTA:
                failures.append(
                    f"{label}: expected edge frames {index:02d}->{next_index:02d} lower-body dark material delta <= "
                    f"{EXPECTED_EDGE_MAX_LOWER_DARK_DELTA:.2f}, got {lower_dark_delta:.2f}"
                )

            if current["lower_dark_pixels"] < median_lower_dark * EXPECTED_EDGE_MIN_LOWER_DARK_RATIO:
                failures.append(
                    f"{label}: expected edge frame {index:02d} lower-body dark material to stay near the loop median, "
                    f"got {current['lower_dark_pixels']} vs median {median_lower_dark}"
                )

        upper_width_delta = abs(current["upper_material_width"] - next_item["upper_material_width"])
        if upper_width_delta > EXPECTED_EDGE_MAX_UPPER_WIDTH_DELTA:
            failures.append(
                f"{label}: expected edge frames {index:02d}->{next_index:02d} upper-body width delta <= "
                f"{EXPECTED_EDGE_MAX_UPPER_WIDTH_DELTA}px, got {upper_width_delta}px"
            )


def _bounds_from_raw(raw, width, height, x_offset=0, y_offset=0, stride_width=None):
    stride_width = stride_width or width
    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    for y in range(height):
        row = ((y + y_offset) * stride_width + x_offset) * 4
        for x in range(width):
            offset = row + x * 4
            if raw[offset + 3] <= 16:
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x < min_x or max_y < min_y:
        return None
    return min_x, min_y, max_x - min_x + 1, max_y - min_y + 1


def _validate_visible_padding(label, bounds, failures, allowed_crop_sides=None):
    allowed_crop_sides = allowed_crop_sides or set()
    if bounds is None:
        failures.append(f"{label}: expected visible pixels")
        return
    x, y, width, height = bounds
    left_margin = x
    top_margin = y
    right_margin = EXPECTED_EXTRA[0] - (x + width)
    bottom_margin = EXPECTED_EXTRA[1] - (y + height)
    if "top" not in allowed_crop_sides and top_margin < EXPECTED_VISIBLE_MARGIN:
        failures.append(
            f"{label}: expected visible pixels to stay within top {EXPECTED_VISIBLE_MARGIN}px padding, "
            f"got {width}x{height}+{x}+{y} with top={top_margin}"
        )
    if "bottom" not in allowed_crop_sides and bottom_margin < EXPECTED_VISIBLE_MARGIN:
        failures.append(
            f"{label}: expected visible pixels to stay within bottom {EXPECTED_VISIBLE_MARGIN}px padding, "
            f"got {width}x{height}+{x}+{y} with bottom={bottom_margin}"
        )
    if "left" not in allowed_crop_sides and left_margin < EXPECTED_VISIBLE_MARGIN:
        failures.append(
            f"{label}: expected visible pixels to stay within left {EXPECTED_VISIBLE_MARGIN}px padding, "
            f"got {width}x{height}+{x}+{y} with left={left_margin}"
        )
    if "right" not in allowed_crop_sides and right_margin < EXPECTED_VISIBLE_MARGIN:
        failures.append(
            f"{label}: expected visible pixels to stay within right {EXPECTED_VISIBLE_MARGIN}px padding, "
            f"got {width}x{height}+{x}+{y} with right={right_margin}"
        )


def _validate_atlas(sprite, failures):
    raw = _rgba_bytes(sprite)
    for row in range(EXPECTED_ATLAS_ROWS):
        first = raw[
            row * EXPECTED_EXTRA[1] * EXPECTED[0] * 4:
            (row * EXPECTED_EXTRA[1] + EXPECTED_EXTRA[1]) * EXPECTED[0] * 4
        ]
        first_cell = bytearray()
        last_cell = bytearray()
        for y in range(EXPECTED_EXTRA[1]):
            first_start = ((row * EXPECTED_EXTRA[1] + y) * EXPECTED[0]) * 4
            last_start = ((row * EXPECTED_EXTRA[1] + y) * EXPECTED[0] + (EXPECTED_ATLAS_COLUMNS - 1) * EXPECTED_EXTRA[0]) * 4
            first_cell.extend(raw[first_start:first_start + EXPECTED_EXTRA[0] * 4])
            last_cell.extend(raw[last_start:last_start + EXPECTED_EXTRA[0] * 4])
        if _canonical_rgba(first_cell) != _canonical_rgba(last_cell):
            failures.append(f"{sprite}: expected row {row} first and last frames to match")

        for column in range(EXPECTED_ATLAS_COLUMNS):
            bounds = _bounds_from_raw(
                raw,
                EXPECTED_EXTRA[0],
                EXPECTED_EXTRA[1],
                x_offset=column * EXPECTED_EXTRA[0],
                y_offset=row * EXPECTED_EXTRA[1],
                stride_width=EXPECTED[0],
            )
            _validate_visible_padding(f"{sprite}: row {row} column {column}", bounds, failures)


def main():
    args = parse_args()
    failures = []
    if args.character:
        pet_json_paths = [CHARACTER_ROOT / character / "pet.json" for character in args.character]
    else:
        pet_json_paths = sorted(CHARACTER_ROOT.glob("*/pet.json"))

    for pet_json in pet_json_paths:
        if not pet_json.exists():
            failures.append(f"{pet_json}: missing pet.json")
            continue
        directory = pet_json.parent
        pet = json.loads(pet_json.read_text(encoding="utf-8"))
        sprite = directory / pet["spritesheetPath"]
        if not sprite.exists():
            failures.append(f"{pet_json}: missing {sprite.name}")
            continue
        size = _dimensions(sprite)
        if size != EXPECTED:
            failures.append(f"{sprite}: expected {EXPECTED[0]}x{EXPECTED[1]}, got {size[0]}x{size[1]}")
        else:
            _validate_atlas(sprite, failures)

        manifest_path = directory / "openplana-character.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            referenced_extra_files = set()
            manifest_sprite_path = manifest.get("spritesheetPath")
            if manifest_sprite_path:
                manifest_sprite = directory / manifest_sprite_path
                if not manifest_sprite.exists():
                    failures.append(f"{manifest_path}: missing {manifest_sprite_path}")
                else:
                    manifest_sprite_size = _dimensions(manifest_sprite)
                    if manifest_sprite_size != EXPECTED:
                        failures.append(f"{manifest_sprite}: expected {EXPECTED[0]}x{EXPECTED[1]}, got {manifest_sprite_size[0]}x{manifest_sprite_size[1]}")
                    elif manifest_sprite != sprite:
                        _validate_atlas(manifest_sprite, failures)
            for state, config in manifest.get("extraStates", {}).items():
                frame_paths = config.get("framePaths", [])
                edge_loop_metrics = []
                expected_frame_names = [f"{index:02d}.png" for index in range(len(frame_paths))]
                actual_frame_names = [pathlib.PurePosixPath(frame).name for frame in frame_paths]
                if actual_frame_names != expected_frame_names:
                    failures.append(f"{manifest_path}: expected {state} ordered frame names {expected_frame_names}, got {actual_frame_names}")
                for frame_name in actual_frame_names:
                    if not EXPECTED_EXTRA_FRAME_NAME.match(frame_name):
                        failures.append(f"{manifest_path}: expected {state} frame name to be numeric PNG, got {frame_name}")
                if _is_looping(config) and len(frame_paths) != EXPECTED_LOOP_FRAME_COUNT:
                    failures.append(f"{manifest_path}: expected looping {state} to have {EXPECTED_LOOP_FRAME_COUNT} frames, got {len(frame_paths)}")
                if not _is_looping(config) and not frame_paths:
                    failures.append(f"{manifest_path}: expected non-looping {state} to have at least 1 frame")

                duration = config.get("frameDuration")
                if duration is None or abs(float(duration) - EXPECTED_FRAME_DURATION) > 0.000001:
                    failures.append(f"{manifest_path}: expected {state} frameDuration to be {EXPECTED_FRAME_DURATION:.10f}, got {duration}")

                expected_dir = str(pathlib.PurePosixPath("extra") / state)
                actual_dirs = {str(pathlib.PurePosixPath(frame).parent) for frame in frame_paths}
                if actual_dirs != {expected_dir}:
                    failures.append(f"{manifest_path}: expected {state} frames under {expected_dir}, got {sorted(actual_dirs)}")

                for frame in frame_paths:
                    frame_path = directory / frame
                    referenced_extra_files.add(frame_path.resolve())
                    if not frame_path.exists():
                        failures.append(f"{manifest_path}: missing {state} frame {frame}")
                        continue
                    size = _dimensions(frame_path)
                    if size != EXPECTED_EXTRA:
                        failures.append(f"{frame_path}: expected {EXPECTED_EXTRA[0]}x{EXPECTED_EXTRA[1]}, got {size[0]}x{size[1]}")
                    if not _has_visible_pixels(frame_path):
                        failures.append(f"{frame_path}: expected visible pixels")
                        continue
                    bounds = _visible_bounds(frame_path, state)
                    if bounds is None:
                        failures.append(f"{frame_path}: could not read alpha bounds")
                        continue
                    _validate_visible_padding(frame_path, bounds, failures, allowed_crop_sides=_allowed_crop_sides(state))
                    edge_nonblack = _edge_boundary_nonblack_pixels(frame_path, state)
                    if edge_nonblack:
                        failures.append(f"{frame_path}: expected only black screen-edge pixels on the edge boundary, got {edge_nonblack} non-black pixels")
                    edge_black = _edge_boundary_black_pixels(frame_path, state)
                    if _allowed_edge_touch(state) is not None and edge_black < EXPECTED_EDGE_MIN_LINE_PIXELS:
                        failures.append(
                            f"{frame_path}: expected black screen-edge line on the dock side, "
                            f"got {edge_black} black pixels"
                        )
                    opposite_edge_black = _edge_opposite_boundary_black_pixels(frame_path, state)
                    if opposite_edge_black > EXPECTED_EDGE_MAX_OPPOSITE_LINE_PIXELS:
                        failures.append(
                            f"{frame_path}: expected no opposite-side black edge line, "
                            f"got {opposite_edge_black} black pixels"
                        )
                    _validate_edge_position(frame_path, state, bounds, failures)
                    edge_metrics = _edge_material_metrics(frame_path, state)
                    if edge_metrics is not None:
                        edge_loop_metrics.append(edge_metrics)
                    allowed_crop_sides = _allowed_crop_sides(state)
                    _validate_sign_color(
                        frame_path,
                        state,
                        _sign_color_components(frame_path, state),
                        failures,
                        allowed_crop_sides=allowed_crop_sides,
                    )

                if _is_looping(config) and len(frame_paths) >= 2:
                    first = directory / frame_paths[0]
                    last = directory / frame_paths[-1]
                    if first.exists() and last.exists() and _canonical_rgba(_rgba_bytes(first)) != _canonical_rgba(_rgba_bytes(last)):
                        failures.append(f"{manifest_path}: expected looping {state} first and last frames to match")
                    if state.startswith("edge-") and len(edge_loop_metrics) == len(frame_paths):
                        _validate_edge_loop_continuity(f"{manifest_path}: {state}", edge_loop_metrics, failures)

            extra_root = directory / "extra"
            if extra_root.exists():
                for extra_png in sorted(extra_root.rglob("*.png")):
                    if extra_png.resolve() not in referenced_extra_files:
                        failures.append(f"{extra_png}: unexpected extra animation PNG outside manifest framePaths")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("pet assets ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
