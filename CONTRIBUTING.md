# Contributing to retitle

Thanks for helping out! `retitle` is small, stdlib-only Python — easy to hack on.

## Setup

```bash
git clone https://github.com/study8677/retitle.git && cd retitle
pip install -e ".[dev]"
pytest          # 22 tests, all using synthetic fixtures (never your real data)
```

There are **no runtime dependencies** by design — please keep it that way. The only dev
dependency is `pytest`. Everything uses the Python standard library (`sqlite3`, `json`,
`urllib`, `tomllib`, `plistlib`, …).

## Project layout

```
src/retitle/
├── cli.py            # argparse front-end
├── engine.py         # the rename decision loop
├── config.py         # TOML config + defaults
├── state.py          # JSON store of "what we already renamed"
├── util.py           # paths, text cleaning, noise filtering, title shaping
├── service.py        # launchd / systemd install
├── adapters/         # one file per tool
│   ├── base.py       # the Adapter contract
│   ├── claude_code.py
│   ├── codex.py
│   └── cursor.py
└── namers/           # title generators
    ├── base.py       # the Namer contract + prompt helpers
    ├── heuristic.py  # default, offline
    ├── cli_namer.py  # shells out to claude/codex
    └── api.py        # anthropic/openai
```

## Adding support for a new tool

Implement one `Adapter` subclass (see `src/retitle/adapters/base.py`):

```python
class MyToolAdapter(Adapter):
    name = "mytool"          # used in config + state
    label = "My Tool"

    def available(self) -> bool:
        """Is this tool's data present on the machine?"""

    def discover(self, since: float) -> list[Session]:
        """Sessions active at/after `since` (epoch seconds), with title + last_active."""

    def read_transcript(self, session: Session) -> list[Message]:
        """The conversation, oldest first, for naming."""

    def set_title(self, session: Session, title: str) -> None:
        """Persist the new display title."""
```

Then register it in `adapters/__init__.py` and add it to `ALL_TOOLS` in `config.py`.

### Data-safety rules for adapters

This tool writes to people's real session stores. Hold to these:

1. **Only ever change the title.** Never reorder, delete, or rewrite conversation content.
2. **Reads must not mutate.** Use `connect_read()` (it sets `query_only`) for SQLite reads.
3. **Round-trip JSON losslessly.** If you `json.loads` a blob, mutate one field, and write it
   back, make sure you're not dropping or reformatting anything the app depends on.
4. **Assume the app is running.** Use `connect_write()` (sets `busy_timeout`) and keep writes
   to a single small transaction. Prefer append-only formats where possible.
5. **Fail soft.** A malformed file or locked DB should make the adapter skip that session, not
   crash the daemon. The engine already wraps adapter calls, but don't rely on it for cleanup —
   close your handles.

Add a round-trip test in `tests/` using a synthetic fixture (see `tests/test_adapters.py`).

## Adding a namer

Implement a `Namer` (see `src/retitle/namers/base.py`) with one `generate(...)` method that
returns a short title or `None`. Register it in `namers/__init__.py`.

## Style

- Match the surrounding code. Type hints on public functions. Short, focused functions.
- Keep titles short: the engine runs everything through `util.shape_title`.
- Run `pytest` before opening a PR.
