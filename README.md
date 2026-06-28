# OpenPlana Codex Pet

OpenPlana is a Codex-aware desktop pet. The repository currently contains:

- `mac_os/`: the original SwiftUI/AppKit macOS implementation.
- `shared/Characters/`: shared character manifests and animation frames.
- `windows/`: a lightweight Tkinter/ttk Windows implementation.

## Windows

Launch the Windows port:

```bat
windows\run_open_plana.bat
```

The launcher can use the bundled Codex runtime Python. If you use your own
Python, install Pillow first with `pip install -r windows\requirements.txt`.

Useful commands:

```bat
windows\run_open_plana.bat --verify
windows\run_open_plana.bat --demo-state running
windows\install_hooks.bat
```

For more details, see `windows\README.md`.
