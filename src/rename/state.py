"""Tiny JSON-backed store remembering what we have already renamed.

The engine renames a session only when its content has changed since the last
title we wrote. That makes renaming idempotent (re-running does nothing) and
quietly respects titles a user edits by hand — until the conversation moves on.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from . import util

_META_KEY = "_meta"


class StateStore:
    def __init__(self, path: Path | None = None):
        self.path = path or util.state_path()
        self._data: dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        self._loaded = True

    def _ensure(self) -> None:
        if not self._loaded:
            self.load()

    # ---- Per-tool / per-session bookkeeping ---------------------------- #

    def _tools(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Per-tool sub-dict, skipping the top-level ``_meta`` namespace."""
        return {k: v for k, v in self._data.items() if k != _META_KEY and isinstance(v, dict)}

    def get(self, tool: str, sid: str) -> dict[str, Any] | None:
        self._ensure()
        bucket = self._data.get(tool)
        if not isinstance(bucket, dict):
            return None
        return bucket.get(sid)

    def renamed_count(self, tool: str) -> int:
        """How many of `tool`'s sessions rename has renamed (have renamed_at)."""
        self._ensure()
        bucket = self._data.get(tool)
        if not isinstance(bucket, dict):
            return 0
        return sum(1 for e in bucket.values() if isinstance(e, dict) and e.get("renamed_at"))

    def update(self, tool: str, sid: str, **fields: Any) -> None:
        self._ensure()
        bucket = self._data.setdefault(tool, {})
        if not isinstance(bucket, dict):
            bucket = self._data[tool] = {}
        entry = bucket.setdefault(sid, {})
        entry.update(fields)

    def prune(self, alive: set[tuple[str, str]], healthy: set[str]) -> None:
        """Drop bookkeeping for sessions no longer discoverable.

        Only prunes tools whose adapter discovered successfully this pass
        (``healthy``). If an adapter errored (e.g. its database was briefly
        locked), we keep all of its state untouched — otherwise the next pass
        would treat every one of its sessions as brand-new and could clobber
        titles the user set by hand.
        """
        self._ensure()
        for tool in list(self._data.keys()):
            if tool == _META_KEY:
                continue
            if tool not in healthy:
                continue
            bucket = self._data[tool]
            if not isinstance(bucket, dict):
                continue
            for sid in list(bucket.keys()):
                if (tool, sid) not in alive:
                    del bucket[sid]
            if not bucket:
                del self._data[tool]

    # ---- Top-level meta (baseline timestamp etc.) ---------------------- #

    def baseline(self) -> float | None:
        """Wall-clock timestamp at which the daemon first saw a session store.

        Used to skip pre-existing (historical) sessions from auto-rename:
        only conversations whose ``last_active`` is at or after the baseline
        are eligible. Returns ``None`` if no baseline has been recorded yet
        (treat as "rename anything", e.g. for the explicit historical pass).
        """
        self._ensure()
        meta = self._data.get(_META_KEY)
        if not isinstance(meta, dict):
            return None
        b = meta.get("baseline_ts")
        try:
            return float(b) if b is not None else None
        except (TypeError, ValueError):
            return None

    def set_baseline(self, ts: float) -> None:
        self._ensure()
        meta = self._data.setdefault(_META_KEY, {})
        if not isinstance(meta, dict):
            meta = self._data[_META_KEY] = {}
        meta["baseline_ts"] = float(ts)

    def ensure_baseline(self, ts: float) -> float:
        """Set the baseline to ``ts`` only if it isn't already set; return the
        active value either way."""
        existing = self.baseline()
        if existing is not None:
            return existing
        self.set_baseline(ts)
        return ts

    def save(self) -> None:
        self._ensure()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write so a crash mid-write never corrupts state.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
