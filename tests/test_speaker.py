from pathlib import Path

import pytest

from talkback import playback, speaker


@pytest.fixture
def calls(monkeypatch, tmp_path):
    c = {"summarize": [], "render": [], "play": []}

    def render(text, s, token):
        p = tmp_path / f"speech-{token}.aiff"
        p.write_bytes(b"x")
        c["render"].append((text, p))
        return p, "say"

    monkeypatch.setattr(speaker.summarizers, "run", lambda text, s: c["summarize"].append(text) or "Summary.")
    monkeypatch.setattr(speaker.voices, "render", render)
    monkeypatch.setattr(speaker, "play_file", lambda path, token: c["play"].append((path, path.exists())))
    return c


def test_speaker_plays_rendered_file_and_deletes_it(calls):
    speaker.speak("I fixed the bug in `x`. Tests pass.")
    assert calls["summarize"] == ["I fixed the bug in. Tests pass."]
    (text, path), = calls["render"]
    assert text == "Summary." and calls["play"] == [(path, True)]
    assert not path.exists()


def test_speaker_code_only_is_silent(calls):
    speaker.speak("```py\nx = 1\n```")
    assert calls["summarize"] == [] and calls["render"] == [] and calls["play"] == []


def test_speaker_stale_after_render_does_not_play_and_deletes(calls, monkeypatch):
    real_render = speaker.voices.render

    def render_then_newer_claims(text, s, token):
        out = real_render(text, s, token)
        playback.claim()
        return out

    monkeypatch.setattr(speaker.voices, "render", render_then_newer_claims)
    speaker.speak("Done.")
    assert calls["play"] == []
    (_, path), = calls["render"]
    assert not path.exists()


def test_stops_previous_playback_first(calls, monkeypatch):
    stopped = []
    real = speaker.claim_and_stop
    monkeypatch.setattr(speaker, "claim_and_stop", lambda: stopped.append(1) or real())
    speaker.speak("Done.")
    assert stopped == [1]


def test_unexpected_error_is_logged(calls, monkeypatch, tmp_path):
    def boom(text, s):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(speaker.summarizers, "run", boom)
    speaker.speak("Done.")
    assert "RuntimeError" in (tmp_path / "log.txt").read_text()
