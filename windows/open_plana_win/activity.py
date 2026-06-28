from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import paths

ACTIVE_TASK_TTL_SECONDS = 5 * 60


STATUS_ALIASES = {
    "completed": "success",
    "complete": "success",
    "finished": "success",
    "finish": "success",
    "succeeded": "success",
    "done": "success",
}


@dataclass
class TaskBubble:
    id: str
    title: str = ""
    detail: str = ""
    message: str = ""
    status_text: str = ""
    status: str = "idle"
    phase: str = "idle"
    updated_at: dt.datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status in {"running", "waiting", "review"} or self.phase in {
            "start",
            "active",
            "authorization",
        }

    @property
    def shows_bubble(self) -> bool:
        return self.status in {"running", "waiting", "failed", "success"} or self.phase in {
            "start",
            "active",
            "authorization",
            "finish",
            "failed",
        }

    @property
    def display_title(self) -> str:
        return self.title.strip() or self.status_text.strip() or "Codex"

    @property
    def display_detail(self) -> str:
        for value in (self.message, self.detail, self.status_text):
            value = value.strip()
            if value and value != self.display_title:
                return value
        return ""


@dataclass
class Activity:
    event: str = "Idle"
    phase: str = "idle"
    status: str = "idle"
    status_text: str = "Idle"
    task_title: str = ""
    task_detail: str = ""
    detail: str = ""
    message: str = ""
    updated_at: dt.datetime | None = None
    tasks: list[TaskBubble] = field(default_factory=list)

    @property
    def has_active_session(self) -> bool:
        if any(task.is_active and not _is_internal_text(task.display_title) for task in self.tasks):
            return True
        if self.status in {"running", "waiting", "review"}:
            return not self.is_internal
        return self.phase in {"start", "active", "authorization"} and not self.is_internal

    @property
    def is_internal(self) -> bool:
        return any(
            _is_internal_text(value)
            for value in (self.task_title, self.task_detail, self.detail, self.message)
        )

    @property
    def bubble_text(self) -> str:
        for value in (self.message, self.detail):
            value = value.strip()
            if value and self.phase != "active":
                return value
        return ""

    @property
    def visible_tasks(self) -> list[TaskBubble]:
        tasks = [task for task in self.tasks if task.shows_bubble and not _is_internal_text(task.display_title)]
        if tasks:
            return _dedupe_tasks(tasks)
        if self.status in {"running", "failed", "success"} or self.phase in {"start", "active", "finish", "failed"}:
            title = self.task_title.strip() or self.task_detail.strip() or self.status_text
            detail = self.task_detail.strip() or self.detail.strip() or self.status_text
            return [
                TaskBubble(
                    id="current",
                    title=title,
                    detail=detail,
                    message=self.message,
                    status_text=self.status_text,
                    status=self.status,
                    phase=self.phase,
                    updated_at=self.updated_at,
                )
            ]
        return []


class ActivityStore:
    def __init__(self, state_path: Path | None = None) -> None:
        self.state_path = state_path or paths.state_file()
        self.last_error: str | None = None

    def read(self) -> Activity:
        if not self.state_path.exists():
            self.last_error = None
            return Activity()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            activity = activity_from_snapshot(data)
            activity.tasks = [
                task
                for task in activity.tasks
                if not _is_stale(task.updated_at) and not _is_internal_text(task.display_title)
            ]
            if activity.is_internal or (activity.updated_at and _is_stale(activity.updated_at) and activity.has_active_session):
                return Activity()
            self.last_error = None
            return activity
        except Exception as exc:  # noqa: BLE001 - surfaced in settings UI.
            self.last_error = str(exc)
            return Activity(event="ReadError", status_text="State read failed")


def activity_from_snapshot(data: dict[str, Any]) -> Activity:
    phase = str(data.get("phase") or _phase_for_event(str(data.get("event") or ""))).lower()
    status = normalize_status(data.get("status") or _status_for_event(str(data.get("event") or "")))
    if phase == "finish" and status != "failed":
        status = "success"
    tasks = [_task_from_snapshot(item) for item in data.get("tasks") or [] if isinstance(item, dict)]
    return Activity(
        event=str(data.get("event") or "Idle"),
        phase=phase,
        status=status,
        status_text=str(data.get("statusText") or status.title()),
        task_title=str(data.get("taskTitle") or ""),
        task_detail=str(data.get("taskDetail") or ""),
        detail=str(data.get("detail") or ""),
        message=str(data.get("message") or ""),
        updated_at=parse_time(data.get("updatedAt")),
        tasks=tasks,
    )


def normalize_status(value: Any) -> str:
    raw = str(value or "idle").strip().lower()
    raw = STATUS_ALIASES.get(raw, raw)
    if raw in {"idle", "running", "waiting", "review", "failed", "success"}:
        return raw
    return "idle"


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _task_from_snapshot(data: dict[str, Any]) -> TaskBubble:
    phase = str(data.get("phase") or "active").lower()
    status = normalize_status(data.get("status") or ("success" if phase == "finish" else "running"))
    if phase == "finish" and status != "failed":
        status = "success"
    return TaskBubble(
        id=str(data.get("id") or data.get("sessionId") or data.get("cwd") or "current"),
        title=str(data.get("title") or data.get("taskTitle") or ""),
        detail=str(data.get("detail") or data.get("taskDetail") or ""),
        message=str(data.get("message") or ""),
        status_text=str(data.get("statusText") or status.title()),
        status=status,
        phase=phase,
        updated_at=parse_time(data.get("updatedAt")),
    )


def _phase_for_event(event: str) -> str:
    lower = event.lower()
    if "prompt" in lower or "session" in lower:
        return "start"
    if "notification" in lower:
        return "authorization"
    if "stop" in lower or "finish" in lower or "complete" in lower:
        return "finish"
    if "error" in lower or "fail" in lower:
        return "failed"
    if "tool" in lower:
        return "active"
    return "idle"


def _status_for_event(event: str) -> str:
    lower = event.lower()
    if "notification" in lower:
        return "waiting"
    if "stop" in lower or "finish" in lower or "complete" in lower:
        return "success"
    if "error" in lower or "fail" in lower:
        return "failed"
    if "prompt" in lower or "session" in lower or "tool" in lower:
        return "running"
    return "idle"


def _is_stale(value: dt.datetime | None) -> bool:
    if value is None:
        return False
    now = dt.datetime.now(dt.timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return (now - value).total_seconds() > ACTIVE_TASK_TTL_SECONDS


def _is_internal_text(value: str) -> bool:
    return any(
        needle in value
        for needle in (
            "## Memory Writing Agent:",
            "Memory Writing Agent: Phase 2",
            "/.codex/memories",
            "/.codex/rollout_summaries",
        )
    )


def _semantic_key(task: TaskBubble) -> str:
    value = task.display_title.casefold().strip()
    return re.sub(r"\s+", " ", value) or task.id


def _dedupe_tasks(tasks: list[TaskBubble]) -> list[TaskBubble]:
    seen: set[str] = set()
    result: list[TaskBubble] = []
    for task in tasks:
        key = _semantic_key(task)
        if key in seen:
            continue
        seen.add(key)
        result.append(task)
    return result
