from __future__ import annotations

import argparse
import compileall
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageGrab

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "windows") not in sys.path:
    sys.path.insert(0, str(ROOT / "windows"))

from open_plana_win.activity import Activity, ActivityStore, activity_from_snapshot
from open_plana_win.app import resolve_animation_state
from open_plana_win.characters import CharacterStore
from open_plana_win.hooks import hook_status, install_hooks
from open_plana_win.settings import Settings, clamp_scale, load_settings, save_settings

REQUIRED_STATES = [
    "idle-normal",
    "idle-read",
    "idle-sleep",
    "coding",
    "checking",
    "awaiting",
    "rejected",
    "success",
    "pinched",
    "carried",
    "edge-peek-left",
    "edge-peek-right",
    "edge-idle-read-left",
    "edge-idle-read-right",
    "edge-idle-normal-left",
    "edge-idle-normal-right",
    "edge-idle-sleep-left",
    "edge-idle-sleep-right",
    "edge-coding-left",
    "edge-coding-right",
    "edge-checking-left",
    "edge-checking-right",
    "edge-awaiting-left",
    "edge-awaiting-right",
    "edge-rejected-left",
    "edge-rejected-right",
    "edge-success-left",
    "edge-success-right",
    "edge-pinched-left",
    "edge-pinched-right",
]

