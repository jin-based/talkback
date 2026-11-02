import io
import subprocess
import urllib.error
from pathlib import Path

import pytest

from talkback import voices
from talkback.config import VoiceSettings
from talkback.voices import elevenlabs, say

SAY = VoiceSettings("say", "", "eleven_flash_v2_5")
ELEVEN = VoiceSettings("elevenlabs", "21m00Tcm4TlvDq8ikWAM", "eleven_flash_v2_5")


@pytest.fixture
def say_calls(monkeypatch):
    calls = []

    def fake(args, **k):
        calls.append(args)
        Path(args[args.index("-o") + 1]).write_bytes(b"FORMaiff")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(say, "_run", fake)
    return calls


def test_say_args_and_dash_text(say_calls, tmp_path):
    p = say.synthesize("-5 tests", SAY, None, tmp_path / "s")
    assert p == tmp_path / "s.aiff" and p.exists()
    assert say_calls == [["say", "-o", str(tmp_path / "s.aiff"), "--", "-5 tests"]]


def test_say_with_voice(say_calls, tmp_path):
    say.synthesize("hi", VoiceSettings("say", "Samantha", ""), None, tmp_path / "s")
    assert say_calls[0][:3] == ["say", "-v", "Samantha"]


def test_say_unknown_voice_retries_with_system_voice(monkeypatch, tmp_path):
    calls = []

    def fake(args, **k):
        calls.append(args)
        if "-v" in args:
            raise subprocess.CalledProcessError(1, args)
        Path(args[args.index("-o") + 1]).write_bytes(b"x")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(say, "_run", fake)
    assert say.synthesize("hi", VoiceSettings("say", "Nonexistent", ""), None, tmp_path / "s").exists()
    assert len(calls) == 2 and "-v" not in calls[1]


@pytest.fixture
def eleven(monkeypatch):
    rec = {"reply": b"ID3audio", "calls": []}

    def fake(url, headers, body, timeout):
        rec["calls"].append(dict(url=url, headers=headers, body=body, timeout=timeout))
        if isinstance(rec["reply"], Exception):
            raise rec["reply"]
        return rec["reply"]

    monkeypatch.setattr(elevenlabs, "post_audio", fake)
    return rec


def test_elevenlabs_request_unchanged(eleven, tmp_path):
    p = elevenlabs.synthesize("hi", ELEVEN, "k", tmp_path / "s")
    assert p == tmp_path / "s.mp3" and p.read_bytes() == b"ID3audio"
    c = eleven["calls"][0]
    assert c["url"] == "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
    assert c["headers"] == {"xi-api-key": "k", "Content-Type": "application/json", "Accept": "audio/mpeg"}
    assert c["body"] == {"text": "hi", "model_id": "eleven_flash_v2_5"} and c["timeout"] == 8


def test_elevenlabs_raw_mpeg_frame_ok(eleven, tmp_path):
    eleven["reply"] = b"\xff\xfb\x90\x00rest"
    assert elevenlabs.synthesize("hi", ELEVEN, "k", tmp_path / "s").exists()


def test_elevenlabs_non_audio_raises(eleven, tmp_path):
    eleven["reply"] = b'{"detail":"quota_exceeded"}'
    with pytest.raises(RuntimeError):
        elevenlabs.synthesize("hi", ELEVEN, "k", tmp_path / "s")


def test_elevenlabs_no_key_raises(eleven, tmp_path):
    with pytest.raises(RuntimeError):
        elevenlabs.synthesize("hi", ELEVEN, None, tmp_path / "s")
    assert eleven["calls"] == []


def test_render_falls_back_to_say(eleven, say_calls, monkeypatch, tmp_path):
    monkeypatch.setattr(voices, "get_key", lambda service: "k")
    eleven["reply"] = urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b""))
    path, who = voices.render("hi", ELEVEN, "tok")
    assert who == "say" and path.name.startswith("speech-tok-") and path.suffix == ".aiff"
    assert "elevenlabs" in (tmp_path / "log.txt").read_text()


def test_render_uses_configured_provider(eleven, monkeypatch, tmp_path):
    monkeypatch.setattr(voices, "get_key", lambda service: "k")
    path, who = voices.render("hi", ELEVEN, "tok")
    assert who == "elevenlabs" and path.name.startswith("speech-tok-") and path.suffix == ".mp3"


def test_render_say_configured_no_fallback_loop(say_calls, tmp_path):
    path, who = voices.render("hi", SAY, "tok")
    assert who == "say" and path.suffix == ".aiff" and len(say_calls) == 1


def test_audio_stem_is_unique_per_call(tmp_path):
    a, b = voices.audio_stem("abc"), voices.audio_stem("abc")
    assert a != b and a.parent == tmp_path and a.name.startswith("speech-abc-")


def test_each_render_gets_its_own_file(say_calls):
    p1, _ = voices.render("one", SAY, "tok")
    p2, _ = voices.render("two", SAY, "tok")
    assert p1 != p2 and p1.exists() and p2.exists()
