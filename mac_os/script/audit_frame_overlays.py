#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys
from dataclasses import asdict, dataclass

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
QA_ROOT = ROOT / "docs" / "qa" / "current-target" / "overlay-audit"
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
EDGE_LINE_WIDTH = 4
WIDTH_DELTA_LIMIT = 22
HEIGHT_DELTA_LIMIT = 24
AREA_RATIO_LIMIT = 1.34
POSITION_X_WARNING_LIMIT = 28
POSITION_Y_WARNING_LIMIT = 28
IDLE_WIDTH_RANGE_LIMIT = 8
IDLE_CENTER_Y_RANGE_LIMIT = 4.0
IDLE_AREA_RATIO_LIMIT = 1.10

FRAME_COLORS = [
    (230, 63, 63, 86),
    (255, 140, 42, 86),
    (230, 190, 48, 86),
    (110, 190, 70, 86),
    (32, 180, 152, 86),
    (46, 150, 230, 86),
    (106, 116, 238, 86),
    (172, 92, 224, 86),
    (220, 70, 160, 86),
    (136, 136, 136, 86),
    (255, 255, 255, 72),
    (40, 40, 40, 92),
]


@dataclass
class FrameMetrics:
    frame: int
    bbox: tuple[int, int, int, int] | None
    width: int
    height: int
    visible: int
    cx: float
    cy: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", action="append")
    parser.add_argument("--json-out", type=pathlib.Path)
    return parser.parse_args()


def character_dirs(names: list[str] | None) -> list[pathlib.Path]:
    if names:
        return [CHARACTER_ROOT / name for name in names]
    return sorted(path for path in CHARACTER_ROOT.iterdir() if path.is_dir() and path.name.endswith("-neo"))


def edge_side(state: str) -> str | None:
    if state.startswith("edge-") and state.endswith("-left"):
        return "left"
    if state.startswith("edge-") and state.endswith("-right"):
        return "right"
    return None


def frame_for_metrics(image: Image.Image, state: str) -> Image.Image:
    side = edge_side(state)
    if side is None:
        return image
    image = image.copy()
    draw = ImageDraw.Draw(image)
    if side == "left":
        draw.rectangle((0, 0, EDGE_LINE_WIDTH - 1, image.height - 1), fill=(0, 0, 0, 0))
    else:
        draw.rectangle((image.width - EDGE_LINE_WIDTH, 0, image.width - 1, image.height - 1), fill=(0, 0, 0, 0))
    return image


def frame_metrics(image: Image.Image, state: str, index: int) -> FrameMetrics:
    metric_image = frame_for_metrics(image.convert("RGBA"), state)
    alpha = metric_image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > 16 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return FrameMetrics(index, None, 0, 0, 0, 0.0, 0.0)

    left, top, right, bottom = bbox
    visible = 0
    x_sum = 0
    y_sum = 0
    pixels = alpha.load()
    for y in range(top, bottom):
        for x in range(left, right):
            if pixels[x, y] <= 16:
                continue
            visible += 1
            x_sum += x
            y_sum += y
    if visible == 0:
        return FrameMetrics(index, None, 0, 0, 0, 0.0, 0.0)
    return FrameMetrics(
        index,
        bbox,
        right - left,
        bottom - top,
        visible,
        x_sum / visible,
        y_sum / visible,
    )


def load_manifest(character_dir: pathlib.Path) -> dict[str, object]:
    return json.loads((character_dir / "openplana-character.json").read_text(encoding="utf-8"))


def load_atlas_frames(character_dir: pathlib.Path) -> dict[str, list[Image.Image]]:
    manifest = load_manifest(character_dir)
    atlas_path = character_dir / str(manifest.get("spritesheetPath", "spritesheet.png"))
    atlas = Image.open(atlas_path).convert("RGBA")
    expected = (CELL_SIZE * ATLAS_COLUMNS, CELL_SIZE * len(ATLAS_ROWS))
    if atlas.size != expected:
        raise ValueError(f"{character_dir.name}: atlas size {atlas.size[0]}x{atlas.size[1]} != {expected[0]}x{expected[1]}")

    states: dict[str, list[Image.Image]] = {}
    for row, state in enumerate(ATLAS_ROWS):
        frames = []
        for index in range(ATLAS_COLUMNS):
            frames.append(atlas.crop((
                index * CELL_SIZE,
                row * CELL_SIZE,
                (index + 1) * CELL_SIZE,
                (row + 1) * CELL_SIZE,
            )))
        states[state] = frames
    return states


