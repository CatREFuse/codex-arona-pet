#!/usr/bin/env python3
import datetime as _dt
import json
import os
import pathlib
import re
import shutil
import stat


ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK_SCRIPT = ROOT / "script" / "codex_hook.py"
CODEX_HOME = pathlib.Path(os.environ.get("CODEX_HOME", pathlib.Path.home() / ".codex"))
HOOKS_FILE = CODEX_HOME / "hooks.json"
CONFIG_FILE = CODEX_HOME / "config.toml"
EVENTS = {
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


def _load_hooks():
    if not HOOKS_FILE.exists():
        return {"hooks": {}}
    with HOOKS_FILE.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if "hooks" not in data or not isinstance(data["hooks"], dict):
        data["hooks"] = {}
    return data


def _quote(path):
    return "'" + str(path).replace("'", "'\"'\"'") + "'"


def _entry(event_config):
    result = {
        "hooks": [
            {
                "type": "command",
                "command": _quote(HOOK_SCRIPT),
                "timeout": 15,
            }
        ]
    }
    if event_config.get("matcher"):
        result["matcher"] = event_config["matcher"]
    return result


def _contains_open_plana_hook(item):
    for hook in item.get("hooks", []):
        command = hook.get("command", "")
        if str(HOOK_SCRIPT) in command:
            return True
    return False


def _open_plana_hook_positions(data):
    positions = []
    for event, entries in data.get("hooks", {}).items():
        slug = EVENT_SLUGS.get(event)
        if not slug:
            continue
        for entry_index, entry in enumerate(entries):
            for hook_index, hook in enumerate(entry.get("hooks", [])):
                command = hook.get("command", "")
                if str(HOOK_SCRIPT) in command:
                    key = f"{HOOKS_FILE}:{slug}:{entry_index}:{hook_index}"
                    positions.append(key)
    return positions


def _replace_or_append_hook_state(config_text, key):
    header = f'[hooks.state."{key}"]'
    start = config_text.find(header)
    if start >= 0:
        body_start = start + len(header)
        if body_start < len(config_text) and config_text[body_start] == "\n":
            body_start += 1
        next_section = config_text.find("\n[", body_start)
        body_end = len(config_text) if next_section < 0 else next_section + 1
        body = config_text[body_start:body_end]
        body_lines = [
            line
            for line in body.splitlines()
            if not re.match(r"^enabled\s*=", line)
        ]
        remaining = "\n".join(body_lines).strip()
        body = "enabled = true\n"
        if remaining:
            body += remaining + "\n"
        return config_text[:body_start] + body + config_text[body_end:]

    section = f'\n[hooks.state."{key}"]\nenabled = true\n'
    hooks_state_header = "[hooks.state]"
    if hooks_state_header not in config_text:
        return config_text.rstrip() + "\n\n[hooks.state]\n" + section

    return config_text.rstrip() + "\n" + section


def _enable_codex_hooks_feature(config_text):
    match = re.search(r"(?ms)^(\[features\]\s*\n)(.*?)(?=^\[|\Z)", config_text)
    if not match:
        return config_text.rstrip() + "\n\n[features]\ncodex_hooks = true\n"

    body_lines = [
        line
        for line in match.group(2).splitlines()
        if not re.match(r"^\s*codex_hooks\s*=", line)
    ]
    body = "codex_hooks = true\n"
    if body_lines:
        body += "\n".join(body_lines).strip("\n") + "\n"
    return config_text[: match.start(2)] + body + config_text[match.end(2) :]


def _update_config_hook_state(keys):
    if not keys:
        return False

    if CONFIG_FILE.exists():
        config_text = CONFIG_FILE.read_text(encoding="utf-8")
    else:
        config_text = ""

    next_text = _enable_codex_hooks_feature(config_text)

    for key in keys:
        next_text = _replace_or_append_hook_state(next_text, key)

    if next_text == config_text:
        return False

    if CONFIG_FILE.exists():
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(CONFIG_FILE, CONFIG_FILE.with_suffix(f".toml.backup-{stamp}"))

    CONFIG_FILE.write_text(next_text.rstrip() + "\n", encoding="utf-8")
    return True


def main():
    if not HOOK_SCRIPT.exists():
        raise SystemExit(f"missing hook script: {HOOK_SCRIPT}")

    mode = HOOK_SCRIPT.stat().st_mode
    HOOK_SCRIPT.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    data = _load_hooks()

    changed = False
    for event, config in EVENTS.items():
        entries = data["hooks"].setdefault(event, [])
        filtered = [item for item in entries if not _contains_open_plana_hook(item)]
        new_entry = _entry(config)
        if filtered != entries or new_entry not in filtered:
            data["hooks"][event] = filtered + [new_entry]
            changed = True

    if HOOKS_FILE.exists() and changed:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(HOOKS_FILE, HOOKS_FILE.with_suffix(f".json.backup-{stamp}"))

    with HOOKS_FILE.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    keys = _open_plana_hook_positions(data)
    config_changed = _update_config_hook_state(keys)

    print(json.dumps({
        "ok": True,
        "hooks": str(HOOKS_FILE),
        "config": str(CONFIG_FILE),
        "hook": str(HOOK_SCRIPT),
        "configChanged": config_changed,
        "stateKeys": keys,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
