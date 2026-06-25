from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    value = os.environ.get("OPEN_PLANA_ROOT")
    if value:
        return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def codex_home() -> Path:
    value = os.environ.get("CODEX_HOME")
    if value:
        return Path(value).expanduser().resolve()
    return Path.home() / ".codex"


def state_dir() -> Path:
    return codex_home() / "open-plana"


def state_file() -> Path:
    return state_dir() / "state.json"


def hooks_file() -> Path:
    return codex_home() / "hooks.json"


def codex_config_file() -> Path:
    return codex_home() / "config.toml"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "OpenPlanaWin"
    return Path.home() / "AppData" / "Roaming" / "OpenPlanaWin"


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def hook_script() -> Path:
    return repo_root() / "mac_os" / "script" / "codex_hook.py"


def character_roots() -> list[Path]:
    return [
        repo_root() / "shared" / "Characters",
        app_data_dir() / "Characters",
        codex_home() / "pets",
    ]
