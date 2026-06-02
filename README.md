<div align="center">

# 🏷️ retitle

### Your AI coding sessions are a goldmine. Bad titles bury it. retitle digs it back up.

Every session with Claude Code, Codex or Cursor is hard-won context — the bugs you chased,
the decisions you made, the code you shipped. It's a **valuable asset**. But all three tools
title a chat from your **first message** and then freeze it forever. An hour later the work has
moved on, yet the sidebar still says *"Check if branches are synced."* Multiply that by hundreds
of sessions and your most valuable history becomes an unsearchable graveyard.

That asset is too good to waste on a stale title.

**`retitle` runs quietly in the background and, once a session goes idle, rewrites its title to
match what the work actually became — across all three tools.** Then `retitle search` lets you
mine that history: find any past session across Claude Code, Codex and Cursor at once.

[![CI](https://github.com/study8677/retitle/actions/workflows/ci.yml/badge.svg)](https://github.com/study8677/retitle/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](pyproject.toml)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](CONTRIBUTING.md)

**English** · [简体中文](README.zh-CN.md)

</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/study8677/retitle/main/assets/demo.svg" alt="retitle rewrites stale Claude Code, Codex and Cursor session titles to match the latest work" width="820">
</p>

<p align="center"><b>30-second try</b> — no install, writes nothing:</p>

```bash
uvx --from git+https://github.com/study8677/retitle.git retitle list
```

---

## The problem: a goldmine you can't search

Every AI coding tool titles a session once, from its opening prompt, and freezes it there:

| Tool | What the sidebar says | What the session is now about |
|------|----------------------|--------------------------------|
| **Cursor** | `Add a loading spinner` | *migrating the database to Postgres* |
| **Codex** | `Fix a typo in the README` | *debugging a flaky CI pipeline* |
| **Claude Code** | `Check if branches are synced` | *implementing the audit-log feature* |

The title is a lie within ten minutes. So a week later, when you *know* you solved this exact
bug with the AI before, you can't find the conversation — the asset is there, but it's buried.
`retitle` keeps the title honest, so the goldmine stays searchable.

<sub>(Examples are illustrative — `retitle` reads your sessions locally and never publishes them anywhere.)</sub>

## What it looks like

```console
$ retitle list

Claude Code
     16m  Check if branches are synced          → Implement the audit-log feature
     34m  —                                     → Fix dashboard white-screen on load
      2m  Refactor the deploy script            · active

Codex
    1.2h  Set up the new service                → Design the session auto-rename flow
    2.1h  Review the API changes                · no new content since last rename

Cursor
     29m  Add a loading spinner                 → 修复登录页面的样式问题
    2.4h  First sync question                   → Track down the duplicate-error bug

7 session(s) would be renamed next pass (idle ≥ 5m, namer=heuristic).
Run `retitle once` to apply, or `retitle install` to do it continuously.
```

---

## 🔍 Also: find any past session

Accurate titles are only half the point — the other half is *finding* the session
again. `retitle search` looks across Claude Code, Codex and Cursor at once:

```console
$ retitle search "stripe webhook"

🔍 "stripe webhook" — 2 matches

  Cursor        3h    Wire up the Stripe webhook handler    payments-api
  Claude Code   2d    Debug the Stripe webhook signature    billing-svc

$ retitle search postgres --content      # also grep message text, with snippets
```

---

## Quick start

`retitle` is pure Python with **zero dependencies**. Install it as an isolated CLI:

```bash
# with pipx (recommended)
pipx install git+https://github.com/study8677/retitle.git

# or with uv
uv tool install git+https://github.com/study8677/retitle.git

# or from source
git clone https://github.com/study8677/retitle.git && cd retitle
pip install -e .
```

Then:

```bash
retitle status         # what did it detect on this machine?
retitle list           # preview: current title → proposed title (writes nothing)
retitle once           # do one rename pass right now
retitle install        # run it forever in the background (launchd / systemd)
```

That's it. With `retitle install` it wakes up every minute, finds sessions that have been idle
for 5 minutes, and retitles the ones whose content has changed since it last looked.

---

## How it works

```
        ┌──────────── every  poll_seconds (default 60s) ────────────┐
        │                                                           │
   discover ──► for each session idle ≥ 5m with NEW content ──► namer ──► write title back
   (per tool)         │                                           │            │
   Claude Code        │ skip if still active                      │            ├─ Claude Code: append an `ai-title` line
   Codex              │ skip if unchanged since last rename        │            ├─ Codex:       UPDATE threads SET title
   Cursor             │ skip if a human renamed it (until          │            └─ Cursor:      patch composerHeaders + composerData
                      │      the conversation moves on)            │
```

The decision rule for each session is deliberately conservative:

1. **Still in use?** Idle for less than your threshold → leave it alone.
2. **Nothing new?** Content hash matches the title we last wrote → skip (re-runs are free).
3. **Renamed by hand?** We never clobber a human edit — until you send new messages and it goes idle again.
4. Otherwise: generate a fresh title and write it.

This makes the whole thing **idempotent** and **safe to run continuously**.

**Where the title comes from.** By default retitle shells out to the `claude`
(or `codex`) CLI you're already logged into — `claude --model haiku -p "…"` — so
titles are real LLM summaries of the conversation, with no API key. No CLI
installed? It falls back to the offline heuristic.

**Rename past sessions on demand.** To work through a backlog without calling your
CLI on everything at once, a pass renames at most `batch_size` sessions
(default 25), most-recent first; the daemon finishes the rest over later passes.

```bash
retitle once                # rename the latest batch right now
retitle once --limit 50     # rename the 50 most-recent eligible sessions
retitle once --all          # rename ALL eligible history (idle 0, any age; slower)
retitle once --all --dry-run   # preview the whole backlog without writing
```

---

## Supported tools

| Tool | Reads | Writes | Status |
|------|-------|--------|--------|
| **Claude Code** | `~/.claude/projects/**/<id>.jsonl` | appends an `ai-title` line (append-only — the safest write) | ✅ stable |
| **Codex** | `~/.codex/state_*.sqlite` + rollout files | `UPDATE threads SET title` | ✅ stable |
| **Cursor** | `state.vscdb` (`composerHeaders` + `composerData`) | patches both title fields | ⚠️ experimental |
| **Antigravity** *(Google)* | IDE: `state.vscdb` (`antigravityUnifiedStateSync.trajectorySummaries`) — Companion: `~/.gemini/antigravity/agyhub_summaries_proto.pb` | rewrites the `summary` field of one `CascadeTrajectorySummary` (atomic-rename for the Companion file) | ⚠️ experimental — [see notes](#antigravity-notes) |

> **A note on writing while the app is open.** Codex, Cursor and Antigravity keep their data
> in live SQLite databases. `retitle` writes carefully (read-only reads, `busy_timeout` on
> writes), and only ever touches *idle* sessions. Still, the host apps cache chats in memory,
> so a title you change on disk may be overwritten if you reopen that exact chat in the
> running app. For the most reliable results, let `retitle` run while the app is closed.
> Claude Code's append-only format has no such caveat.

### Antigravity notes

Antigravity ships in two forms — the **IDE** (a VS Code fork with a Gemini sidebar)
and a standalone **Companion App** (Windows-only). `retitle` supports both:

| Flavor | Title store | Format |
|---|---|---|
| IDE | `state.vscdb` → `ItemTable['antigravityUnifiedStateSync.trajectorySummaries']` | base64(envelope(base64(`CascadeTrajectorySummary`))) — same pattern as Cursor |
| Companion App | `~/.gemini/antigravity/agyhub_summaries_proto.pb` | raw protobuf, `repeated TopEntry { uuid; CascadeTrajectorySummary }` |

Both flavors share the same `CascadeTrajectorySummary` schema (reverse-engineered
from Antigravity 2.0's bundled `FileDescriptorProto`); only the outer wrapping
differs. The IDE store is rewritten via `UPDATE`; the Companion file is rewritten
by atomic rename. Conversation transcripts (`~/.gemini/antigravity/conversations/<uuid>.pb`)
are **encrypted at rest** in either flavor, but Antigravity's agent writes plaintext
working artifacts to `~/.gemini/antigravity/brain/<uuid>/` (`task.md`,
`implementation_plan.md`, `walkthrough.md`, plus `*.metadata.json` summaries) — those
are the material `retitle` feeds to the namer.

- ✅ Antigravity sessions show up in `retitle list`, `retitle search`, `retitle stats`
- ✅ Automatic rename works for any conversation that has produced brain artifacts
  (longer / planning-heavy chats — the ones whose title most often drifts). Short
  chats with no artifacts are skipped by the substance gate, which is fine — there'd
  be nothing to title with anyway.
- ✅ Manual `retitle once --tool antigravity` works regardless.

If Antigravity ships an extension API exposing raw chat-session transcripts later,
we'll wire it in for full coverage. Track at
[#1](https://github.com/study8677/retitle/issues/1).

---

## Naming backends — no API key required

The default, **`auto`**, needs **no API key at all**. retitle reuses the `claude` or
`codex` CLI you're *already logged into* to write good, LLM-quality titles, and falls
back to a fully-offline heuristic if neither is installed. You never paste a key.

| `namer` | What it does | API key? |
|---------|--------------|----------|
| `auto` | your logged-in `claude` / `codex` CLI, else `heuristic` | **none** · default |
| `heuristic` | a cleaned-up snippet of your latest message; instant, offline | none |
| `claude` | always the `claude` CLI (fast Haiku model) | none — your login |
| `codex` | always the `codex` CLI (`gpt-5-codex`) | none — your login |
| `anthropic` | Anthropic API directly | `ANTHROPIC_API_KEY` |
| `openai` | OpenAI API directly | `OPENAI_API_KEY` |

Out of the box — nothing to configure, no key to paste — you get LLM-quality titles
using credits you already have. Prefer zero cost / fully offline? Set `namer = "heuristic"`.

```bash
retitle status        # shows what auto resolved to, e.g. "namer=auto → claude"
```

---

## Optional: native macOS app (menu bar + dashboard)

`retitle` ships a small **SwiftUI app** in [`macos-app/`](macos-app/) so you don't
have to live in the terminal to see what the daemon is doing. It's a thin viewer
over the CLI — all the real work still happens in the Python daemon you already
installed with `retitle install`.

**What you get**

- **Menu bar icon** — running/paused indicator, the last 5 renames (old → new
  title), Pause/Resume daemon, Refresh now, Open dashboard, Quit
- **Dashboard window** — stats header (tracked / sessions / stale / lifetime
  renames), tool filter (All / Claude Code / Codex / Cursor / Antigravity),
  per-session search, table of every session with the proposed new title and
  a per-row "Rename now" button (bypasses the idle gate for that one
  conversation), one-click access to config + log

**Build & run** (needs only Command Line Tools, no full Xcode):

```bash
# from the repo root
cd macos-app
./build-app.sh
open Retitle.app
```

Drag `Retitle.app` into `~/Applications` and add it to **Login Items** to
keep the menu bar icon around between reboots. The app is a `LSUIElement`
— it lives in the menu bar only, never appears in the Dock or ⌘-Tab.

**Localization** — English and 简体中文, follows your system language.

**Architecture** — Swift + SwiftUI, ~1k LOC. Talks to the Python CLI through
`Process` + JSON (`retitle status --json`, `retitle list --json`,
`retitle stats --json`, `retitle once --session <id>`). Daemon control is
plain `launchctl load / unload` on the existing `.plist`. No new state, no
new storage — the CLI stays the single source of truth.

---

## Configuration

`retitle config` creates and prints `~/.config/retitle/config.toml`:

```toml
idle_seconds = 300          # rename after 5 minutes idle
poll_seconds = 60           # scan once a minute
batch_size = 25             # rename at most N sessions per scan (0 = no limit)
tools = ["claude-code", "codex", "cursor"]
namer = "heuristic"         # heuristic | claude | codex | anthropic | openai
max_age_days = 7            # ignore sessions older than a week
min_user_messages = 1       # need at least this many real messages
dry_run = false

[anthropic]
model = "claude-haiku-4-5"

[openai]
model = "gpt-4o-mini"
```

Any field can be overridden per-invocation: `retitle run --idle 600 --namer anthropic --tool cursor`.

## Commands

| Command | Description |
|---------|-------------|
| `retitle list` | Preview every discovered session and its proposed title (writes nothing) |
| `retitle search <q>` | Find sessions across all tools by title (add `--content` to grep message text) |
| `retitle stats` | A quick overview: sessions per tool, how many are untitled / stale |
| `retitle once` | Rename the latest batch now (`--limit N`, `--all`, `--dry-run`) |
| `retitle run` | Run continuously in the foreground (add `--once`, `--dry-run`) |
| `retitle install` | Install + start the background service (launchd on macOS, systemd on Linux) |
| `retitle uninstall` | Stop and remove the background service |
| `retitle status` | Show config, detected tools, and daemon status |
| `retitle config` | Create / print the config file |

> `retitle list`, `retitle search` and `retitle stats` also accept `--json` for scripting.

---

## Privacy & safety

- **No key to paste; titling uses your own logged-in tool.** The default `auto` namer asks the
  `claude`/`codex` CLI you're already signed into to write the title, so a short transcript
  excerpt goes to that provider (credits you already have — no API key needed). Want nothing to
  leave your machine at all? Set `namer = "heuristic"` and it's 100% offline.
- **It only ever changes titles.** `retitle` reads transcripts and writes a single title field /
  appends a single line. It never edits, deletes, or reorders your conversations.
- **It's reversible and idempotent.** A bad title is just a title — send a message and it gets
  re-evaluated. Re-running does nothing unless content changed.

## FAQ

**Will it fight with the tool's own auto-naming?**
No. The tools title once and stop; `retitle` only acts after a session is idle, so they aren't
writing at the same time.

**Will it overwrite titles I set myself?**
No — not until you add new messages to that session. Manual titles are respected until the
conversation actually moves on.

**Do I need an API key?**
No. The default reuses the `claude` / `codex` CLI you're already logged into — no key to
paste. It spends credits you already have; for zero cost, set `namer = "heuristic"` (offline).

**Is it safe to run all the time?**
Yes — that's the design. See [How it works](#how-it-works). The one caveat is editing Cursor's DB
while Cursor is open (above).

## Contributing

Curious how it works under the hood — including the reverse-engineered session
storage format of each tool? See **[ARCHITECTURE.md](ARCHITECTURE.md)**.

Adding support for another tool is one file — implement four methods (`available`, `discover`,
`read_transcript`, `set_title`) in `src/retitle/adapters/`. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/study8677/retitle.git && cd retitle
pip install -e ".[dev]"
pytest
```

## Star this repo

Your AI sessions are an asset worth keeping. If `retitle` helps you reclaim yours, a ⭐ helps
other people find it — and motivates more adapters (Aider, Continue, Zed, …). Issues and PRs welcome.

## Acknowledgments

- **[@xiongaox](https://github.com/xiongaox)** filed [#1](https://github.com/study8677/retitle/issues/1)
  asking for Antigravity support. That issue is what unlocked the whole Antigravity adapter —
  the protobuf schema reverse-engineering, the `brain/` artifacts discovery, and (after he
  shared the Companion App's `.pb` file header in the same issue) the Companion App store
  format. Thank you 🙏.

## License

[MIT](LICENSE) © JingWen Fan
