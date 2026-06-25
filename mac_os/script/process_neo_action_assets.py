#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import pathlib
from collections import deque
from dataclasses import dataclass

from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CHARACTER_ROOT = REPO_ROOT / "shared" / "Characters"
ACTION_MANIFEST = REPO_ROOT / ".codex" / "tmp" / "neo-pets" / "action-generation-manifest.json"
CELL_SIZE = 256
CONTENT_SIZE = 238
EDGE_GUIDE_WIDTH = 4
FRAME_DURATION = 0.1666666667
ATLAS_COLUMNS = 12
ATLAS_ROWS = 9
ATLAS_SIZE = (CELL_SIZE * ATLAS_COLUMNS, CELL_SIZE * ATLAS_ROWS)
KEY_COLORS = {
    "plana": (0, 255, 0),
    "plana-neo": (0, 255, 0),
    "arona": (255, 0, 255),
    "arona-neo": (255, 0, 255),
}


@dataclass
class Component:
    count: int
    bbox: tuple[int, int, int, int]
    cx: float
    cy: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=pathlib.Path, default=ACTION_MANIFEST)
    parser.add_argument("--character")
    parser.add_argument("--state")
    return parser.parse_args()


def edge_side(state: str) -> str | None:
    if state.startswith("edge-") and state.endswith("-left"):
        return "left"
    if state.startswith("edge-") and state.endswith("-right"):
        return "right"
    return None


def key_color(character: str) -> tuple[int, int, int]:
    return KEY_COLORS.get(character, (0, 255, 0))


def grid_layout(frame_count: int) -> tuple[int, int]:
    if frame_count <= 0:
        raise ValueError(f"frame_count must be positive, got {frame_count}")
    if frame_count == 12:
        return 4, 3
    columns = max(1, math.ceil(math.sqrt(frame_count * 4 / 3)))
    rows = math.ceil(frame_count / columns)
    return columns, rows


def is_bg_green(r: int, g: int, b: int) -> bool:
    green_dominance = g - max(r, b)
    return g >= 105 and green_dominance >= 24 and b <= g - 18


def is_green_fringe(r: int, g: int, b: int) -> bool:
    green_dominance = g - max(r, b)
    return g >= 95 and green_dominance >= 14 and b <= g - 8


def is_bg_magenta(r: int, g: int, b: int) -> bool:
    magenta_strength = min(r, b) - g
    return min(r, b) >= 105 and magenta_strength >= 28 and abs(r - b) <= 88


def is_magenta_fringe(r: int, g: int, b: int) -> bool:
    magenta_strength = min(r, b) - g
    return min(r, b) >= 92 and magenta_strength >= 14 and abs(r - b) <= 112


def is_bg_key(r: int, g: int, b: int, key: tuple[int, int, int]) -> bool:
    if key == (255, 0, 255):
        return is_bg_magenta(r, g, b)
    return is_bg_green(r, g, b)


def is_key_fringe(r: int, g: int, b: int, key: tuple[int, int, int]) -> bool:
    if key == (255, 0, 255):
        return is_magenta_fringe(r, g, b)
    return is_green_fringe(r, g, b)


def reduce_key_spill(r: int, g: int, b: int, key: tuple[int, int, int]) -> tuple[int, int, int]:
    if key == (255, 0, 255):
        spill = max(0, min(r, b) - g)
        if spill <= 0:
            return r, g, b
        target = max(g + 10, min(r, b) - min(spill, 36))
        return min(r, target), g, min(b, target)
    return r, min(g, max(r, b) + 8), b


def should_preserve_success_green(
    component: list[tuple[int, int]],
    width: int,
    height: int,
    preserve_green_sign: bool,
) -> bool:
    if not preserve_green_sign:
        return False
    if len(component) < 180:
        return False
    min_x = min(x for x, _ in component)
    max_x = max(x for x, _ in component)
    min_y = min(y for _, y in component)
    max_y = max(y for _, y in component)
    component_width = max_x - min_x + 1
    component_height = max_y - min_y + 1
    center_y = (min_y + max_y) / 2
    touches_outer_edge = min_x <= 2 or max_x >= width - 3 or min_y <= 2 or max_y >= height - 3
    if touches_outer_edge:
        return False
    if center_y < height * 0.26:
        return False
    if component_width < 12 or component_height < 8:
        return False
    if component_width < component_height * 0.75:
        return False
    return True


