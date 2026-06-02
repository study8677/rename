# Architecture

`retitle` is small and strictly layered, with **zero third-party dependencies**.
A polling **engine** asks **adapters** (one per tool) to discover sessions, then
uses a **namer** to produce a fresh title and writes it back through the adapter.

```
            ┌──────────────── engine (every poll_seconds) ────────────────┐
            │                                                              │
 adapter.discover ─► engine decides (idle? changed? manual edit?) ─► namer.generate ─► adapter.set_title
   per tool                         │                                  │                   │
                                    └── state.json (content hashes, last titles) ◄─────────┘
```

## Components

| Module | Responsibility |
|--------|----------------|
| `engine.py` | The decision loop: which idle sessions need a new title, and apply it. |
| `adapters/` | One file per tool. The *only* code that knows a tool's on-disk format. |
| `namers/` | Turn a transcript into a short title (heuristic / CLI / API). |
| `state.py` | Atomic JSON store of "what we already renamed" (content hash + last title). |
| `config.py` | Typed defaults + TOML loading. |
| `service.py` | launchd / systemd install. |
| `util.py` | Paths, text cleaning, noise filtering, content signatures, title shaping. |

The adapter contract is four methods (`adapters/base.py`):
`available()`, `discover(since)`, `read_transcript(session)`, `set_title(session, title)`.

## How each tool stores its sessions — and how we rename them

These formats were reverse-engineered from local data; treat them as observed,
not officially documented. Each adapter isolates the quirks below.

### Claude Code  ✅ stable

- **Location:** `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` — one
  append-only JSONL file per session.
- **Title:** the **last** `{"type":"ai-title","aiTitle":"…","sessionId":"…"}`
  line. Claude Code appends a new one whenever it (re)titles and reads the latest.
- **Transcript:** we read `{"type":"last-prompt","lastPrompt":"…"}` lines for the
  exact user prompts (free of the caveats / interruption markers that pollute raw
  `user` message lines) plus `assistant` text.
- **Write:** append one `ai-title` line. Append-only is the safest possible write —
  a single `O_APPEND` write lands atomically at EOF, and we never touch existing bytes.

### Codex  ✅ stable

- **Location:** titles live in `~/.codex/state_<N>.sqlite` (table `threads`,
  column `title`, keyed by thread `id`). The full transcript is the rollout JSONL
  at `threads.rollout_path`.
- **Title:** `SELECT title FROM threads WHERE id = ?`.
- **Transcript:** rollout `response_item` lines with `payload.type == "message"`.
- **Write:** `UPDATE threads SET title = ? WHERE id = ?`. The Desktop app reads
  this column for its thread list.

### Cursor  ⚠️ experimental

- **Location:** the global `state.vscdb` SQLite database. The title is stored in
  **two** synchronized places:
  - `ItemTable['composer.composerHeaders']` → JSON `allComposers[i].name` (the chat list)
  - `cursorDiskKV['composerData:<id>']` → top-level `name`
- **Transcript:** `composerData:<id>.fullConversationHeadersOnly[]` gives the bubble
  order; each `bubbleId:<cid>:<bid>` holds the message (`type` 1 = user, 2 = assistant).
- **Write:** both copies, in a single `BEGIN IMMEDIATE` transaction, with rollback
  on any error (see *Data-safety design*).

### Antigravity  ⚠️ experimental

Antigravity (Google) ships in two flavors that store conversation summaries
in **different places** but share the same protobuf schema:

- **IDE** (the VS Code fork with a Gemini-powered chat sidebar): titles live in
  `state.vscdb` under `antigravityUnifiedStateSync.trajectorySummaries`, a
  base64-encoded protobuf with **plaintext titles**.
- **Companion App** (standalone desktop client, Windows-only): titles live in
  `~/.gemini/antigravity/agyhub_summaries_proto.pb`, a raw protobuf file —
  no base64, no envelope wrapping.

Conversation **transcripts** in either flavor live at
`~/.gemini/antigravity/conversations/<uuid>.pb` and are **encrypted at rest**
(uniform-byte ciphertext, key held by the OS keychain). We cannot read them.

Both stores share the same `CascadeTrajectorySummary` schema, reverse-engineered
from Antigravity 2.0's bundled `FileDescriptorProto` (search the JS bundle for
`CascadeTrajectorySummary`):

```
CascadeTrajectorySummary {
  string    summary @ 1                  # ← the title
  uint32    step_count @ 2
  Timestamp last_modified_time @ 3
  string    trajectory_id @ 4
  enum      status @ 5
  Timestamp created_time @ 7
  Workspaces workspaces @ 9
  Timestamp last_user_input_time @ 10
  …
}
```

The two stores differ only in how entries are wrapped:

```
# IDE store — antigravityUnifiedStateSync.trajectorySummaries
base64( Envelope {                       # field 1 repeated
  TopEntry { key=uuid, value=Wrapper }
    Wrapper { value @ 1 = base64(        # yes, base64 inside base64 —
                CascadeTrajectorySummary # that's how unifiedStateSync
            ) }                          # encodes its synced values
})

# Companion App store — agyhub_summaries_proto.pb (raw bytes on disk)
TopEntry {                               # field 1 repeated, no base64
  uuid @ 1
  CascadeTrajectorySummary @ 2           # directly, no inner base64
}
```

