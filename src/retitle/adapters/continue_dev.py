"""Continue (continue.dev VS Code / JetBrains extension) adapter.

⚠️ Experimental — Continue's session schema evolves frequently and we can
only verify it against the version installed at the time of writing.
PRs to track schema changes are welcome.

Storage (cross-platform, in the user's home dir):

  ~/.continue/sessions/<sessionId>.json

Each file is a self-contained session record roughly shaped like:

  {
    "sessionId": "...",
    "title": "Untitled" | "user-set title",
    "history": [
      { "message": { "role": "user", "content": "..." } },
      { "message": { "role": "assistant", "content": "..." } },
      ...
    ],
    "workspaceDirectory": "/path/to/cwd",
    ...
  }
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Message, Session
from .base import Adapter

_SESSIONS_DIR = Path.home() / ".continue" / "sessions"
_MAX_MESSAGES = 40


def _sessions_dir() -> Path | None:
    if _SESSIONS_DIR.is_dir():
        return _SESSIONS_DIR
    return None


class ContinueAdapter(Adapter):
    name = "continue"
    label = "Continue"

    def available(self) -> bool:
        return _sessions_dir() is not None

    def discover(self, since: float) -> list[Session]:
        root = _sessions_dir()
        if not root:
            return []
        sessions: list[Session] = []
        for path in root.glob("*.json"):
            try:
                data = json.loads(path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            try:
                last_active = path.stat().st_mtime
            except OSError:
                continue
            if last_active < since:
                continue
            sid = str(data.get("sessionId") or path.stem)
            title = data.get("title")
            cwd = data.get("workspaceDirectory") or data.get("workspace")
            sessions.append(
                Session(
                    tool=self.name,
                    id=sid,
                    title=title if isinstance(title, str) and title.strip() else None,
                    last_active=last_active,
                    cwd=cwd if isinstance(cwd, str) else None,
                    meta={"file": str(path)},
                )
            )
        return sessions

    def read_transcript(self, session: Session) -> list[Message]:
        path = Path(session.meta.get("file") or "")
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        out: list[Message] = []
        for item in (data.get("history") or [])[-_MAX_MESSAGES:]:
            msg = item.get("message") if isinstance(item, dict) else None
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            content = msg.get("content")
            if role not in ("user", "assistant") or not isinstance(content, str):
                continue
            out.append(Message(role=role, text=content))
        return out

    def set_title(self, session: Session, title: str) -> None:
        path = Path(session.meta["file"])
        data = json.loads(path.read_text("utf-8"))
        data["title"] = title
        # Atomic-ish write: same dir, then replace.
        tmp = path.with_suffix(path.suffix + ".retitle.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        tmp.replace(path)
