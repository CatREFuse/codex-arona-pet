#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib

from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CHARACTER_ROOT = REPO_ROOT / "shared" / "Characters"
DEFAULT_SCHEMA = CHARACTER_ROOT / "plana" / "openplana-character.json"
CELL_SIZE = 256
EDGE_GUIDE_WIDTH = 4
FRAME_DURATION = 1 / 6
TEMPLATE_CHARACTER = "plana"
EDGE_LEAN_DEGREES = 10
EDGE_SIGN_LEAN_DEGREES = 4
EDGE_SIGN_MIN_WIDTH = 134

EDGE_SOURCES = {
    "edge-peek": "awaiting",
    "edge-success": "success",
    "edge-idle-read": "idle-read",
    "edge-idle-normal": "idle-normal",
    "edge-idle-sleep": "idle-sleep",
    "edge-coding": "coding",
    "edge-checking": "checking",
    "edge-awaiting": "awaiting",
    "edge-rejected": "rejected",
    "edge-pinched": "pinched",
}


def schema_extra_state(state: str) -> dict | None:
    data = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    config = data.get("extraStates", {}).get(state)
    return config if isinstance(config, dict) else None


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A")
    return alpha.point(lambda value: 255 if value > 16 else 0).getbbox()


def edge_state_name(prefix: str, side: str) -> str:
    return f"{prefix}-{side}"


def clear_edge_line_area(image: Image.Image) -> None:
    pixels = image.load()
    for y in range(CELL_SIZE):
        for x in range(EDGE_GUIDE_WIDTH):
            pixels[x, y] = (16, 16, 16, 255)
        for x in range(CELL_SIZE - EDGE_GUIDE_WIDTH, CELL_SIZE):
            pixels[x, y] = (0, 0, 0, 0)


def draw_edge_line(image: Image.Image, side: str) -> None:
    pixels = image.load()
    if side == "left":
        xs = range(EDGE_GUIDE_WIDTH)
    else:
        xs = range(CELL_SIZE - EDGE_GUIDE_WIDTH, CELL_SIZE)
    for y in range(CELL_SIZE):
        for x in xs:
            pixels[x, y] = (16, 16, 16, 255)


def visible_bounds(frame: Image.Image, side: str) -> tuple[int, int, int, int] | None:
    pixels = frame.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(CELL_SIZE):
        for x in range(CELL_SIZE):
            r, g, b, a = pixels[x, y]
            if a <= 16:
                continue
            if side == "left" and x < EDGE_GUIDE_WIDTH and r < 35 and g < 35 and b < 35:
                continue
            if side == "right" and x >= CELL_SIZE - EDGE_GUIDE_WIDTH and r < 35 and g < 35 and b < 35:
                continue
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def read_template_bounds(state: str, side: str) -> list[tuple[int, int, int, int] | None]:
    directory = CHARACTER_ROOT / TEMPLATE_CHARACTER / "extra" / state
    paths = sorted(directory.glob("*.png"))
    if len(paths) != 12:
        return [None] * 12
    return [visible_bounds(Image.open(path).convert("RGBA"), side) for path in paths]


def median_int(values: list[int], default: int) -> int:
    if not values:
        return default
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def template_for_frame(
    bounds: list[tuple[int, int, int, int] | None],
    index: int,
    side: str,
) -> tuple[int, int, int, int]:
    valid = [bound for bound in bounds if bound is not None]
    if not valid:
        width = 112
        return (EDGE_GUIDE_WIDTH if side == "left" else CELL_SIZE - EDGE_GUIDE_WIDTH - width, 10, width, 236)
    source = bounds[index] if index < len(bounds) and bounds[index] is not None else valid[0]
    assert source is not None
    widths = [bound[2] for bound in valid]
    heights = [bound[3] for bound in valid]
    width = median_int(widths, source[2])
    height = median_int(heights, source[3])
    x = EDGE_GUIDE_WIDTH if side == "left" else CELL_SIZE - EDGE_GUIDE_WIDTH - width
    return x, source[1], width, height


def stable_template(
    bounds: list[tuple[int, int, int, int] | None],
    side: str,
) -> tuple[int, int, int, int]:
    valid = [bound for bound in bounds if bound is not None]
    if not valid:
        width = 112
        return (EDGE_GUIDE_WIDTH if side == "left" else CELL_SIZE - EDGE_GUIDE_WIDTH - width, 10, width, 236)
    widths = [bound[2] for bound in valid]
    heights = [bound[3] for bound in valid]
    ys = [bound[1] for bound in valid]
    width = median_int(widths, valid[0][2])
    height = median_int(heights, valid[0][3])
    y = median_int(ys, valid[0][1])
    x = EDGE_GUIDE_WIDTH if side == "left" else CELL_SIZE - EDGE_GUIDE_WIDTH - width
    return x, y, width, height