def flood_green_components(mask: list[list[bool]], width: int, height: int) -> tuple[set[tuple[int, int]], list[list[tuple[int, int]]]]:
    visited: set[tuple[int, int]] = set()
    border: set[tuple[int, int]] = set()
    enclosed: list[list[tuple[int, int]]] = []

    def walk(start: tuple[int, int]) -> list[tuple[int, int]]:
        component: list[tuple[int, int]] = []
        queue: deque[tuple[int, int]] = deque([start])
        visited.add(start)
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if nx < 0 or nx >= width or ny < 0 or ny >= height:
                    continue
                point = (nx, ny)
                if point in visited or not mask[ny][nx]:
                    continue
                visited.add(point)
                queue.append(point)
        return component

    for x in range(width):
        for y in (0, height - 1):
            if mask[y][x] and (x, y) not in visited:
                border.update(walk((x, y)))
    for y in range(height):
        for x in (0, width - 1):
            if mask[y][x] and (x, y) not in visited:
                border.update(walk((x, y)))

    for y in range(height):
        for x in range(width):
            if mask[y][x] and (x, y) not in visited:
                enclosed.append(walk((x, y)))

    return border, enclosed


def has_transparent_neighbor(removable: set[tuple[int, int]], x: int, y: int, width: int, height: int) -> bool:
    for ny in range(max(0, y - 1), min(height, y + 2)):
        for nx in range(max(0, x - 1), min(width, x + 2)):
            if (nx, ny) in removable:
                return True
    return False


def remove_chroma_background(image: Image.Image, character: str, preserve_green_sign: bool = False) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    key = key_color(character)

    mask = [
        [
            pixels[x, y][3] > 0 and is_bg_key(pixels[x, y][0], pixels[x, y][1], pixels[x, y][2], key)
            for x in range(width)
        ]
        for y in range(height)
    ]
    removable, enclosed_components = flood_green_components(mask, width, height)
    preserved_success_green: set[tuple[int, int]] = set()
    for component in enclosed_components:
        if key == (0, 255, 0) and should_preserve_success_green(component, width, height, preserve_green_sign):
            preserved_success_green.update(component)
        else:
            removable.update(component)

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if (x, y) in removable:
                pixels[x, y] = (0, 0, 0, 0)
            elif (x, y) in preserved_success_green:
                pixels[x, y] = (min(r, 60), max(g, 155), min(b, 95), a)
            elif is_key_fringe(r, g, b, key) and has_transparent_neighbor(removable, x, y, width, height):
                nr, ng, nb = reduce_key_spill(r, g, b, key)
                pixels[x, y] = (nr, ng, nb, max(0, int(a * 0.45)))
            elif is_bg_key(r, g, b, key):
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def remove_green_background(image: Image.Image, preserve_green_sign: bool = False) -> Image.Image:
    return remove_chroma_background(image, "plana", preserve_green_sign)


