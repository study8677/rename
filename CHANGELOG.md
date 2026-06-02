# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **Daemon: skip historical sessions by default.** First run records a
  baseline timestamp in `state.json`; only sessions whose `last_active` is at
  or after that baseline are eligible for the background loop. Existing
  chats from before retitle was installed stay untouched unless the user
  opts in. Bumps the GUI's `status --json` payload with `baseline_ts`.
- **`retitle once --historical`** opt-in flag (CLI) and **"Rename historical
  sessions"** button (macOS + Windows GUI) — confirms with a dialog, then
  runs a full backlog pass with optional dry-run mode. Both GUIs show a
  toast with the CLI summary when finished.

### Fixed
- **CI: Windows tests fail with `UnicodeEncodeError`** because `cp1252` is
  the default codec there. Now passes `encoding="utf-8"` on every
  `Path.write_text` in the test suite and exports `PYTHONUTF8=1` /
  `PYTHONIOENCODING=utf-8` for all CI runners as a belt-and-suspenders.
- CI: bump `actions/checkout@v4 → v5`, `actions/setup-python@v5 → v6`,
  `actions/upload-artifact@v4 → v5`, macOS runner `macos-14 → macos-15`,
  drop the now-redundant Windows GUI smoke job per user request.

## [0.5.0] - 2026-06-02

### Added
- **Four new experimental adapters** — `continue`, `zed`, `windsurf`, and
  `aider`. Each is a thin best-effort implementation:
  - `continue` reads `~/.continue/sessions/<id>.json`, rewrites the `title`
    field via atomic rename
  - `zed` reads `~/Library/Application Support/Zed/conversations/<uuid>.json`
    (etc. on other OSes), rewrites `summary` / `title`
  - `windsurf` is a Cursor-fork; the adapter reuses the Cursor write path
    with the Windsurf data dir
  - `aider` is read-only — Aider has no native title slot, so renames go
    to a `.aider.chat.history.md.title` sidecar that only retitle reads
- **macOS Homebrew tap** — `brew install study8677/retitle/retitle` (after
  running `brew tap study8677/retitle https://github.com/study8677/retitle.git`).
  Includes a `brew services start retitle` integration that mirrors
  `retitle install` on launchd.
- **GitHub Actions matrix expansion** — `windows-latest` job for the Python
  test suite, a new `macos-app` job that builds `Retitle.app` and uploads it
  as an artifact on every push, and a `windows-gui` job that smoke-imports
  the PySide6 GUI.
- **Hand-crafted Dashboard + menu-bar SVGs** in `assets/` — embedded at the
  top of the READMEs so visitors see the GUI before they read anything.
- **Antigravity (Google) adapter** ⚠️ experimental. Lists, searches and renames
  Antigravity conversations by rewriting `CascadeTrajectorySummary.summary`
  inside `state.vscdb`'s `antigravityUnifiedStateSync.trajectorySummaries`
  blob (base64 → protobuf → base64 → CascadeTrajectorySummary). Schema
  reverse-engineered from Antigravity 2.0's bundled `FileDescriptorProto`.
  Encoder/decoder in `adapters/_proto.py` (stdlib only, ~80 lines).
- **Auto-rename works for Antigravity too.** Although raw chat transcripts are
  encrypted, Antigravity's agent writes plain-text working artifacts to
  `~/.gemini/antigravity/brain/<uuid>/` (`task.md`,
  `implementation_plan.md`, `walkthrough.md`, plus `*.metadata.json`
  summaries). `read_transcript` feeds those to the namer, so any conversation
  with brain artifacts gets a fresh title in the daemon loop just like the
  other three tools. On a sample install ≈35% of conversations had artifacts.