def place_edge_frame(
    frame: Image.Image,
    side: str,
    template: tuple[int, int, int, int] | None = None,
    lean_degrees: int = EDGE_LEAN_DEGREES,
    min_target_width: int | None = None,
) -> Image.Image:
    rgba = frame.convert("RGBA")
    bbox = alpha_bbox(rgba)
    out = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    if bbox is None:
        draw_edge_line(out, side)
        return out

    cropped = rgba.crop(bbox)
    lean_degrees = -lean_degrees if side == "left" else lean_degrees
    cropped = cropped.rotate(
        lean_degrees,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(0, 0, 0, 0),
    )
    if template is None:
        target_x, target_y, target_width, target_height = (EDGE_GUIDE_WIDTH, 8, 116, 238)
        if side == "right":
            target_x = CELL_SIZE - EDGE_GUIDE_WIDTH - target_width
    else:
        target_x, target_y, target_width, target_height = template
    if min_target_width is not None and target_width < min_target_width:
        target_width = min_target_width
        if side == "right":
            target_x = CELL_SIZE - EDGE_GUIDE_WIDTH - target_width

    scale_y = min((target_height + 2) / cropped.height, 1.0)
    resized_height = max(1, round(cropped.height * scale_y))
    cropped = cropped.resize(
        (max(1, round(target_width)), resized_height),
        Image.Resampling.LANCZOS,
    )
    y = round(target_y + (target_height - cropped.height) / 2)
    y = max(8, min(CELL_SIZE - 8 - cropped.height, y))
    if side == "left":
        x = EDGE_GUIDE_WIDTH
    else:
        x = CELL_SIZE - EDGE_GUIDE_WIDTH - cropped.width

    out.alpha_composite(cropped, (x, y))
    draw_edge_line(out, side)
    return out


def read_frames(character: str, state: str) -> list[Image.Image]:
    directory = CHARACTER_ROOT / character / "extra" / state
    paths = sorted(directory.glob("*.png"))
    if len(paths) != 12:
        raise ValueError(f"{directory} expected 12 frames, got {len(paths)}")
    return [Image.open(path).convert("RGBA") for path in paths]


def write_contact_sheet(frames: list[Image.Image], output: pathlib.Path) -> None:
    thumb = 128
    columns = 4
    rows = 3
    sheet = Image.new("RGB", (columns * thumb, rows * thumb), (43, 43, 43))
    for index, frame in enumerate(frames):
        preview = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (43, 43, 43, 255))
        preview.alpha_composite(frame)
        sheet.paste(
            preview.convert("RGB").resize((thumb, thumb), Image.Resampling.LANCZOS),
            ((index % columns) * thumb, (index // columns) * thumb),
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def update_manifest(character: str, state: str) -> None:
    path = CHARACTER_ROOT / character / "openplana-character.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    schema_config = schema_extra_state(state) or {}
    data.setdefault("extraStates", {})[state] = {
        "framePaths": [f"extra/{state}/{index:02d}.png" for index in range(12)],
        "frameDuration": float(schema_config.get("frameDuration", FRAME_DURATION)),
        "loop": bool(schema_config.get("loop", True)),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def derive_state(character: str, prefix: str, source_state: str, side: str) -> None:
    state = edge_state_name(prefix, side)
    source_frames = read_frames(character, source_state)
    template_bounds = read_template_bounds(state, side)
    lean_degrees = EDGE_SIGN_LEAN_DEGREES if prefix in {"edge-success", "edge-rejected"} else EDGE_LEAN_DEGREES
    min_target_width = EDGE_SIGN_MIN_WIDTH if prefix in {"edge-success", "edge-rejected"} else None
    if prefix == "edge-idle-normal":
        source_frames = [source_frames[0].copy() for _ in source_frames]
    frames = [
        place_edge_frame(
            source_frame,
            side,
            template_for_frame(template_bounds, index, side),
            lean_degrees,
            min_target_width,
        )
        for index, source_frame in enumerate(source_frames)
    ]
    frames[-1] = frames[0].copy()

    out_dir = CHARACTER_ROOT / character / "extra" / state
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    for index, frame in enumerate(frames):
        frame.save(out_dir / f"{index:02d}.png")
    write_contact_sheet(frames, CHARACTER_ROOT / character / "qa" / f"{state}-contact-sheet.png")
    update_manifest(character, state)
    print(f"derived {character} {state} from {source_state}")


def main() -> int:
    for character_dir in sorted(CHARACTER_ROOT.glob("*-neo")):
        character = character_dir.name
        for prefix, source_state in EDGE_SOURCES.items():
            derive_state(character, prefix, source_state, "left")
            derive_state(character, prefix, source_state, "right")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
