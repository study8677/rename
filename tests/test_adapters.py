"""Round-trip tests for each adapter against synthetic fixtures.

These also exercise the write path (set_title) without touching any real data.
"""

import base64
import json
import sqlite3
import time

import pytest

from retitle.adapters import _proto, antigravity, claude_code, codex, cursor


# --------------------------------------------------------------------------- #
# Claude Code
# --------------------------------------------------------------------------- #
def _write_jsonl(path, rows):
    # Force UTF-8 — on Windows the default encoding is cp1252 which can't
    # represent Unicode (e.g. CJK) characters in our fixtures.
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def test_claude_adapter_roundtrip(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    proj = projects / "-Users-me-proj"
    proj.mkdir(parents=True)
    sid = "11111111-1111-1111-1111-111111111111"
    f = proj / f"{sid}.jsonl"
    _write_jsonl(
        f,
        [
            {"type": "permission-mode", "permissionMode": "default"},
            {"type": "last-prompt", "lastPrompt": "Add a dark mode toggle", "sessionId": sid},
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Sure."}]},
            },
            {"type": "last-prompt", "lastPrompt": "好的", "sessionId": sid},
            {"type": "last-prompt", "lastPrompt": "Now fix the migration bug", "sessionId": sid},
            {"type": "ai-title", "aiTitle": "Dark mode toggle", "sessionId": sid},
        ],
    )
    monkeypatch.setattr(claude_code, "_projects_root", lambda: projects)
    adapter = claude_code.ClaudeCodeAdapter()

    sessions = adapter.discover(0)
    assert len(sessions) == 1
    s = sessions[0]
    assert s.id == sid
    assert s.title == "Dark mode toggle"

    msgs = adapter.read_transcript(s)
    users = [m.text for m in msgs if m.role == "user"]
    assert "Add a dark mode toggle" in users
    assert "Now fix the migration bug" in users

    adapter.set_title(s, "Fix DB migration")
    assert claude_code._last_ai_title(f) == "Fix DB migration"


# --------------------------------------------------------------------------- #
# Codex
# --------------------------------------------------------------------------- #
def test_codex_adapter_roundtrip(tmp_path, monkeypatch):
    db = tmp_path / "state_5.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, rollout_path TEXT, "
        "updated_at_ms INTEGER, cwd TEXT, archived INTEGER, first_user_message TEXT)"
    )
    tid = "019e0000-0000-7000-8000-000000000000"
    rollout = tmp_path / "rollout.jsonl"
    _write_jsonl(
        rollout,
        [
            {"type": "session_meta", "payload": {"id": tid}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Refactor the auth module"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Done"}],
                },
            },
        ],
    )
    now_ms = int(time.time() * 1000)
    con.execute(
        "INSERT INTO threads VALUES (?,?,?,?,?,?,?)",
        (tid, "Old title", str(rollout), now_ms, "/proj", 0, "Refactor the auth module"),
    )
    con.commit()
    con.close()
    monkeypatch.setattr(codex, "_find_state_db", lambda: db)
    adapter = codex.CodexAdapter()

    sessions = adapter.discover(0)
    assert len(sessions) == 1
    s = sessions[0]
    assert s.id == tid and s.title == "Old title"

    msgs = adapter.read_transcript(s)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].text == "Refactor the auth module"

    adapter.set_title(s, "Auth refactor")
    con = sqlite3.connect(db)
    got = con.execute("SELECT title FROM threads WHERE id=?", (tid,)).fetchone()[0]
    con.close()
    assert got == "Auth refactor"


def test_codex_skips_archived(tmp_path, monkeypatch):
    db = tmp_path / "state_5.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, rollout_path TEXT, "
        "updated_at_ms INTEGER, cwd TEXT, archived INTEGER, first_user_message TEXT)"
    )
    now_ms = int(time.time() * 1000)
    con.execute(
        "INSERT INTO threads VALUES (?,?,?,?,?,?,?)",
        ("a", "T", "", now_ms, "/p", 1, "x"),  # archived
    )
    con.commit()
    con.close()
    monkeypatch.setattr(codex, "_find_state_db", lambda: db)
    assert codex.CodexAdapter().discover(0) == []


