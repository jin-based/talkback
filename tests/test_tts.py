import io
import urllib.error

from talkback import tts


def test_no_key_returns_none(monkeypatch, cfg):
    monkeypatch.setattr(tts, "post_audio", lambda *a: 1 / 0)
    assert tts.synthesize("hi", cfg, None) is None


def test_request_shape_and_file(monkeypatch, tmp_path):
    from talkback.config import Config, SummarySettings, VoiceSettings
    cfg = Config(SummarySettings("none", "", ""), VoiceSettings("elevenlabs", "21m00Tcm4TlvDq8ikWAM", "eleven_flash_v2_5"))
    seen = {}

    def fake(url, headers, body, timeout):
        seen.update(url=url, headers=headers, body=body, timeout=timeout)
        return b"ID3fakeaudio"

    monkeypatch.setattr(tts, "post_audio", fake)
    p = tts.synthesize("hi", cfg, "k")
    assert p == tmp_path / "speech.mp3" and p.read_bytes() == b"ID3fakeaudio"
    assert seen["url"] == "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
    assert seen["headers"] == {"xi-api-key": "k", "Content-Type": "application/json", "Accept": "audio/mpeg"}
    assert seen["timeout"] == 8
    assert seen["body"] == {"text": "hi", "model_id": "eleven_flash_v2_5"}


def test_raw_mpeg_frame_counts_as_audio(monkeypatch, cfg):
    monkeypatch.setattr(tts, "post_audio", lambda *a: b"\xff\xfb\x90\x00rest")
    assert tts.synthesize("hi", cfg, "k") is not None


def test_non_audio_response_is_failure(monkeypatch, cfg):
    monkeypatch.setattr(tts, "post_audio", lambda *a: b'{"detail":"quota_exceeded"}')
    assert tts.synthesize("hi", cfg, "k") is None


def test_http_error_is_failure(monkeypatch, cfg, tmp_path):
    def raise_401(*a):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b"bad key"))

    monkeypatch.setattr(tts, "post_audio", raise_401)
    assert tts.synthesize("hi", cfg, "k") is None
    assert "401" in (tmp_path / "log.txt").read_text()
