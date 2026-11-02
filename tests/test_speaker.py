from pathlib import Path

import pytest

from talkback import queue, sessions, speaker

HOOK = {"session_id": "S1", "cwd": "/work/talkback"}


@pytest.fixture
def rec(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    r = {"summarize": [], "render": [], "enqueued": [], "player": 0}

    def render(text, s, token):
        p = tmp_path / f"speech-{token}.aiff"
        p.write_bytes(b"x")
        r["render"].append((text, s.voice, p))
        return p, s.provider

    monkeypatch.setattr(speaker.summarizers, "run", lambda text, s: r["summarize"].append(text) or "Summary.")
    monkeypatch.setattr(speaker.voices, "render", render)
    monkeypatch.setattr(speaker.queue, "enqueue",
                        lambda session, token, audio, kind, front: r["enqueued"].append((session, audio, kind, front)))
    monkeypatch.setattr(speaker.queue, "run_player", lambda: r.__setitem__("player", r["player"] + 1))
    return r


def test_speak_enqueues_summary_and_runs_player(rec):
    speaker.speak("I fixed the bug. Tests pass.", HOOK)
    (text, _, path), = rec["render"]
    assert text == "Summary." and rec["enqueued"] == [("S1", path, "summary", False)] and rec["player"] == 1
    assert path.exists()  # the queue owns the file now


def test_code_only_is_silent(rec):
    speaker.speak("```py\nx = 1\n```", HOOK)
    assert rec["summarize"] == [] and rec["enqueued"] == []


def test_prefix_only_when_two_sessions_active(rec):
    speaker.speak("Done.", HOOK)
    assert rec["render"][-1][0] == "Summary."
    sessions.touch("S2")
    speaker.speak("Done.", HOOK)
    assert rec["render"][-1][0] == "talkback: Summary."


def test_project_voice_override_used(rec, tmp_path):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "kokoro"}, "projects": {"talkback": {"voice": "af_bella", "name": "Talk Back"}}}')
    sessions.touch("S2")
    speaker.speak("Done.", HOOK)
    text, voice, _ = rec["render"][-1]
    assert voice == "af_bella" and text == "Talk Back: Summary."


def test_newer_reply_makes_older_stale(rec):
    speaker.speak("First.", HOOK)
    first_token = sessions.current_token("S1")
    speaker.speak("Second.", HOOK)
    assert not sessions.is_current("S1", first_token)


def test_stale_after_render_not_enqueued_and_deleted(rec, monkeypatch):
    real = speaker.voices.render

    def render_then_newer(text, s, token):
        out = real(text, s, token)
        sessions.claim("S1")
        return out

    monkeypatch.setattr(speaker.voices, "render", render_then_newer)
    speaker.speak("Done.", HOOK)
    assert rec["enqueued"] == [] and not rec["render"][-1][2].exists()


def test_unexpected_error_is_logged(rec, monkeypatch, tmp_path):
    monkeypatch.setattr(speaker.summarizers, "run", lambda t, s: (_ for _ in ()).throw(RuntimeError("kaboom")))
    speaker.speak("Done.", HOOK)
    assert "RuntimeError" in (tmp_path / "log.txt").read_text()


def test_compose():
    assert speaker.compose("Done.", " It asks: ok?", "horizon", 1) == "Done. It asks: ok?"
    assert speaker.compose("Done.", "", "horizon", 2) == "horizon: Done."
