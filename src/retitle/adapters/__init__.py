"""Adapter registry."""

from __future__ import annotations

from .. import util
from ..config import Config
from .base import Adapter
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .cursor import CursorAdapter

_REGISTRY: dict[str, type[Adapter]] = {
    ClaudeCodeAdapter.name: ClaudeCodeAdapter,
    CodexAdapter.name: CodexAdapter,
    CursorAdapter.name: CursorAdapter,
}


def all_adapters() -> list[Adapter]:
    return [cls() for cls in _REGISTRY.values()]


def get_adapters(cfg: Config) -> list[Adapter]:
    """Instantiate the configured adapters whose data is present locally."""
    out: list[Adapter] = []
    for name in cfg.tools:
        cls = _REGISTRY.get(name)
        if cls is None:
            util.log(f"unknown tool '{name}' in config", level="warn")
            continue
        adapter = cls()
        if adapter.available():
            out.append(adapter)
        else:
            util.log(f"{name}: no local data found, skipping", level="debug")
    return out


__all__ = [
    "Adapter",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "CursorAdapter",
    "all_adapters",
    "get_adapters",
]