def strip_source_edge_line(frame: Image.Image, state: str) -> Image.Image:
    side = edge_side(state)
    if side is None:
        return frame

    rgba = frame.copy()
    pixels = rgba.load()
    width, height = rgba.size
    if side == "left":
        xs = range(min(16, width))
    else:
        xs = range(max(0, width - 16), width)
    for y in range(height):
        for x in xs:
            r, g, b, a = pixels[x, y]
            if a > 16 and r < 45 and g < 45 and b < 45:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def normalize_frame(frame: Image.Image, state: str) -> Image.Image:
    alpha = frame.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > 12 else 0).getbbox()
    if bbox is None:
        return Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))

    cropped = frame.crop(bbox)
    scale = min(CONTENT_SIZE / cropped.width, CONTENT_SIZE / cropped.height)
    resized = cropped.resize(
        (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))),
        Image.Resampling.LANCZOS,
    )
    out = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    side = edge_side(state)
    if side == "left":
        x = EDGE_GUIDE_WIDTH
    elif side == "right":
        x = CELL_SIZE - EDGE_GUIDE_WIDTH - resized.width
    else:
        x = (CELL_SIZE - resized.width) // 2
    y = (CELL_SIZE - resized.height) // 2
    out.alpha_composite(resized, (x, y))
    if side == "left":
        for line_x in range(EDGE_GUIDE_WIDTH):
            for line_y in range(CELL_SIZE):
                out.putpixel((line_x, line_y), (16, 16, 16, 255))
    elif side == "right":
        for line_x in range(CELL_SIZE - EDGE_GUIDE_WIDTH, CELL_SIZE):
            for line_y in range(CELL_SIZE):
                out.putpixel((line_x, line_y), (16, 16, 16, 255))
    return out


def alpha_components(image: Image.Image) -> list[Component]:
    pixels = image.load()
    width, height = image.size
    visited: set[tuple[int, int]] = set()
    components: list[Component] = []

    for y in range(height):
        for x in range(width):
            if (x, y) in visited or pixels[x, y][3] <= 16:
                continue
            queue: deque[tuple[int, int]] = deque([(x, y)])
            visited.add((x, y))
            xs: list[int] = []
            ys: list[int] = []
            while queue:
                px, py = queue.popleft()
                xs.append(px)
                ys.append(py)
                for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        continue
                    point = (nx, ny)
                    if point in visited or pixels[nx, ny][3] <= 16:
                        continue
                    visited.add(point)
                    queue.append(point)
            count = len(xs)
            components.append(
                Component(
                    count=count,
                    bbox=(min(xs), min(ys), max(xs) + 1, max(ys) + 1),
                    cx=sum(xs) / count,
                    cy=sum(ys) / count,
                )
            )
    return components


def component_grid_frames(
    path: pathlib.Path,
    frame_count: int,
    character: str,
    preserve_green_sign: bool,
) -> list[Image.Image] | None:
    source = Image.open(path).convert("RGBA")
    keyed = remove_chroma_background(source, character, preserve_green_sign=preserve_green_sign)
    components = alpha_components(keyed)
    body_components = [component for component in components if component.count >= 1000]
    if len(body_components) < frame_count:
        return None

    selected = sorted(body_components, key=lambda component: component.count, reverse=True)[:frame_count]
    ordered_rows = []
    for row_start in range(0, frame_count, 4):
        row = sorted(selected, key=lambda component: component.cy)[row_start : row_start + 4]
        if len(row) != 4:
            return None
        ordered_rows.append(sorted(row, key=lambda component: component.cx))

    row_centers = [sum(component.cy for component in row) / len(row) for row in ordered_rows]
    column_centers = [
        sum(ordered_rows[row][column].cx for row in range(len(ordered_rows))) / len(ordered_rows)
        for column in range(4)
    ]
    row_bounds = [0]
    for upper, lower in zip(row_centers, row_centers[1:]):
        row_bounds.append(round((upper + lower) / 2))
    row_bounds.append(keyed.height)
    column_bounds = [0]
    for left, right in zip(column_centers, column_centers[1:]):
        column_bounds.append(round((left + right) / 2))
    column_bounds.append(keyed.width)

    frames: list[Image.Image] = []
    for row in range(3):
        for column in range(4):
            left = column_bounds[column]
            right = column_bounds[column + 1]
            top = row_bounds[row]
            bottom = row_bounds[row + 1]
            cell_components = [
                component
                for component in components
                if component.count >= 8 and left <= component.cx < right and top <= component.cy < bottom
            ]
            if not cell_components:
                return None
            min_x = max(0, min(component.bbox[0] for component in cell_components) - 16)
            min_y = max(0, min(component.bbox[1] for component in cell_components) - 16)
            max_x = min(keyed.width, max(component.bbox[2] for component in cell_components) + 16)
            max_y = min(keyed.height, max(component.bbox[3] for component in cell_components) + 16)
            frames.append(keyed.crop((min_x, min_y, max_x, max_y)))
    return frames


