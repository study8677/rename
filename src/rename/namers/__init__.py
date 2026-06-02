"""Namer registry and factory."""

from __future__ import annotations

from .. import util
from ..config import Config
from .api import ApiNamer
from .base import Namer
from .cli_namer import CliNamer
from .heuristic import HeuristicNamer

NAMER_NAMES = ("auto", "heuristic", "claude", "codex", "anthropic", "openai")


def get_namer(cfg: Config) -> Namer:
    """Build the configured namer, falling back to heuristic if unavailable."""
    choice = (cfg.namer or "auto").lower()

    if choice == "auto":
        # No API key needed: reuse a CLI the user is already logged into.
        for name in ("claude", "codex"):
            namer = CliNamer(name, cfg.namer_options(name))
            if namer.available():
                util.log(
                    f"namer: auto → using your '{name}' CLI (no API key needed)",
                    level="debug",
                )
                return namer
        util.log(
            "namer: auto → no claude/codex CLI found; using the offline heuristic",
            level="debug",
        )
        return HeuristicNamer()

    if choice == "heuristic":
        return HeuristicNamer()

    if choice in ("claude", "codex"):
        namer = CliNamer(choice, cfg.namer_options(choice))
        if namer.available():
            return namer
        util.log(
            f"namer '{choice}' not found on PATH; falling back to heuristic",
            level="warn",
        )
        return HeuristicNamer()

    if choice in ("anthropic", "openai"):
        namer = ApiNamer(choice, cfg.namer_options(choice))
        if namer.available():
            return namer
        util.log(
            f"namer '{choice}' has no API key set; falling back to heuristic",
            level="warn",
        )
        return HeuristicNamer()

    util.log(f"unknown namer '{choice}'; using heuristic", level="warn")
    return HeuristicNamer()


__all__ = ["Namer", "get_namer", "HeuristicNamer", "CliNamer", "ApiNamer", "NAMER_NAMES"]
