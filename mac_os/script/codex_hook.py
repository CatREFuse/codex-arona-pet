#!/usr/bin/env python3
import datetime as _dt
import json
import os
import pathlib
import re
import sys
import tempfile


CODEX_HOME = pathlib.Path(os.environ.get("CODEX_HOME", pathlib.Path.home() / ".codex"))
STATE_DIR = CODEX_HOME / "open-plana"
STATE_FILE = STATE_DIR / "state.json"
EVENTS_FILE = STATE_DIR / "events.jsonl"
MAX_TASKS = 5
ACTIVE_TASK_TTL_SECONDS = 5 * 60


def _utc_now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _read_event():
    raw = sys.stdin.read()
    if not raw.strip():
        return {"hook_event_name": "Manual"}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"hook_event_name": "Raw", "message": raw[:1000]}


def _event_name(payload):
    for key in ("hook_event_name", "event", "type"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return "Unknown"


def _status_for_event(name, payload):
    lower = name.lower()
    if "prompt" in lower:
        return "running"
    if "pretooluse" in lower or "posttooluse" in lower:
        return "running"
    if "notification" in lower:
        return "waiting"
    if "stop" in lower:
        return "review"
    if "error" in lower or "fail" in lower:
        return "failed"
    if "tool" in lower:
        return "running"
    return "idle"


def _collapse(text, limit=160):
    if text is None:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) > limit:
        return text[:max(limit - 3, 0)].rstrip() + "..."
    return text