- **Title:** `CascadeTrajectorySummary.summary` (field 1) in either flavor.
- **Transcript:** the raw chat is encrypted, but Antigravity's agent writes
  plaintext working artifacts to `~/.gemini/antigravity/brain/<uuid>/`
  (`task.md`, `implementation_plan.md`, `walkthrough.md`, each with a
  `*.metadata.json` sidecar carrying a `summary`). We feed those to the namer.
  Sessions without brain artifacts (early/short chats) get an empty transcript;
  the substance gate then skips them, which is what we want — Antigravity's own
  auto-titler already handles the short-chat case.
- **Write (IDE):** rewrite the one matching `CascadeTrajectorySummary.summary`
  inside the layered envelope and `UPDATE ItemTable` under `BEGIN IMMEDIATE`.
- **Write (Companion):** rewrite the matching entry in the raw `.pb` and replace
  the file atomically (write to `*.retitle.tmp`, then `os.replace`).
- **Proto codec:** hand-rolled in [`_proto.py`](src/retitle/adapters/_proto.py)
  — varints + length-prefixed fields, ~80 lines of stdlib.
- **Caveats:** The IDE store is a *synced* store; a local write may be
  overwritten by cloud sync or pushed to other devices. The Companion store is
  a single file rewritten by atomic rename — on Windows, an exclusive handle
  held by a running Companion can cause the rename to fail; close the app and
  retry. Treat both as best-effort while Antigravity is running.

## The rename decision

For each discovered session, in order:

1. **Historical gate** — if the state store has a baseline timestamp and the
   session's `last_active` is older than it, skip. The session existed before
   retitle started watching this machine; auto-renaming it would be a surprise.
   The user can override per-pass with `include_historical=True` (the GUI's
   "Rename historical sessions" button / `retitle once --historical`), or
   per-session with `--session ID` (a deliberate single-target rename).
2. **Idle gate** — if it has been idle for less than `idle_seconds` (default 300),
   skip. It's still in use.
3. **No-activity short-circuit** — if `last_active` is unchanged since we last
   fully evaluated it (`seen_active` in state), skip without re-reading the
   transcript. Cheap; keeps the poll loop light.
4. **Substance** — skip if there are fewer than `min_user_messages` non-trivial
   user messages (acknowledgements, slash-commands and harness/tool noise are
   filtered out in `util.is_trivial` / `is_noise`).
5. **Unchanged content** — hash the recent transcript (`util.signature`); if it
   matches the hash tied to the title we last wrote, skip. This makes runs
   idempotent and **respects titles you edit by hand** — until the conversation
   moves on.
6. Otherwise generate a title, shape it (`util.shape_title`), and write it if it
   differs from the current one.

### Baseline timestamp (v0.6.0+)

`state.json` carries a top-level `_meta.baseline_ts` set on the **first
non-dry-run tick** of the daemon's lifetime on this machine (`StateStore.ensure_baseline`).
From that moment on, the engine treats any session whose `last_active` predates
the baseline as **historical** and silently skips it from automatic passes —
even if its idle/substance/content gates would otherwise approve a rename.

The invariant retitle promises: *installing the daemon never retroactively
rewrites your existing chat titles without an explicit user action.* Two
escape hatches exist for the user to opt in:

- **`tick(include_historical=True)`** — bypass the gate for one whole pass.
  Used by `retitle once --historical` and the dashboard's "Rename historical
  sessions" button. The CLI also drops `max_age_days` and the batch cap in
  this mode (`since = 0.0`, `limit = 0`) so the *full* backlog is processed.
- **`tick(session_filter={…})`** — a per-session override. Per-session forced
  renames bypass the historical gate because the user explicitly named a
  single target.

Dry-run passes (`cfg.dry_run = True`) do *not* persist the baseline — so a
user previewing with `retitle once --dry-run` won't inadvertently lock in a
baseline they didn't want to commit to.

## Data-safety design

`retitle` writes to your real session stores, so the rules are conservative:

- **Idle-only.** It only ever touches sessions that have gone quiet.
- **No retroactive renames without consent.** A baseline timestamp recorded on
  first run holds back every pre-install chat from the automatic loop
  ([Baseline timestamp](#baseline-timestamp-v060)).
- **Title-only.** It appends/updates a single title field and never edits,
  deletes, or reorders conversations.
- **Read-only reads.** SQLite reads use a `query_only` connection.
- **Atomic writes.** Codex is a single `UPDATE`. Cursor takes the write lock up
  front (`BEGIN IMMEDIATE`), updates both title copies, verifies row counts, and
  rolls back on any error — a half-update can never be committed. Claude Code is
  append-only.
- **Failure isolation.** If an adapter's `discover()` throws (e.g. a briefly
  locked DB), its state is *not* pruned, so a transient error can never cause the
  next pass to clobber a hand-edited title.
- **Titling via your own logged-in CLI by default.** The default `auto` namer
  reuses the `claude`/`codex` CLI you're signed into (no API key); a short excerpt
  goes to that provider. Set `namer = "heuristic"` for a fully offline run. See
  [SECURITY.md](SECURITY.md).

## Adding a tool

Implement the four-method `Adapter` contract and register it. See
[CONTRIBUTING.md](CONTRIBUTING.md) — it's usually one small file.

