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

### Antigravity  ⚠️ experimental — read-only for naming

Antigravity (Google) is a VS Code fork with a Gemini-powered chat sidebar. It
splits its data across two stores:

- **Conversation transcripts** at `~/.gemini/antigravity/conversations/<uuid>.pb`
  are **encrypted at rest** — uniform-byte ciphertext, key held by the OS
  keychain. We cannot read them.
- **Title + metadata index** lives in `state.vscdb`, key
  `antigravityUnifiedStateSync.trajectorySummaries`. The value is a
  base64-encoded protobuf with **plaintext titles**, reverse-engineered from
  Antigravity 2.0's bundled `FileDescriptorProto` (search the JS bundle for
  `CascadeTrajectorySummary` to see the canonical schema). Layered shape:

  ```
  Envelope                              # base64 → repeated field 1
    TopEntry { key=uuid, value=Wrapper }
      Wrapper { value @ 1 = base64(   # yes, base64 inside base64 — that's
                  CascadeTrajectorySummary  # how unifiedStateSync stores it
              ) }
        CascadeTrajectorySummary {
          string  summary @ 1                    # ← the title
          uint32  step_count @ 2
          Timestamp last_modified_time @ 3
          string  trajectory_id @ 4
          enum    status @ 5
          Timestamp created_time @ 7
          Workspaces workspaces @ 9
          Timestamp last_user_input_time @ 10
          …
        }
  ```

- **Title:** `CascadeTrajectorySummary.summary` (field 1).
- **Transcript:** we return `[]` — see above. The engine's substance gate then
  skips Antigravity sessions in the rename loop, which is what we want
  (Antigravity already auto-titles its own conversations). `retitle list` /
  `search` / `stats` still surface them. Manual rename via
  `retitle once --tool antigravity` works.
- **Write:** rewrite the one matching `CascadeTrajectorySummary.summary` inside
  the layered envelope and `UPDATE ItemTable` under `BEGIN IMMEDIATE`. The proto
  is hand-encoded (varints + length-prefixed fields) in
  [`_proto.py`](src/retitle/adapters/_proto.py) — zero deps, ~80 lines.
- **Caveat:** `trajectorySummaries` is a synced store; a local write may be
  overwritten by cloud sync or pushed to other devices. Treat as best-effort
  while Antigravity is running.

## The rename decision

For each discovered session, in order:

1. **Idle gate** — if it has been idle for less than `idle_seconds` (default 300),
   skip. It's still in use.
2. **No-activity short-circuit** — if `last_active` is unchanged since we last
   fully evaluated it (`seen_active` in state), skip without re-reading the
   transcript. Cheap; keeps the poll loop light.
3. **Substance** — skip if there are fewer than `min_user_messages` non-trivial
   user messages (acknowledgements, slash-commands and harness/tool noise are
   filtered out in `util.is_trivial` / `is_noise`).
4. **Unchanged content** — hash the recent transcript (`util.signature`); if it
   matches the hash tied to the title we last wrote, skip. This makes runs
   idempotent and **respects titles you edit by hand** — until the conversation
   moves on.
5. Otherwise generate a title, shape it (`util.shape_title`), and write it if it
   differs from the current one.

## Data-safety design

`retitle` writes to your real session stores, so the rules are conservative:

- **Idle-only.** It only ever touches sessions that have gone quiet.
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