def _text_from_content(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for key in ("text", "content", "message"):
                    if isinstance(item.get(key), str):
                        parts.append(item[key])
        return " ".join(parts)
    if isinstance(value, dict):
        for key in ("text", "content", "message"):
            if isinstance(value.get(key), str):
                return value[key]
    return ""


def _request_text_from_prompt(text):
    if text is None:
        return ""
    raw = str(text).strip()
    marker = "## My request for Codex:"
    if marker in raw:
        raw = raw.split(marker, 1)[1].strip()
    raw = re.split(r"<image\b|<file\b", raw, maxsplit=1)[0].strip()
    return raw


def _is_internal_system_text(value):
    text = str(value or "")
    return (
        "## Memory Writing Agent:" in text
        or "Memory Writing Agent: Phase 2" in text
        or "/.codex/memories" in text
        or "/.codex/rollout_summaries" in text
    )


def _is_internal_system_task(task):
    if not isinstance(task, dict):
        return False
    return any(
        _is_internal_system_text(task.get(key))
        for key in ("title", "taskTitle", "detail", "taskDetail", "message", "cwd")
    )


def _is_internal_system_event(payload, detail="", task_title="", task_detail=""):
    values = [
        payload.get("cwd"),
        payload.get("prompt"),
        payload.get("message"),
        payload.get("input"),
        _text_from_content(payload.get("content")),
        detail,
        task_title,
        task_detail,
    ]
    return any(_is_internal_system_text(value) for value in values)


def _read_previous_state():
    try:
        with STATE_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _task_id(payload, previous):
    for key in ("session_id", "sessionId", "conversation_id", "conversationId"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        return f"cwd:{cwd.strip()}"
    value = previous.get("sessionId") or previous.get("session_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "current"


def _task_from_legacy(previous):
    title = _collapse(previous.get("taskTitle") or previous.get("task_title") or "", limit=44)
    detail = _collapse(previous.get("taskDetail") or previous.get("task_detail") or "", limit=220)
    status = previous.get("status") or ""
    phase = previous.get("phase") or ""
    if not title and not detail:
        return None
    if status not in ("running", "waiting") and phase not in ("start", "active", "authorization"):
        return None
    task = {
        "id": previous.get("sessionId") or previous.get("session_id") or previous.get("cwd") or "current",
        "title": title or detail or previous.get("statusText") or "Codex 任务",
        "detail": detail or previous.get("statusText") or "",
        "message": previous.get("message") or detail or previous.get("statusText") or "",
        "statusText": previous.get("statusText") or "正在处理",
        "status": status or "running",
        "phase": phase or "active",
        "sessionId": previous.get("sessionId") or previous.get("session_id"),
        "cwd": previous.get("cwd"),
        "updatedAt": previous.get("updatedAt"),
    }
    return None if _is_internal_system_task(task) else task


def _previous_tasks(previous):
    result = []
    seen = set()
    for item in previous.get("tasks") or []:
        if not isinstance(item, dict):
            continue
        if _is_internal_system_task(item):
            continue
        item_id = _collapse(item.get("id") or item.get("sessionId") or item.get("cwd") or "", limit=160)
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        result.append(dict(item, id=item_id))

    legacy = _task_from_legacy(previous)
    if legacy and legacy["id"] not in seen:
        result.append(legacy)
    return result


def _matching_task(tasks, task_id):
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None


def _task_is_active(task):
    return task.get("status") in ("running", "waiting") or task.get("phase") in ("start", "active", "authorization")


def _task_semantic_key(task):
    title = _collapse(task.get("title") or task.get("taskTitle") or task.get("detail") or "", limit=120).casefold()
    title = re.sub(r"\s+", " ", title).strip()
    return title or _collapse(task.get("id") or task.get("sessionId") or task.get("cwd") or "", limit=160)


def _pruned_tasks(tasks):
    now = _dt.datetime.now(_dt.timezone.utc)
    active = []
    for task in tasks:
        updated = _parse_time(task.get("updatedAt"))
        if updated and (now - updated).total_seconds() > ACTIVE_TASK_TTL_SECONDS:
            continue
        if _task_is_active(task):
            active.append(task)

    result = []
    seen = set()
    for task in sorted(active, key=lambda item: item.get("updatedAt") or "", reverse=True):
        key = _task_semantic_key(task)
        if key in seen:
            continue
        seen.add(key)
        result.append(task)
        if len(result) >= MAX_TASKS:
            break
    return result


def _transcript_message(path):
    if not path:
        return ""
    transcript = pathlib.Path(path)
    if not transcript.exists() or not transcript.is_file():
        return ""

    try:
        lines = transcript.read_text(encoding="utf-8", errors="ignore").splitlines()[-100:]
    except OSError:
        return ""

    for line in reversed(lines):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        candidates = [item]
        if isinstance(item.get("payload"), dict):
            candidates.append(item["payload"])
        if isinstance(item.get("item"), dict):
            candidates.append(item["item"])

        for candidate in candidates:
            role = candidate.get("role")
            if role not in ("assistant", "user"):
                continue
            text = _text_from_content(candidate.get("content"))
            if text:
                return text
    return ""


def _phase_for_event(name):
    lower = name.lower()
    if "prompt" in lower:
        return "start"
    if "notification" in lower:
        return "authorization"
    if "stop" in lower:
        return "finish"
    if "error" in lower or "fail" in lower:
        return "failed"
    if "session" in lower:
        return "start"
    if "tool" in lower:
        return "active"
    return "idle"


def _status_text_for_event(name):
    lower = name.lower()
    if "prompt" in lower:
        return "任务已开始"
    if "notification" in lower:
        return "等待授权"
    if "stop" in lower:
        return "任务已结束"
    if "error" in lower or "fail" in lower:
        return "检查未通过"
    if "session" in lower:
        return "会话已连接"
    if "tool" in lower:
        return "正在处理"
    return "空闲"


def _prompt_detail(payload):
    raw = (
        payload.get("prompt")
        or payload.get("message")
        or payload.get("input")
        or _text_from_content(payload.get("content"))
        or "收到新任务"
    )
    return _collapse(
        _request_text_from_prompt(raw) or raw,
        limit=220,
    )


def _notification_detail(payload):
    return _collapse(
        payload.get("message")
        or _text_from_content(payload.get("notification"))
        or payload.get("text")
        or _text_from_content(payload.get("content"))
        or "Codex 需要确认",
        limit=220,
    )


def _tool_detail(payload):
    tool_name = _collapse(payload.get("tool_name") or payload.get("toolName") or "")
    if tool_name:
        return f"正在使用 {tool_name}"
    return "正在处理任务"


def _task_title_from_text(text):
    if text is None:
        return ""
    raw = str(text).strip()
    if not raw:
        return ""
    raw = _request_text_from_prompt(raw) or raw
    first_line = re.split(r"[。！？!?\n]", raw, maxsplit=1)[0].strip()
    return _collapse(first_line or raw, limit=44)


def _detail_for_event(name, payload):
    lower = name.lower()
    if "prompt" in lower:
        return _prompt_detail(payload)
    if "notification" in lower:
        return _notification_detail(payload)
    if "stop" in lower:
        transcript_text = _transcript_message(payload.get("transcript_path"))
        return _collapse(transcript_text or payload.get("message") or "任务已完成", limit=220)
    if "session" in lower:
        return _collapse(payload.get("message") or "Codex 会话已连接", limit=220)
    if "tool" in lower:
        return _tool_detail(payload)
    return _collapse(payload.get("message") or "", limit=220)


def _task_fields_for_event(name, detail, previous, payload=None):
    lower = name.lower()
    previous_title = _collapse(previous.get("taskTitle") or previous.get("task_title") or "", limit=44)
    previous_detail = _collapse(previous.get("taskDetail") or previous.get("task_detail") or "", limit=220)

    if "prompt" in lower:
        payload = payload or {}
        title_source = (
            payload.get("prompt")
            or payload.get("message")
            or payload.get("input")
            or _text_from_content(payload.get("content"))
            or detail
        )
        title = _task_title_from_text(title_source) or "Codex 任务"
        return title, detail

    if "session" in lower:
        return previous_title, previous_detail

    if "notification" in lower or "tool" in lower:
        return previous_title, previous_detail

    if "stop" in lower or "error" in lower or "fail" in lower:
        return previous_title or _task_title_from_text(detail), previous_detail or detail

    return previous_title, previous_detail


def _tasks_for_event(name, payload, current_state, previous):
    lower = name.lower()
    task_id = _task_id(payload, previous)
    tasks = [task for task in _previous_tasks(previous) if task.get("id") != task_id]

    if "stop" in lower or "error" in lower or "fail" in lower:
        return _pruned_tasks(tasks)

    if (
        "prompt" in lower
        or "session" in lower
        or "notification" in lower
        or "tool" in lower
        or current_state["status"] in ("running", "waiting")
    ):
        current_task = {
            "id": task_id,
            "title": current_state["taskTitle"] or current_state["statusText"] or "Codex 任务",
            "detail": current_state["taskDetail"] or current_state["detail"] or current_state["statusText"],
            "message": current_state["detail"] or current_state["message"] or current_state["statusText"],
            "statusText": current_state["statusText"],
            "status": current_state["status"],
            "phase": current_state["phase"],
            "sessionId": current_state.get("sessionId"),
            "cwd": current_state.get("cwd"),
            "updatedAt": current_state["updatedAt"],
        }
        if not _is_internal_system_task(current_task):
            tasks.insert(0, current_task)

    return _pruned_tasks(tasks)


def _message_for_event(name, detail):
    lower = name.lower()
    if "prompt" in lower:
        return _collapse(f"开始：{detail}")
    if "notification" in lower:
        return _collapse(f"请求授权：{detail}")
    if "stop" in lower:
        return _collapse(f"结束：{detail}")
    if "session" in lower:
        return _collapse(detail)
    if "tool" in lower:
        return ""
    return _collapse(detail)


def _write_json_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def _idle_state(name="Idle"):
    now = _utc_now()
    return {
        "version": 1,
        "event": name,
        "phase": "idle",
        "status": "idle",
        "statusText": "空闲",
        "taskTitle": "",
        "taskDetail": "",
        "detail": "",
        "message": "",
        "sessionId": None,
        "cwd": None,
        "updatedAt": now,
        "tasks": [],
    }


def main():
    payload = _read_event()
    name = _event_name(payload)
    previous = _read_previous_state()
    task_id = _task_id(payload, previous)
    previous_task = _matching_task(_previous_tasks(previous), task_id)
    previous_for_fields = dict(previous)
    if previous_task:
        previous_for_fields["taskTitle"] = previous_task.get("title") or previous_task.get("taskTitle") or ""
        previous_for_fields["taskDetail"] = previous_task.get("detail") or previous_task.get("taskDetail") or ""

    detail = _detail_for_event(name, payload)
    task_title, task_detail = _task_fields_for_event(name, detail, previous_for_fields, payload)
    if _is_internal_system_event(payload, detail, task_title, task_detail):
        state = _idle_state("InternalSystemIgnored")
        remaining_tasks = _pruned_tasks(_previous_tasks(previous))
        if remaining_tasks:
            state["tasks"] = remaining_tasks
        _write_json_atomic(STATE_FILE, state)
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with EVENTS_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n")
        print(json.dumps({"ok": True, "state": str(STATE_FILE), "ignored": True}, ensure_ascii=False))
        return

    state = {
        "version": 1,
        "event": name,
        "phase": _phase_for_event(name),
        "status": _status_for_event(name, payload),
        "statusText": _status_text_for_event(name),
        "taskTitle": task_title,
        "taskDetail": task_detail,
        "detail": detail,
        "message": _message_for_event(name, detail),
        "sessionId": payload.get("session_id") or payload.get("sessionId"),
        "cwd": payload.get("cwd"),
        "updatedAt": _utc_now(),
    }
    state["tasks"] = _tasks_for_event(name, payload, state, previous)

    _write_json_atomic(STATE_FILE, state)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with EVENTS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n")

    print(json.dumps({"ok": True, "state": str(STATE_FILE)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
