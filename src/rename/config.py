"""Configuration: typed defaults, TOML loading, and a friendly default file."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import util

ALL_TOOLS = (
    "claude-code",
    "codex",
    "cursor",
    "antigravity",
    "continue",
    "zed",
    "windsurf",
    "aider",
)

DEFAULT_TOML = """\
# rename configuration — https://github.com/study8677/rename
# All times are in seconds. Edit and the daemon picks it up on its next pass.

# Rename a session once it has been idle for this long (default: 5 minutes).
idle_seconds = 300

# How often the daemon scans for idle sessions.
poll_seconds = 60

# Rename at most this many sessions per scan, so a big backlog doesn't hammer
# your claude/codex CLI all at once — the daemon works through the rest over the
# next passes (most-recent first). 0 = no limit. `rename once --all` ignores it.
batch_size = 25

# Which tools to manage. Remove any you don't use.
#
# Stable: "claude-code", "codex"
# Experimental: "cursor", "antigravity", "continue", "zed", "windsurf", "aider"
#   * "antigravity" is read-only for naming when transcripts are encrypted, but
#     is still listed/searched alongside the others (drop it to hide it)
#   * "aider" is read-only — Aider has no native title slot, so renames go to
#     a sidecar file that only rename reads
tools = ["claude-code", "codex", "cursor", "antigravity"]

# How titles are generated. The default needs NO API key.
#   "auto"      - reuse the `claude` or `codex` CLI you're already logged into
#                 for good titles (no API key!); falls back to "heuristic" if
#                 neither is installed. (default)
#   "heuristic" - instant, fully offline, no LLM, no token cost
#   "claude"    - always use the `claude` CLI (defaults to the fast Haiku model)
#   "codex"     - always use the `codex` CLI
#   "anthropic" - Anthropic API directly, with your OWN key (set api_key in the
#                 [anthropic] table below, or export ANTHROPIC_API_KEY)
#   "openai"    - OpenAI API directly, with your OWN key (set api_key in the
#                 [openai] table below, or export OPENAI_API_KEY)
namer = "auto"

# Ignore sessions whose last activity is older than this many days.
max_age_days = 7

# Only rename sessions with at least this many real (non-trivial) user messages.
min_user_messages = 1

# Set true to preview renames without writing anything.
dry_run = false

# Model overrides for the CLI namers (optional). These reuse your existing
# login — no API key. Defaults are the fast/cheap models, which are plenty for
# a short title.
[claude]
model = "haiku"

[codex]
model = "gpt-5-codex"

# Bring-your-own-key namers. To use one, set `namer` above to "anthropic" or
# "openai" and provide a key below (or via the matching environment variable).
# The Rename desktop app can fill these in for you under Settings → Namer.
[anthropic]
model = "claude-haiku-4-5"
# api_key = "sk-ant-..."     # or export ANTHROPIC_API_KEY

[openai]
model = "gpt-4o-mini"
# api_key = "sk-..."         # or export OPENAI_API_KEY
"""


@dataclass
class Config:
    idle_seconds: int = 300
    poll_seconds: int = 60
    batch_size: int = 25
    tools: tuple[str, ...] = ALL_TOOLS
    namer: str = "auto"
    max_age_days: int = 7
    min_user_messages: int = 1
    dry_run: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def namer_options(self, name: str) -> dict[str, Any]:
        """Return the ``[name]`` sub-table from config (e.g. model overrides)."""
        opts = self.raw.get(name, {})
        return opts if isinstance(opts, dict) else {}


def load(path: Path | None = None) -> Config:
    """Load config from disk, falling back to defaults for anything missing."""
    path = path or util.config_path()
    raw: dict[str, Any] = {}
    if path.exists():
        try:
            raw = tomllib.loads(path.read_text("utf-8"))
        except (tomllib.TOMLDecodeError, OSError) as exc:
            util.log(f"could not read config at {path}: {exc}", level="warn")
            raw = {}

    cfg = Config(raw=raw)
    cfg.idle_seconds = int(raw.get("idle_seconds", cfg.idle_seconds))
    cfg.poll_seconds = int(raw.get("poll_seconds", cfg.poll_seconds))
    cfg.batch_size = int(raw.get("batch_size", cfg.batch_size))
    cfg.namer = str(raw.get("namer", cfg.namer))
    cfg.max_age_days = int(raw.get("max_age_days", cfg.max_age_days))
    cfg.min_user_messages = int(raw.get("min_user_messages", cfg.min_user_messages))
    cfg.dry_run = bool(raw.get("dry_run", cfg.dry_run))

    tools = raw.get("tools")
    if isinstance(tools, list) and tools:
        cfg.tools = tuple(str(t) for t in tools if t in ALL_TOOLS)
    return cfg


def ensure_default(path: Path | None = None) -> Path:
    """Create the default config file if absent. Returns its path."""
    path = path or util.config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_TOML, "utf-8")
    return path
