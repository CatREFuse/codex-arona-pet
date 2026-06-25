from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from . import paths
from .activity import Activity, ActivityStore
from .characters import CharacterStore, PetCharacter
from .hooks import hook_status, install_hooks
from .settings import Settings, clamp_scale, load_settings, save_settings

TRANSPARENT = "#ff00ff"
SPRITE_BASE_SIZE = 256


def resolve_animation_state(
    activity: Activity,
    settings: Settings,
    *,
    dragging: bool = False,
    clicking: bool = False,
    idle_variant: str = "idle-sleep",
    running_variant: str = "coding",
) -> str:
    if dragging:
        return "carried"
    if clicking:
        return _side_state(settings, "pinched", "edge-pinched-left", "edge-pinched-right")
    if activity.status == "failed":
        return _side_state(settings, "rejected", "edge-rejected-left", "edge-rejected-right")
    if activity.status == "success":
        return _side_state(settings, "success", "edge-success-left", "edge-success-right")
    if not activity.has_active_session:
        return _side_state(settings, "idle-sleep", "edge-idle-sleep-left", "edge-idle-sleep-right")
    if activity.status == "running":
        return _side_state(settings, running_variant, f"edge-{running_variant}-left", f"edge-{running_variant}-right")
    if activity.status == "waiting":
        return _side_state(settings, "awaiting", "edge-awaiting-left", "edge-awaiting-right")
    if activity.status == "review":
        return _side_state(settings, "checking", "edge-checking-left", "edge-checking-right")
    return _side_state(settings, idle_variant, f"edge-{idle_variant}-left", f"edge-{idle_variant}-right")


def _side_state(settings: Settings, normal: str, left: str, right: str) -> str:
    if not settings.docked:
        return normal
    return left if settings.dock_side == "left" else right