def load_extra_frames(character_dir: pathlib.Path) -> dict[str, tuple[list[Image.Image], bool]]:
    manifest = load_manifest(character_dir)
    states: dict[str, tuple[list[Image.Image], bool]] = {}
    for state, config in manifest.get("extraStates", {}).items():
        frame_paths = [character_dir / path for path in config.get("framePaths", [])]
        frames = [Image.open(path).convert("RGBA") for path in frame_paths]
        states[state] = (frames, bool(config.get("loop", True)))
    return states


def overlay_frame(image: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda value: min(value, color[3]) if value > 16 else 0)
    overlay = Image.new("RGBA", rgba.size, color)
    overlay.putalpha(alpha)
    return overlay


def checkerboard(size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGBA", size, (36, 36, 36, 255))
    draw = ImageDraw.Draw(image)
    tile = 16
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2 == 0:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=(46, 46, 46, 255))
    return image


def draw_overlay(path: pathlib.Path, state: str, frames: list[Image.Image], metrics: list[FrameMetrics]) -> None:
    canvas = checkerboard((CELL_SIZE, CELL_SIZE))
    for index, frame in enumerate(frames):
        canvas.alpha_composite(overlay_frame(frame, FRAME_COLORS[index % len(FRAME_COLORS)]))

    draw = ImageDraw.Draw(canvas)
    side = edge_side(state)
    if side == "left":
        draw.rectangle((0, 0, EDGE_LINE_WIDTH - 1, CELL_SIZE - 1), outline=(255, 255, 255, 180))
    elif side == "right":
        draw.rectangle((CELL_SIZE - EDGE_LINE_WIDTH, 0, CELL_SIZE - 1, CELL_SIZE - 1), outline=(255, 255, 255, 180))

    for index, item in enumerate(metrics):
        if item.bbox is None:
            continue
        color = FRAME_COLORS[index % len(FRAME_COLORS)]
        outline = (color[0], color[1], color[2], 210)
        draw.rectangle(item.bbox, outline=outline, width=1)

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def pair_indices(frame_count: int, loop: bool) -> list[tuple[int, int]]:
    pairs = [(index, index + 1) for index in range(max(0, frame_count - 1))]
    if loop and frame_count > 1:
        pairs.append((frame_count - 1, 0))
    return pairs


def analyze_state(character: str, state: str, frames: list[Image.Image], loop: bool, overlay_path: pathlib.Path) -> dict[str, object]:
    metrics = [frame_metrics(frame, state, index) for index, frame in enumerate(frames)]
    size_issues: list[dict[str, object]] = []
    position_warnings: list[dict[str, object]] = []

    for a_index, b_index in pair_indices(len(metrics), loop):
        a = metrics[a_index]
        b = metrics[b_index]
        if a.bbox is None or b.bbox is None:
            size_issues.append({
                "character": character,
                "state": state,
                "frame": a_index,
                "nextFrame": b_index,
                "reason": "blank frame",
            })
            continue

        reasons: list[str] = []
        width_delta = abs(a.width - b.width)
        height_delta = abs(a.height - b.height)
        area_ratio = max(a.visible, b.visible) / max(1, min(a.visible, b.visible))
        if width_delta > WIDTH_DELTA_LIMIT:
            reasons.append(f"width delta {width_delta}")
        if height_delta > HEIGHT_DELTA_LIMIT:
            reasons.append(f"height delta {height_delta}")
        if area_ratio > AREA_RATIO_LIMIT:
            reasons.append(f"visible-area ratio {area_ratio:.2f}")
        if reasons:
            size_issues.append({
                "character": character,
                "state": state,
                "frame": a_index,
                "nextFrame": b_index,
                "reason": "; ".join(reasons),
            })

        cx_delta = abs(a.cx - b.cx)
        cy_delta = abs(a.cy - b.cy)
        position_reasons: list[str] = []
        if cx_delta > POSITION_X_WARNING_LIMIT:
            position_reasons.append(f"center-x delta {cx_delta:.1f}")
        if cy_delta > POSITION_Y_WARNING_LIMIT:
            position_reasons.append(f"center-y delta {cy_delta:.1f}")
        if position_reasons:
            position_warnings.append({
                "character": character,
                "state": state,
                "frame": a_index,
                "nextFrame": b_index,
                "reason": "; ".join(position_reasons),
            })

    draw_overlay(overlay_path, state, frames, metrics)
    visible_metrics = [item for item in metrics if item.bbox is not None]
    widths = [item.width for item in visible_metrics]
    heights = [item.height for item in visible_metrics]
    areas = [item.visible for item in visible_metrics]
    center_ys = [item.cy for item in visible_metrics]
    if state == "idle" and visible_metrics:
        idle_reasons: list[str] = []
        width_range = max(widths) - min(widths)
        area_ratio = max(areas) / max(1, min(areas))
        center_y_range = max(center_ys) - min(center_ys)
        if width_range > IDLE_WIDTH_RANGE_LIMIT:
            idle_reasons.append(f"idle width range {width_range}")
        if area_ratio > IDLE_AREA_RATIO_LIMIT:
            idle_reasons.append(f"idle visible-area range ratio {area_ratio:.2f}")
        if center_y_range > IDLE_CENTER_Y_RANGE_LIMIT:
            idle_reasons.append(f"idle center-y range {center_y_range:.1f}")
        if idle_reasons:
            size_issues.append({
                "character": character,
                "state": state,
                "frame": 0,
                "nextFrame": len(metrics) - 1,
                "reason": "; ".join(idle_reasons),
            })
    return {
        "frameCount": len(frames),
        "loop": loop,
        "overlayPath": str(overlay_path.relative_to(REPO_ROOT)),
        "metrics": [asdict(item) for item in metrics],
        "ranges": {
            "width": [min(widths), max(widths)] if widths else [0, 0],
            "height": [min(heights), max(heights)] if heights else [0, 0],
            "visible": [min(areas), max(areas)] if areas else [0, 0],
        },
        "sizeIssues": size_issues,
        "positionWarnings": position_warnings,
    }