- **Antigravity Companion App** support (Windows). The standalone Companion
  stores titles in a raw protobuf at `~/.gemini/antigravity/agyhub_summaries_proto.pb`
  (no SQLite, no base64 — just `repeated TopEntry { uuid; CascadeTrajectorySummary }`).
  `discover` and `set_title` now handle both stores; `read_transcript` reads
  the same `brain/` artifacts regardless of store. Writes go through a
  write-tmp + `os.replace` atomic rename. Verified against a `.pb` file shared
  by [@xiongaox](https://github.com/xiongaox) on the issue.
- Closes [#1](https://github.com/study8677/retitle/issues/1). Thanks to
  [@xiongaox](https://github.com/xiongaox) for filing it AND for sharing the
  Companion App `.pb` that unlocked the second store format — the issue is
  what made the whole Antigravity adapter possible.
- **Optional native macOS app** in `macos-app/` — a Swift + SwiftUI menu-bar
  app (with a dashboard window) that talks to the existing Python CLI through
  JSON. Highlights:
  - Card-style stats header, brand-coloured tool filter chips, hover effects,
    before/after diff rows
  - **Visual settings panel** — sliders/spinners for idle / poll / batch sizes,
    namer picker, per-tool toggles; reads/writes `~/.config/retitle/config.toml`
    preserving comments
  - **First-launch onboarding** — explains Full Disk Access with one-click
    System Settings deep link; UserDefaults flag suppresses on subsequent
    launches
  - **Lazy data loading** — only the lightweight `status` poll runs in the
    background (every 5 min); the heavy `list / stats` scan only fires when
    the Dashboard is open or you hit Refresh. No more permission-prompt storm.
  - **Toast notifications** — friendly messages ("Background renaming paused",
    "Renamed to …") replace raw stderr surfacing in the UI
  - Localized in English and 简体中文. Builds with just Command Line Tools
    (`./build-app.sh` → `Retitle.app`).
- **Optional Windows / cross-platform GUI** in `windows-app/` — Python +
  PySide6 (Qt6). Mirrors the macOS app feature-for-feature using the same
  CLI bridge. On Windows it can spawn/kill `retitle run` as a managed child
  process (no native service integration there yet). Shipped untested by
  the developer — pull requests with Windows fixes welcome.
- `retitle status --json` — structured output so any GUI can read config,
  detected tools, namer resolution and daemon state.
- `retitle once --session ID` (repeatable) — rename one specific session,
  bypassing the idle and substance gates. Powers the GUI "Rename now" button.

## [0.4.1] - 2026-05-30

### Fixed
- **The `codex` namer was broken** — it read the last line of `codex exec`'s
  noisy transcript, which is `tokens used: N`, not the title. It now uses
  `codex exec --output-last-message <file>` and reads the clean final message.
- The `codex` namer now defaults to the fast `gpt-5-codex` model (the previously
  implied `gpt-5.3-codex` does not exist). Configurable via `[codex] model`.
- Raised the CLI namer timeout to 90s so slower reasoning models don't time out.

### Added
- `[claude]` and `[codex]` config sections to override the namer model.

## [0.4.0] - 2026-05-30

### Added
- `retitle once --limit N` and `retitle once --all` to rename past sessions on
  demand, in controlled batches (with progress output).

### Changed
- Renaming now assesses sessions first (fast, local) and only calls the namer for
  real candidates, most-recent first, capped at `batch_size` per pass (default 25,
  a new config option). This keeps the background daemon responsive and avoids
  calling your `claude`/`codex` CLI on a large backlog all at once.

## [0.3.0] - 2026-05-30

### Changed
- **Default namer is now `auto` — no API key required.** retitle reuses the
  `claude` or `codex` CLI you're already logged into to produce LLM-quality
  titles, falling back to the offline heuristic if neither is installed. The
  `claude` namer defaults to the fast Haiku model. Set `namer = "heuristic"` for a
  fully offline, zero-cost run.

### Added
- `retitle status` now shows what `auto` resolved to (e.g. `namer=auto → claude`).

## [0.2.0] - 2026-05-29

### Added
- `retitle search <query>` — find sessions across Claude Code, Codex and Cursor
  at once, by title (fast) or with `--content` to grep message text, with
  highlighted matches and snippets.
- `retitle stats` — a one-glance overview: sessions per tool, untitled / stale
  counts, oldest active session, and how many retitle has renamed.
- `--json` output for `retitle list`, `retitle search` and `retitle stats`.
- `SECURITY.md` documenting the privacy/data-safety model and how to report issues.
- `ARCHITECTURE.md` explaining the layering and each tool's reverse-engineered storage.
- Ruff linting, enforced in CI.

## [0.1.0] - 2026-05-29

Initial release.

### Added
- Background renamer that retitles AI coding sessions once they go idle (default 5 minutes).
- Adapters for **Claude Code** (append-only `ai-title` lines), **Codex** (`state_*.sqlite`
  `threads.title`), and **Cursor** (`state.vscdb` composer headers + data).
- Naming backends: `heuristic` (default, offline, zero-dependency), `claude` / `codex` (CLI
  shell-out), and `anthropic` / `openai` (direct API).
- Idempotent engine: renames only when a session has new content since the last title, and
  respects titles edited by hand until the conversation moves on.
- CLI: `list`, `once`, `run`, `install`, `uninstall`, `status`, `config`.
- Background service install for macOS (launchd) and Linux (systemd).
- Zero runtime dependencies — pure standard library.
