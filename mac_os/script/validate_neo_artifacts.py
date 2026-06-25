#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import statistics
import sys
from collections import deque
from dataclasses import dataclass

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError:
    fallback_python = shutil.which("python3.10")
    if fallback_python and pathlib.Path(fallback_python).resolve() != pathlib.Path(sys.executable).resolve():
        os.execv(fallback_python, [fallback_python, *sys.argv])
    raise


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CHARACTER_ROOT = REPO_ROOT / "shared" / "Characters"
CELL_SIZE = 256
ATLAS_COLUMNS = 12
ATLAS_ROWS = [
    "idle",
    "running-right",
    "running-left",
    "waving",
    "jumping",
    "failed",
    "waiting",
    "running",
    "review",
]


@dataclass
class FrameMetrics:
    bbox: tuple[int, int, int, int] | None
    visible: int
    cx: float
    cy: float


@dataclass
class VisualMetrics:
    bbox: tuple[int, int, int, int] | None
    face_bbox: tuple[int, int, int, int] | None
    face_skin_area: int
    eye_dark_pixels: int
    iris_pixels: int
    mouth_dark_pixels: int

    @property
    def has_front_face_evidence(self) -> bool:
        return self.face_skin_area >= 80 and self.eye_dark_pixels >= 6


@dataclass
class AlphaComponent:
    area: int
    bbox: tuple[int, int, int, int]
    colors: list[tuple[int, int, int, int]]


def has_centered_carried_face(metrics: VisualMetrics) -> bool:
    if metrics.bbox is None or metrics.face_bbox is None:
        return False
    left, _, right, _ = metrics.bbox
    face_left, _, face_right, _ = metrics.face_bbox
    width = max(right - left, 1)
    relative_face_center = (((face_left + face_right) / 2) - left) / width
    return metrics.face_skin_area >= 220 and 0.32 <= relative_face_center <= 0.68


