from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from . import paths

SPRITE_CELL = 256
SPRITE_COLUMNS = 12
ALPHA_KEY_THRESHOLD = 88
ALPHA_OPAQUE_THRESHOLD = 238
EDGE_COLOR_SOURCE_THRESHOLD = 160
EDGE_COLOR_BLEED_STEPS = 8
EDGE_MATTE_RGB = (248, 249, 252)
SPRITE_ROWS: dict[str, tuple[int, int]] = {
    "idle": (0, 12),
    "running-right": (1, 12),
    "running-left": (2, 12),
    "waving": (3, 12),
    "jumping": (4, 12),
    "failed": (5, 12),
    "waiting": (6, 12),
    "running": (7, 12),
    "review": (8, 12),
}

FALLBACK_STATE = {
    "carried": "jumping",
    "idle-read": "idle",
    "idle-normal": "idle",
    "idle-sleep": "idle",
    "pinched": "idle",
    "edge-peek-left": "idle",
    "edge-peek-right": "idle",
    "edge-idle-read-left": "idle",
    "edge-idle-read-right": "idle",
    "edge-idle-normal-left": "idle",
    "edge-idle-normal-right": "idle",
    "edge-idle-sleep-left": "idle",
    "edge-idle-sleep-right": "idle",
    "edge-pinched-left": "idle",
    "edge-pinched-right": "idle",
    "coding": "running",
    "edge-coding-left": "running",
    "edge-coding-right": "running",
    "checking": "review",
    "edge-checking-left": "review",
    "edge-checking-right": "review",
    "awaiting": "waiting",
    "edge-awaiting-left": "waiting",
    "edge-awaiting-right": "waiting",
    "rejected": "failed",
    "edge-rejected-left": "failed",
    "edge-rejected-right": "failed",
    "success": "failed",
    "edge-success-left": "failed",
    "edge-success-right": "failed",
}


@dataclass(frozen=True)
class ExtraAnimation:
    frame_paths: tuple[str, ...]
    frame_duration: float = 1.0 / 6.0
    loop: bool = True


@dataclass(frozen=True)
class PetCharacter:
    id: str
    display_name: str
    description: str
    directory: Path
    spritesheet: Path
    extra_states: dict[str, ExtraAnimation]