# --------------------------------------------------------------------------- #
# Cursor
# --------------------------------------------------------------------------- #
def test_cursor_adapter_roundtrip(tmp_path, monkeypatch):
    db = tmp_path / "state.vscdb"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
    cid = "comp-1"
    now_ms = int(time.time() * 1000)
    headers = {"allComposers": [{"composerId": cid, "name": "Old Name", "lastUpdatedAt": now_ms}]}
    con.execute(
        "INSERT INTO ItemTable VALUES (?,?)",
        ("composer.composerHeaders", json.dumps(headers)),
    )
    composer_data = {
        "composerId": cid,
        "name": "Old Name",
        "fullConversationHeadersOnly": [
            {"bubbleId": "b1", "type": 1},
            {"bubbleId": "b2", "type": 2},
        ],
    }
    con.execute(
        "INSERT INTO cursorDiskKV VALUES (?,?)",
        (f"composerData:{cid}", json.dumps(composer_data)),
    )
    con.execute(
        "INSERT INTO cursorDiskKV VALUES (?,?)",
        (f"bubbleId:{cid}:b1", json.dumps({"type": 1, "text": "Optimize the SQL query"})),
    )
    con.execute(
        "INSERT INTO cursorDiskKV VALUES (?,?)",
        (f"bubbleId:{cid}:b2", json.dumps({"type": 2, "text": "Sure"})),
    )
    con.commit()
    con.close()
    monkeypatch.setattr(cursor, "_vscdb", lambda: db)
    adapter = cursor.CursorAdapter()

    sessions = adapter.discover(0)
    assert len(sessions) == 1
    s = sessions[0]
    assert s.id == cid and s.title == "Old Name"

    msgs = adapter.read_transcript(s)
    assert msgs[0].role == "user" and "SQL" in msgs[0].text
    assert msgs[1].role == "assistant"

    adapter.set_title(s, "SQL optimization")
    con = sqlite3.connect(db)
    hraw = con.execute(
        "SELECT value FROM ItemTable WHERE key='composer.composerHeaders'"
    ).fetchone()[0]
    craw = con.execute(
        "SELECT value FROM cursorDiskKV WHERE key=?", (f"composerData:{cid}",)
    ).fetchone()[0]
    con.close()
    assert json.loads(hraw)["allComposers"][0]["name"] == "SQL optimization"
    assert json.loads(craw)["name"] == "SQL optimization"


def _cursor_db_with_headers(tmp_path, cid, composer_data_value):
    """Build a Cursor DB with a header row and an optional composerData row."""
    db = tmp_path / "state.vscdb"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
    headers = {
        "allComposers": [
            {"composerId": cid, "name": "Old", "lastUpdatedAt": int(time.time() * 1000)}
        ]
    }
    con.execute(
        "INSERT INTO ItemTable VALUES (?,?)", ("composer.composerHeaders", json.dumps(headers))
    )
    if composer_data_value is not None:
        con.execute(
            "INSERT INTO cursorDiskKV VALUES (?,?)", (f"composerData:{cid}", composer_data_value)
        )
    con.commit()
    con.close()
    return db


def _header_name(db, cid):
    con = sqlite3.connect(db)
    raw = con.execute(
        "SELECT value FROM ItemTable WHERE key='composer.composerHeaders'"
    ).fetchone()[0]
    con.close()
    return json.loads(raw)["allComposers"][0]["name"]


def test_cursor_set_title_missing_blob_raises_and_rolls_back(tmp_path, monkeypatch):
    cid = "comp-x"
    db = _cursor_db_with_headers(tmp_path, cid, composer_data_value=None)  # no composerData row
    monkeypatch.setattr(cursor, "_vscdb", lambda: db)
    adapter = cursor.CursorAdapter()
    s = adapter.discover(0)[0]
    with pytest.raises(Exception):
        adapter.set_title(s, "New")
    assert _header_name(db, cid) == "Old"  # header NOT half-updated


def test_cursor_set_title_corrupt_blob_rolls_back(tmp_path, monkeypatch):
    cid = "comp-y"
    db = _cursor_db_with_headers(tmp_path, cid, composer_data_value="{not valid json")
    monkeypatch.setattr(cursor, "_vscdb", lambda: db)
    adapter = cursor.CursorAdapter()
    s = adapter.discover(0)[0]
    with pytest.raises(Exception):
        adapter.set_title(s, "New")
    assert _header_name(db, cid) == "Old"  # atomic: header untouched