def draw_overview(output: pathlib.Path, state_reports: dict[str, dict[str, object]]) -> pathlib.Path:
    items = sorted((state, pathlib.Path(str(report["overlayPath"]))) for state, report in state_reports.items())
    thumb = 128
    label_height = 28
    columns = 6
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * thumb, rows * (thumb + label_height)), (28, 28, 28, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for item_index, (state, relative_path) in enumerate(items):
        image = Image.open(REPO_ROOT / relative_path).convert("RGBA").resize((thumb, thumb), Image.Resampling.LANCZOS)
        x = (item_index % columns) * thumb
        y = (item_index // columns) * (thumb + label_height)
        sheet.alpha_composite(image, (x, y + label_height))
        draw.rectangle((x, y, x + thumb, y + label_height), fill=(18, 18, 18, 255))
        draw.text((x + 4, y + 7), state[:22], fill=(235, 235, 235, 255), font=font)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(output)
    return output


def main() -> int:
    args = parse_args()
    result: dict[str, object] = {
        "ok": True,
        "thresholds": {
            "widthDelta": WIDTH_DELTA_LIMIT,
            "heightDelta": HEIGHT_DELTA_LIMIT,
            "visibleAreaRatio": AREA_RATIO_LIMIT,
            "edgeLineWidthExcluded": EDGE_LINE_WIDTH,
            "idleWidthRange": IDLE_WIDTH_RANGE_LIMIT,
            "idleVisibleAreaRatio": IDLE_AREA_RATIO_LIMIT,
            "idleCenterYRange": IDLE_CENTER_Y_RANGE_LIMIT,
        },
        "characters": {},
        "sizeIssues": [],
        "positionWarnings": [],
    }

    for character_dir in character_dirs(args.character):
        manifest = load_manifest(character_dir)
        character = str(manifest["id"])
        overlay_root = QA_ROOT / character / "states"
        state_reports: dict[str, dict[str, object]] = {}

        for state, frames in load_atlas_frames(character_dir).items():
            state_reports[state] = analyze_state(character, state, frames, True, overlay_root / f"{state}.png")

        for state, (frames, loop) in load_extra_frames(character_dir).items():
            state_reports[state] = analyze_state(character, state, frames, loop, overlay_root / f"{state}.png")

        overview = draw_overview(QA_ROOT / character / "overview.png", state_reports)
        character_report = {
            "displayName": manifest.get("displayName", character),
            "overviewPath": str(overview.relative_to(REPO_ROOT)),
            "states": state_reports,
        }
        result["characters"][character] = character_report

        for state, report in state_reports.items():
            result["sizeIssues"].extend(report["sizeIssues"])
            result["positionWarnings"].extend(report["positionWarnings"])

    result["ok"] = len(result["sizeIssues"]) == 0
    output_path = args.json_out or (QA_ROOT / "overlay-audit.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"ok={str(result['ok']).lower()}")
    print(f"sizeIssues={len(result['sizeIssues'])}")
    print(f"positionWarnings={len(result['positionWarnings'])}")
    print(f"report={output_path.relative_to(REPO_ROOT)}")
    for issue in result["sizeIssues"][:40]:
        print(f"size {issue['character']}:{issue['state']} {issue['frame']}->{issue['nextFrame']} {issue['reason']}")
    if len(result["sizeIssues"]) > 40:
        print(f"size ... {len(result['sizeIssues']) - 40} more")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
