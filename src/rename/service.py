"""Install rename as a background service.

launchd on macOS, systemd on Linux, a login Startup shortcut on Windows.
"""

from __future__ import annotations

import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

from . import util

LABEL = "com.github.rename"
_PASS_ENV = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def _program_args() -> list[str]:
    # `-m rename` is robust regardless of where the console script landed.
    return [sys.executable, "-m", "rename", "run"]


def _launch_agent_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _systemd_unit() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / "rename.service"


def _passthrough_env() -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}
    for key in _PASS_ENV:
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def install() -> int:
    if sys.platform == "darwin":
        return _install_launchd()
    if sys.platform.startswith("linux"):
        return _install_systemd()
    if sys.platform == "win32":
        return _install_windows()
    util.log(
        f"auto-install unsupported on {sys.platform}; "
        "run `rename run` under your own process manager.",
        level="warn",
    )
    return 1


def uninstall() -> int:
    if sys.platform == "darwin":
        return _uninstall_launchd()
    if sys.platform.startswith("linux"):
        return _uninstall_systemd()
    if sys.platform == "win32":
        return _uninstall_windows()
    util.log(f"nothing to uninstall on {sys.platform}")
    return 0


# -- macOS / launchd -------------------------------------------------------- #
def _install_launchd() -> int:
    plist = _launch_agent_plist()
    plist.parent.mkdir(parents=True, exist_ok=True)
    log = util.log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    spec = {
        "Label": LABEL,
        "ProgramArguments": _program_args(),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
        "EnvironmentVariables": _passthrough_env(),
    }
    with open(plist, "wb") as fh:
        plistlib.dump(spec, fh)
    plist.chmod(0o600)  # may embed API keys — keep it owner-only
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    res = subprocess.run(
        ["launchctl", "load", "-w", str(plist)], capture_output=True, text=True
    )
    if res.returncode != 0:
        util.log(f"launchctl load failed: {res.stderr.strip()}", level="warn")
        return 1
    util.log(f"installed launchd agent → {plist}")
    util.log(f"logs → {log}")
    return 0


def _uninstall_launchd() -> int:
    plist = _launch_agent_plist()
    if not plist.exists():
        util.log("no launchd agent installed")
        return 0
    subprocess.run(["launchctl", "unload", "-w", str(plist)], capture_output=True)
    plist.unlink()
    util.log(f"removed {plist}")
    return 0


# -- Linux / systemd -------------------------------------------------------- #
def _install_systemd() -> int:
    unit = _systemd_unit()
    unit.parent.mkdir(parents=True, exist_ok=True)
    exec_start = " ".join(shlex.quote(a) for a in _program_args())
    env_lines = "\n".join(
        f'Environment="{k}={v}"' for k, v in _passthrough_env().items()
    )
    unit.write_text(
        f"""[Unit]
Description=rename — auto-rename idle AI coding sessions
After=default.target

[Service]
Type=simple
ExecStart={exec_start}
{env_lines}
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
""",
        "utf-8",
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    res = subprocess.run(
        ["systemctl", "--user", "enable", "--now", "rename.service"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        util.log(f"systemctl enable failed: {res.stderr.strip()}", level="warn")
        return 1
    util.log(f"installed systemd user service → {unit}")
    return 0


def _uninstall_systemd() -> int:
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", "rename.service"],
        capture_output=True,
    )
    unit = _systemd_unit()
    if unit.exists():
        unit.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    util.log("removed systemd user service")
    return 0


# -- Windows / Startup shortcut --------------------------------------------- #
def _startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _windows_shortcut() -> Path:
    return _startup_dir() / "rename.lnk"


def _pythonw() -> str:
    # pythonw.exe runs the daemon with no console window; fall back to python.exe.
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return str(pyw if pyw.exists() else exe)


def _ps(script: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )


def _install_windows() -> int:
    # Windows has no launchd/systemd, so we register a per-user login Startup
    # shortcut (the documented, dependency-free equivalent) and start the
    # daemon immediately — launchd's RunAtLoad / systemd's `--now`.
    startup = _startup_dir()
    startup.mkdir(parents=True, exist_ok=True)
    lnk = _windows_shortcut()
    pyw = _pythonw()
    log = util.log_path()
    log.parent.mkdir(parents=True, exist_ok=True)

    def q(p: object) -> str:  # single-quote-safe for a PowerShell '...' literal
        return str(p).replace("'", "''")

    script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{q(lnk)}'); "
        f"$s.TargetPath = '{q(pyw)}'; "
        "$s.Arguments = '-m rename run'; "
        f"$s.WorkingDirectory = '{q(Path.home())}'; "
        "$s.WindowStyle = 7; "
        "$s.Description = 'rename - auto-rename idle AI coding sessions'; "
        "$s.Save()"
    )
    res = _ps(script)
    if res.returncode != 0:
        util.log(
            f"failed to create Startup shortcut: {res.stderr.strip() or res.returncode}",
            level="warn",
        )
        return 1

    # Start it now too, fully detached and with no console window. The child
    # inherits its own copy of the log handle, so we close ours right after.
    DETACHED_PROCESS = 0x00000008
    try:
        log_fh = open(log, "a", buffering=1)
        try:
            subprocess.Popen(
                [pyw, "-m", "rename", "run"],
                stdout=log_fh,
                stderr=log_fh,
                stdin=subprocess.DEVNULL,
                creationflags=DETACHED_PROCESS,
                close_fds=True,
            )
        finally:
            log_fh.close()
    except OSError as e:
        util.log(f"shortcut installed but could not start now: {e}", level="warn")

    util.log(f"installed Startup shortcut → {lnk}")
    util.log("rename will start automatically when you sign in.")
    util.log(f"logs → {log}")
    return 0


def _running_daemon_count() -> int:
    res = _ps(
        "@(Get-CimInstance Win32_Process -Filter "
        "\"Name='pythonw.exe' or Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*-m rename run*' }).Count"
    )
    try:
        return int((res.stdout or "0").strip() or "0")
    except ValueError:
        return 0


def _uninstall_windows() -> int:
    lnk = _windows_shortcut()
    removed = False
    if lnk.exists():
        try:
            lnk.unlink()
            removed = True
        except OSError as e:
            util.log(f"could not remove shortcut: {e}", level="warn")
    # Best-effort: stop a daemon a previous sign-in may have started.
    _ps(
        "Get-CimInstance Win32_Process -Filter "
        "\"Name='pythonw.exe' or Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*-m rename run*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    util.log("removed Startup shortcut" if removed else "no Startup shortcut installed")
    return 0


def status_line() -> str:
    if sys.platform == "darwin":
        if not _launch_agent_plist().exists():
            return "daemon: not installed (launchd)"
        res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        running = LABEL in (res.stdout or "")
        return f"daemon: {'running' if running else 'installed (not running)'} (launchd)"
    if sys.platform.startswith("linux"):
        if not _systemd_unit().exists():
            return "daemon: not installed (systemd)"
        res = subprocess.run(
            ["systemctl", "--user", "is-active", "rename.service"],
            capture_output=True,
            text=True,
        )
        return f"daemon: {res.stdout.strip() or 'unknown'} (systemd)"
    if sys.platform == "win32":
        if not _windows_shortcut().exists():
            return "daemon: not installed (Windows Startup)"
        state = (
            "running" if _running_daemon_count() > 0 else "installed (starts at sign-in)"
        )
        return f"daemon: {state} (Windows Startup)"
    return "daemon: manual (auto-install unsupported on this platform)"