class DesktopPetApp:
    def __init__(self, *, show_settings_on_start: bool = False) -> None:
        self.settings = load_settings()
        self.character_store = CharacterStore()
        self.character_store.reload()
        self.activity_store = ActivityStore()
        self.activity = Activity()
        self.character = self.character_store.get(self.settings.character_id)
        if self.character and self.character.id != self.settings.character_id:
            self.settings.character_id = self.character.id

        self.tick = 0
        self.current_state = ""
        self.dragging = False
        self.drag_start: tuple[int, int] | None = None
        self.window_start: tuple[int, int] | None = None
        self.click_until = 0.0
        self.idle_variant = random.choice(["idle-read", "idle-sleep"])
        self.running_variant_index = 0
        self.last_idle_switch = time.monotonic()
        self.last_running_switch = time.monotonic()
        self.photo: ImageTk.PhotoImage | None = None
        self.settings_window: tk.Toplevel | None = None

        self.root = tk.Tk()
        self.root.title("OpenPlana")
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            self.root.attributes("-alpha", 0.98)

        self.container = tk.Frame(self.root, bg=TRANSPARENT, bd=0, highlightthickness=0)
        self.container.pack(fill="both", expand=True)
        self.bubble = tk.Label(
            self.container,
            bg="#ffffff",
            fg="#20242a",
            bd=1,
            relief="solid",
            padx=10,
            pady=6,
            justify="left",
            wraplength=280,
            font=("Segoe UI", 9),
        )
        self.sprite = tk.Label(self.container, bg=TRANSPARENT, bd=0, highlightthickness=0)
        self.sprite.pack()

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Settings", command=self.show_settings)
        self.menu.add_command(label="Install Codex hooks", command=self.install_hooks_from_ui)
        self.menu.add_separator()
        self.menu.add_command(label="Next character", command=self.next_character)
        self.menu.add_command(label="Reset position", command=self.reset_position)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.quit)

        for widget in (self.root, self.container, self.sprite, self.bubble):
            widget.bind("<ButtonPress-1>", self.on_press)
            widget.bind("<B1-Motion>", self.on_drag)
            widget.bind("<ButtonRelease-1>", self.on_release)
            widget.bind("<Button-3>", self.show_menu)
            widget.bind("<MouseWheel>", self.on_wheel)

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.place_initially()
        self.loop()
        if show_settings_on_start:
            self.root.after(250, self.show_settings)

    def run(self) -> None:
        self.root.mainloop()

    def loop(self) -> None:
        self.activity = self.activity_store.read()
        state = self.resolve_state()
        if state != self.current_state:
            self.current_state = state
            self.tick = 0
        self.draw_frame(state)
        self.draw_bubble()
        self.tick += 1
        delay = int(self.frame_duration(state) * 1000)
        self.root.after(max(delay, 50), self.loop)

    def resolve_state(self) -> str:
        now = time.monotonic()
        if now - self.last_idle_switch > 14:
            self.idle_variant = "idle-sleep" if self.idle_variant == "idle-read" else "idle-read"
            self.last_idle_switch = now
        if now - self.last_running_switch > 8:
            self.running_variant_index = (self.running_variant_index + 1) % 3
            self.last_running_switch = now

        running_variant = ["coding", "idle-read", "checking"][self.running_variant_index]
        return resolve_animation_state(
            self.activity,
            self.settings,
            dragging=self.dragging,
            clicking=time.monotonic() < self.click_until,
            idle_variant=self.idle_variant,
            running_variant=running_variant,
        )

    def frame_duration(self, state: str) -> float:
        if not self.character:
            return 1.0 / 6.0
        return self.character_store.frame_duration(self.character, state)

    def draw_frame(self, state: str) -> None:
        if not self.character:
            return
        size = max(32, int(SPRITE_BASE_SIZE * clamp_scale(self.settings.scale)))
        try:
            frame = self.character_store.display_frame(self.character, state, self.tick, size=size)
        except Exception:  # noqa: BLE001 - fallback keeps the window alive.
            frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self.photo = ImageTk.PhotoImage(frame)
        self.sprite.configure(image=self.photo, width=size, height=size)
        self.root.update_idletasks()

    def draw_bubble(self) -> None:
        if self.settings.task_bubbles_collapsed:
            self.bubble.pack_forget()
            return

        lines: list[str] = []
        tasks = self.activity.visible_tasks[:3]
        if tasks:
            for task in tasks:
                detail = task.display_detail
                lines.append(task.display_title if not detail else f"{task.display_title}\n{detail}")
        elif self.activity.bubble_text:
            lines.append(self.activity.bubble_text)

        text = "\n\n".join(line for line in lines if line.strip())
        if not text:
            self.bubble.pack_forget()
            return
        self.bubble.configure(text=text)
        if not self.bubble.winfo_ismapped():
            self.bubble.pack(side="top", pady=(0, 4))
            self.sprite.pack(side="top")

    def place_initially(self) -> None:
        self.root.update_idletasks()
        width = max(self.root.winfo_reqwidth(), int(SPRITE_BASE_SIZE * self.settings.scale))
        height = max(self.root.winfo_reqheight(), int(SPRITE_BASE_SIZE * self.settings.scale))
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        if self.settings.x is None or self.settings.y is None:
            x = screen_width - width - 16
            y = screen_height - height - 96
            self.settings.dock_side = "right"
        else:
            x = int(self.settings.x)
            y = int(self.settings.y)
        self.root.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def on_press(self, event: tk.Event) -> None:
        self.drag_start = (event.x_root, event.y_root)
        self.window_start = (self.root.winfo_x(), self.root.winfo_y())

    def on_drag(self, event: tk.Event) -> None:
        if not self.drag_start or not self.window_start:
            return
        dx = event.x_root - self.drag_start[0]
        dy = event.y_root - self.drag_start[1]
        if abs(dx) + abs(dy) > 3:
            self.dragging = True
            self.settings.docked = False
        self.root.geometry(f"+{self.window_start[0] + dx}+{self.window_start[1] + dy}")

    def on_release(self, event: tk.Event) -> None:
        was_dragging = self.dragging
        self.dragging = False
        if not was_dragging:
            self.click_until = time.monotonic() + 1.4
            return
        self.snap_if_near_edge()
        self.settings.x = self.root.winfo_x()
        self.settings.y = self.root.winfo_y()
        save_settings(self.settings)

    def on_wheel(self, event: tk.Event) -> None:
        delta = 0.05 if event.delta > 0 else -0.05
        self.settings.scale = clamp_scale(self.settings.scale + delta)
        save_settings(self.settings)

    def snap_if_near_edge(self) -> None:
        x = self.root.winfo_x()
        width = self.root.winfo_width()
        screen_width = self.root.winfo_screenwidth()
        threshold = 80
        if x <= threshold:
            self.settings.docked = True
            self.settings.dock_side = "left"
            self.root.geometry(f"+0+{self.root.winfo_y()}")
        elif screen_width - (x + width) <= threshold:
            self.settings.docked = True
            self.settings.dock_side = "right"
            self.root.geometry(f"+{screen_width - width}+{self.root.winfo_y()}")

    def show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def next_character(self) -> None:
        if not self.character_store.characters:
            return
        ids = [character.id for character in self.character_store.characters]
        current = ids.index(self.character.id) if self.character and self.character.id in ids else -1
        self.settings.character_id = ids[(current + 1) % len(ids)]
        self.character = self.character_store.get(self.settings.character_id)
        save_settings(self.settings)

    def reset_position(self) -> None:
        self.settings.x = None
        self.settings.y = None
        self.settings.docked = True
        self.settings.dock_side = "right"
        save_settings(self.settings)
        self.place_initially()

    def install_hooks_from_ui(self) -> None:
        try:
            result = install_hooks()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("OpenPlana", str(exc), parent=self.root)
            return
        messagebox.showinfo("OpenPlana", f"Hooks installed.\n{result['hooks']}", parent=self.root)

    def show_settings(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        window = tk.Toplevel(self.root)
        window.title("OpenPlana Settings")
        window.resizable(False, False)
        window.attributes("-topmost", True)
        self.settings_window = window

        frame = ttk.Frame(window, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Character").grid(row=0, column=0, sticky="w")
        values = [character.id for character in self.character_store.characters]
        selected = tk.StringVar(value=self.settings.character_id)
        combo = ttk.Combobox(frame, textvariable=selected, values=values, state="readonly", width=26)
        combo.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        ttk.Label(frame, text="Scale").grid(row=1, column=0, sticky="w", pady=(10, 0))
        scale_var = tk.DoubleVar(value=self.settings.scale)
        scale = ttk.Scale(frame, from_=0.7, to=1.6, variable=scale_var, orient="horizontal")
        scale.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(10, 0))

        docked_var = tk.BooleanVar(value=self.settings.docked)
        ttk.Checkbutton(frame, text="Dock to edge", variable=docked_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        collapsed_var = tk.BooleanVar(value=self.settings.task_bubbles_collapsed)
        ttk.Checkbutton(frame, text="Collapse task bubbles", variable=collapsed_var).grid(row=3, column=0, columnspan=2, sticky="w")

        status = hook_status()
        ttk.Label(frame, text="Hooks").grid(row=4, column=0, sticky="w", pady=(10, 0))
        ttk.Label(frame, text="Installed" if status["installed"] else "Not installed").grid(row=4, column=1, sticky="w", padx=(10, 0), pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Install Hooks", command=self.install_hooks_from_ui).pack(side="left")
        ttk.Button(buttons, text="Apply", command=lambda: self.apply_settings(selected, scale_var, docked_var, collapsed_var)).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="left", padx=(8, 0))
        window.update_idletasks()
        x = min(max(self.root.winfo_x() + 48, 0), max(window.winfo_screenwidth() - window.winfo_width() - 16, 0))
        y = min(max(self.root.winfo_y() + 48, 0), max(window.winfo_screenheight() - window.winfo_height() - 48, 0))
        window.geometry(f"+{x}+{y}")
        window.lift()

    def apply_settings(
        self,
        selected: tk.StringVar,
        scale_var: tk.DoubleVar,
        docked_var: tk.BooleanVar,
        collapsed_var: tk.BooleanVar,
    ) -> None:
        self.settings.character_id = selected.get()
        self.settings.scale = clamp_scale(scale_var.get())
        self.settings.docked = bool(docked_var.get())
        self.settings.task_bubbles_collapsed = bool(collapsed_var.get())
        self.character = self.character_store.get(self.settings.character_id)
        save_settings(self.settings)

    def quit(self) -> None:
        save_settings(self.settings)
        self.root.destroy()


def verify() -> int:
    store = CharacterStore()
    characters = store.reload()
    details = []
    for character in characters:
        idle = store.animation(character, "idle-sleep")
        first = store.frame(character, "idle-sleep", 0)
        details.append(
            {
                "id": character.id,
                "states": len(character.extra_states),
                "idleFrames": len(idle.frame_paths),
                "firstFrame": list(first.size),
            }
        )
    status = hook_status()
    output = {
        "ok": bool(characters),
        "repoRoot": str(paths.repo_root()),
        "stateFile": str(paths.state_file()),
        "characters": details,
        "hooksInstalled": status["installed"],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if characters else 1


def write_demo_state(status: str) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    status = status if status in {"idle", "running", "waiting", "review", "failed", "success"} else "running"
    phase = {
        "idle": "idle",
        "running": "active",
        "waiting": "authorization",
        "review": "active",
        "failed": "failed",
        "success": "finish",
    }[status]
    payload = {
        "version": 1,
        "event": "Demo",
        "phase": phase,
        "status": status,
        "statusText": status.title(),
        "taskTitle": "OpenPlana Windows demo",
        "taskDetail": f"Current state: {status}",
        "detail": f"Current state: {status}",
        "message": "",
        "updatedAt": now,
        "tasks": [
            {
                "id": "demo",
                "title": "OpenPlana Windows demo",
                "detail": f"Current state: {status}",
                "message": f"Current state: {status}",
                "statusText": status.title(),
                "status": status,
                "phase": phase,
                "updatedAt": now,
            }
        ],
    }
    path = paths.state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenPlana Windows desktop pet")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--install-hooks", action="store_true")
    parser.add_argument("--show-settings", action="store_true")
    parser.add_argument("--demo-state", choices=["idle", "running", "waiting", "review", "failed", "success"])
    args = parser.parse_args(argv)

    if args.verify:
        return verify()
    if args.install_hooks:
        print(json.dumps(install_hooks(), indent=2, ensure_ascii=False))
        return 0
    if args.demo_state:
        write_demo_state(args.demo_state)
        return 0

    app = DesktopPetApp(show_settings_on_start=args.show_settings)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