STATUS_CASES = {
    "idle": ("idle", "idle"),
    "running": ("running", "active"),
    "waiting": ("waiting", "authorization"),
    "review": ("review", "active"),
    "failed": ("failed", "failed"),
    "success": ("success", "finish"),
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


class QA:
    def __init__(self, *, live: bool) -> None:
        self.live = live
        self.out_dir = ROOT / "screenshots" / "windows-qa"
        self.tmp_dir = ROOT / ".codex" / "tmp" / "windows-qa"
        self.appdata = self.tmp_dir / "appdata"
        self.codex_home = self.tmp_dir / "codex-home"
        self.checks: list[Check] = []
        self.artifacts: dict[str, str] = {}
        self.env = os.environ.copy()
        self.env["OPEN_PLANA_ROOT"] = str(ROOT)
        self.env["CODEX_HOME"] = str(self.codex_home)
        self.env["APPDATA"] = str(self.appdata)
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.env["OPEN_PLANA_PYTHON"] = sys.executable

    def run(self) -> int:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.codex_home.mkdir(parents=True, exist_ok=True)
        self.appdata.mkdir(parents=True, exist_ok=True)

        self.check_compile()
        characters = self.check_characters()
        self.check_settings()
        self.check_activity_and_mapping()
        self.check_hooks()
        self.check_launcher()
        self.build_asset_contact_sheets(characters)
        self.build_status_matrix(characters[0] if characters else None)
        if self.live:
            self.capture_live_ui()
        self.clean_pycache()
        self.write_report()
        self.print_summary()
        return 0 if all(check.ok for check in self.checks) else 1

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(name, ok, detail))

    def check_compile(self) -> None:
        ok = compileall.compile_dir(str(ROOT / "windows"), quiet=1, force=True)
        self.record("python-compile", ok, "compileall windows")

    def clean_pycache(self) -> None:
        for directory in (ROOT / "windows").rglob("__pycache__"):
            shutil.rmtree(directory, ignore_errors=True)

    def check_characters(self) -> list:
        store = CharacterStore()
        characters = store.reload()
        self.record("characters-found", len(characters) >= 4, f"loaded={len(characters)}")
        for character in characters:
            missing = [state for state in REQUIRED_STATES if state not in character.extra_states]
            self.record(f"character-{character.id}-required-states", not missing, ", ".join(missing[:5]))
            blank_states: list[str] = []
            bad_size_states: list[str] = []
            for state in REQUIRED_STATES:
                try:
                    frame_count = store.frame_count(character, state)
                    if frame_count < 1:
                        blank_states.append(state)
                        continue
                    for index in (0, frame_count // 2, frame_count - 1):
                        frame = store.frame(character, state, index)
                        if frame.size != (256, 256):
                            bad_size_states.append(f"{state}:{frame.size}")
                        if frame.getbbox() is None:
                            blank_states.append(state)
                            break
                except Exception as exc:  # noqa: BLE001
                    blank_states.append(f"{state}:{exc}")
            self.record(f"character-{character.id}-frame-sizes", not bad_size_states, "; ".join(bad_size_states[:5]))
            self.record(f"character-{character.id}-visible-frames", not blank_states, "; ".join(blank_states[:5]))
        return characters

    def check_settings(self) -> None:
        os.environ["APPDATA"] = str(self.appdata)
        settings = Settings(character_id="plana-neo", scale=2.5, docked=True, dock_side="left", x=10, y=20)
        save_settings(settings)
        loaded = load_settings()
        self.record("settings-clamp", loaded.scale == 1.6, f"scale={loaded.scale}")
        bom_path = self.appdata / "OpenPlanaWin" / "settings.json"
        bom_path.write_text('{"character_id":"arona-neo","scale":0.1,"dock_side":"left"}', encoding="utf-8-sig")
        loaded = load_settings()
        self.record("settings-utf8-bom", loaded.character_id == "arona-neo" and loaded.scale == 0.7, f"{loaded}")
        self.record("scale-clamp-low-high", clamp_scale(0.1) == 0.7 and clamp_scale(2.5) == 1.6)

    def check_activity_and_mapping(self) -> None:
        floating = Settings(docked=False)
        left = Settings(docked=True, dock_side="left")
        right = Settings(docked=True, dock_side="right")
        expected = {
            "running": ("coding", "edge-coding-left", "edge-coding-right"),
            "waiting": ("awaiting", "edge-awaiting-left", "edge-awaiting-right"),
            "review": ("checking", "edge-checking-left", "edge-checking-right"),
            "failed": ("rejected", "edge-rejected-left", "edge-rejected-right"),
            "success": ("success", "edge-success-left", "edge-success-right"),
        }
        for status, phase in STATUS_CASES.values():
            activity = self._activity(status, phase)
            if status == "idle":
                self.record(
                    "state-map-idle-sleep",
                    resolve_animation_state(activity, right) == "edge-idle-sleep-right",
                )
                continue
            normal, edge_left, edge_right = expected[status]
            self.record(f"state-map-{status}-floating", resolve_animation_state(activity, floating) == normal)
            self.record(f"state-map-{status}-left", resolve_animation_state(activity, left) == edge_left)
            self.record(f"state-map-{status}-right", resolve_animation_state(activity, right) == edge_right)
        running = self._activity("running", "active")
        self.record("state-map-dragging", resolve_animation_state(running, right, dragging=True) == "carried")
        self.record("state-map-clicking", resolve_animation_state(running, left, clicking=True) == "edge-pinched-left")

        state_path = self.codex_home / "open-plana" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(self._snapshot("running", "active"), indent=2), encoding="utf-8")
        store = ActivityStore(state_path)
        self.record("activity-store-running", store.read().status == "running")

    def check_hooks(self) -> None:
        os.environ["CODEX_HOME"] = str(self.codex_home)
        result = install_hooks(sys.executable)
        status = hook_status()
        self.record("hook-install-ok", bool(result["ok"]) and status["installed"], json.dumps(status, ensure_ascii=False))
        self.record("hook-state-count", len(status["keys"]) == 6, f"keys={len(status['keys'])}")

        payload = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Windows QA hook event",
            "cwd": str(ROOT),
        }
        completed = subprocess.run(
            [sys.executable, str(ROOT / "mac_os" / "script" / "codex_hook.py")],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
            env=self.env,
        )
        state = ActivityStore(self.codex_home / "open-plana" / "state.json").read()
        self.record("hook-runtime-state", completed.returncode == 0 and state.status == "running", completed.stdout.strip())

    def check_launcher(self) -> None:
        completed = subprocess.run(
            ["cmd", "/c", str(ROOT / "windows" / "run_open_plana.bat"), "--verify"],
            text=True,
            capture_output=True,
            check=False,
            env=self.env,
            cwd=ROOT,
        )
        self.record("bat-launcher-verify", completed.returncode == 0 and '"ok": true' in completed.stdout, completed.stdout[-400:])

    def build_asset_contact_sheets(self, characters: list) -> None:
        store = CharacterStore()
        store.reload()
        for character in characters:
            thumbs = []
            for state in REQUIRED_STATES:
                frame = store.frame(character, state, 0).resize((96, 96), Image.Resampling.LANCZOS)
                thumbs.append((state, frame))
            sheet = self._grid(thumbs, columns=6, cell=(150, 124), title=f"{character.id} states")
            path = self.out_dir / f"asset-contact-{character.id}.png"
            sheet.save(path)
        self.artifacts["assetContactSheets"] = str(self.out_dir / "asset-contact-*.png")

    def build_status_matrix(self, character) -> None:
        if character is None:
            return
        store = CharacterStore()
        store.reload()
        rows = []
        for status, (raw_status, phase) in STATUS_CASES.items():
            activity = self._activity(raw_status, phase)
            settings = Settings(docked=True, dock_side="right")
            state = resolve_animation_state(activity, settings)
            frame = store.frame(character, state, 0).resize((128, 128), Image.Resampling.LANCZOS)
            panel = Image.new("RGBA", (300, 170), (245, 247, 252, 255))
            panel.alpha_composite(frame, (12, 22))
            draw = ImageDraw.Draw(panel)
            draw.rectangle((154, 36, 292, 118), fill=(255, 255, 255, 255), outline=(120, 130, 150, 255))
            draw.text((162, 44), status, fill=(20, 24, 30, 255))
            draw.text((162, 68), state, fill=(50, 62, 75, 255))
            rows.append((status, panel))
        sheet = self._grid(rows, columns=3, cell=(320, 204), title="status to animation matrix")
        path = self.out_dir / "status-matrix.png"
        sheet.save(path)
        self.artifacts["statusMatrix"] = str(path)

    def capture_live_ui(self) -> None:
        appdata_settings = self.appdata / "OpenPlanaWin" / "settings.json"
        appdata_settings.parent.mkdir(parents=True, exist_ok=True)
        appdata_settings.write_text(
            json.dumps(
                {
                    "character_id": "plana-neo",
                    "scale": 1.0,
                    "docked": False,
                    "dock_side": "right",
                    "x": 1040,
                    "y": 80,
                    "task_bubbles_collapsed": False,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        shots = []
        proc = self._start_ui([])
        try:
            for status in STATUS_CASES:
                subprocess.run(
                    [sys.executable, str(ROOT / "windows" / "open_plana.py"), "--demo-state", status],
                    env=self.env,
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                time.sleep(0.9)
                shot = self._capture_region(f"live-{status}.png")
                shots.append((status, shot))
            self.artifacts["liveStatusScreenshots"] = str(self.out_dir / "live-*.png")
        finally:
            self._stop_process(proc)

        proc = self._start_ui(["--show-settings"])
        try:
            time.sleep(3.0)
            rect = self._find_window_rect("OpenPlana Settings")
            self.record("settings-window-created", rect is not None, str(rect))
            if rect is None:
                settings_shot = self._capture_region("settings-window.png", left=900, top=40, right=1900, bottom=700)
            else:
                left, top, right, bottom = rect
                settings_shot = self._capture_region(
                    "settings-window.png",
                    left=max(left - 24, 0),
                    top=max(top - 24, 0),
                    right=right + 24,
                    bottom=bottom + 24,
                )
            self.artifacts["settingsWindow"] = str(settings_shot)
        finally:
            self._stop_process(proc)

        panels = []
        for status, path in shots:
            img = Image.open(path).convert("RGBA").resize((280, 190), Image.Resampling.LANCZOS)
            panels.append((status, img))
        sheet = self._grid(panels, columns=3, cell=(320, 230), title="live UI screenshots")
        matrix_path = self.out_dir / "live-status-matrix.png"
        sheet.save(matrix_path)
        self.artifacts["liveStatusMatrix"] = str(matrix_path)

    def _start_ui(self, args: list[str]) -> subprocess.Popen:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        executable = str(pythonw if pythonw.exists() else Path(sys.executable))
        return subprocess.Popen(
            [executable, str(ROOT / "windows" / "open_plana.py"), *args],
            env=self.env,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _stop_process(self, proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)

    def _capture_region(
        self,
        name: str,
        *,
        left: int = 900,
        top: int = 40,
        right: int = 1900,
        bottom: int = 650,
    ) -> Path:
        img = ImageGrab.grab(all_screens=True)
        right = min(right, img.size[0])
        bottom = min(bottom, img.size[1])
        crop = img.crop((left, top, right, bottom))
        path = self.out_dir / name
        crop.save(path)
        self.record(f"live-shot-{name}", _image_has_content(crop), f"{crop.size}")
        self.record(f"live-shot-no-magenta-fringe-{name}", _magenta_pixel_ratio(crop) < 0.0008, f"ratio={_magenta_pixel_ratio(crop):.6f}")
        return path

    def _find_window_rect(self, title: str) -> tuple[int, int, int, int] | None:
        import ctypes

        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

        user32 = ctypes.windll.user32
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        text = ctypes.create_unicode_buffer(512)
        result: list[tuple[int, int, int, int]] = []

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            user32.GetWindowTextW(hwnd, text, 512)
            if text.value != title:
                return True
            rect = RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                result.append((rect.left, rect.top, rect.right, rect.bottom))
            return False

        user32.EnumWindows(enum_proc(callback), 0)
        return result[0] if result else None

    def write_report(self) -> None:
        report = {
            "ok": all(check.ok for check in self.checks),
            "checks": [asdict(check) for check in self.checks],
            "artifacts": self.artifacts,
        }
        json_path = self.out_dir / "report.json"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        md_path = self.out_dir / "report.md"
        lines = [
            "# Windows QA Report",
            "",
            f"Overall: {'PASS' if report['ok'] else 'FAIL'}",
            "",
            "## Checks",
            "",
        ]
        for check in self.checks:
            lines.append(f"- {'PASS' if check.ok else 'FAIL'} `{check.name}` {check.detail}")
        lines.extend(["", "## Artifacts", ""])
        for key, value in self.artifacts.items():
            lines.append(f"- `{key}`: `{value}`")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.artifacts["reportJson"] = str(json_path)
        self.artifacts["reportMarkdown"] = str(md_path)

    def print_summary(self) -> None:
        failed = [check for check in self.checks if not check.ok]
        print(json.dumps(
            {
                "ok": not failed,
                "checks": len(self.checks),
                "failed": [check.name for check in failed],
                "artifacts": self.artifacts,
            },
            indent=2,
            ensure_ascii=False,
        ))

    def _activity(self, status: str, phase: str) -> Activity:
        return activity_from_snapshot(self._snapshot(status, phase))

    def _snapshot(self, status: str, phase: str) -> dict:
        return {
            "version": 1,
            "event": "QA",
            "phase": phase,
            "status": status,
            "statusText": status.title(),
            "taskTitle": f"QA {status}",
            "taskDetail": f"Testing {status}",
            "detail": f"Testing {status}",
            "message": "",
            "updatedAt": "2099-01-01T00:00:00Z",
            "tasks": [] if status == "idle" else [
                {
                    "id": f"qa-{status}",
                    "title": f"QA {status}",
                    "detail": f"Testing {status}",
                    "message": f"Testing {status}",
                    "statusText": status.title(),
                    "status": status,
                    "phase": phase,
                    "updatedAt": "2099-01-01T00:00:00Z",
                }
            ],
        }

    def _grid(self, items, *, columns: int, cell: tuple[int, int], title: str) -> Image.Image:
        rows = (len(items) + columns - 1) // columns
        width = columns * cell[0]
        height = rows * cell[1] + 42
        sheet = Image.new("RGBA", (width, height), (238, 241, 247, 255))
        draw = ImageDraw.Draw(sheet)
        draw.text((12, 12), title, fill=(20, 24, 30, 255))
        for index, (label, image) in enumerate(items):
            col = index % columns
            row = index // columns
            x = col * cell[0]
            y = 42 + row * cell[1]
            draw.rectangle((x + 6, y + 6, x + cell[0] - 6, y + cell[1] - 6), fill=(255, 255, 255, 255), outline=(204, 212, 224, 255))
            sheet.alpha_composite(image, (x + 12, y + 12))
            draw.text((x + 12, y + cell[1] - 22), label[:24], fill=(35, 42, 55, 255))
        return sheet


def _image_has_content(image: Image.Image) -> bool:
    extrema = image.convert("RGB").getextrema()
    return any(high - low > 8 for low, high in extrema)


def _magenta_pixel_ratio(image: Image.Image) -> float:
    rgb = image.convert("RGB")
    pixels = rgb.load()
    width, height = rgb.size
    count = 0
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r > 235 and b > 235 and g < 45:
                count += 1
    return count / max(width * height, 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run functional and visual QA for OpenPlana Windows")
    parser.add_argument("--live", action="store_true", help="launch the Tkinter UI and capture screenshots")
    args = parser.parse_args(argv)
    return QA(live=args.live).run()


if __name__ == "__main__":
    raise SystemExit(main())
