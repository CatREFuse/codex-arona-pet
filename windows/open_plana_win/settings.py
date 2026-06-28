from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from . import paths


@dataclass
class Settings:
    character_id: str = "plana-neo"
    scale: float = 1.0
    docked: bool = True
    dock_side: str = "right"
    x: int | None = None
    y: int | None = None
    task_bubbles_collapsed: bool = False


def load_settings() -> Settings:
    path = paths.settings_file()
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    settings = Settings()
    for key in asdict(settings):
        if key in data:
            setattr(settings, key, data[key])
    settings.scale = clamp_scale(settings.scale)
    settings.dock_side = "left" if settings.dock_side == "left" else "right"
    return settings


def save_settings(settings: Settings) -> None:
    path = paths.settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clamp_scale(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 1.0
    return min(max(number, 0.7), 1.6)
