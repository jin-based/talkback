"""v0.2.1: housekeeping, friendlier alerts, honest messages, clearer logs, key safety."""
import io
import json
import os
import subprocess
import time
import urllib.error
from pathlib import Path

import pytest

import configure
import set_key
import status
import voices as voices_cli
from talkback import alerts, config, housekeeping, log, queue, question, summarizers
from talkback.config import SummarySettings
from talkback.voices.catalog import Voice


def _age(path: Path, seconds: float):
    t = time.time() - seconds
    os.utime(path, (t, t))


# 1. Clean up after itself
def test_prune_removes_old_files_only(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "pending").mkdir()
    old_seen, new_seen = tmp_path / "sessions" / "a.seen", tmp_path / "sessions" / "b.seen"
    old_tok, old_pend = tmp_path / "sessions" / "a.token", tmp_path / "pending" / "a.json"
    old_audio, new_audio = tmp_path / "speech-x-1.aiff", tmp_path / "speech-y-2.aiff"
    for p in (old_seen, new_seen, old_tok, old_pend, old_audio, new_audio):
        p.write_text("x")
    for p in (old_seen, old_tok):
        _age(p, 2 * 86400)
    _age(old_pend, 2 * 3600)
    _age(old_audio, 2 * 3600)
    housekeeping.prune()
    assert not old_seen.exists() and not old_pend.exists() and not old_audio.exists()
    assert new_seen.exists() and new_audio.exists()
    assert old_tok.exists()  # tokens are never pruned: an idle session's next alert still needs it


def test_player_prunes(monkeypatch):
    called = []
    monkeypatch.setattr(queue.housekeeping, "prune", lambda: called.append(1))
    queue.run_player()
    assert called == [1]


def test_log_is_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(log, "MAX_BYTES", 200)
    for i in range(20):
        log.log_error(f"line {i} " + "x" * 30)
    assert (tmp_path / "log.txt").stat().st_size <= 200 + 100
    assert (tmp_path / "log.old.txt").exists()


# 2. Friendlier tool names
@pytest.mark.parametrize("tool,phrase", [
    ("mcp__github__create_issue", "use the github create issue tool"),
    ("mcp__claude-in-chrome__navigate", "use the claude in chrome navigate tool"),
    ("WebFetch", "fetch a web page"),
    ("WebSearch", "search the web"),
    ("ExitPlanMode", "approve the plan"),
    ("SomeNewTool", "use some new tool"),
])
def test_friendly_tool_names(tool, phrase):
    assert alerts.permission_short(tool, {}) == phrase


# 3. Honest voice-picker messages
@pytest.fixture
def kokoro_cfg(tmp_path):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "kokoro"}}')


def _fake_render(tmp_path):
    def render(text, s, token):
        p = tmp_path / "p.wav"
        p.write_bytes(b"x")
        return p, s.provider
    return render


def test_preview_says_queued_when_another_voice_is_speaking(kokoro_cfg, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(voices_cli.voices, "render", _fake_render(tmp_path))
    monkeypatch.setattr(voices_cli.queue, "enqueue", lambda *a, **k: None)
    monkeypatch.setattr(voices_cli.queue, "run_player", lambda: False)
    voices_cli.main(["preview", "Bella"])
    out = capsys.readouterr().out
    assert "Played" not in out and "after" in out


def test_preview_failure_is_not_called_a_list_failure(kokoro_cfg, monkeypatch, capsys):
    monkeypatch.setattr(voices_cli.voices, "render", lambda *a: (_ for _ in ()).throw(RuntimeError("say broke")))
    assert voices_cli.main(["preview", "Bella"]) == 1
    out = capsys.readouterr().out
    assert "Couldn't play a sample" in out and "voice list" not in out


def test_run_player_reports_whether_it_played(tmp_path):
    import fcntl
    assert queue.run_player() is True
    with open(tmp_path / "player.lock", "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        assert queue.run_player() is False


# 4. Cleaner question reader
def test_nested_bullets_are_not_options():
    reply = "Which approach?\n1. Alpha\n   - sub detail\n2. Beta"
    assert question.extract(reply) == ("Which approach?", ["Alpha", "Beta"])


def test_heading_last_line_is_not_a_question():
    assert question.extract("Done.\n\n## Next steps?") is None


def test_blockquote_question_is_read_cleanly():
    assert question.extract("Done.\n\n> Should I push?") == ("Should I push?", [])


def test_hard_wrapped_question_is_joined():
    reply = "I updated the parser.\n\nShould I also update\nthe docs and the changelog?"
    assert question.extract(reply)[0] == "Should I also update the docs and the changelog?"


# 5. Easier diagnosis
def test_http_error_reason_is_logged(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(b'{"error":"quota_exceeded"}'))
    monkeypatch.setattr(summarizers._http, "post_json", boom)
    summarizers.run("I fixed it.", SummarySettings("ollama", "m", "http://localhost:11434"))
    text = (tmp_path / "log.txt").read_text()
    assert "429" in text and "quota_exceeded" in text


def test_settings_problem_logged_once(tmp_path):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "nope"}}')
    for _ in range(3):
        config.load_config()
    assert (tmp_path / "log.txt").read_text().count("unknown provider") == 1


# 6. Uninstalled Mac voice is flagged
def test_status_flags_missing_mac_voice(tmp_path, monkeypatch, capsys):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "say", "voice": "Nobody"}}')
    monkeypatch.setattr(status, "_ollama_models", lambda url: None)
    monkeypatch.setattr(status, "_keychain_has", lambda s: False)
    monkeypatch.setattr(status, "all_say_names", lambda: {"samantha"})
    status.main()
    assert "Mac voice Nobody isn't installed" in capsys.readouterr().out


# 7. Key safety
def test_pasted_key_argument_warns(capsys):
    assert set_key.main(["openai", "sk-proj-abcdefghijklmnop1234"]) == 1
    out = capsys.readouterr().out
    assert "looks like an API key" in out and "sk-proj" not in out


def test_save_is_verified(monkeypatch, capsys):
    def fake(args, **k):
        if args[0] == "osascript":
            return subprocess.CompletedProcess(args, 0, stdout="sk-123secret\n", stderr="")
        if args[:2] == ["security", "-i"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:2] == ["security", "find-generic-password"]:
            return subprocess.CompletedProcess(args, 44, stdout="", stderr="")
        raise AssertionError(args)
    monkeypatch.setattr(set_key, "_run", fake)
    assert set_key.main(["elevenlabs"]) == 1
    assert "Could not save the key" in capsys.readouterr().out


def test_config_written_atomically(tmp_path, monkeypatch):
    replaced = []
    real = os.replace
    monkeypatch.setattr(configure.os, "replace", lambda a, b: replaced.append(Path(b).name) or real(a, b))
    configure.main(["voice.provider=kokoro"])
    assert replaced == ["config.json"] and not list(tmp_path.glob("config.json.*"))


def test_status_accepts_non_english_mac_voice(tmp_path, monkeypatch, capsys):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "say", "voice": "Kyoko"}}')
    monkeypatch.setattr(status, "_ollama_models", lambda url: None)
    monkeypatch.setattr(status, "_keychain_has", lambda s: False)
    monkeypatch.setattr(status, "all_say_names", lambda: {"samantha", "kyoko"})
    status.main()
    assert "isn't installed" not in capsys.readouterr().out


def test_key_without_service_warns(capsys):
    assert set_key.main(["sk-ant-abcdefghijklmnopqrstu"]) == 1
    out = capsys.readouterr().out
    assert "looks like an API key" in out and "sk-ant" not in out