class CharacterStore:
    def __init__(self) -> None:
        self.characters: list[PetCharacter] = []
        self._sheet_cache: dict[Path, Image.Image] = {}
        self._frame_cache: dict[tuple[str, str, int], Image.Image] = {}

    def reload(self) -> list[PetCharacter]:
        loaded: list[PetCharacter] = []
        seen: set[str] = set()
        for root in paths.character_roots():
            if not root.exists():
                continue
            for directory in sorted(item for item in root.iterdir() if item.is_dir()):
                character = self._load_character(directory)
                if not character or character.id in seen:
                    continue
                loaded.append(character)
                seen.add(character.id)
        self.characters = sorted(loaded, key=lambda item: item.id.lower())
        return self.characters

    def get(self, character_id: str | None) -> PetCharacter | None:
        if not self.characters:
            self.reload()
        if character_id:
            for character in self.characters:
                if character.id == character_id:
                    return character
        return self.characters[0] if self.characters else None

    def animation(self, character: PetCharacter, state: str) -> ExtraAnimation:
        if state in character.extra_states:
            return character.extra_states[state]
        fallback = FALLBACK_STATE.get(state, state)
        row, frames = SPRITE_ROWS.get(fallback, SPRITE_ROWS["idle"])
        return ExtraAnimation(tuple(f"__sheet__/{row}/{index}" for index in range(frames)))

    def frame_count(self, character: PetCharacter, state: str) -> int:
        return max(len(self.animation(character, state).frame_paths), 1)

    def frame_duration(self, character: PetCharacter, state: str) -> float:
        return max(self.animation(character, state).frame_duration, 0.05)

    def is_looping(self, character: PetCharacter, state: str) -> bool:
        return self.animation(character, state).loop

    def frame(self, character: PetCharacter, state: str, index: int) -> Image.Image:
        animation = self.animation(character, state)
        index = abs(index) % max(len(animation.frame_paths), 1)
        key = (character.id, state, index)
        cached = self._frame_cache.get(key)
        if cached is not None:
            return cached

        frame_path = animation.frame_paths[index]
        if frame_path.startswith("__sheet__/"):
            _, row_text, column_text = frame_path.split("/")
            image = self._sheet_frame(character.spritesheet, int(row_text), int(column_text))
        else:
            image = Image.open(character.directory / frame_path).convert("RGBA")
        self._frame_cache[key] = image
        return image

    def display_frame(self, character: PetCharacter, state: str, index: int, size: int | None = None) -> Image.Image:
        """Return a frame with binary alpha for Tk color-key transparency.

        Tkinter's Windows transparent-color mode composites translucent PNG
        edges against the key color before the key is removed. The source
        frames are proper RGBA, but that pipeline leaves a visible magenta
        fringe. Quantizing alpha for the displayed frame avoids that color
        bleed while keeping the asset files untouched.
        """
        frame = self.frame(character, state, index)
        key = (character.id, f"display:{state}:{size or SPRITE_CELL}", index)
        cached = self._frame_cache.get(key)
        if cached is not None:
            return cached
        bleed_key = (character.id, f"bleed:{state}", index)
        prepared = self._frame_cache.get(bleed_key)
        if prepared is None:
            prepared = _bleed_edge_colors(frame)
            self._frame_cache[bleed_key] = prepared
        if size is not None and prepared.size != (size, size):
            prepared = prepared.resize((size, size), Image.Resampling.LANCZOS)
        image = _color_key_safe_frame(prepared)
        self._frame_cache[key] = image
        return image

    def _sheet_frame(self, path: Path, row: int, column: int) -> Image.Image:
        sheet = self._sheet_cache.get(path)
        if sheet is None:
            sheet = Image.open(path).convert("RGBA")
            self._sheet_cache[path] = sheet
        left = column * SPRITE_CELL
        top = row * SPRITE_CELL
        return sheet.crop((left, top, left + SPRITE_CELL, top + SPRITE_CELL))

    def _load_character(self, directory: Path) -> PetCharacter | None:
        pet_path = directory / "pet.json"
        if not pet_path.exists():
            return None
        try:
            pet = json.loads(pet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        manifest = _read_json(directory / "openplana-character.json")
        spritesheet_name = manifest.get("spritesheetPath") or pet.get("spritesheetPath")
        if not spritesheet_name:
            return None
        spritesheet = directory / str(spritesheet_name)
        if not spritesheet.exists():
            return None

        extra_states: dict[str, ExtraAnimation] = {}
        for state, payload in (manifest.get("extraStates") or {}).items():
            if not isinstance(payload, dict):
                continue
            frame_paths = tuple(str(item) for item in payload.get("framePaths") or [])
            if not frame_paths:
                continue
            extra_states[str(state)] = ExtraAnimation(
                frame_paths=frame_paths,
                frame_duration=float(payload.get("frameDuration") or (1.0 / 6.0)),
                loop=bool(payload.get("loop", True)),
            )

        character_id = str(manifest.get("id") or pet.get("id") or directory.name)
        return PetCharacter(
            id=character_id,
            display_name=str(manifest.get("displayName") or pet.get("displayName") or character_id),
            description=str(manifest.get("description") or pet.get("description") or ""),
            directory=directory,
            spritesheet=spritesheet,
            extra_states=extra_states,
        )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _bleed_edge_colors(frame: Image.Image) -> Image.Image:
    image = frame.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    colored = [[pixels[x, y][3] >= EDGE_COLOR_SOURCE_THRESHOLD for x in range(width)] for y in range(height)]

    for _step in range(EDGE_COLOR_BLEED_STEPS):
        updates: list[tuple[int, int, tuple[int, int, int]]] = []
        for y in range(height):
            for x in range(width):
                if colored[y][x]:
                    continue
                total_r = total_g = total_b = count = 0
                for ny in range(max(0, y - 1), min(height, y + 2)):
                    for nx in range(max(0, x - 1), min(width, x + 2)):
                        if nx == x and ny == y:
                            continue
                        if not colored[ny][nx]:
                            continue
                        r, g, b, _a = pixels[nx, ny]
                        total_r += r
                        total_g += g
                        total_b += b
                        count += 1
                if count:
                    updates.append((x, y, (total_r // count, total_g // count, total_b // count)))
        if not updates:
            break
        for x, y, (r, g, b) in updates:
            _old_r, _old_g, _old_b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, a)
            colored[y][x] = True
    return image


def _color_key_safe_frame(frame: Image.Image) -> Image.Image:
    image = frame.convert("RGBA")
    alpha = image.getchannel("A")
    visible = alpha.point(lambda value: 255 if value >= ALPHA_KEY_THRESHOLD else 0)
    image.putalpha(visible)

    # Tk color-key transparency is binary, so pre-composite translucent edges
    # against the light app background instead of letting dark matte pixels
    # become fully opaque.
    pixels = image.load()
    original_alpha = alpha.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            if original_alpha[x, y] <= ALPHA_KEY_THRESHOLD:
                pixels[x, y] = (255, 0, 255, 0)
            elif original_alpha[x, y] < ALPHA_OPAQUE_THRESHOLD:
                r, g, b, _a = pixels[x, y]
                coverage = original_alpha[x, y] / 255.0
                mr, mg, mb = EDGE_MATTE_RGB
                pixels[x, y] = (
                    round(r * coverage + mr * (1.0 - coverage)),
                    round(g * coverage + mg * (1.0 - coverage)),
                    round(b * coverage + mb * (1.0 - coverage)),
                    255,
                )
    return image
