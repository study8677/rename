# retitle cookbook

Practical recipes for searching, mining, and curating your AI session history.
Each example is a one-liner you can paste into a terminal. Combine them in
your own scripts.

> **Heads-up:** Everything here works against your real, live AI session
> stores. The commands below are read-only or operate within retitle's safe
> write path — but if you're going to script anything aggressive, add
> `--dry-run`.

## 1. "Find that conversation I had about JWT refresh tokens last week"

```bash
retitle search "JWT" --content --days 7
```

`--content` greps the actual message text (not just titles), and `--days 7`
caps the look-back window so the search stays fast. Drop `--days` to grep
your entire history.

## 2. Friday afternoon: weekly progress report

```bash
# What did I touch this week, across every tool?
retitle list --json --max-age-days 7 \
  | jq -r '.[] | "\(.idle_seconds/3600|floor)h ago — [\(.tool)] \(.title // .proposed_title // "—")"' \
  | sort
```

Pipe to a markdown formatter for an "Engineering Journal" file you commit
weekly. Combined with `retitle stats --json`, you get a one-glance dashboard
of where your hours went.

## 3. Rename only the sessions inside one project directory

```bash
retitle once --max-age-days 30 \
  --tool claude-code --tool codex --tool cursor \
  # only the namer runs against eligible sessions; combine with a wrapper:
```

Even simpler — filter `retitle list --json` by `cwd`, then call
`retitle once --session <id>` for each match:

```bash
PROJ="$HOME/work/payments-api"
retitle list --json \
  | jq -r ".[] | select(.cwd | startswith(\"$PROJ\")) | .id" \
  | xargs -I{} retitle once --session {}
```

## 4. Heuristic mode for an instant, free, offline rename pass

```bash
retitle once --all --namer heuristic
```

Useful before disconnecting on a flight, or when your `claude` / `codex` CLI
isn't logged in. The heuristic namer is bundled stdlib code — no LLM call.
Quality is decent for "give every conversation a non-default title", though
the LLM namer does better when the topic is subtle.

## 5. Preview without writing anything

```bash
retitle once --all --dry-run | tee /tmp/retitle-preview.log
```

Or per-tool:

```bash
retitle once --tool antigravity --dry-run
```

Useful before you `retitle install` a daemon on a fresh machine — you can
see what *would* get renamed first.

## 6. JSON pipelines for downstream tools

Every retitle command supports `--json`:

```bash
# What are my untitled / "Untitled" sessions, sorted by age?
retitle list --json \
  | jq -r '.[] | select((.title // "") == "" or (.title == "Untitled")) | "\(.idle_seconds/86400|floor)d  \(.tool)  \(.id[0:8])"' \
  | sort -nr
```

Or pipe to Marker, Datasette, sqlite-utils — anything that eats JSON.

## 7. Manually rename one session from the command line

```bash
# Find the id you want
retitle list --json --tool claude-code --limit 5 | jq -r '.[0]'

# Force it through (bypasses idle + min-message gates)
retitle once --session 1234abcd-...
```

This is exactly what the GUI's "Rename now" button does.

## 8. Open the dashboard, ignore the daemon

If you just want to *browse* your sessions without enabling auto-rename:

```bash
retitle list                       # quick text view
retitle list --tool claude-code    # one tool only
retitle search "anything"          # find a topic
retitle stats                      # one-glance overview
```

You can also install retitle without installing the daemon (`retitle install`
is the optional part). All CLI commands work fine standalone.

## 9. Use it from a script / cron job

If you want a cron-style daily pass without the launchd / systemd setup:

```cron
# crontab -e
0 9 * * *  /usr/local/bin/retitle once >> ~/.local/state/retitle/cron.log 2>&1
```

`retitle once` exits as soon as the pass finishes, returning 0 on success and
a non-zero exit on error.

## 10. Pre-commit hook: rename when you finish a workday

Drop this into `~/.git-templates/hooks/pre-push` (after `git config --global
init.templatedir ~/.git-templates`):

```bash
#!/usr/bin/env bash
retitle once --limit 5 --max-age-days 1 || true
```

Every push gives the LLM 5 sessions to retitle — quietly enough not to block,
and free if you use the `auto` namer that reuses your already-logged-in
`claude` or `codex` CLI.

---

## See also

- [README](../README.md) — install + quick start
- [ARCHITECTURE](../ARCHITECTURE.md) — how each adapter works under the hood
- [CHANGELOG](../CHANGELOG.md) — what's new

Got a recipe that's not here? Send a PR — small ones welcome.
