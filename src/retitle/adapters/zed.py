"""Zed (zed.dev) Assistant adapter.

⚠️ Experimental — Zed Assistant's storage layout has shifted between
releases (legacy ``conversations/`` dir vs. the newer SQLite-backed
``threads``). This adapter targets the file-based layout commonly seen
today; PRs to track newer storage are welcome.

Storage:

  ~/Library/Application Support/Zed/conversations/<uuid>.json     # macOS
  ~/.config/Zed/conversations/<uuid>.json                          # Linux
  %APPDATA%/Zed/conversations/<uuid>.json                          # Windows

Each file mirrors Zed's in-memory ``Thread``: a top-level ``summary``
string (Zed's auto-title), a ``messages`` list of ``{ role, text }``
objects, and a ``project`` hint for cwd.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..models import Message, Session
from .base import Adapter

_MAX_MESSAGES = 40


def _store_dir() -> Path | None:
    candidates = [
        Path.home() / "Library/Application Support/Zed/conversations",        # macOS
        Path.home() / ".config/Zed/conversations",                            # Linux
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Zed/conversations")
    for c in candidates:
        if c.is_dir():
            return c
    return None


class ZedAdapter(Adapter):
    name = "zed"
    label = "Zed"

    def available(self) -> bool:
        return _store_dir() is not None

    def discover(self, since: float) -> list[Session]:
        root = _store_dir()
        if not root:
            return []
        out: list[Session] = []
        for path in root.glob("*.json"):
            try:
                data = json.loads(path.read_text("utf-8"))
                last_active = path.stat().st_mtime
            except (OSError, json.JSONDecodeError):
                continue
            if last_active < since:
                continue
            sid = path.stem
            title = data.get("summary") or data.get("title")
            cwd = None
            project = data.get("project") or {}
            if isinstance(project, dict):
                cwd = project.get("path") or project.get("root")
            out.append(
                Session(
                    tool=self.name,
                    id=sid,
                    title=title if isinstance(title, str) and title.strip() else None,
                    last_active=last_active,
                    cwd=cwd if isinstance(cwd, str) else None,
                    meta={"file": str(path)},
                )
            )
        return out

    def read_transcript(self, session: Session) -> list[Message]:
        path = Path(session.meta.get("file") or "")
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        msgs: list[Message] = []
        for item in (data.get("messages") or [])[-_MAX_MESSAGES:]:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            text = item.get("text") or item.get("content")
            if role not in ("user", "assistant") or not isinstance(text, str):
                continue
            msgs.append(Message(role=role, text=text))
        return msgs

    def set_title(self, session: Session, title: str) -> None:
        path = Path(session.meta["file"])
        data = json.loads(path.read_text("utf-8"))
        # Zed's auto-title field is "summary"; some legacy builds use "title".
        if "summary" in data:
            data["summary"] = title
        else:
            data["title"] = title
        tmp = path.with_suffix(path.suffix + ".retitle.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        tmp.replace(path)
