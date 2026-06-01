"""Antigravity adapter.

Google's Antigravity stores conversation summaries in the VS Code-style
``state.vscdb`` SQLite database, under
``ItemTable['antigravityUnifiedStateSync.trajectorySummaries']``. The value is
a base64-encoded protobuf with this layered shape (reverse-engineered from
Antigravity 2.0's bundled file descriptor):

  Envelope                             # repeated field 1
    Entry { string key = 1;            # the trajectory UUID
            Value value = 2 }          # nested wrapper
      Value { string value = 1 }       # itself a base64 string …
        base64-decoded →
        CascadeTrajectorySummary {
          string  summary             = 1   # ← THE TITLE
          uint32  step_count          = 2
          Timestamp last_modified_time = 3
          string  trajectory_id       = 4
          enum    status              = 5
          Timestamp created_time      = 7
          Workspaces workspaces       = 9   # repeated WorkspaceFolder
          Timestamp last_user_input_time = 10
          …                                  # plus more metadata fields
        }

Conversation transcripts (the chat messages themselves) live at
``~/.gemini/antigravity/conversations/<uuid>.pb`` and are encrypted at rest,
so we never see the raw chat. But Antigravity's agent ALSO writes plain-text
working artifacts to ``~/.gemini/antigravity/brain/<uuid>/`` while it works
— ``task.md``, ``implementation_plan.md``, ``walkthrough.md``, etc., each
with a ``*.metadata.json`` sidecar carrying a human-readable ``summary``.
``read_transcript`` feeds those to the namer, which is enough material to
produce a fresh title when Antigravity's own auto-title has gone stale.

Caveats:
  * ``trajectorySummaries`` is a *synced* store (``unifiedStateSync``). A
    local write may be overwritten by cloud sync, or get pushed to other
    devices. Treat ``set_title`` as best-effort while Antigravity is running.
  * Conversations that haven't produced brain artifacts yet (early/short
    chats) yield no transcript — the substance gate will skip those.
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
from pathlib import Path

from ..models import Message, Session
from . import _proto
from ._sqlite import connect_read, connect_write
from .base import Adapter

_KEY = "antigravityUnifiedStateSync.trajectorySummaries"
_BRAIN_DIR = Path.home() / ".gemini/antigravity/brain"

# Per-artifact and total caps so a giant implementation_plan.md doesn't blow
# the namer's prompt budget. The namer's build_excerpt also trims further.
_MAX_MD_CHARS = 1200
_MAX_MSGS = 12

# CascadeTrajectorySummary field numbers — see the docstring at the top.
_F_SUMMARY = 1
_F_TRAJECTORY_ID = 4
_F_WORKSPACES = 9
_F_LAST_USER_INPUT = 10
_F_LAST_MODIFIED = 3


def _state_vscdb() -> Path | None:
    candidates = [
        Path.home()
        / "Library/Application Support/Antigravity/User/globalStorage/state.vscdb",  # macOS
        Path.home() / ".config/Antigravity/User/globalStorage/state.vscdb",  # Linux
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Antigravity/User/globalStorage/state.vscdb")
    for c in candidates:
        if c.exists():
            return c
    return None


def _parse_entries(envelope_b64: str) -> list[tuple[str, bytes]]:
    """Decode the SQLite text -> [(uuid, CascadeTrajectorySummary-bytes), …]."""
    try:
        envelope = base64.b64decode(envelope_b64)
    except (ValueError, TypeError):
        return []
    out: list[tuple[str, bytes]] = []
    # Envelope: repeated TopEntry as field 1, wire-type 2.
    for fn, wt, val, *_ in _proto.iter_fields(envelope):
        if fn != 1 or wt != _proto.WIRE_LEN:
            continue
        uid = None
        wrapper = None
        for f2, w2, v2, *_ in _proto.iter_fields(val):
            if f2 == 1 and w2 == _proto.WIRE_LEN:
                uid = v2.decode("utf-8", errors="replace")
            elif f2 == 2 and w2 == _proto.WIRE_LEN:
                wrapper = v2
        if not uid or wrapper is None:
            continue
        # Wrapper: { value: base64-of-CascadeTrajectorySummary @ field 1 }.
        b64 = None
        for f3, w3, v3, *_ in _proto.iter_fields(wrapper):
            if f3 == 1 and w3 == _proto.WIRE_LEN:
                b64 = v3
                break
        if not b64:
            continue
        try:
            inner = base64.b64decode(b64)
        except (ValueError, TypeError):
            continue
        out.append((uid, inner))
    return out


def _first_workspace_uri(workspaces_blob: bytes | None) -> str | None:
    """Return the first workspace folder URI from a Workspaces message, if any.

    The inner schema (WorkspaceFolder) isn't in our minimal codec, so we just
    scan one level down for a length-delimited field whose bytes decode to a
    URI-looking string. Any parse misalignment (real-world payloads contain
    fields whose contents aren't valid protobuf) is swallowed — at worst we
    return ``None`` and skip the cwd hint.
    """
    if not workspaces_blob:
        return None
    try:
        outer = list(_proto.iter_fields(workspaces_blob))
    except (ValueError, IndexError):
        return None
    for _fn, wt, val, *_ in outer:
        if wt != _proto.WIRE_LEN or not val:
            continue
        try:
            inner = list(_proto.iter_fields(val))
        except (ValueError, IndexError):
            continue
        for _f2, w2, v2, *_ in inner:
            if w2 != _proto.WIRE_LEN or not v2:
                continue
            try:
                s = v2.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if s.startswith(("file:", "/", "vscode-remote:", "C:", "D:")):
                return s
    return None


def _summary_field(inner: bytes, field_num: int):
    """Return the raw value of one top-level field in CascadeTrajectorySummary."""
    for fn, _wt, val, *_ in _proto.iter_fields(inner):
        if fn == field_num:
            return val
    return None


def _rewrite_summary(envelope_b64: str, target_uid: str, new_summary: str) -> str:
    """Return a new base64 envelope with ``target_uid``'s summary field replaced."""
    envelope = base64.b64decode(envelope_b64)
    target_uid_bytes = target_uid.encode("utf-8")
    new_summary_bytes = new_summary.encode("utf-8")

    def rewrite_inner(inner: bytes) -> bytes:
        # Replace field 1 (summary) inside CascadeTrajectorySummary.
        return _proto.rewrite(
            inner,
            when=lambda fn, wt, val: fn == _F_SUMMARY and wt == _proto.WIRE_LEN,
            replace=lambda _fn, _wt, _val: _proto.encode_len_field(
                _F_SUMMARY, new_summary_bytes
            ),
        )

    def rewrite_wrapper(wrapper: bytes) -> bytes:
        # Replace wrapper.value (field 1) = base64(rewritten CascadeTrajectorySummary).
        b64_inner = None
        for f3, w3, v3, *_ in _proto.iter_fields(wrapper):
            if f3 == 1 and w3 == _proto.WIRE_LEN:
                b64_inner = v3
                break
        if b64_inner is None:
            return wrapper
        inner = base64.b64decode(b64_inner)
        new_inner = rewrite_inner(inner)
        new_b64 = base64.b64encode(new_inner)
        return _proto.rewrite(
            wrapper,
            when=lambda fn, wt, val: fn == 1 and wt == _proto.WIRE_LEN,
            replace=lambda _fn, _wt, _val: _proto.encode_len_field(1, new_b64),
        )

    def matches_target(entry_bytes: bytes) -> bool:
        for f2, w2, v2, *_ in _proto.iter_fields(entry_bytes):
            if f2 == 1 and w2 == _proto.WIRE_LEN and v2 == target_uid_bytes:
                return True
        return False

    def rewrite_entry(entry_bytes: bytes) -> bytes:
        return _proto.rewrite(
            entry_bytes,
            when=lambda fn, wt, val: fn == 2 and wt == _proto.WIRE_LEN,
            replace=lambda _fn, _wt, val: _proto.encode_len_field(2, rewrite_wrapper(val)),
        )

    new_envelope = _proto.rewrite(
        envelope,
        when=lambda fn, wt, val: (
            fn == 1 and wt == _proto.WIRE_LEN and matches_target(val)
        ),
        replace=lambda _fn, _wt, val: _proto.encode_len_field(1, rewrite_entry(val)),
    )
    return base64.b64encode(new_envelope).decode("ascii")


class AntigravityAdapter(Adapter):
    name = "antigravity"
    label = "Antigravity"

    def available(self) -> bool:
        return _state_vscdb() is not None

    def discover(self, since: float) -> list[Session]:
        db = _state_vscdb()
        if not db:
            return []
        con = connect_read(db)
        try:
            row = con.execute(
                "SELECT value FROM ItemTable WHERE key = ?", (_KEY,)
            ).fetchone()
        except sqlite3.Error:
            return []
        finally:
            con.close()
        if not row or not row[0]:
            return []

        out: list[Session] = []
        for uid, inner in _parse_entries(row[0]):
            try:
                summary_bytes = _summary_field(inner, _F_SUMMARY) or b""
                try:
                    title = summary_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    title = ""
                last_active = _proto.timestamp_to_epoch(
                    _summary_field(inner, _F_LAST_USER_INPUT)
                    or _summary_field(inner, _F_LAST_MODIFIED)
                    or b""
                )
                if last_active and last_active < since:
                    continue
                cwd = _first_workspace_uri(_summary_field(inner, _F_WORKSPACES))
            except (ValueError, IndexError, UnicodeDecodeError):
                continue  # one mangled entry shouldn't sink the whole list
            out.append(
                Session(
                    tool=self.name,
                    id=uid,
                    title=title or None,
                    last_active=last_active,
                    cwd=cwd,
                    meta={"db": str(db)},
                )
            )
        return out

    def read_transcript(self, session: Session) -> list[Message]:
        # The raw chat is encrypted (see module docstring), but Antigravity's
        # agent leaves plain-text working artifacts in
        # ~/.gemini/antigravity/brain/<uuid>/. Use those as the transcript so
        # the namer has real material when Antigravity's own auto-title goes
        # stale. Each artifact's .metadata.json carries a short ``summary``;
        # the .md alongside is the full document. We treat them as ``user``
        # turns so the heuristic namer (which only inspects user messages) can
        # use them too.
        brain = _BRAIN_DIR / session.id
        if not brain.is_dir():
            return []

        msgs: list[Message] = []

        # 1) Short, agent-authored summaries first — high signal density.
        for meta in sorted(brain.glob("*.metadata.json")):
            try:
                data = json.loads(meta.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            summary = (data.get("summary") or "").strip()
            if not summary:
                continue
            kind = (data.get("artifactType") or "").removeprefix("ARTIFACT_TYPE_").lower()
            label = kind or meta.name.removesuffix(".metadata.json")
            msgs.append(Message(role="user", text=f"[{label}] {summary}"))

        # 2) Full markdown bodies — fuller context for LLM namers.
        for md in sorted(brain.glob("*.md")):
            if md.name.endswith(".metadata.json"):
                continue
            try:
                text = md.read_text("utf-8", errors="replace").strip()
            except OSError:
                continue
            if not text:
                continue
            if len(text) > _MAX_MD_CHARS:
                text = text[:_MAX_MD_CHARS].rstrip() + "…"
            msgs.append(Message(role="user", text=text))

        return msgs[-_MAX_MSGS:]

    def set_title(self, session: Session, title: str) -> None:
        db = session.meta["db"]
        con = connect_write(db)
        con.isolation_level = None
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT value FROM ItemTable WHERE key = ?", (_KEY,)
            ).fetchone()
            if not row or not row[0]:
                raise RuntimeError("trajectorySummaries row missing")
            new_value = _rewrite_summary(row[0], session.id, title)
            r = con.execute(
                "UPDATE ItemTable SET value = ? WHERE key = ?", (new_value, _KEY)
            )
            if r.rowcount < 1:
                raise RuntimeError("trajectorySummaries update affected no rows")
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