def crop_grid(
    path: pathlib.Path,
    frame_count: int,
    character: str | None = None,
    preserve_green_sign: bool = False,
    state: str | None = None,
) -> list[Image.Image]:
    source = Image.open(path).convert("RGBA")
    columns, rows = grid_layout(frame_count)
    expected_ratio = columns / rows
    actual_ratio = source.width / source.height
    if abs(actual_ratio - expected_ratio) > 0.05:
        raise ValueError(
            f"{path} must be a {columns}:{rows} source sheet with square frame slots; got {source.width}x{source.height}"
        )
    frames = []
    for index in range(frame_count):
        col = index % columns
        row = index // columns
        cell_left = round(col * source.width / columns)
        cell_right = round((col + 1) * source.width / columns)
        top = round(row * source.height / rows)
        bottom = round((row + 1) * source.height / rows)
        left = cell_left
        right = cell_right
        side = edge_side(state or "")
        if side:
            cell = source.crop((cell_left, top, cell_right, bottom))
            cell_width = cell_right - cell_left
            crop_width = round(cell_width * 0.75)
            local_left = 0 if side == "left" else cell_width - crop_width
            if character:
                keyed = strip_source_edge_line(
                    remove_chroma_background(cell, character, preserve_green_sign=preserve_green_sign),
                    state or "",
                )
                components = [
                    component
                    for component in alpha_components(keyed)
                    if component.count >= 120
                    and not (
                        component.bbox[2] - component.bbox[0] <= 6
                        and component.bbox[3] - component.bbox[1] >= keyed.height * 0.6
                    )
                ]
                if components:
                    if side == "left":
                        side_components = [
                            component for component in components
                            if component.bbox[0] <= cell_width * 0.55
                        ]
                    else:
                        side_components = [
                            component for component in components
                            if component.bbox[2] >= cell_width * 0.45
                        ]
                    if not side_components:
                        side_components = components
                    main_count = max(component.count for component in side_components)
                    kept = [
                        component for component in side_components
                        if component.count >= max(120, main_count * 0.06)
                    ]
                    min_x = min(component.bbox[0] for component in kept)
                    max_x = max(component.bbox[2] for component in kept)
                    margin = max(4, round(cell_width * 0.02))
                    if side == "left":
                        local_left = min(cell_width - crop_width, max(0, max_x + margin - crop_width))
                    else:
                        local_left = max(0, min(cell_width - crop_width, min_x - margin))
            if side == "left":
                left = cell_left + local_left
                right = left + crop_width
            else:
                left = cell_left + local_left
                right = left + crop_width
        frames.append(source.crop((left, top, right, bottom)))
    return frames


