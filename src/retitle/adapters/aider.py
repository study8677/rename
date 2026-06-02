"""Aider adapter (read-only).

⚠️ Experimental and **read-only**.

Aider doesn't keep per-session titles or even a central session index —
each Aider invocation just appends to ``.aider.chat.history.md`` in the
project directory. So we can:

  * Surface Aider sessions in ``retitle list`` / ``retitle search`` /
    ``retitle stats`` (one "session" per project directory that has an
    ``.aider.chat.history.md`` file)
  * Generate titles from those transcripts via the namer
  * **NOT** write the title back — there's nowhere to put it that Aider
    would read

``set_title`` writes a sibling ``.aider.chat.history.md.title`` file so
the title sticks in ``retitle list`` between scans, even though Aider
itself ignores it.

We look in two places:

  * ``~/.aider.chat.history.md`` (Aider's default when run without --chat-history-file)
  * Any directory containing ``.aider.chat.history.md`` that we can find
    via a quick walk under the user's home dir, bounded by depth so we
    don't traverse the whole disk.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..models import Message, Session
from .base import Adapter

# Cap the walk so big homedirs don't kill discovery.
_MAX_DIRS_WALKED = 5000
_MAX_DEPTH = 6
_MAX_TRANSCRIPT_CHARS = 16000
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
              "Library", "Applications", ".cache", "dist", "build", ".next"}


def _walk_for_aider_chats(root: Path) -> list[Path]:
    found: list[Path] = []
    if not root.is_dir():
        return found
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        seen += 1
        if seen > _MAX_DIRS_WALKED:
            break
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth > _MAX_DEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".cache")]
        if ".aider.chat.history.md" in filenames:
            found.append(Path(dirpath) / ".aider.chat.history.md")
    return found


def _discover_chats() -> list[Path]:
    chats: list[Path] = []
    home_chat = Path.home() / ".aider.chat.history.md"
    if home_chat.exists():
        chats.append(home_chat)
    chats.extend(_walk_for_aider_chats(Path.home()))
    # Deduplicate, preserve order.
    seen: set[Path] = set()
    out: list[Path] = []
    for p in chats:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(rp)
    return out


class AiderAdapter(Adapter):
    name = "aider"
    label = "Aider"

    def available(self) -> bool:
        return bool(_discover_chats())

    def discover(self, since: float) -> list[Session]:
        out: list[Session] = []
        for chat in _discover_chats():
            try:
                last_active = chat.stat().st_mtime
            except OSError:
                continue
            if last_active < since:
                continue
            sid = str(chat.parent.resolve()).replace("/", "_")
            title_sidecar = chat.with_suffix(chat.suffix + ".title")
            title = None
            if title_sidecar.exists():
                try:
                    title = title_sidecar.read_text("utf-8").strip() or None
                except OSError:
                    pass
            out.append(
                Session(
                    tool=self.name,
                    id=sid,
                    title=title,
                    last_active=last_active,
                    cwd=str(chat.parent),
                    meta={"chat": str(chat), "sidecar": str(title_sidecar)},
                )
            )
        return out

    def read_transcript(self, session: Session) -> list[Message]:
        chat = Path(session.meta.get("chat") or "")
        if not chat.exists():
            return []
        try:
            text = chat.read_text("utf-8", errors="replace")
        except OSError:
            return []
        # Aider's chat history is structured with "####" headers for user
        # turns and free-form text for replies. Treat the file's content
        # as one big user message — the namer can summarize it.
        if len(text) > _MAX_TRANSCRIPT_CHARS:
            text = text[-_MAX_TRANSCRIPT_CHARS:]
        return [Message(role="user", text=text)]

    def set_title(self, session: Session, title: str) -> None:
        # Aider has no native title slot. Persist to a sidecar file so the
        # name sticks in `retitle list` across scans.
        sidecar = Path(session.meta["sidecar"])
        sidecar.write_text(title, "utf-8")