# --------------------------------------------------------------------------- #
# Antigravity
# --------------------------------------------------------------------------- #
def _ag_encode_timestamp(seconds: int, nanos: int = 0) -> bytes:
    return _proto.encode_len_field(
        3,  # placeholder field — actual field number set by caller
        b"",
    )  # not used directly; we use _ag_inline_timestamp below


def _ag_timestamp_payload(seconds: int, nanos: int = 0) -> bytes:
    """The bytes inside a Timestamp message: seconds @ 1, nanos @ 2."""
    out = bytearray()
    if seconds:
        out += _proto.write_varint((1 << 3) | _proto.WIRE_VARINT)
        out += _proto.write_varint(seconds)
    if nanos:
        out += _proto.write_varint((2 << 3) | _proto.WIRE_VARINT)
        out += _proto.write_varint(nanos)
    return bytes(out)


def _ag_make_summary(*, summary: str, trajectory_id: str, last_user_input: int) -> bytes:
    """Build a minimal CascadeTrajectorySummary payload."""
    out = bytearray()
    # Field numbers from CascadeTrajectorySummary
    out += _proto.encode_len_field(1, summary.encode("utf-8"))  # summary
    out += _proto.encode_len_field(4, trajectory_id.encode("ascii"))  # trajectory_id
    out += _proto.encode_len_field(10, _ag_timestamp_payload(last_user_input))
    return bytes(out)


def _ag_make_envelope(entries: list[tuple[str, bytes]]) -> str:
    """Build the base64-encoded TrajectorySummariesUpdate envelope."""
    out = bytearray()
    for uid, inner_bytes in entries:
        # ValueWrapper { value @ 1 = base64(inner) }
        wrapper = _proto.encode_len_field(1, base64.b64encode(inner_bytes))
        # TopEntry { key @ 1 = uuid; value @ 2 = wrapper }
        entry = (
            _proto.encode_len_field(1, uid.encode("ascii"))
            + _proto.encode_len_field(2, wrapper)
        )
        # Envelope: repeated TopEntry @ field 1
        out += _proto.encode_len_field(1, entry)
    return base64.b64encode(bytes(out)).decode("ascii")


def _ag_make_db(tmp_path, entries):
    db = tmp_path / "state.vscdb"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    con.execute(
        "INSERT INTO ItemTable VALUES (?,?)",
        ("antigravityUnifiedStateSync.trajectorySummaries", _ag_make_envelope(entries)),
    )
    con.commit()
    con.close()
    return db


def test_antigravity_discover_and_set_title(tmp_path, monkeypatch):
    uid_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    uid_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    now = int(time.time())
    entries = [
        (uid_a, _ag_make_summary(summary="Old A", trajectory_id=uid_a, last_user_input=now - 100)),
        (uid_b, _ag_make_summary(summary="Old B", trajectory_id=uid_b, last_user_input=now - 50)),
    ]
    db = _ag_make_db(tmp_path, entries)
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: db)
    adapter = antigravity.AntigravityAdapter()

    assert adapter.available() is True
    sessions = adapter.discover(0)
    by_id = {s.id: s for s in sessions}
    assert set(by_id) == {uid_a, uid_b}
    assert by_id[uid_a].title == "Old A"
    assert by_id[uid_b].title == "Old B"
    assert abs(by_id[uid_a].last_active - (now - 100)) < 1
    assert adapter.read_transcript(by_id[uid_a]) == []  # encrypted — no transcript

    # Rename A; B must remain untouched.
    adapter.set_title(by_id[uid_a], "Renamed A")
    sessions2 = adapter.discover(0)
    by_id2 = {s.id: s for s in sessions2}
    assert by_id2[uid_a].title == "Renamed A"
    assert by_id2[uid_b].title == "Old B"


