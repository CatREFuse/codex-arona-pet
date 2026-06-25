#!/usr/bin/env python3
import argparse
import json
import pathlib
import shutil
import subprocess
import tempfile
from typing import Iterable


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CHARACTER_DIR = REPO_ROOT / "shared" / "Characters" / "plana"
MANIFEST_PATH = CHARACTER_DIR / "openplana-character.json"
EXTRA_DIR = CHARACTER_DIR / "extra"
FRAME_SIZE = (256, 256)
CONTENT_SIZE = (240, 240)
FRAME_COUNT = 12
SPRITE_ROWS = 9
SPRITESHEET_SIZE = (FRAME_SIZE[0] * FRAME_COUNT, FRAME_SIZE[1] * SPRITE_ROWS)
FRAME_DURATION = 1 / 6
LEGACY_SPRITESHEET_SIZE = (1536, 1872)
LEGACY_FRAME_SIZE = (192, 208)
LEGACY_COLUMNS = 8
LEGACY_ROW_FRAME_COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6]
NON_LOOP_STATES = {
    "pinched",
    "edge-pinched-left",
    "edge-pinched-right",
    "edge-peek-left",
    "edge-peek-right",
}


def magick() -> str:
    path = shutil.which("magick") or "/opt/homebrew/bin/magick"
    if not pathlib.Path(path).exists():
        raise FileNotFoundError("ImageMagick is required: magick not found")
    return path


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def image_size(path: pathlib.Path) -> tuple[int, int]:
    output = subprocess.check_output(
        [magick(), "identify", "-format", "%[width]x%[height]", str(path)],
        text=True,
    )
    width, height = output.split("x", 1)
    return int(width), int(height)


def frame_paths(directory: pathlib.Path) -> list[pathlib.Path]:
    return sorted(directory.glob("[0-9][0-9].png"))