def is_sleep_state(state: str) -> bool:
    return "sleep" in state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", action="append")
    parser.add_argument("--json-out", type=pathlib.Path)
    parser.add_argument("--candidate-sheet-dir", type=pathlib.Path)
    parser.add_argument("--strict-visual-candidates", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--include-atlas", action="store_true")
    return parser.parse_args()


def default_character_ids() -> list[str]:
    return sorted(path.parent.name for path in CHARACTER_ROOT.glob("*/pet.json"))


def allows_original_prop(state: str) -> bool:
    return state == "idle-normal" or state.startswith("edge-idle-normal")


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A")
    return alpha.point(lambda value: 255 if value > 16 else 0).getbbox()


def frame_metrics(image: Image.Image) -> FrameMetrics:
    pixels = image.convert("RGBA").load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(image.height):
        for x in range(image.width):
            if pixels[x, y][3] <= 16:
                continue
            xs.append(x)
            ys.append(y)
    if not xs:
        return FrameMetrics(None, 0, 0, 0)
    return FrameMetrics(
        (min(xs), min(ys), max(xs) + 1, max(ys) + 1),
        len(xs),
        sum(xs) / len(xs),
        sum(ys) / len(ys),
    )


def is_skin_pixel(r: int, g: int, b: int, a: int) -> bool:
    if a <= 16:
        return False
    if r < 118 or g < 74 or b < 54:
        return False
    if max(r, g, b) - min(r, g, b) < 8:
        return False
    return r > g + 4 and r > b + 8 and g >= b - 24


def is_eye_dark_pixel(r: int, g: int, b: int, a: int) -> bool:
    if a <= 16:
        return False
    dark_line = r < 82 and g < 78 and b < 105
    gray_lavender_iris = (
        54 <= r <= 215
        and 50 <= g <= 210
        and 76 <= b <= 230
        and b >= r - 18
        and b >= g - 14
        and max(r, g, b) - min(r, g, b) >= 6
        and min(r, g, b) <= 205
    )
    blue_iris = (
        35 <= r <= 135
        and 76 <= g <= 185
        and 118 <= b <= 230
        and b >= r + 35
        and b >= g + 2
    )
    return dark_line or gray_lavender_iris or blue_iris


def is_iris_pixel(character: str, r: int, g: int, b: int, a: int) -> bool:
    if a <= 16:
        return False
    if character.startswith("arona"):
        return (
            25 <= r <= 130
            and 70 <= g <= 210
            and 120 <= b <= 255
            and b >= r + 45
            and b >= g + 5
        )
    return (
        45 <= r <= 175
        and 50 <= g <= 175
        and 70 <= b <= 205
        and b >= r - 10
        and b >= g - 8
        and max(r, g, b) - min(r, g, b) >= 12
        and min(r, g, b) <= 150
    )


def is_mouth_dark_pixel(r: int, g: int, b: int, a: int) -> bool:
    if a <= 16:
        return False
    red_mouth = r > 105 and g < 86 and b < 100 and r > g + 22 and r >= b - 4
    dark_mouth = r < 92 and g < 76 and b < 86 and r >= b - 4 and r > g + 5
    return red_mouth or dark_mouth


def skin_components(image: Image.Image) -> list[dict[str, int]]:
    pixels = image.convert("RGBA").load()
    remaining: set[tuple[int, int]] = set()
    for y in range(image.height):
        for x in range(image.width):
            if is_skin_pixel(*pixels[x, y]):
                remaining.add((x, y))

    components: list[dict[str, int]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        area = 0
        min_x = image.width
        min_y = image.height
        max_x = -1
        max_y = -1
        while stack:
            x, y = stack.pop()
            area += 1
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
            for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                point = (next_x, next_y)
                if point in remaining:
                    remaining.remove(point)
                    stack.append(point)
        components.append({
            "area": area,
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x + 1,
            "max_y": max_y + 1,
        })
    return components


def likely_face_component(image: Image.Image, bbox: tuple[int, int, int, int] | None) -> dict[str, int] | None:
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    width = max(right - left, 1)
    height = max(bottom - top, 1)
    center_x = left + width / 2
    candidates: list[tuple[float, dict[str, int]]] = []
    for component in skin_components(image):
        component_width = component["max_x"] - component["min_x"]
        component_height = component["max_y"] - component["min_y"]
        if component["area"] < 40 or component_width < 5 or component_height < 5:
            continue
        aspect = component_width / max(component_height, 1)
        if aspect < 0.35 or aspect > 2.45:
            continue
        component_cx = (component["min_x"] + component["max_x"]) / 2
        component_cy = (component["min_y"] + component["max_y"]) / 2
        if component_cy > top + height * 0.68:
            continue
        if not (left + width * 0.16 <= component_cx <= right - width * 0.16):
            continue
        center_penalty = abs(component_cx - center_x) * 0.9
        low_penalty = max(0.0, component_cy - (top + height * 0.48)) * 1.8
        score = component["area"] - center_penalty - low_penalty
        candidates.append((score, component))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def frame_iris_pixels(image: Image.Image, character: str, bbox: tuple[int, int, int, int] | None) -> int:
    if bbox is None:
        return 0
    left, top, right, bottom = bbox
    height = max(bottom - top, 1)
    scan_top = top + int(height * 0.22)
    scan_bottom = top + int(height * 0.72)
    pixels = image.load()
    count = 0
    for y in range(scan_top, scan_bottom):
        for x in range(left, right):
            if is_iris_pixel(character, *pixels[x, y]):
                count += 1
    return count


def visual_metrics(image: Image.Image, character: str = "") -> VisualMetrics:
    rgba = image.convert("RGBA")
    bbox = alpha_bbox(rgba)
    frame_iris = frame_iris_pixels(rgba, character, bbox)
    face = likely_face_component(rgba, bbox)
    if face is None:
        return VisualMetrics(bbox, None, 0, 0, frame_iris, 0)

    pixels = rgba.load()
    min_x = max(face["min_x"] - 10, 0)
    min_y = max(face["min_y"] - 4, 0)
    max_x = min(face["max_x"] + 10, rgba.width)
    max_y = min(face["max_y"] + 5, rgba.height)
    face_height = max(max_y - min_y, 1)
    eye_top = min_y + int(face_height * 0.18)
    eye_bottom = min_y + int(face_height * 0.62)
    mouth_top = min_y + int(face_height * 0.52)
    eye_dark = 0
    mouth_dark = 0
    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            pixel = pixels[x, y]
            if eye_top <= y <= eye_bottom and is_eye_dark_pixel(*pixel):
                eye_dark += 1
            if mouth_top <= y <= max_y and is_mouth_dark_pixel(*pixel):
                mouth_dark += 1
    return VisualMetrics(
        bbox,
        (min_x, min_y, max_x, max_y),
        face["area"],
        eye_dark,
        frame_iris,
        mouth_dark,
    )


def candidate_entry(
    candidate_type: str,
    character: str,
    state: str,
    frame: int,
    reason: str,
    metrics: VisualMetrics,
    source: str,
) -> dict[str, object]:
    return {
        "type": candidate_type,
        "character": character,
        "state": state,
        "frame": frame,
        "source": source,
        "reason": reason,
        "metrics": {
            "bbox": metrics.bbox,
            "faceBBox": metrics.face_bbox,
            "faceSkinArea": metrics.face_skin_area,
            "eyeDarkPixels": metrics.eye_dark_pixels,
            "irisPixels": metrics.iris_pixels,
            "mouthDarkPixels": metrics.mouth_dark_pixels,
        },
    }


def size_candidate_entry(
    character: str,
    state: str,
    frame: int,
    reason: str,
    metrics: FrameMetrics,
    source: str,
) -> dict[str, object]:
    width = 0
    height = 0
    if metrics.bbox is not None:
        width = metrics.bbox[2] - metrics.bbox[0]
        height = metrics.bbox[3] - metrics.bbox[1]
    return {
        "type": "size",
        "character": character,
        "state": state,
        "frame": frame,
        "source": source,
        "reason": reason,
        "metrics": {
            "bbox": metrics.bbox,
            "visible": metrics.visible,
            "width": width,
            "height": height,
            "cx": metrics.cx,
            "cy": metrics.cy,
        },
    }


def edge_side(state: str) -> str | None:
    if state.startswith("edge-") and state.endswith("-left"):
        return "left"
    if state.startswith("edge-") and state.endswith("-right"):
        return "right"
    return None


def alpha_components(image: Image.Image) -> list[AlphaComponent]:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    visited: set[tuple[int, int]] = set()
    components: list[AlphaComponent] = []

    for y in range(rgba.height):
        for x in range(rgba.width):
            if (x, y) in visited or pixels[x, y][3] <= 16:
                continue
            queue: deque[tuple[int, int]] = deque([(x, y)])
            visited.add((x, y))
            xs: list[int] = []
            ys: list[int] = []
            colors: list[tuple[int, int, int, int]] = []
            while queue:
                px, py = queue.popleft()
                xs.append(px)
                ys.append(py)
                colors.append(pixels[px, py])
                for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    if nx < 0 or nx >= rgba.width or ny < 0 or ny >= rgba.height:
                        continue
                    point = (nx, ny)
                    if point in visited or pixels[nx, ny][3] <= 16:
                        continue
                    visited.add(point)
                    queue.append(point)
            components.append(AlphaComponent(
                area=len(xs),
                bbox=(min(xs), min(ys), max(xs) + 1, max(ys) + 1),
                colors=colors,
            ))
    return sorted(components, key=lambda component: component.area, reverse=True)


def component_color_ratios(component: AlphaComponent) -> dict[str, float]:
    total = max(1, len(component.colors))
    return {
        "white": sum(1 for r, g, b, _ in component.colors if r > 180 and g > 180 and b > 180) / total,
        "red": sum(1 for r, g, b, _ in component.colors if r > 150 and g < 90 and b < 90) / total,
        "green": sum(1 for r, g, b, _ in component.colors if g > 120 and r < 110 and b < 130) / total,
        "cyan": sum(1 for r, g, b, _ in component.colors if b > 130 and g > 110 and r < 150) / total,
    }


def is_edge_line_component(component: AlphaComponent, state: str) -> bool:
    left, top, right, bottom = component.bbox
    side = edge_side(state)
    if component.area < 700 or bottom - top < 220 or right - left > 8:
        return False
    if side == "left" and left <= 1:
        return True
    if side == "right" and right >= CELL_SIZE - 1:
        return True
    return False


def is_halo_component(component: AlphaComponent) -> bool:
    left, top, right, bottom = component.bbox
    width = right - left
    height = bottom - top
    ratios = component_color_ratios(component)
    return (
        component.area < 900
        and top < 80
        and height < 55
        and width < 95
        and (ratios["red"] > 0.15 or ratios["cyan"] > 0.15)
    )


def is_sign_component(component: AlphaComponent, state: str) -> bool:
    if not any(label in state for label in ("success", "rejected", "failed")):
        return False
    left, top, right, bottom = component.bbox
    width = right - left
    height = bottom - top
    ratios = component_color_ratios(component)
    return (
        component.area > 700
        and height > 20
        and width > 35
        and ratios["white"] > 0.28
        and (ratios["red"] > 0.02 or ratios["green"] > 0.02 or width > 45)
    )


def adjacent_frame_candidates_for_frame(
    character: str,
    state: str,
    frame: int,
    source: str,
    image: Image.Image,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    components = [
        component for component in alpha_components(image)
        if component.area >= 180
        and not is_edge_line_component(component, state)
        and not is_halo_component(component)
        and not is_sign_component(component, state)
    ]
    if not components:
        return candidates

    main = components[0]
    main_left, main_top, main_right, main_bottom = main.bbox
    main_cx = (main_left + main_right) / 2
    main_cy = (main_top + main_bottom) / 2
    flexible_states = ("coding", "pinched", "carried")
    for component in components[1:]:
        left, top, right, bottom = component.bbox
        cx = (left + right) / 2
        cy = (top + bottom) / 2
        far_from_main = abs(cx - main_cx) > 45 or abs(cy - main_cy) > 45
        very_far_from_main = abs(cx - main_cx) > 65 or abs(cy - main_cy) > 65
        if component.area > 900 and far_from_main and not any(label in state for label in flexible_states):
            candidates.append({
                "type": "adjacent-frame",
                "character": character,
                "state": state,
                "frame": frame,
                "source": source,
                "reason": f"detached body-sized component area {component.area} at {component.bbox}",
                "metrics": {
                    "componentArea": component.area,
                    "componentBBox": component.bbox,
                    "mainArea": main.area,
                    "mainBBox": main.bbox,
                },
            })
        elif component.area > 1800 and very_far_from_main:
            candidates.append({
                "type": "adjacent-frame",
                "character": character,
                "state": state,
                "frame": frame,
                "source": source,
                "reason": f"large detached component area {component.area} at {component.bbox}",
                "metrics": {
                    "componentArea": component.area,
                    "componentBBox": component.bbox,
                    "mainArea": main.area,
                    "mainBBox": main.bbox,
                },
            })
    return candidates


def visual_candidates_for_state(
    character: str,
    state: str,
    frames: list[tuple[int, str, Image.Image]],
) -> dict[str, list[dict[str, object]]]:
    metrics_by_frame = [(index, source, visual_metrics(frame, character)) for index, source, frame in frames]
    size_metrics_by_frame = [(index, source, frame_metrics(frame)) for index, source, frame in frames]
    result = {
        "sizeCandidates": [],
        "blinkCandidates": [],
        "closedEyeCandidates": [],
        "openMouthCandidates": [],
        "backFacingCandidates": [],
        "carryFacingCandidates": [],
        "adjacentFrameCandidates": [],
    }

    for index, source, frame in frames:
        result["adjacentFrameCandidates"].extend(
            adjacent_frame_candidates_for_frame(character, state, index, source, frame)
        )

    if state in {"coding", "idle-read"}:
        visible_metrics = [item for item in size_metrics_by_frame if item[2].bbox is not None and item[2].visible > 0]
        if len(visible_metrics) >= 3:
            widths = [item[2].bbox[2] - item[2].bbox[0] for item in visible_metrics if item[2].bbox is not None]
            visible_counts = [item[2].visible for item in visible_metrics]
            median_width = statistics.median(widths)
            median_visible = statistics.median(visible_counts)
            width_range = max(widths) - min(widths)
            visible_ratio = max(visible_counts) / max(1, min(visible_counts))
            if width_range > 12 or visible_ratio > 1.15:
                for index, source, metrics in visible_metrics:
                    if metrics.bbox is None:
                        continue
                    width = metrics.bbox[2] - metrics.bbox[0]
                    visible_delta = metrics.visible / max(1, median_visible)
                    too_large = width >= median_width + 9 or visible_delta >= 1.12
                    too_small = width <= median_width - 9 or visible_delta <= 0.90
                    if too_large or too_small:
                        direction = "large" if too_large else "small"
                        result["sizeCandidates"].append(size_candidate_entry(
                            character,
                            state,
                            index,
                            (
                                f"{direction} frame: width {width} vs median {median_width:.1f}; "
                                f"visible ratio {visible_delta:.2f}; state width range {width_range}; "
                                f"visible range ratio {visible_ratio:.2f}"
                            ),
                            metrics,
                            source,
                        ))

    if state == "carried":
        for index, source, metrics in metrics_by_frame:
            if not has_centered_carried_face(metrics):
                reason = (
                    "carried frame lacks centered frontal face evidence; verify that the character faces screen, "
                    "is held by collar/nape, and has hanging limbs"
                )
                back_candidate = candidate_entry("back-facing", character, state, index, reason, metrics, source)
                carry_candidate = candidate_entry("carry-facing", character, state, index, reason, metrics, source)
                result["backFacingCandidates"].append(back_candidate)
                result["carryFacingCandidates"].append(carry_candidate)

    face_metrics = [metrics for _, _, metrics in metrics_by_frame if metrics.face_skin_area >= 80]
    if len(face_metrics) >= 3:
        eye_values = [metrics.eye_dark_pixels for metrics in face_metrics if metrics.eye_dark_pixels > 0]
        iris_values = [metrics.iris_pixels for metrics in face_metrics if metrics.iris_pixels > 0]
        mouth_values = [metrics.mouth_dark_pixels for metrics in face_metrics]
        median_eye = statistics.median(eye_values) if eye_values else 0
        max_iris = max(iris_values) if iris_values else 0
        median_mouth = statistics.median(mouth_values) if mouth_values else 0
        check_eye_blinks = not is_sleep_state(state)
        check_closed_eye = state.startswith("edge-coding") and not is_sleep_state(state) and max_iris >= 45
        check_open_mouth = not is_sleep_state(state)

        for position, (index, source, metrics) in enumerate(metrics_by_frame):
            if metrics.face_skin_area < 80:
                continue
            previous_eye = metrics_by_frame[position - 1][2].eye_dark_pixels if position > 0 else median_eye
            next_eye = metrics_by_frame[position + 1][2].eye_dark_pixels if position + 1 < len(metrics_by_frame) else median_eye
            neighbor_eye = max(previous_eye, next_eye)
            if (
                check_eye_blinks
                and median_eye >= 12
                and neighbor_eye >= median_eye * 0.65
                and metrics.eye_dark_pixels <= min(6, max(2, int(median_eye * 0.28)))
            ):
                result["blinkCandidates"].append(candidate_entry(
                    "blink",
                    character,
                    state,
                    index,
                    f"eye-dark pixels dropped to {metrics.eye_dark_pixels} from state median {median_eye:.1f}",
                    metrics,
                    source,
                ))

            if (
                check_closed_eye
                and metrics.eye_dark_pixels >= 40
                and metrics.iris_pixels <= max(8, int(max_iris * 0.16))
            ):
                result["closedEyeCandidates"].append(candidate_entry(
                    "closed-eye",
                    character,
                    state,
                    index,
                    f"iris pixels dropped to {metrics.iris_pixels} from state max {max_iris}",
                    metrics,
                    source,
                ))

            previous_mouth = metrics_by_frame[position - 1][2].mouth_dark_pixels if position > 0 else median_mouth
            next_mouth = metrics_by_frame[position + 1][2].mouth_dark_pixels if position + 1 < len(metrics_by_frame) else median_mouth
            neighbor_mouth = max(previous_mouth, next_mouth)
            mouth_threshold = max(24, int(median_mouth * 2.8 + 10))
            if (
                check_open_mouth
                and metrics.mouth_dark_pixels >= mouth_threshold
                and metrics.mouth_dark_pixels >= neighbor_mouth * 1.8 + 8
            ):
                result["openMouthCandidates"].append(candidate_entry(
                    "open-mouth",
                    character,
                    state,
                    index,
                    f"mouth-dark pixels spiked to {metrics.mouth_dark_pixels} from state median {median_mouth:.1f}",
                    metrics,
                    source,
                ))

    return result


def prop_like_long_runs(image: Image.Image, character: str) -> list[dict[str, object]]:
    pixels = image.convert("RGBA").load()
    runs: list[dict[str, object]] = []

    def matches(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        if a <= 16:
            return False
        if character.startswith("plana"):
            return y >= 48 and r < 92 and g < 92 and b < 118
        bright_umbrella = r > 150 and g > 150 and b > 150 and abs(r - g) < 80 and abs(g - b) < 95
        cyan_handle = g > 110 and b > 128 and r < 135
        dark_bar = r < 92 and g < 98 and b < 120
        return y >= 54 and (bright_umbrella or cyan_handle or dark_bar)

    for y in range(CELL_SIZE):
        x = 0
        row_runs: list[tuple[int, int]] = []
        while x < CELL_SIZE:
            if not matches(x, y):
                x += 1
                continue
            start = x
            while x < CELL_SIZE and matches(x, y):
                x += 1
            if x - start >= 12:
                row_runs.append((start, x - 1))
        if not row_runs:
            continue
        total = sum(end - start + 1 for start, end in row_runs)
        span = max(end for _, end in row_runs) - min(start for start, _ in row_runs) + 1
        if total >= 34 and span >= 86:
            runs.append({"y": y, "total": total, "span": span, "runs": row_runs})
    return runs


def atlas_frames(character_dir: pathlib.Path) -> list[tuple[str, int, Image.Image]]:
    atlas = Image.open(character_dir / "spritesheet.png").convert("RGBA")
    frames: list[tuple[str, int, Image.Image]] = []
    for row, state in enumerate(ATLAS_ROWS):
        for index in range(ATLAS_COLUMNS):
            frame = atlas.crop(
                (
                    index * CELL_SIZE,
                    row * CELL_SIZE,
                    (index + 1) * CELL_SIZE,
                    (row + 1) * CELL_SIZE,
                )
            )
            frames.append((state, index, frame))
    return frames


def extra_frames(character_dir: pathlib.Path) -> list[tuple[str, int, Image.Image]]:
    frames: list[tuple[str, int, Image.Image]] = []
    manifest = json.loads((character_dir / "openplana-character.json").read_text(encoding="utf-8"))
    configured_states = set(manifest.get("extraStates", {}))
    for state_dir in sorted((character_dir / "extra").iterdir()):
        if not state_dir.is_dir():
            continue
        if state_dir.name not in configured_states:
            continue
        for path in sorted(state_dir.glob("*.png")):
            frames.append((state_dir.name, int(path.stem), Image.open(path).convert("RGBA")))
    return frames


def draw_contact_sheet(
    path: pathlib.Path,
    candidates: list[dict[str, object]],
    frame_images: dict[tuple[str, str, int], Image.Image],
) -> None:
    unique: dict[tuple[str, str, int], set[str]] = {}
    for candidate in candidates:
        key = (str(candidate["character"]), str(candidate["state"]), int(candidate["frame"]))
        unique.setdefault(key, set()).add(str(candidate["type"]))
    items = sorted(unique.items())
    if not items:
        return

    label_height = 42
    cell_width = CELL_SIZE
    cell_height = CELL_SIZE + label_height
    columns = min(4, len(items))
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * cell_width, rows * cell_height), (32, 32, 32, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for item_index, (key, types) in enumerate(items):
        character, state, frame = key
        image = frame_images.get(key)
        if image is None:
            continue
        x = (item_index % columns) * cell_width
        y = (item_index // columns) * cell_height
        sheet.alpha_composite(image.convert("RGBA"), (x, y + label_height))
        label = f"{character} {state} #{frame:02d}"
        reason = ",".join(sorted(types))
        draw.rectangle((x, y, x + cell_width, y + label_height), fill=(18, 18, 18, 255))
        draw.text((x + 6, y + 5), label[:38], fill=(255, 255, 255, 255), font=font)
        draw.text((x + 6, y + 22), reason[:42], fill=(255, 190, 90, 255), font=font)

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(path)


def check_motion(character: str, state: str, frames: list[Image.Image]) -> list[dict[str, object]]:
    metrics = [frame_metrics(frame) for frame in frames]
    issues: list[dict[str, object]] = []
    for index, (a, b) in enumerate(zip(metrics, metrics[1:])):
        if a.bbox is None or b.bbox is None:
            issues.append({"character": character, "state": state, "frame": index, "reason": "blank frame"})
            continue
        aw = a.bbox[2] - a.bbox[0]
        ah = a.bbox[3] - a.bbox[1]
        bw = b.bbox[2] - b.bbox[0]
        bh = b.bbox[3] - b.bbox[1]
        issue_reasons: list[str] = []
        if abs(aw - bw) > 22:
            issue_reasons.append(f"width delta {abs(aw - bw)}")
        if abs(ah - bh) > 24:
            issue_reasons.append(f"height delta {abs(ah - bh)}")
        if abs(a.cx - b.cx) > 18:
            issue_reasons.append(f"center-x delta {abs(a.cx - b.cx):.1f}")
        if abs(a.cy - b.cy) > 20:
            issue_reasons.append(f"center-y delta {abs(a.cy - b.cy):.1f}")
        ratio = max(a.visible, b.visible) / max(1, min(a.visible, b.visible))
        if ratio > 1.34:
            issue_reasons.append(f"visible-area ratio {ratio:.2f}")
        if issue_reasons:
            issues.append({"character": character, "state": state, "frame": index, "reason": "; ".join(issue_reasons)})
    return issues


def main() -> int:
    args = parse_args()
    characters = args.character or default_character_ids()
    prop_candidates: list[dict[str, object]] = []
    motion_issues: list[dict[str, object]] = []
    cutout_issues: list[dict[str, object]] = []
    size_candidates: list[dict[str, object]] = []
    blink_candidates: list[dict[str, object]] = []
    closed_eye_candidates: list[dict[str, object]] = []
    open_mouth_candidates: list[dict[str, object]] = []
    back_facing_candidates: list[dict[str, object]] = []
    carry_facing_candidates: list[dict[str, object]] = []
    adjacent_frame_candidates: list[dict[str, object]] = []
    frame_images: dict[tuple[str, str, int], Image.Image] = {}

    for character in characters:
        character_dir = CHARACTER_ROOT / character
        if args.include_atlas:
            atlas_by_state: dict[str, list[Image.Image]] = {state: [] for state in ATLAS_ROWS}
            atlas_visual_by_state: dict[str, list[tuple[int, str, Image.Image]]] = {state: [] for state in ATLAS_ROWS}
            for state, index, frame in atlas_frames(character_dir):
                frame_images[(character, state, index)] = frame
                atlas_by_state[state].append(frame)
                atlas_visual_by_state[state].append((index, "atlas", frame))
                metrics = frame_metrics(frame)
                if metrics.visible < 500:
                    cutout_issues.append({"character": character, "state": state, "frame": index, "reason": "too few visible pixels"})
                if not allows_original_prop(state):
                    runs = prop_like_long_runs(frame, character)
                    if runs:
                        prop_candidates.append({"character": character, "state": state, "frame": index, "runs": runs[:3]})
            for state, frames in atlas_by_state.items():
                motion_issues.extend(check_motion(character, state, frames))
            for state, frames in atlas_visual_by_state.items():
                state_candidates = visual_candidates_for_state(character, state, frames)
                size_candidates.extend(state_candidates["sizeCandidates"])
                blink_candidates.extend(state_candidates["blinkCandidates"])
                closed_eye_candidates.extend(state_candidates["closedEyeCandidates"])
                open_mouth_candidates.extend(state_candidates["openMouthCandidates"])
                back_facing_candidates.extend(state_candidates["backFacingCandidates"])
                carry_facing_candidates.extend(state_candidates["carryFacingCandidates"])
                adjacent_frame_candidates.extend(state_candidates["adjacentFrameCandidates"])

        extra_by_state: dict[str, list[Image.Image]] = {}
        extra_visual_by_state: dict[str, list[tuple[int, str, Image.Image]]] = {}
        for state, index, frame in extra_frames(character_dir):
            frame_images[(character, state, index)] = frame
            extra_by_state.setdefault(state, []).append(frame)
            extra_visual_by_state.setdefault(state, []).append((index, "extra", frame))
            metrics = frame_metrics(frame)
            if metrics.visible < 500:
                cutout_issues.append({"character": character, "state": state, "frame": index, "reason": "too few visible pixels"})
            if not allows_original_prop(state):
                runs = prop_like_long_runs(frame, character)
                if runs:
                    prop_candidates.append({"character": character, "state": state, "frame": index, "runs": runs[:3]})
        for state, frames in extra_by_state.items():
            if not state.startswith("edge-"):
                motion_issues.extend(check_motion(character, state, frames))
        for state, frames in extra_visual_by_state.items():
            state_candidates = visual_candidates_for_state(character, state, frames)
            size_candidates.extend(state_candidates["sizeCandidates"])
            blink_candidates.extend(state_candidates["blinkCandidates"])
            closed_eye_candidates.extend(state_candidates["closedEyeCandidates"])
            open_mouth_candidates.extend(state_candidates["openMouthCandidates"])
            back_facing_candidates.extend(state_candidates["backFacingCandidates"])
            carry_facing_candidates.extend(state_candidates["carryFacingCandidates"])
            adjacent_frame_candidates.extend(state_candidates["adjacentFrameCandidates"])

    visual_candidates = [
        *size_candidates,
        *blink_candidates,
        *closed_eye_candidates,
        *open_mouth_candidates,
        *back_facing_candidates,
        *carry_facing_candidates,
        *adjacent_frame_candidates,
    ]
    candidate_sheet_path = None
    if args.candidate_sheet_dir and visual_candidates:
        candidate_sheet_path = args.candidate_sheet_dir / "visual-candidates-contact-sheet.png"
        draw_contact_sheet(candidate_sheet_path, visual_candidates, frame_images)

    result = {
        "ok": not motion_issues and not cutout_issues and (not args.strict_visual_candidates or not visual_candidates),
        "propCandidates": prop_candidates,
        "motionIssues": motion_issues,
        "cutoutIssues": cutout_issues,
        "sizeCandidates": size_candidates,
        "blinkCandidates": blink_candidates,
        "closedEyeCandidates": closed_eye_candidates,
        "openMouthCandidates": open_mouth_candidates,
        "backFacingCandidates": back_facing_candidates,
        "carryFacingCandidates": carry_facing_candidates,
        "adjacentFrameCandidates": adjacent_frame_candidates,
        "candidateContactSheet": str(candidate_sheet_path) if candidate_sheet_path else None,
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.summary:
        print(f"ok={str(result['ok']).lower()}")
        for key in (
            "motionIssues",
            "cutoutIssues",
            "sizeCandidates",
            "blinkCandidates",
            "closedEyeCandidates",
            "openMouthCandidates",
            "backFacingCandidates",
            "carryFacingCandidates",
            "adjacentFrameCandidates",
            "propCandidates",
        ):
            counts: dict[tuple[str, str], int] = {}
            for issue in result[key]:
                issue_key = (str(issue["character"]), str(issue["state"]))
                counts[issue_key] = counts.get(issue_key, 0) + 1
            print(f"{key}={len(result[key])}")
            for (character, state), count in sorted(counts.items()):
                print(f"  {character}:{state} {count}")
        if result["candidateContactSheet"]:
            print(f"candidateContactSheet={result['candidateContactSheet']}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