def test_antigravity_read_transcript_from_brain(tmp_path, monkeypatch):
    """When brain artifacts exist, we feed them to the namer as user messages."""
    uid = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    db = _ag_make_db(
        tmp_path,
        [(uid, _ag_make_summary(summary="stale", trajectory_id=uid, last_user_input=1))],
    )
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: db)

    brain = tmp_path / "brain" / uid
    brain.mkdir(parents=True)
    (brain / "task.md.metadata.json").write_text(
        json.dumps(
            {
                "artifactType": "ARTIFACT_TYPE_TASK",
                "summary": "Migrate auth middleware to use the new JWT signer.",
                "updatedAt": "2026-06-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (brain / "task.md").write_text(
        "# Task\n\nMigrate the auth middleware away from the legacy HMAC signer.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(antigravity, "_BRAIN_DIR", tmp_path / "brain")

    adapter = antigravity.AntigravityAdapter()
    s = adapter.discover(0)[0]
    msgs = adapter.read_transcript(s)
    assert msgs, "brain artifacts should produce a non-empty transcript"
    joined = " ".join(m.text for m in msgs)
    assert "JWT signer" in joined or "HMAC signer" in joined
    assert all(m.role == "user" for m in msgs)


def test_antigravity_read_transcript_empty_when_no_brain(tmp_path, monkeypatch):
    uid = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    db = _ag_make_db(
        tmp_path,
        [(uid, _ag_make_summary(summary="no brain", trajectory_id=uid, last_user_input=1))],
    )
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: db)
    monkeypatch.setattr(antigravity, "_BRAIN_DIR", tmp_path / "brain")  # missing dir
    adapter = antigravity.AntigravityAdapter()
    s = adapter.discover(0)[0]
    assert adapter.read_transcript(s) == []


def test_antigravity_set_title_unicode(tmp_path, monkeypatch):
    uid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    db = _ag_make_db(
        tmp_path,
        [(uid, _ag_make_summary(summary="x", trajectory_id=uid, last_user_input=int(time.time())))],
    )
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: db)
    adapter = antigravity.AntigravityAdapter()
    s = adapter.discover(0)[0]
    adapter.set_title(s, "修复登录页面 ✨")
    s2 = adapter.discover(0)[0]
    assert s2.title == "修复登录页面 ✨"


def test_antigravity_unavailable_when_no_db(tmp_path, monkeypatch):
    # An empty tmp dir has no state.vscdb
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: None)
    adapter = antigravity.AntigravityAdapter()
    assert adapter.available() is False
    assert adapter.discover(0) == []


def test_antigravity_survives_malformed_envelope(tmp_path, monkeypatch):
    db = tmp_path / "state.vscdb"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    con.execute(
        "INSERT INTO ItemTable VALUES (?,?)",
        ("antigravityUnifiedStateSync.trajectorySummaries", "not-base64-at-all!!!"),
    )
    con.commit()
    con.close()
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: db)
    assert antigravity.AntigravityAdapter().discover(0) == []


def test_antigravity_set_title_unknown_id_rolls_back(tmp_path, monkeypatch):
    uid = "11111111-1111-1111-1111-111111111111"
    other = "22222222-2222-2222-2222-222222222222"
    entries = [
        (uid, _ag_make_summary(summary="Only one", trajectory_id=uid, last_user_input=1))
    ]
    db = _ag_make_db(tmp_path, entries)
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: db)
    adapter = antigravity.AntigravityAdapter()
    # Real session present, but we pass a Session with a different id
    from retitle.models import Session

    s = Session(tool="antigravity", id=other, title="X", last_active=0, meta={"db": str(db)})
    # Our rewrite is a no-op when the target isn't found, but the UPDATE still
    # runs — the file content is byte-identical, which is fine: the existing
    # entry's title stays "Only one".
    adapter.set_title(s, "Should not appear")
    sessions = adapter.discover(0)
    assert sessions[0].title == "Only one"


# --------------------------------------------------------------------------- #
# Antigravity — Companion App (raw .pb file, no base64/envelope)
# --------------------------------------------------------------------------- #
def _ag_make_pb_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    """Build a Companion App agyhub_summaries_proto.pb payload.

    Top-level: repeated TopEntry @ field 1. TopEntry: {uuid @ 1, inner @ 2}
    where ``inner`` is the CascadeTrajectorySummary directly (no base64).
    """
    out = bytearray()
    for uid, inner_bytes in entries:
        entry = (
            _proto.encode_len_field(1, uid.encode("ascii"))
            + _proto.encode_len_field(2, inner_bytes)
        )
        out += _proto.encode_len_field(1, entry)
    return bytes(out)


def _ag_make_pb_file(tmp_path, entries) -> "object":
    pb = tmp_path / "agyhub_summaries_proto.pb"
    pb.write_bytes(_ag_make_pb_bytes(entries))
    return pb


