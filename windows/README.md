# OpenPlana for Windows

This is a lightweight Windows port of the macOS OpenPlana desktop pet.
It uses Tkinter/ttk for the UI and reuses the shared character assets plus
the existing Codex hook state protocol.

## Requirements

- Windows 10 or later
- Python 3.10 or later, or the bundled Codex runtime Python under
  `%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime`
- Pillow: `pip install -r windows\requirements.txt` when using your own Python

Tkinter is included with standard Python installers on Windows.
The bundled Codex runtime already includes the needed packages.

## Run

From the repository root:

```bat
windows\run_open_plana.bat
```

The launcher first uses `OPEN_PLANA_PYTHON`, then the bundled Codex runtime,
then `py`/`python` from `PATH`. If you want to force a specific interpreter,
set `OPEN_PLANA_PYTHON` first:

```bat
set OPEN_PLANA_PYTHON=C:\Path\To\python.exe
windows\run_open_plana.bat
```

Useful checks:

```bat
windows\run_open_plana.bat --verify
windows\run_open_plana.bat --demo-state running
windows\install_hooks.bat
```

The pet reads Codex state from:

```text
%USERPROFILE%\.codex\open-plana\state.json
```

Settings are stored in:

```text
%APPDATA%\OpenPlanaWin\settings.json
```

## Controls

- Drag the sprite to move it.
- Drop it near the left or right screen edge to dock it.
- Right-click for settings, hook install, reset, and exit.
- Mouse wheel changes scale.

## Notes

The Windows hook installer writes Codex hooks using the current Python
interpreter and the shared `mac_os\script\codex_hook.py` script. It also
enables `codex_hooks = true` in `%USERPROFILE%\.codex\config.toml`.