def make_contact_sheet(frames: list[Image.Image], output: pathlib.Path) -> None:
    thumb = 128
    columns = 4
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb, rows * thumb), (43, 43, 43))
    for index, frame in enumerate(frames):
        preview = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (43, 43, 43, 255))
        preview.alpha_composite(frame)
        sheet.paste(preview.convert("RGB").resize((thumb, thumb), Image.Resampling.LANCZOS), ((index % columns) * thumb, (index // columns) * thumb))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def make_atlas_contact_sheet(atlas: Image.Image, output: pathlib.Path) -> None:
    thumb = 96
    sheet = Image.new("RGB", (ATLAS_COLUMNS * thumb, ATLAS_ROWS * thumb), (43, 43, 43))
    for row in range(ATLAS_ROWS):
        for column in range(ATLAS_COLUMNS):
            cell = atlas.crop((column * CELL_SIZE, row * CELL_SIZE, (column + 1) * CELL_SIZE, (row + 1) * CELL_SIZE))
            preview = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (43, 43, 43, 255))
            preview.alpha_composite(cell)
            sheet.paste(preview.convert("RGB").resize((thumb, thumb), Image.Resampling.LANCZOS), (column * thumb, row * thumb))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def update_character_manifest(character: str, state: str, frame_count: int, loop: bool, frame_duration: float) -> None:
    path = CHARACTER_ROOT / character / "openplana-character.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    extra_states = data.setdefault("extraStates", {})
    extra_states[state] = {
        "framePaths": [f"extra/{state}/{index:02d}.png" for index in range(frame_count)],
        "frameDuration": frame_duration,
        "loop": loop,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_grid_path(action: dict) -> pathlib.Path:
    if "sourceGridPath" in action:
        return REPO_ROOT / action["sourceGridPath"]
    return (REPO_ROOT / action["sourceStripPath"]).with_name("source-grid-chroma.png")


def prepared_frames(action: dict) -> list[Image.Image] | None:
    grid = source_grid_path(action)
    if not grid.exists():
        return None

    frame_count = int(action["frameCount"])
    state = action["state"]
    preserve_green_sign = "success" in state
    raw_frames = None
    if frame_count == 12 and edge_side(state) is None:
        raw_frames = component_grid_frames(
            grid,
            frame_count,
            action["character"],
            preserve_green_sign=preserve_green_sign,
        )
    if raw_frames is None:
        raw_frames = crop_grid(
            grid,
            frame_count,
            action["character"],
            preserve_green_sign=preserve_green_sign,
            state=state,
        )
    frames = [
        normalize_frame(
            strip_source_edge_line(
                remove_chroma_background(frame, action["character"], preserve_green_sign=preserve_green_sign),
                state,
            ),
            state,
        )
        for frame in raw_frames
    ]
    if action.get("loop", True) and frames:
        frames[-1] = frames[0].copy()
    return frames


def process_extra_action(action: dict) -> bool:
    frames = prepared_frames(action)
    if frames is None:
        return False

    character = action["character"]
    state = action["state"]
    frame_count = int(action["frameCount"])
    out_dir = CHARACTER_ROOT / character / "extra" / state
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    for index, frame in enumerate(frames):
        frame.save(out_dir / f"{index:02d}.png")
    make_contact_sheet(frames, CHARACTER_ROOT / character / "qa" / f"{state}-contact-sheet.png")
    update_character_manifest(character, state, frame_count, bool(action.get("loop", True)), float(action.get("frameDuration", FRAME_DURATION)))
    print(f"processed {character} {state}")
    return True


def process_atlas_row(action: dict) -> bool:
    frames = prepared_frames(action)
    if frames is None:
        return False

    character = action["character"]
    row = int(action["row"])
    state = action["state"]
    atlas_path = CHARACTER_ROOT / character / "spritesheet.png"
    if atlas_path.exists():
        atlas = Image.open(atlas_path).convert("RGBA")
    else:
        atlas = Image.new("RGBA", ATLAS_SIZE, (0, 0, 0, 0))
    if atlas.size != ATLAS_SIZE:
        raise ValueError(f"{atlas_path} expected {ATLAS_SIZE}, got {atlas.size}")

    for column, frame in enumerate(frames):
        x = column * CELL_SIZE
        y = row * CELL_SIZE
        atlas.paste((0, 0, 0, 0), (x, y, x + CELL_SIZE, y + CELL_SIZE))
        atlas.alpha_composite(frame, (x, y))

    character_dir = CHARACTER_ROOT / character
    atlas.save(character_dir / "spritesheet.png")
    atlas.save(character_dir / "spritesheet.webp", lossless=True, quality=100)
    make_contact_sheet(frames, character_dir / "qa" / f"atlas-{state}-contact-sheet.png")
    make_atlas_contact_sheet(atlas, character_dir / "qa" / "atlas-contact-sheet.png")
    print(f"processed {character} atlas {state}")
    return True


def process_action(action: dict) -> bool:
    if action["kind"] == "extra-state":
        return process_extra_action(action)
    if action["kind"] == "atlas-row":
        return process_atlas_row(action)
    return False


def main() -> int:
    args = parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    count = 0
    for action in data["actions"]:
        if args.character and action["character"] != args.character:
            continue
        if args.state and action["state"] != args.state:
            continue
        if process_action(action):
            count += 1
    print(f"processed_count={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
