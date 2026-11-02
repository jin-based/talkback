import os
import time
from pathlib import Path

from talkback import config, sessions


def test_project_dir_prefers_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/work/horizon")
    assert sessions.project_dir({"cwd": "/elsewhere"}) == Path("/work/horizon")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    assert sessions.project_dir({"cwd": "/work/talkback"}) == Path("/work/talkback")


def test_project_name_override(tmp_path):
    (tmp_path / "config.json").write_text('{"projects": {"horizon": {"name": "Horizon App"}}}')
    cfg = config.load_config()
    assert sessions.project_name("horizon", cfg) == "Horizon App"
    assert sessions.project_name("talkback", cfg) == "talkback"


def test_active_count_window():
    for sid in ("a", "b", "c"):
        sessions.touch(sid)
    old = sessions.home() / "sessions" / "c.seen"
    t = time.time() - 1000
    os.utime(old, (t, t))
    assert sessions.active_count() == 2
    assert sessions.active_count(window_s=5000) == 3


def test_claim_per_session_independent():
    a = sessions.claim("A")
    b = sessions.claim("B")
    sessions.claim("A")
    assert not sessions.is_current("A", a) and sessions.is_current("B", b)
    assert sessions.current_token("B") == b and sessions.current_token("nope") is None


def test_safe_names(monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    for raw in ("a/b c", "ünï", "", "x" * 200):
        out = sessions.safe(raw)
        assert out and len(out) <= 64 and all(ch.isalnum() and ch.isascii() or ch in "_-" for ch in out)
    assert sessions.project_folder({"cwd": "/"}) == "project"
    assert sessions.project_folder({"cwd": "/work/my app"}) == "my app"
    sessions.touch("a/b c")
    assert sessions.active_count() == 1