def test_antigravity_companion_discover_and_set_title(tmp_path, monkeypatch):
    uid_a = "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa"
    uid_b = "bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb"
    now = int(time.time())
    entries = [
        (uid_a, _ag_make_summary(summary="Stale title A", trajectory_id=uid_a,
                                 last_user_input=now - 200)),
        (uid_b, _ag_make_summary(summary="Stale title B", trajectory_id=uid_b,
                                 last_user_input=now - 100)),
    ]
    pb = _ag_make_pb_file(tmp_path, entries)
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: None)
    monkeypatch.setattr(antigravity, "_companion_pb", lambda: pb)
    adapter = antigravity.AntigravityAdapter()

    assert adapter.available() is True
    sessions = adapter.discover(0)
    by_id = {s.id: s for s in sessions}
    assert set(by_id) == {uid_a, uid_b}
    assert by_id[uid_a].title == "Stale title A"
    assert by_id[uid_a].meta["store"] == "companion"
    assert by_id[uid_a].meta["pb"] == str(pb)
    assert abs(by_id[uid_a].last_active - (now - 200)) < 1

    # Rename A; B must remain untouched, file structure must round-trip.
    adapter.set_title(by_id[uid_a], "Renamed A")
    sessions2 = adapter.discover(0)
    by_id2 = {s.id: s for s in sessions2}
    assert by_id2[uid_a].title == "Renamed A"
    assert by_id2[uid_b].title == "Stale title B"


def test_antigravity_companion_unicode_title(tmp_path, monkeypatch):
    uid = "cccccccc-3333-3333-3333-cccccccccccc"
    pb = _ag_make_pb_file(
        tmp_path,
        [(uid, _ag_make_summary(summary="x", trajectory_id=uid,
                                last_user_input=int(time.time())))],
    )
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: None)
    monkeypatch.setattr(antigravity, "_companion_pb", lambda: pb)
    adapter = antigravity.AntigravityAdapter()
    s = adapter.discover(0)[0]
    adapter.set_title(s, "重构支付回调 ✨")
    s2 = adapter.discover(0)[0]
    assert s2.title == "重构支付回调 ✨"


def test_antigravity_companion_set_title_unknown_id_is_safe_noop(tmp_path, monkeypatch):
    uid = "dddddddd-4444-4444-4444-dddddddddddd"
    other = "eeeeeeee-5555-5555-5555-eeeeeeeeeeee"
    pb = _ag_make_pb_file(
        tmp_path,
        [(uid, _ag_make_summary(summary="Only one", trajectory_id=uid, last_user_input=1))],
    )
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: None)
    monkeypatch.setattr(antigravity, "_companion_pb", lambda: pb)
    adapter = antigravity.AntigravityAdapter()
    original_bytes = pb.read_bytes()

    from retitle.models import Session

    s = Session(
        tool="antigravity",
        id=other,
        title="X",
        last_active=0,
        meta={"store": "companion", "pb": str(pb)},
    )
    adapter.set_title(s, "Should not appear")
    # No matching entry → rewrite is a no-op; file content is byte-identical.
    assert pb.read_bytes() == original_bytes
    sessions = adapter.discover(0)
    assert sessions[0].title == "Only one"


def test_antigravity_companion_malformed_file_survives(tmp_path, monkeypatch):
    pb = tmp_path / "agyhub_summaries_proto.pb"
    pb.write_bytes(b"\xff\xff\xff not a valid protobuf at all")
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: None)
    monkeypatch.setattr(antigravity, "_companion_pb", lambda: pb)
    adapter = antigravity.AntigravityAdapter()
    assert adapter.available() is True
    # Malformed bytes must not crash discover().
    assert adapter.discover(0) == []


