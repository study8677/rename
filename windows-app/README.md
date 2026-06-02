# Retitle GUI (Windows / cross-platform)

A Qt-based tray + dashboard GUI for retitle, built with **PySide6**.

Designed primarily for Windows (since the [Swift app](../macos-app/) is
macOS-only), but the same code runs on macOS and Linux too — useful if you
want a unified GUI across machines, or you don't want to build Swift on Mac.

## Features

- **System tray icon** with status indicator (running / paused / not installed),
  recent rename notifications (Windows balloons / macOS Notification Center),
  pause/resume daemon, open dashboard, show log, quit
- **Dashboard window** — stats cards (Tracked / Sessions / Stale / Renamed),
  brand-coloured tool filter chips (Claude / Codex / Cursor / Antigravity),
  search across titles and paths, per-session "Rename now" with bypass of the
  idle gate, before/after diff display, hover effects
- **Settings dialog** — visual editor for `~/.config/retitle/config.toml`
  with spin boxes, dropdowns, and checkboxes. Saves back as TOML preserving
  comments
- **i18n** — English + 简体中文, auto-detected from system locale
  (override with `RETITLE_GUI_LANG=en` or `RETITLE_GUI_LANG=zh-Hans`)
- **Lazy loading** — session scanning only triggers on dashboard open or
  manual refresh, so the app doesn't hammer your AI session stores
  (which on Windows means fewer Defender/AntiVirus interruptions; on macOS
  fewer TCC prompts)
- **Friendly progress** — no raw `stderr`; all messages translated to
  human-readable toast notifications

## Install

```powershell
# Install retitle first (the CLI is the source of truth; the GUI just talks to it)
pipx install retitle

# Then install the GUI
pipx install retitle-gui
# or: pip install --user retitle-gui

# Launch
retitle-gui
```

Or from source:

```powershell
git clone https://github.com/study8677/retitle.git
cd retitle/windows-app
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -e .
retitle-gui
```

## Daemon mode on Windows

retitle's `install` subcommand wires up launchd on macOS and systemd on Linux,
but Windows has no equivalent built in. The tray app fills the gap: when you
hit **Resume** on Windows, it spawns `retitle run` as a child process with
no console window and keeps it alive. **Pause** kills the child. Closing
the tray app stops the daemon.

For boot-time start, drop a shortcut to `retitle-gui` (or
`pythonw -m retitle_gui`) into:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

## Layout

```
windows-app/
├── pyproject.toml
└── retitle_gui/
    ├── __main__.py        # entry point: `python -m retitle_gui`
    ├── app.py             # QApp + tray + dashboard + settings + toasts
    ├── bridge.py          # subprocess wrapper around `retitle ... --json`
    ├── config_store.py    # read/write ~/.config/retitle/config.toml
    └── i18n.py            # en / zh-Hans translation dict
```

## Status

**⚠ This GUI is shipped untested on Windows from the developer's end.** Code
was written and reviewed on macOS, but I do not have a Windows machine to
verify it runs. If you try it on Windows and hit anything broken, please
open an issue with the traceback — fixes will be fast.

PySide6 (Qt6) is fully cross-platform; the Windows-specific code paths
(`subprocess` with `CREATE_NO_WINDOW`, plist/systemd guards) all degrade
cleanly on other OSes.
