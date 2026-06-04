# rename cookbook

Practical recipes for searching, mining, and curating your AI session history.
Each example is a one-liner you can paste into a terminal. Combine them in
your own scripts.

> **Heads-up:** Everything here works against your real, live AI session
> stores. The commands below are read-only or operate within rename's safe
> write path — but if you're going to script anything aggressive, add
> `--dry-run`.

## 1. "Find that conversation I had about JWT refresh tokens last week"

```bash
rename search "JWT" --content --days 7
```

`--content` greps the actual message text (not just titles), and `--days 7`
caps the look-back window so the search stays fast. Drop `--days` to grep
your entire history.

## 2. Friday afternoon: weekly progress report

```bash
# What did I touch this week, across every tool?
rename list --json --max-age-days 7 \
  | jq -r '.[] | "\(.idle_seconds/3600|floor)h ago — [\(.tool)] \(.title // .proposed_title // "—")"' \
  | sort
```

Pipe to a markdown formatter for an "Engineering Journal" file you commit
weekly. Combined with `rename stats --json`, you get a one-glance dashboard
of where your hours went.

## 3. Rename only the sessions inside one project directory

```bash
rename once --max-age-days 30 \
  --tool claude-code --tool codex --tool cursor \
  # only the namer runs against eligible sessions; combine with a wrapper:
```

Even simpler — filter `rename list --json` by `cwd`, then call
`rename once --session <id>` for each match:

```bash
PROJ="$HOME/work/payments-api"
rename list --json \
  | jq -r ".[] | select(.cwd | startswith(\"$PROJ\")) | .id" \
  | xargs -I{} rename once --session {}
```

## 4. Heuristic mode for an instant, free, offline rename pass

```bash
rename once --all --namer heuristic
```

Useful before disconnecting on a flight, or when your `claude` / `codex` CLI
isn't logged in. The heuristic namer is bundled stdlib code — no LLM call.
Quality is decent for "give every conversation a non-default title", though
the LLM namer does better when the topic is subtle.

## 5. Preview without writing anything

```bash
rename once --all --dry-run | tee /tmp/rename-preview.log
```

Or per-tool:

```bash
rename once --tool antigravity --dry-run
```

Useful before you `rename install` a daemon on a fresh machine — you can
see what *would* get renamed first.

## 6. JSON pipelines for downstream tools

Every rename command supports `--json`:

```bash
# What are my untitled / "Untitled" sessions, sorted by age?
rename list --json \
  | jq -r '.[] | select((.title // "") == "" or (.title == "Untitled")) | "\(.idle_seconds/86400|floor)d  \(.tool)  \(.id[0:8])"' \
  | sort -nr
```

Or pipe to Marker, Datasette, sqlite-utils — anything that eats JSON.

## 7. Manually rename one session from the command line

```bash
# Find the id you want
rename list --json --tool claude-code --limit 5 | jq -r '.[0]'

# Force it through (bypasses idle + min-message gates)
rename once --session 1234abcd-...
```

This is exactly what the GUI's "Rename now" button does.

## 8. Open the dashboard, ignore the daemon

If you just want to *browse* your sessions without enabling auto-rename:

```bash
rename list                       # quick text view
rename list --tool claude-code    # one tool only
rename search "anything"          # find a topic
rename stats                      # one-glance overview
```

You can also install rename without installing the daemon (`rename install`
is the optional part). All CLI commands work fine standalone.

## 9. Use it from a script / cron job

If you want a cron-style daily pass without the launchd / systemd setup:

```cron
# crontab -e
0 9 * * *  /usr/local/bin/rename once >> ~/.local/state/rename/cron.log 2>&1
```

`rename once` exits as soon as the pass finishes, returning 0 on success and
a non-zero exit on error.

## 10. Pre-commit hook: rename when you finish a workday

Drop this into `~/.git-templates/hooks/pre-push` (after `git config --global
init.templatedir ~/.git-templates`):

```bash
#!/usr/bin/env bash
rename once --limit 5 --max-age-days 1 || true
```

Every push gives the LLM 5 sessions to rename — quietly enough not to block,
and free if you use the `auto` namer that reuses your already-logged-in
`claude` or `codex` CLI.

---

## See also

- [README](../README.en.md) — install + quick start (中文见 [README.md](../README.md))
- [ARCHITECTURE](../ARCHITECTURE.md) — how each adapter works under the hood
- [CHANGELOG](../CHANGELOG.md) — what's new

Got a recipe that's not here? Send a PR — small ones welcome.
