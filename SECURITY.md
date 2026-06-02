# Security Policy

`rename` reads and writes your local AI coding session stores, so its safety and
privacy are a first-class concern.

## What rename does with your data

- **No telemetry, ever, and it only changes titles.** rename never phones home;
  it appends or updates a single title field per session and never edits, deletes,
  or reorders your conversations.
- **Titling uses your own logged-in CLI by default.** The default `auto` namer
  asks the `claude` / `codex` tool you're already signed into to write the title,
  so a short transcript excerpt is sent through that provider — there is no API
  key to paste. The `anthropic` / `openai` namers do the same via a key you set.
- **Fully offline option.** Set `namer = "heuristic"` and nothing ever leaves
  your machine.
- **Conservative writes.** Reads use read-only SQLite connections; writes use a
  busy timeout and a single atomic transaction; it only ever touches *idle*
  sessions.

## Reporting a vulnerability

Please report security issues **privately** via GitHub Security Advisories
(the "Report a vulnerability" button under the repository's **Security** tab),
not a public issue.

Include what you found, the affected version (`rename --version`), and steps to
reproduce. ⚠️ Please **redact any private session content** from your report.

We aim to acknowledge reports within a few days and to fix verified issues
promptly.

## Supported versions

rename is pre-1.0; security fixes land on the latest `main` and the newest
release.