def resample_indices(source_count: int, loop: bool) -> list[int]:
    if source_count <= 0:
        raise ValueError("no source frames")
    if source_count == FRAME_COUNT and not loop:
        return list(range(FRAME_COUNT))
    if loop:
        forward_count = FRAME_COUNT // 2
        if source_count == 1:
            forward = [0] * forward_count
        else:
            forward = [
                round(index * (source_count - 1) / max(forward_count - 1, 1))
                for index in range(forward_count)
            ]
        return forward + list(reversed(forward))
    return [(index * source_count) // FRAME_COUNT for index in range(FRAME_COUNT)]


def normalize_frame(source: pathlib.Path, output: pathlib.Path, gravity: str = "center") -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if image_size(source) == FRAME_SIZE:
        shutil.copy2(source, output)
        return
    run([
        magick(),
        str(source),
        "-alpha",
        "on",
        "-filter",
        "Lanczos",
        "-resize",
        f"{CONTENT_SIZE[0]}x{CONTENT_SIZE[1]}",
        "-background",
        "none",
        "-gravity",
        gravity,
        "-extent",
        f"{FRAME_SIZE[0]}x{FRAME_SIZE[1]}",
        "-unsharp",
        "0x0.6+1.2+0.02",
        "-define",
        "png:color-type=6",
        str(output),
    ])


def source_spritesheet_path(source_character_dir: pathlib.Path) -> pathlib.Path:
    for name in ("spritesheet.png", "spritesheet.webp"):
        candidate = source_character_dir / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no source spritesheet under {source_character_dir}")


def spritesheet_layout(source: pathlib.Path) -> tuple[int, int, int, list[int]]:
    size = image_size(source)
    if size == SPRITESHEET_SIZE:
        return FRAME_SIZE[0], FRAME_SIZE[1], FRAME_COUNT, [FRAME_COUNT] * SPRITE_ROWS
    if size == LEGACY_SPRITESHEET_SIZE:
        return LEGACY_FRAME_SIZE[0], LEGACY_FRAME_SIZE[1], LEGACY_COLUMNS, LEGACY_ROW_FRAME_COUNTS
    raise ValueError(f"unsupported spritesheet size {size[0]}x{size[1]}")


def crop_spritesheet_frame(source: pathlib.Path, row: int, column: int, cell_width: int, cell_height: int, output: pathlib.Path) -> None:
    run([
        magick(),
        str(source),
        "-crop",
        f"{cell_width}x{cell_height}+{column * cell_width}+{row * cell_height}",
        "+repage",
        str(output),
    ])


def rebuild_spritesheets(source_character_dir: pathlib.Path, tmp_root: pathlib.Path) -> None:
    source = source_spritesheet_path(source_character_dir)
    source_copy = tmp_root / f"source-spritesheet{source.suffix}"
    shutil.copy2(source, source_copy)

    cell_width, cell_height, _, row_counts = spritesheet_layout(source_copy)
    normalized_frames: list[pathlib.Path] = []
    for row, source_count in enumerate(row_counts):
        crop_dir = tmp_root / "spritesheet-crops" / f"{row:02d}"
        crop_dir.mkdir(parents=True, exist_ok=True)
        source_frames = []
        for column in range(source_count):
            crop = crop_dir / f"source-{column:02d}.png"
            crop_spritesheet_frame(source_copy, row, column, cell_width, cell_height, crop)
            source_frames.append(crop)

        for column, source_index in enumerate(resample_indices(len(source_frames), loop=True)):
            normalized = tmp_root / "spritesheet-normalized" / f"{row:02d}-{column:02d}.png"
            normalize_frame(source_frames[source_index], normalized)
            normalized_frames.append(normalized)

    atlas_png = CHARACTER_DIR / "spritesheet.png"
    command = [magick(), "-size", f"{SPRITESHEET_SIZE[0]}x{SPRITESHEET_SIZE[1]}", "xc:none"]
    for row in range(SPRITE_ROWS):
        for column in range(FRAME_COUNT):
            frame = tmp_root / "spritesheet-normalized" / f"{row:02d}-{column:02d}.png"
            command.extend([
                str(frame),
                "-geometry",
                f"+{column * FRAME_SIZE[0]}+{row * FRAME_SIZE[1]}",
                "-compose",
                "over",
                "-composite",
            ])
    command.extend(["-define", "png:color-type=6", str(atlas_png)])
    run(command)
    run([magick(), str(atlas_png), "-define", "webp:lossless=true", "-quality", "100", str(CHARACTER_DIR / "spritesheet.webp")])


def rebuild_contact_sheet(state_dir: pathlib.Path) -> None:
    frames = [str(path) for path in frame_paths(state_dir)]
    if not frames:
        return
    run([
        magick(),
        "montage",
        *frames,
        "-background",
        "#2b2b2b",
        "-geometry",
        f"{FRAME_SIZE[0]}x{FRAME_SIZE[1]}+8+8",
        str(state_dir / "contact-sheet.png"),
    ])


def apply_edge_boundary_line(frame: pathlib.Path, state: str) -> None:
    if state.endswith("-left"):
        draw = "rectangle 0,0 3,255"
    elif state.endswith("-right"):
        draw = "rectangle 252,0 255,255"
    else:
        return
    run([
        magick(),
        str(frame),
        "-fill",
        "#111111",
        "-draw",
        draw,
        "-define",
        "png:color-type=6",
        str(frame),
    ])


def copy_backup(target_dir: pathlib.Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(CHARACTER_DIR, target_dir)


def update_manifest(states: Iterable[str]) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    extra_states = manifest.get("extraStates", {})
    for state in states:
        config = extra_states[state]
        state_dir = pathlib.PurePosixPath("extra") / state
        config["framePaths"] = [str(state_dir / f"{index:02d}.png") for index in range(FRAME_COUNT)]
        config["frameDuration"] = FRAME_DURATION
        config["loop"] = state not in NON_LOOP_STATES
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remove_legacy_sources() -> None:
    for path in EXTRA_DIR.glob("*/source-strip-*.png"):
        path.unlink()


def copy_selected_sources(source_extra_dir: pathlib.Path, tmp_root: pathlib.Path, states: list[str], loop_flags: dict[str, bool]) -> dict[str, list[pathlib.Path]]:
    selected: dict[str, list[pathlib.Path]] = {}
    for state in states:
        source_state_dir = source_extra_dir / state
        if not source_state_dir.exists():
            source_state_dir = EXTRA_DIR / state
        source_files = frame_paths(source_state_dir)
        if not source_files:
            raise FileNotFoundError(f"{state}: no source frames under {source_state_dir}")

        copied = []
        for output_index, source_index in enumerate(resample_indices(len(source_files), loop=loop_flags[state])):
            target = tmp_root / "extra-sources" / state / f"{output_index:02d}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_files[source_index], target)
            copied.append(target)
        selected[state] = copied
    return selected


def regenerate(source_extra_dir: pathlib.Path, remove_sources: bool, tmp_root: pathlib.Path) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    states = list(manifest.get("extraStates", {}).keys())
    loop_flags = {
        state: manifest.get("extraStates", {}).get(state, {}).get("loop", state not in NON_LOOP_STATES)
        for state in states
    }
    selected_sources = copy_selected_sources(source_extra_dir, tmp_root, states, loop_flags)

    for state in states:
        gravity = "center"
        if state.endswith("-left"):
            gravity = "west"
        elif state.endswith("-right"):
            gravity = "east"
        state_dir = EXTRA_DIR / state
        state_dir.mkdir(parents=True, exist_ok=True)
        for old_frame in frame_paths(state_dir):
            old_frame.unlink()
        for index, source in enumerate(selected_sources[state]):
            output = state_dir / f"{index:02d}.png"
            normalize_frame(source, output, gravity=gravity)
            apply_edge_boundary_line(output, state)
        rebuild_contact_sheet(state_dir)

    update_manifest(states)
    if remove_sources:
        remove_legacy_sources()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-extra-dir",
        type=pathlib.Path,
        default=None,
        help="Directory containing one subdirectory per animation state.",
    )
    parser.add_argument(
        "--source-character-dir",
        type=pathlib.Path,
        default=CHARACTER_DIR,
        help="Directory containing the source spritesheet and extra directory.",
    )
    parser.add_argument(
        "--backup-dir",
        type=pathlib.Path,
        help="Optional destination for a full copy of the current plana character before writing.",
    )
    parser.add_argument(
        "--remove-legacy-sources",
        action="store_true",
        help="Remove old source-strip images after frames have been rebuilt.",
    )
    args = parser.parse_args()

    if args.backup_dir:
        copy_backup(args.backup_dir)
    source_extra_dir = args.source_extra_dir or args.source_character_dir / "extra"
    with tempfile.TemporaryDirectory(prefix="openplana-regenerate-") as tmp:
        tmp_root = pathlib.Path(tmp)
        rebuild_spritesheets(args.source_character_dir, tmp_root)
        regenerate(source_extra_dir, args.remove_legacy_sources, tmp_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
