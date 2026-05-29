"""Shared SQLite helpers for the Codex and Cursor adapters.

Both tools keep their data in live SQLite databases (WAL mode) that the app may
have open. We read with ``query_only`` (lets WAL reads work without risking a
write) and write with a generous ``busy_timeout`` to ride out brief locks.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_read(path: Path | str) -> sqlite3.Connection:
    con = sqlite3.connect(str(path), timeout=5.0)
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA query_only=ON")
    return con


def connect_write(path: Path | str) -> sqlite3.Connection:
    con = sqlite3.connect(str(path), timeout=5.0)
    con.execute("PRAGMA busy_timeout=5000")
    return con
