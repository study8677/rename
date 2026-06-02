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
[![Latest release](https://img.shields.io/github/v/release/study8677/retitle?label=release&color=blue)](https://github.com/study8677/retitle/releases)
[![GitHub stars](https://img.shields.io/github/stars/study8677/retitle?style=flat&color=yellow)](https://github.com/study8677/retitle/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](pyproject.toml)
[![Supported tools](https://img.shields.io/badge/tools-8-9c27b0.svg)](#supported-tools)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](CONTRIBUTING.md)

**English** · [简体中文](README.zh-CN.md) · [Cookbook](docs/COOKBOOK.md)

</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/study8677/retitle/main/assets/demo.svg" alt="retitle rewrites stale Claude Code, Codex and Cursor session titles to match the latest work" width="820">
</p>

<p align="center">
  <a href="macos-app/">
    <img src="https://raw.githubusercontent.com/study8677/retitle/main/assets/dashboard.svg" alt="The optional native menu-bar app shows every session across Claude Code, Codex, Cursor and Antigravity, with the old → new title diff in one place" width="820">
  </a>
</p>

<p align="center"><sub>The optional <a href="macos-app/">native macOS app</a> and <a href="windows-app/">Windows GUI</a> give you the same picture without opening a terminal.</sub></p>

<p align="center"><b>30-second try</b> — no install, writes nothing:</p>

```bash
uvx --from git+https://github.com/study8677/retitle.git retitle list
```

Or install for real:

```bash
brew install study8677/retitle/retitle   # macOS (Homebrew tap)
pipx install retitle                      # everywhere else (Python 3.11+)
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
| **Continue** *(continue.dev)* | `~/.continue/sessions/<id>.json` | rewrites `title` and atomic-renames the file | ⚠️ experimental |
| **Zed** *(zed.dev Assistant)* | `~/Library/Application Support/Zed/conversations/<uuid>.json` (etc.) | rewrites `summary` / `title` and atomic-renames | ⚠️ experimental — schema varies by Zed version |
| **Windsurf** *(Codeium)* | `state.vscdb` (Cursor-fork layout) | reuses the Cursor write path with the Windsurf store path | ⚠️ experimental |
| **Aider** | `.aider.chat.history.md` (per project) | sidecar `.aider.chat.history.md.title` file (read-only as far as Aider itself is concerned) | ⚠️ experimental — read-only |

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

## Optional: GUI apps (menu bar + dashboard)

`retitle` ships two optional GUI front-ends. Both are thin viewers over the
Python CLI — the daemon you installed with `retitle install` keeps doing all
the real work, the apps just let you see what's happening.

| Flavor | Path | Toolchain | Status |
|---|---|---|---|
| **macOS native** | [`macos-app/`](macos-app/) | Swift + SwiftUI, requires Command Line Tools only | ✅ tested |
| **Windows / cross-platform** | [`windows-app/`](windows-app/) | Python + PySide6 (Qt6), runs on Windows / macOS / Linux | ⚠ shipped untested — see app's README |

Both apps share the same feature set:

- **Tray / menu bar icon** with running/paused indicator and the last few
  renames (old title → new title)
- **Dashboard window** with stat cards (Tracked / Sessions / Stale / Renamed),
  brand-coloured tool filter chips, search across titles & paths, per-session
  "Rename now" button (bypasses the idle gate), before/after diff
- **Visual settings dialog** — sliders, dropdowns and toggles that read & write
  your `config.toml`, so you don't have to edit TOML by hand
- **Friendly progress** — no raw `stderr`; everything is surfaced as toast
  notifications or native system notifications
- **First-launch permissions onboarding** (macOS) — one click to System Settings →
  Full Disk Access so the OS stops asking on every refresh
- **Lazy scanning** — session lists are only fetched when the dashboard is open
  or you hit Refresh, not on every status poll
- **Localized** — English and 简体中文, auto-detected from system language

### macOS build

```bash
cd macos-app
./build-app.sh
open Retitle.app
```

Drag `Retitle.app` into `~/Applications` and add it to **Login Items** to
persist across reboots. It's a `LSUIElement` app — menu bar only, no Dock icon.

### Windows build

```powershell
cd windows-app
python -m venv .venv && .venv\Scripts\activate
pip install -e .
retitle-gui
```

For auto-start, drop a shortcut into `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`.

### Architecture

Both apps talk to the CLI through `subprocess` / `Process` and JSON. The CLI
exposes `retitle status --json`, `list --json`, `stats --json`, `search --json`,
and `once --session <id>` — the GUI calls these and renders the results. There
is no extra state, no extra storage, and no extra daemon — the existing Python
daemon stays the single source of truth.

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
