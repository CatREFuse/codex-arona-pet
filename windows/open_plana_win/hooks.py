from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import paths

EVENTS: dict[str, dict[str, str]] = {
    "SessionStart": {"matcher": "startup|resume"},
    "UserPromptSubmit": {},
    "PreToolUse": {},
    "PostToolUse": {},
    "Stop": {},
    "Notification": {},
}

EVENT_SLUGS = {
    "SessionStart": "session_start",
    "UserPromptSubmit": "user_prompt_submit",
    "PreToolUse": "pre_tool_use",
    "PostToolUse": "post_tool_use",
    "Stop": "stop",
    "Notification": "notification",
}


def install_hooks(python_executable: str | None = None) -> dict[str, object]:
    hook_script = paths.hook_script()
    if not hook_script.exists():
        raise FileNotFoundError(f"missing hook script: {hook_script}")

    python_executable = python_executable or sys.executable
    hooks_file = paths.hooks_file()
    config_file = paths.codex_config_file()
    paths.codex_home().mkdir(parents=True, exist_ok=True)

    data = _load_hooks(hooks_file)
    command = subprocess.list2cmdline([python_executable, str(hook_script)])
    changed = False
    for event, event_config in EVENTS.items():
        entries = data["hooks"].setdefault(event, [])
        filtered = [item for item in entries if not _contains_hook(item, hook_script)]
        new_entry: dict[str, object] = {
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                    "timeout": 15,
                }
            ]
        }
        if event_config.get("matcher"):
            new_entry["matcher"] = event_config["matcher"]
        if filtered != entries or new_entry not in filtered:
            data["hooks"][event] = filtered + [new_entry]
            changed = True

    if hooks_file.exists() and changed:
        _backup(hooks_file)
    hooks_file.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    state_keys = _hook_state_keys(data, hooks_file, hook_script)
    config_changed = _update_config(config_file, state_keys)
    return {
        "ok": True,
        "hooks": str(hooks_file),
        "config": str(config_file),
        "hook": str(hook_script),
        "command": command,
        "configChanged": config_changed,
        "stateKeys": state_keys,
    }


def hook_status() -> dict[str, object]:
    hook_script = paths.hook_script()
    hooks_file = paths.hooks_file()
    config_file = paths.codex_config_file()
    data = _load_hooks(hooks_file)
    keys = _hook_state_keys(data, hooks_file, hook_script)
    slugs = {key.split(":")[-3] for key in keys if ":" in key}
    required = set(EVENT_SLUGS.values())
    config_text = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
    enabled = _codex_hooks_enabled(config_text) and all(_state_enabled(config_text, key) for key in keys)
    return {
        "installed": required.issubset(slugs) and bool(keys) and enabled,
        "hooksFile": str(hooks_file),
        "configFile": str(config_file),
        "stateFile": str(paths.state_file()),
        "hookScript": str(hook_script),
        "stateExists": paths.state_file().exists(),
        "keys": keys,
    }


def _load_hooks(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"hooks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"hooks": {}}
    if not isinstance(data, dict):
        data = {"hooks": {}}
    if not isinstance(data.get("hooks"), dict):
        data["hooks"] = {}
    return data


def _contains_hook(entry: dict[str, object], hook_script: Path) -> bool:
    for hook in entry.get("hooks", []):
        if isinstance(hook, dict) and str(hook_script) in str(hook.get("command") or ""):
            return True
    return False


def _hook_state_keys(data: dict[str, object], hooks_file: Path, hook_script: Path) -> list[str]:
    keys: list[str] = []
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return keys
    for event, entries in hooks.items():
        slug = EVENT_SLUGS.get(str(event))
        if not slug or not isinstance(entries, list):
            continue
        for entry_index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            for hook_index, hook in enumerate(entry.get("hooks", [])):
                if isinstance(hook, dict) and str(hook_script) in str(hook.get("command") or ""):
                    keys.append(f"{hooks_file}:{slug}:{entry_index}:{hook_index}")
    return keys


def _update_config(path: Path, keys: list[str]) -> bool:
    if not keys:
        return False
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = _enable_codex_hooks(current)
    for key in keys:
        updated = _enable_state_key(updated, key)
    updated = updated.rstrip() + "\n"
    if updated == current:
        return False
    if path.exists():
        _backup(path)
    path.write_text(updated, encoding="utf-8")
    return True


def _enable_codex_hooks(text: str) -> str:
    match = re.search(r"(?ms)^(\[features\]\s*\n)(.*?)(?=^\[|\Z)", text)
    if not match:
        return text.rstrip() + "\n\n[features]\ncodex_hooks = true\n"
    body_lines = [line for line in match.group(2).splitlines() if not re.match(r"^\s*codex_hooks\s*=", line)]
    body = "codex_hooks = true\n"
    if body_lines:
        body += "\n".join(body_lines).strip("\n") + "\n"
    return text[: match.start(2)] + body + text[match.end(2) :]


def _enable_state_key(text: str, key: str) -> str:
    header = _state_header(key)
    start = text.find(header)
    if start >= 0:
        body_start = start + len(header)
        if body_start < len(text) and text[body_start] == "\n":
            body_start += 1
        next_section = text.find("\n[", body_start)
        body_end = len(text) if next_section < 0 else next_section + 1
        body_lines = [
            line
            for line in text[body_start:body_end].splitlines()
            if not re.match(r"^\s*enabled\s*=", line)
        ]
        body = "enabled = true\n"
        remaining = "\n".join(body_lines).strip()
        if remaining:
            body += remaining + "\n"
        return text[:body_start] + body + text[body_end:]
    return text.rstrip() + f'\n\n{header}\nenabled = true\n'


def _codex_hooks_enabled(text: str) -> bool:
    match = re.search(r"(?ms)^\[features\]\s*\n(.*?)(?=^\[|\Z)", text)
    return bool(match and re.search(r"(?m)^\s*codex_hooks\s*=\s*true\b", match.group(1)))


def _state_enabled(text: str, key: str) -> bool:
    pattern = re.escape(_state_header(key)) + r"\s*\n(?P<body>.*?)(?=^\[|\Z)"
    match = re.search(pattern, text, re.M | re.S)
    return bool(match and re.search(r"(?m)^\s*enabled\s*=\s*true\b", match.group("body")))


def _state_header(key: str) -> str:
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'[hooks.state."{escaped}"]'


def _backup(path: Path) -> None:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "".join(path.suffixes) or ".bak"
    backup = path.with_name(f"{path.name}.backup-{stamp}{suffix}")
    shutil.copy2(path, backup)
