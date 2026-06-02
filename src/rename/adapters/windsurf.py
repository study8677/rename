"""Windsurf (Codeium) adapter — a Cursor fork.

⚠️ Experimental — Windsurf is a VS Code-based fork of Cursor by Codeium.
Schema appears to mirror Cursor's (state.vscdb with composerHeaders +
composerData), but we rely on those internals being stable across forks.
PRs to track divergence are welcome.

We delegate to the Cursor adapter implementation with the database path
swapped to Windsurf's own user-data directory.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from . import cursor as cursor_mod
from .base import Adapter


def _vscdb() -> Path | None:
    candidates = [
        Path.home()
        / "Library/Application Support/Windsurf/User/globalStorage/state.vscdb",   # macOS
        Path.home() / ".config/Windsurf/User/globalStorage/state.vscdb",            # Linux
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Windsurf/User/globalStorage/state.vscdb")
    for c in candidates:
        if c.exists():
            return c
    return None


class WindsurfAdapter(Adapter):
    name = "windsurf"
    label = "Windsurf"

    def available(self) -> bool:
        return _vscdb() is not None

    def discover(self, since):
        db = _vscdb()
        if not db:
            return []
        # Monkey-patch the Cursor lookup just for this call so we reuse all
        # of Cursor's discovery logic without forking it.
        orig = cursor_mod._vscdb
        cursor_mod._vscdb = lambda: db
        try:
            sessions = cursor_mod.CursorAdapter().discover(since)
        except (sqlite3.Error, OSError, ValueError):
            sessions = []
        finally:
            cursor_mod._vscdb = orig
        # Re-tag the sessions so they're attributed to Windsurf, not Cursor.
        for s in sessions:
            s.tool = self.name
        return sessions

    def read_transcript(self, session):
        orig = cursor_mod._vscdb
        cursor_mod._vscdb = lambda: Path(session.meta.get("db", ""))
        try:
            return cursor_mod.CursorAdapter().read_transcript(session)
        except (sqlite3.Error, OSError, ValueError):
            return []
        finally:
            cursor_mod._vscdb = orig

    def set_title(self, session, title):
        orig = cursor_mod._vscdb
        cursor_mod._vscdb = lambda: Path(session.meta.get("db", ""))
        try:
            return cursor_mod.CursorAdapter().set_title(session, title)
        finally:
            cursor_mod._vscdb = orig
