#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageEnhance, ImageOps


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CHARACTER_ROOT = REPO_ROOT / "shared" / "Characters"
CELL_SIZE = 256
CONTENT_SIZE = 228
ATLAS_COLUMNS = 12
ATLAS_ROWS = 9
ATLAS_SIZE = (CELL_SIZE * ATLAS_COLUMNS, CELL_SIZE * ATLAS_ROWS)
FRAME_DURATION = 1 / 6


@dataclass(frozen=True)
class RowMotion:
    mirror: bool = False
    x: tuple[int, ...] = (0,) * ATLAS_COLUMNS
    y: tuple[int, ...] = (0,) * ATLAS_COLUMNS


MOTIONS = [
    RowMotion(y=(0, -1, -1, -2, -1, 0, 1, 1, 0, -1, -1, 0)),
    RowMotion(x=(0, 1, 2, 3, 2, 1, 0, -1, -2, -3, -2, 0)),
    RowMotion(mirror=True, x=(0, -1, -2, -3, -2, -1, 0, 1, 2, 3, 2, 0)),
    RowMotion(y=(0, -1, -2, -1, 0, 1, 2, 1, 0, -1, -1, 0)),
    RowMotion(y=(0, -2, -4, -6, -8, -6, -4, -2, 0, 1, 0, 0)),
    RowMotion(y=(0, 1, 2, 2, 1, 0, -1, 0, 1, 2, 1, 0)),
    RowMotion(y=(0, 0, -1, 0, 1, 0, -1, 0, 1, 0, 0, 0)),
    RowMotion(x=(0, 1, 1, 2, 1, 0, -1, -1, -2, -1, 0, 0)),
    RowMotion(y=(0, -1, 0, 1, 0, -1, 0, 1, 0, -1, 0, 0)),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def remove_green_background(source: pathlib.Path) -> Image.Image:
    image = Image.open(source).convert("RGBA")
    pixels = image.load()
    width, height = image.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            green_dominance = g - max(r, b)
            bg_like = g >= 115 and green_dominance >= 30 and b <= g - 24
            fringe_like = g >= 100 and green_dominance >= 18 and b <= g - 12
            if bg_like:
                pixels[x, y] = (0, 0, 0, 0)
            elif fringe_like:
                new_alpha = max(0, min(a, int(a * 0.45)))
                pixels[x, y] = (r, min(g, max(r, b) + 10), b, new_alpha)
            elif g > max(r, b) + 8:
                pixels[x, y] = (r, max(r, b) + 8, b, a)

    return image


def normalize_to_cell(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > 12 else 0).getbbox()
    if bbox is None:
        raise ValueError("source has no visible pixels after chroma key removal")

    cropped = image.crop(bbox)
    scale = min(CONTENT_SIZE / cropped.width, CONTENT_SIZE / cropped.height)
    resized = cropped.resize(
        (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))),
        Image.Resampling.LANCZOS,
    )

    frame = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    x = (CELL_SIZE - resized.width) // 2
    y = max(16, min(CELL_SIZE - resized.height - 10, (CELL_SIZE - resized.height) // 2))
    frame.alpha_composite(resized, (x, y))
    return frame


def shifted_frame(base: Image.Image, motion: RowMotion, index: int) -> Image.Image:
    frame = ImageOps.mirror(base) if motion.mirror else base
    if index in (3, 4, 5, 8):
        frame = ImageEnhance.Brightness(frame).enhance(1.0 + (0.015 if index % 2 else -0.01))

    out = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    out.alpha_composite(frame, (motion.x[index], motion.y[index]))
    return out


def make_atlas(base: Image.Image) -> Image.Image:
    atlas = Image.new("RGBA", ATLAS_SIZE, (0, 0, 0, 0))
    for row, motion in enumerate(MOTIONS):
        for column in range(ATLAS_COLUMNS):
            frame = shifted_frame(base, motion, column)
            atlas.alpha_composite(frame, (column * CELL_SIZE, row * CELL_SIZE))
    return atlas


def make_contact_sheet(atlas: Image.Image, output: pathlib.Path) -> None:
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


def alpha_bounds(image: Image.Image) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > 16 else 0).getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    return (left, top, right - left, bottom - top)


def write_character(args: argparse.Namespace) -> None:
    out_dir = CHARACTER_ROOT / args.id
    if out_dir.exists() and not args.force:
        raise FileExistsError(f"{out_dir} already exists; pass --force")
    out_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = out_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    keyed = remove_green_background(args.source)
    base = normalize_to_cell(keyed)
    atlas = make_atlas(base)

    source_copy = qa_dir / "source-green.png"
    Image.open(args.source).save(source_copy)
    keyed.save(qa_dir / "source-keyed-full.png")
    base.save(qa_dir / "base-frame.png")
    atlas.save(out_dir / "spritesheet.png")
    atlas.save(out_dir / "spritesheet.webp", lossless=True, quality=100)
    make_contact_sheet(atlas, qa_dir / "base-contact-sheet.png")

    pet = {
        "id": args.id,
        "displayName": args.display_name,
        "description": args.description,
        "spritesheetPath": "spritesheet.webp",
    }
    manifest = {
        "id": args.id,
        "displayName": args.display_name,
        "description": args.description,
        "spritesheetPath": "spritesheet.png",
        "codexSpritesheetPath": "spritesheet.webp",
    }
    (out_dir / "pet.json").write_text(json.dumps(pet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "openplana-character.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics = {
        "id": args.id,
        "source": str(args.source),
        "sourceSize": Image.open(args.source).size,
        "baseBounds": alpha_bounds(base),
        "atlasSize": atlas.size,
        "cornerAlpha": [
            atlas.getpixel((0, 0))[3],
            atlas.getpixel((ATLAS_SIZE[0] - 1, 0))[3],
            atlas.getpixel((0, ATLAS_SIZE[1] - 1))[3],
            atlas.getpixel((ATLAS_SIZE[0] - 1, ATLAS_SIZE[1] - 1))[3],
        ],
        "note": "base-stage atlas uses generated identity art with lightweight deterministic row motion; action-specific imagegen rows are still required for final full animation fidelity.",
    }
    (qa_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out_dir)


def main() -> int:
    args = parse_args()
    write_character(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
