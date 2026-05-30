"""Namer that shells out to an installed CLI (`claude` or `codex`).

Reuses whatever login the user already has for that tool — no API key wiring,
no extra cost beyond the tool's own usage. Slower than the API namer, so it is
opt-in via ``namer = "claude"`` / ``"codex"``.
"""

from __future__ import annotations

import shutil
import subprocess

from .. import util
from .base import INSTRUCTION, Namer, build_excerpt

_TIMEOUT = 45


class CliNamer(Namer):
    def __init__(self, name: str, options: dict | None = None):
        self.name = name  # "claude" or "codex"
        self.options = options or {}

    def available(self) -> bool:
        return shutil.which(self.name) is not None

    def _argv(self, prompt: str) -> list[str]:
        if self.name == "codex":
            argv = ["codex", "exec"]
            model = self.options.get("model")
            if model:
                argv += ["-m", str(model)]
            argv.append(prompt)
            return argv
        # claude headless; default to the fast, cheap Haiku model for titling.
        argv = ["claude"]
        model = self.options.get("model", "haiku")
        if model:
            argv += ["--model", str(model)]
        argv += ["-p", prompt]
        return argv

    def generate(self, messages, *, old_title=None, cwd=None, tool=None):
        excerpt = build_excerpt(messages)
        if not excerpt:
            return None
        prompt = f"{INSTRUCTION}\n\n--- conversation ---\n{excerpt}\n--- end ---"
        try:
            proc = subprocess.run(
                self._argv(prompt),
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            util.log(f"{self.name} namer call failed: {exc}", level="debug")
            return None
        if proc.returncode != 0:
            util.log(
                f"{self.name} namer exited {proc.returncode}: "
                f"{proc.stderr.strip()[:160]}",
                level="debug",
            )
            return None
        # Take the last non-empty line to dodge any model preamble.
        lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        return lines[-1] if lines else None
