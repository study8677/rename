"""Thin wrapper around the ``retitle`` CLI installed elsewhere on the user's
machine. Mirrors the Swift app's RetitleCLI.swift so behavior is consistent
across platforms."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


class RetitleError(RuntimeError):
    pass


def find_retitle() -> str | None:
    """Locate the ``retitle`` binary. Honours $RETITLE_BIN, then $PATH, then
    falls back to common install locations."""
    env = os.environ.get("RETITLE_BIN")
    if env and Path(env).exists():
        return env
    via_path = shutil.which("retitle")
    if via_path:
        return via_path
    candidates = [
        Path.home() / ".local/bin/retitle",
        Path("/opt/homebrew/bin/retitle"),
        Path("/usr/local/bin/retitle"),
    ]
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(
                Path(appdata) / r"Python\PythonNN\Scripts\retitle.exe"
            )  # placeholder; user typically installs via pipx
        candidates.extend(
            [
                Path.home() / ".local/bin/retitle.exe",
                Path.home() / ".local/Programs/retitle/retitle.exe",
                Path(r"C:\Program Files\retitle\retitle.exe"),
            ]
        )
    for c in candidates:
        if c.exists():
            return str(c)
    return None


class RetitleCLI:
    def __init__(self, executable: str) -> None:
        self.executable = executable

    # -- low-level runner -------------------------------------------------

    def _run(self, args: list[str], timeout: int = 90) -> bytes:
        try:
            res = subprocess.run(
                [self.executable, *args],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as e:
            raise RetitleError(f"retitle binary missing: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise RetitleError(f"retitle {args[0]} timed out") from e
        if res.returncode != 0:
            stderr = res.stderr.decode("utf-8", errors="replace").strip()
            raise RetitleError(f"retitle {args[0]} failed: {stderr or res.returncode}")
        return res.stdout

    # -- typed calls ------------------------------------------------------

    def status(self) -> dict:
        return json.loads(self._run(["status", "--json"], timeout=30))

    def list_sessions(self, limit: int = 500, tool: str | None = None) -> list[dict]:
        args = ["list", "--json", "--limit", str(limit)]
        if tool:
            args += ["--tool", tool]
        return json.loads(self._run(args, timeout=180))

    def stats(self) -> dict:
        return json.loads(self._run(["stats", "--json"], timeout=60))

    def rename_session(self, session_id: str, tool: str | None = None) -> None:
        args = ["once", "--session", session_id]
        if tool:
            args += ["--tool", tool]
        # rename can be slow (LLM call); cap at 4 minutes.
        self._run(args, timeout=240)

    def rename_historical(self, dry_run: bool = False) -> str:
        """Run a full historical rename pass — the GUI "Rename historical
        sessions" button. Returns the last line of stderr as a short summary.
        Can take a long time; callers should run on a background thread."""
        args = ["once", "--historical", "--all"]
        if dry_run:
            args.append("--dry-run")
        try:
            res = subprocess.run(
                [self.executable, *args],
                capture_output=True,
                timeout=60 * 60,  # 1 hour cap
                check=False,
            )
        except FileNotFoundError as e:
            raise RetitleError(f"retitle binary missing: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise RetitleError("retitle once --historical timed out") from e
        stderr = res.stderr.decode("utf-8", errors="replace")
        if res.returncode != 0:
            raise RetitleError(
                f"retitle once --historical failed: "
                f"{stderr.strip() or res.returncode}"
            )
        return stderr


class DaemonControl:
    """Platform-specific daemon start/stop. On Windows retitle has no service
    integration, so we keep an explicit foreground subprocess managed by this
    tray app — paused / resumed by killing / spawning the child."""

    def __init__(self, executable: str) -> None:
        self.executable = executable
        self._child: subprocess.Popen | None = None

    def is_running(self, status: dict | None) -> bool:
        # Prefer the daemon status reported by retitle (covers launchd/systemd).
        if status and isinstance(status.get("daemon"), dict):
            line = status["daemon"].get("status_line", "")
            if "running" in line:
                return True
        return self._child is not None and self._child.poll() is None

    def pause(self, status: dict | None) -> None:
        if sys.platform == "darwin":
            self._launchctl(["unload", self._plist_path()])
            return
        if sys.platform.startswith("linux"):
            subprocess.run(
                ["systemctl", "--user", "stop", "retitle.service"],
                check=False,
            )
            return
        # Windows: kill our child, if any.
        if self._child and self._child.poll() is None:
            self._child.terminate()
            try:
                self._child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._child.kill()
        self._child = None

    def resume(self, status: dict | None) -> None:
        if sys.platform == "darwin":
            self._launchctl(["load", "-w", self._plist_path()])
            return
        if sys.platform.startswith("linux"):
            subprocess.run(
                ["systemctl", "--user", "start", "retitle.service"],
                check=False,
            )
            return
        # Windows: spawn `retitle run` as a foreground subprocess we own.
        if self._child and self._child.poll() is None:
            return
        # CREATE_NO_WINDOW = 0x08000000 (no console window)
        flags = 0
        if sys.platform == "win32":
            flags = 0x08000000
        self._child = subprocess.Popen(
            [self.executable, "run"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )

    @staticmethod
    def _plist_path() -> str:
        return str(Path.home() / "Library/LaunchAgents/com.github.retitle.plist")

    @staticmethod
    def _launchctl(args: list[str]) -> None:
        subprocess.run(["launchctl", *args], capture_output=True, check=False)
