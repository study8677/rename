"""Adapter contract. One concrete adapter per supported tool.

An adapter is the only thing that knows a tool's on-disk format. The engine
asks it to *discover* recent sessions, *read* a transcript for naming, and
*write* a new title back — nothing else.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Message, Session


class Adapter(ABC):
    #: stable identifier used in config/state, e.g. "claude-code"
    name: str = ""
    #: human-facing label, e.g. "Claude Code"
    label: str = ""

    @abstractmethod
    def available(self) -> bool:
        """True if this tool's data is present on the current machine."""

    @abstractmethod
    def discover(self, since: float) -> list[Session]:
        """Return sessions whose last activity is at or after ``since`` (epoch)."""

    @abstractmethod
    def read_transcript(self, session: Session) -> list[Message]:
        """Return the conversation messages for ``session``, oldest first."""

    @abstractmethod
    def set_title(self, session: Session, title: str) -> None:
        """Persist ``title`` as the session's display name."""
