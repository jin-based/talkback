from pathlib import Path

import pytest

from talkback import playback, speaker


@pytest.fixture
def calls(monkeypatch):
    c = {"summarize": [], "synthesize": [], "play_file": [], "play_say": []}
    monkeypatch.setattr(speaker, "summarize", lambda text, cfg: c["summarize"].append(text) or "Summary.")
    monkeypatch.setattr(speaker, "synthesize",
                        lambda text, cfg, key: c["synthesize"].append((text, key)) or Path("/tmp/a.mp3"))
    monkeypatch.setattr(speaker, "play_file", lambda path, token: c["play_file"].append(path))
    monkeypatch.setattr(speaker, "play_say", lambda text, token: c["play_say"].append(text))
    monkeypatch.setattr(speaker, "get_api_key", lambda: "k")
    return c


def test_happy_path_plays_elevenlabs_audio(calls):
    speaker.speak("I fixed the bug in `x`. Tests pass.")
    assert calls["summarize"] == ["I fixed the bug in. Tests pass."]
    assert calls["synthesize"] == [("Summary.", "k")]
    assert calls["play_file"] == [Path("/tmp/a.mp3")] and calls["play_say"] == []


def test_falls_back_to_say_when_tts_fails(calls, monkeypatch):
    monkeypatch.setattr(speaker, "synthesize", lambda *a: None)
    speaker.speak("Done.")
    assert calls["play_say"] == ["Summary."] and calls["play_file"] == []


def test_code_only_reply_is_silent(calls):
    speaker.speak("```py\nx = 1\n```")
    assert calls["summarize"] == [] and calls["play_file"] == [] and calls["play_say"] == []


def test_stale_speaker_does_not_play(calls, monkeypatch):
    def newer_speaker_claims(text, cfg):
        playback.claim()
        return "Old summary."

    monkeypatch.setattr(speaker, "summarize", newer_speaker_claims)
    speaker.speak("Done.")
    assert calls["play_file"] == [] and calls["play_say"] == []


def test_stops_previous_playback_first(calls, monkeypatch):
    stopped = []
    real = speaker.claim_and_stop
    monkeypatch.setattr(speaker, "claim_and_stop", lambda: stopped.append(1) or real())
    speaker.speak("Done.")
    assert stopped == [1]


def test_unexpected_error_is_logged(calls, monkeypatch, tmp_path):
    def boom(text, cfg):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(speaker, "summarize", boom)
    speaker.speak("Done.")
    assert "RuntimeError" in (tmp_path / "log.txt").read_text()
