import retitle.namers.cli_namer as cli_namer
from retitle.config import Config
from retitle.namers import get_namer


def _which(*available):
    avail = set(available)
    return lambda name: f"/usr/bin/{name}" if name in avail else None


def test_auto_prefers_claude(monkeypatch):
    monkeypatch.setattr(cli_namer.shutil, "which", _which("claude", "codex"))
    assert get_namer(Config(namer="auto")).name == "claude"


def test_auto_falls_back_to_codex(monkeypatch):
    monkeypatch.setattr(cli_namer.shutil, "which", _which("codex"))
    assert get_namer(Config(namer="auto")).name == "codex"


def test_auto_falls_back_to_heuristic_without_clis(monkeypatch):
    monkeypatch.setattr(cli_namer.shutil, "which", _which())  # nothing installed
    assert get_namer(Config(namer="auto")).name == "heuristic"


def test_explicit_heuristic_ignores_clis(monkeypatch):
    monkeypatch.setattr(cli_namer.shutil, "which", _which("claude"))
    assert get_namer(Config(namer="heuristic")).name == "heuristic"


def test_claude_argv_uses_fast_model_by_default():
    argv = cli_namer.CliNamer("claude", {})._argv("hello")
    assert argv[0] == "claude"
    assert "--model" in argv and "haiku" in argv
    assert "-p" in argv and "hello" in argv


def test_claude_argv_respects_model_override():
    argv = cli_namer.CliNamer("claude", {"model": "sonnet"})._argv("x")
    assert "sonnet" in argv and "haiku" not in argv


def test_codex_argv():
    argv = cli_namer.CliNamer("codex", {})._argv("x")
    assert argv[:2] == ["codex", "exec"]
    assert argv[-1] == "x"
