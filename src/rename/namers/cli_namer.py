"""Namer that shells out to an installed CLI (`claude` or `codex`).

Reuses whatever login the user already has for that tool — no API key wiring,
no extra cost beyond the tool's own usage. This is the default (via ``auto``),
which prefers ``claude`` then ``codex``.

Calls are ephemeral: they must not land in the user's Claude Code / Codex
session list. A persisted namer call shows up as a real session titled with
the naming prompt itself, and rename would then try to rename *that* session
by calling the CLI again — a loop.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from .. import util
from .base import INSTRUCTION, Namer, build_excerpt

_TIMEOUT = 90  # codex with reasoning can take a while; keep generous

# Official Codex CLI model id (OpenAI, Feb 2026). Fast enough for a 6-word title.
_CODEX_DEFAULT_MODEL = "gpt-5.3-codex-spark"
# Claude's small/fast model — plenty for a 6-word title, and cheap.
_CLAUDE_DEFAULT_MODEL = "haiku"

# Flags that stop the namer call from showing up as a real coding session.
# Some CLI versions don't know them; we retry without them if rejected.
_CLAUDE_EPHEMERAL_FLAGS = ("--bare", "--no-session-persistence")
_CODEX_EPHEMERAL_FLAGS = ("--ephemeral", "--skip-git-repo-check")


def _scratch_cwd() -> str:
    """Isolated cwd so a leaking CLI cannot dump sessions into a user project."""
    path = util.state_dir() / "namer-scratch"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def _unknown_flag(stderr: str) -> bool:
    low = (stderr or "").lower()
    return any(
        needle in low
        for needle in (
            "unknown option",
            "unknown argument",
            "unexpected argument",
            "unrecognized",
            "invalid option",
            "unexpected option",
        )
    )


def _run(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            env=merged,
            cwd=cwd,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        util.log(f"{argv[0]} namer call failed: {exc}", level="debug")
        return None


def _run_ephemeral(
    required: list[str],
    optional: tuple[str, ...],
    trailing: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
):
    """Run with persistence-killing flags; retry without them on older CLIs."""
    proc = _run(required + list(optional) + trailing, env=env, cwd=cwd)
    if proc is not None and proc.returncode != 0 and _unknown_flag(proc.stderr):
        proc = _run(required + trailing, env=env, cwd=cwd)
    return proc


class CliNamer(Namer):
    def __init__(self, name: str, options: dict | None = None):
        self.name = name  # "claude" or "codex"
        self.options = options or {}

    def available(self) -> bool:
        return shutil.which(self.name) is not None

    def _prompt(self, messages) -> str | None:
        excerpt = build_excerpt(messages)
        if not excerpt:
            return None
        return f"{INSTRUCTION}\n\n--- conversation ---\n{excerpt}\n--- end ---"

    # -- claude ------------------------------------------------------------ #
    def _generate_claude(self, prompt: str) -> str | None:
        argv = ["claude"]
        model = self.options.get("model", _CLAUDE_DEFAULT_MODEL)
        if model:
            argv += ["--model", str(model)]
        env = {"CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1"}
        proc = _run_ephemeral(
            argv,
            _CLAUDE_EPHEMERAL_FLAGS,
            ["-p", prompt],
            env=env,
            cwd=_scratch_cwd(),
        )
        if proc is None:
            return None
        if proc.returncode != 0:
            util.log(
                f"claude namer exited {proc.returncode}: {proc.stderr.strip()[:160]}",
                level="debug",
            )
            return None
        # `claude -p` prints just the response; take the last non-empty line.
        lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        return lines[-1] if lines else None

    # -- codex ------------------------------------------------------------- #
    def _generate_codex(self, prompt: str) -> str | None:
        # `codex exec` streams a noisy transcript to stdout, so we ask it to
        # write ONLY the final assistant message to a file and read that back.
        fd, out_path = tempfile.mkstemp(prefix="rename-codex-", suffix=".txt")
        os.close(fd)
        try:
            argv = ["codex", "exec"]
            model = self.options.get("model", _CODEX_DEFAULT_MODEL)
            if model:
                argv += ["-m", str(model)]
            proc = _run_ephemeral(
                argv,
                _CODEX_EPHEMERAL_FLAGS,
                ["--output-last-message", out_path, prompt],
                cwd=_scratch_cwd(),
            )
            if proc is None:
                return None
            if proc.returncode != 0:
                util.log(
                    f"codex namer exited {proc.returncode}: "
                    f"{proc.stderr.strip()[:160]}",
                    level="debug",
                )
                return None
            try:
                text = open(out_path, encoding="utf-8", errors="replace").read()
            except OSError:
                return None
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            return lines[-1] if lines else None
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    def generate(self, messages, *, old_title=None, cwd=None, tool=None):
        prompt = self._prompt(messages)
        if not prompt:
            return None
        if self.name == "codex":
            return self._generate_codex(prompt)
        return self._generate_claude(prompt)
