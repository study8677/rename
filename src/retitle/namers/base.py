"""Namer contract and shared prompt-building helpers.

A namer turns a transcript into a short title. The default is offline and free;
LLM-backed namers produce nicer titles when you opt in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Message
from ..util import clean_text, is_trivial

INSTRUCTION = (
    "You name coding-assistant sessions. Read the conversation and reply with a "
    "concise title of 3 to 6 words capturing what the user is currently working on. "
    "Write it in the user's own language. No quotes, no trailing punctuation, no "
    "preamble — output only the title."
)


class Namer(ABC):
    name: str = ""

    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        *,
        old_title: str | None = None,
        cwd: str | None = None,
        tool: str | None = None,
    ) -> str | None:
        """Return a candidate title, or None to leave the session unchanged."""


def build_excerpt(
    messages: list[Message],
    *,
    max_msgs: int = 14,
    per_msg: int = 320,
    total: int = 3200,
) -> str:
    """Compact, recent slice of a transcript suitable for a naming prompt."""
    kept = [m for m in messages if not is_trivial(m.text)]
    rows: list[str] = []
    for m in kept[-max_msgs:]:
        text = clean_text(m.text)
        if not text:
            continue
        if len(text) > per_msg:
            text = text[:per_msg] + "…"
        who = "User" if m.role == "user" else "Assistant"
        rows.append(f"{who}: {text}")
    joined = "\n".join(rows)
    if len(joined) > total:  # keep the most recent context
        joined = joined[-total:]
    return joined