def test_antigravity_companion_brain_transcript(tmp_path, monkeypatch):
    """Brain artifacts work the same for Companion-store sessions."""
    uid = "ffffffff-6666-6666-6666-ffffffffffff"
    pb = _ag_make_pb_file(
        tmp_path,
        [(uid, _ag_make_summary(summary="stale", trajectory_id=uid, last_user_input=1))],
    )
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: None)
    monkeypatch.setattr(antigravity, "_companion_pb", lambda: pb)

    brain = tmp_path / "brain" / uid
    brain.mkdir(parents=True)
    (brain / "implementation_plan.md.metadata.json").write_text(
        json.dumps(
            {
                "artifactType": "ARTIFACT_TYPE_IMPLEMENTATION_PLAN",
                "summary": "Add CSV export to the invoice dashboard.",
            }
        ),
        encoding="utf-8",
    )
    (brain / "implementation_plan.md").write_text(
        "# Implementation plan\n\nWire a CSV export button into the invoice list page.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(antigravity, "_BRAIN_DIR", tmp_path / "brain")

    adapter = antigravity.AntigravityAdapter()
    s = adapter.discover(0)[0]
    msgs = adapter.read_transcript(s)
    assert msgs, "brain artifacts should produce a non-empty transcript"
    joined = " ".join(m.text for m in msgs)
    assert "CSV export" in joined
    assert all(m.role == "user" for m in msgs)


def test_antigravity_both_stores_listed_together(tmp_path, monkeypatch):
    """When IDE and Companion stores both exist, sessions from both show up."""
    uid_ide = "11111111-1111-1111-1111-111111111111"
    uid_app = "22222222-2222-2222-2222-222222222222"
    db = _ag_make_db(
        tmp_path,
        [(uid_ide, _ag_make_summary(summary="IDE session", trajectory_id=uid_ide,
                                    last_user_input=1))],
    )
    pb_dir = tmp_path / "companion"
    pb_dir.mkdir()
    pb = _ag_make_pb_file(
        pb_dir,
        [(uid_app, _ag_make_summary(summary="Companion session", trajectory_id=uid_app,
                                    last_user_input=2))],
    )
    monkeypatch.setattr(antigravity, "_state_vscdb", lambda: db)
    monkeypatch.setattr(antigravity, "_companion_pb", lambda: pb)
    adapter = antigravity.AntigravityAdapter()
    sessions = adapter.discover(0)
    by_id = {s.id: s for s in sessions}
    assert set(by_id) == {uid_ide, uid_app}
    assert by_id[uid_ide].meta["store"] == "vscdb"
    assert by_id[uid_app].meta["store"] == "companion"


# --------------------------------------------------------------------------- #
# Experimental adapters — Continue / Zed / Windsurf / Aider
# Smoke tests verifying they import, default to unavailable when no data is
# present, and round-trip a minimal fixture.
# --------------------------------------------------------------------------- #
def test_continue_unavailable_when_dir_missing(tmp_path, monkeypatch):
    from retitle.adapters import continue_dev
    monkeypatch.setattr(continue_dev, "_SESSIONS_DIR", tmp_path / "does_not_exist")
    a = continue_dev.ContinueAdapter()
    assert a.available() is False
    assert a.discover(0) == []


def test_continue_roundtrip(tmp_path, monkeypatch):
    from retitle.adapters import continue_dev
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sid = "session-abc-123"
    payload = {
        "sessionId": sid,
        "title": "Old title",
        "workspaceDirectory": "/Users/me/proj",
        "history": [
            {"message": {"role": "user", "content": "Add a dark-mode toggle"}},
            {"message": {"role": "assistant", "content": "Sure."}},
        ],
    }
    (sessions_dir / f"{sid}.json").write_text(json.dumps(payload), "utf-8")
    monkeypatch.setattr(continue_dev, "_SESSIONS_DIR", sessions_dir)
    a = continue_dev.ContinueAdapter()
    sessions = a.discover(0)
    assert len(sessions) == 1
    assert sessions[0].title == "Old title"
    msgs = a.read_transcript(sessions[0])
    assert any("dark-mode" in m.text for m in msgs)
    a.set_title(sessions[0], "New title for the toggle session")
    assert a.discover(0)[0].title == "New title for the toggle session"


def test_zed_unavailable_when_dir_missing(monkeypatch, tmp_path):
    from retitle.adapters import zed
    monkeypatch.setattr(zed, "_store_dir", lambda: None)
    assert zed.ZedAdapter().available() is False
    assert zed.ZedAdapter().discover(0) == []


def test_zed_roundtrip(monkeypatch, tmp_path):
    from retitle.adapters import zed
    store = tmp_path / "conversations"
    store.mkdir()
    payload = {
        "summary": "Old Zed title",
        "messages": [
            {"role": "user", "text": "Help me write a CSV importer"},
            {"role": "assistant", "text": "Sure."},
        ],
    }
    (store / "z-1.json").write_text(json.dumps(payload), "utf-8")
    monkeypatch.setattr(zed, "_store_dir", lambda: store)
    a = zed.ZedAdapter()
    sessions = a.discover(0)
    assert len(sessions) == 1
    assert sessions[0].title == "Old Zed title"
    a.set_title(sessions[0], "Renamed Zed session")
    assert a.discover(0)[0].title == "Renamed Zed session"


def test_windsurf_unavailable_when_db_missing(monkeypatch):
    from retitle.adapters import windsurf
    monkeypatch.setattr(windsurf, "_vscdb", lambda: None)
    assert windsurf.WindsurfAdapter().available() is False
    assert windsurf.WindsurfAdapter().discover(0) == []


def test_aider_unavailable_when_no_chats(monkeypatch, tmp_path):
    from retitle.adapters import aider
    monkeypatch.setattr(aider, "_discover_chats", lambda: [])
    assert aider.AiderAdapter().available() is False
    assert aider.AiderAdapter().discover(0) == []


def test_aider_sidecar_roundtrip(monkeypatch, tmp_path):
    from retitle.adapters import aider
    proj = tmp_path / "myproj"
    proj.mkdir()
    chat = proj / ".aider.chat.history.md"
    chat.write_text("#### user\nplease add a CSV importer\n\nassistant: sure\n", "utf-8")
    monkeypatch.setattr(aider, "_discover_chats", lambda: [chat])
    a = aider.AiderAdapter()
    sessions = a.discover(0)
    assert len(sessions) == 1
    assert sessions[0].title is None  # no sidecar yet
    a.set_title(sessions[0], "Add a CSV importer")
    sessions = a.discover(0)
    assert sessions[0].title == "Add a CSV importer"
    msgs = a.read_transcript(sessions[0])
    assert msgs and "CSV importer" in msgs[0].text


# --------------------------------------------------------------------------- #
# Robustness: malformed / missing data must degrade gracefully, not crash
# --------------------------------------------------------------------------- #
def test_claude_skips_corrupt_lines(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    proj = projects / "-Users-me-proj"
    proj.mkdir(parents=True)
    sid = "c0000000-0000-0000-0000-000000000000"
    f = proj / f"{sid}.jsonl"
    f.write_text(
        '{"type":"last-prompt","lastPrompt":"Real request one","sessionId":"%s"}\n'
        "this line is not json at all {oops\n"
        '{"type":"assistant","message":{"role":"assistant","content":'
        '[{"type":"text","text":"ok"}]}}\n'
        '{"type":"ai-title","aiTitle":"Good title","sessionId":"%s"}\n' % (sid, sid),
        encoding="utf-8",
    )
    monkeypatch.setattr(claude_code, "_projects_root", lambda: projects)
    adapter = claude_code.ClaudeCodeAdapter()
    s = adapter.discover(0)[0]
    assert s.title == "Good title"  # ai-title read past the corrupt line
    users = [m.text for m in adapter.read_transcript(s) if m.role == "user"]
    assert "Real request one" in users  # corrupt line skipped, real prompt kept


def test_codex_read_transcript_falls_back_when_rollout_missing(tmp_path, monkeypatch):
    db = tmp_path / "state_5.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, rollout_path TEXT, "
        "updated_at_ms INTEGER, cwd TEXT, archived INTEGER, first_user_message TEXT)"
    )
    now_ms = int(time.time() * 1000)
    con.execute(
        "INSERT INTO threads VALUES (?,?,?,?,?,?,?)",
        ("t1", "Title", "/no/such/rollout.jsonl", now_ms, "/p", 0, "The original request"),
    )
    con.commit()
    con.close()
    monkeypatch.setattr(codex, "_find_state_db", lambda: db)
    adapter = codex.CodexAdapter()
    s = adapter.discover(0)[0]
    msgs = adapter.read_transcript(s)  # rollout file is gone
    assert len(msgs) == 1
    assert msgs[0].text == "The original request"  # falls back to first_user_message


def test_cursor_discover_survives_corrupt_headers(tmp_path, monkeypatch):
    db = tmp_path / "state.vscdb"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
    con.execute(
        "INSERT INTO ItemTable VALUES (?,?)",
        ("composer.composerHeaders", "{this is not valid json"),
    )
    con.commit()
    con.close()
    monkeypatch.setattr(cursor, "_vscdb", lambda: db)
    assert cursor.CursorAdapter().discover(0) == []  # no crash, just empty
