"""Read/write ``~/.config/retitle/config.toml`` via minimal regex substitution.

retitle uses a flat TOML with a couple of trivial subtables — not worth
pulling in tomli/tomli-w. Same approach as the Swift app's ConfigStore.swift."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ALL_NAMERS = ("auto", "heuristic", "claude", "codex", "anthropic", "openai")
ALL_TOOLS = ("claude-code", "codex", "cursor", "antigravity")


def config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "retitle/config.toml"


@dataclass
class Values:
    idle_seconds: int = 300
    poll_seconds: int = 60
    batch_size: int = 25
    max_age_days: int = 7
    min_user_messages: int = 1
    namer: str = "auto"
    dry_run: bool = False
    tools: list[str] = field(default_factory=lambda: ["claude-code", "codex", "cursor"])


def _top_level_lines(text: str) -> list[str]:
    """Yield top-level lines (before the first ``[section]``)."""
    out = []
    for line in text.split("\n"):
        if line.strip().startswith("["):
            break
        out.append(line)
    return out


def _match(text: str, key: str) -> str | None:
    pat = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.*)$")
    for line in _top_level_lines(text):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        m = pat.match(line)
        if m:
            return m.group(1).strip()
    return None


def _int(text: str, key: str, default: int) -> int:
    raw = _match(text, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool(text: str, key: str, default: bool) -> bool:
    raw = _match(text, key)
    if raw is None:
        return default
    return raw.strip().lower() == "true"


def _string(text: str, key: str, default: str) -> str:
    raw = _match(text, key)
    if raw and raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    return default


def _array(text: str, key: str, default: list[str]) -> list[str]:
    raw = _match(text, key)
    if not raw or not raw.startswith("[") or not raw.endswith("]"):
        return default
    body = raw[1:-1]
    items = []
    for piece in body.split(","):
        p = piece.strip()
        if p.startswith('"') and p.endswith('"') and len(p) >= 2:
            items.append(p[1:-1])
    return items or default


def load() -> Values:
    path = config_path()
    if not path.exists():
        return Values()
    text = path.read_text(encoding="utf-8")
    return Values(
        idle_seconds=_int(text, "idle_seconds", 300),
        poll_seconds=_int(text, "poll_seconds", 60),
        batch_size=_int(text, "batch_size", 25),
        max_age_days=_int(text, "max_age_days", 7),
        min_user_messages=_int(text, "min_user_messages", 1),
        namer=_string(text, "namer", "auto"),
        dry_run=_bool(text, "dry_run", False),
        tools=_array(text, "tools", ["claude-code", "codex", "cursor"]),
    )


def _replace_or_append(text: str, key: str, value: str) -> str:
    lines = text.split("\n")
    section_at: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith("["):
            section_at = i
            break
    scan_end = section_at if section_at is not None else len(lines)
    pat = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for i in range(scan_end):
        if lines[i].lstrip().startswith("#"):
            continue
        if pat.match(lines[i]):
            lines[i] = f"{key} = {value}"
            return "\n".join(lines)
    insert_at = section_at if section_at is not None else len(lines)
    lines.insert(insert_at, f"{key} = {value}")
    return "\n".join(lines)


def save(v: Values) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    text = _replace_or_append(text, "idle_seconds", str(v.idle_seconds))
    text = _replace_or_append(text, "poll_seconds", str(v.poll_seconds))
    text = _replace_or_append(text, "batch_size", str(v.batch_size))
    text = _replace_or_append(text, "max_age_days", str(v.max_age_days))
    text = _replace_or_append(text, "min_user_messages", str(v.min_user_messages))
    text = _replace_or_append(text, "namer", f'"{v.namer}"')
    text = _replace_or_append(text, "dry_run", "true" if v.dry_run else "false")
    tools_str = "[" + ", ".join(f'"{t}"' for t in v.tools) + "]"
    text = _replace_or_append(text, "tools", tools_str)
    path.write_text(text, encoding="utf-8")
