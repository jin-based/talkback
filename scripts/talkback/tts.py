"""ElevenLabs text-to-speech. Returns an mp3 path, or None on any failure."""
import json
import urllib.request
from pathlib import Path

from talkback.config import Config, home
from talkback.log import log_error

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TIMEOUT = 8


def post_audio(url: str, headers: dict, body: dict, timeout: float) -> bytes:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _looks_like_mp3(data: bytes) -> bool:
    return data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)


def synthesize(text: str, cfg: Config, api_key: str | None) -> Path | None:
    if not api_key:
        return None
    headers = {"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    body = {"text": text, "model_id": cfg.eleven_model}
    try:
        data = post_audio(API.format(voice_id=cfg.voice_id), headers, body, TIMEOUT)
    except Exception as e:
        log_error(f"tts: ElevenLabs failed: {e!r}")
        return None
    if not _looks_like_mp3(data):
        log_error(f"tts: ElevenLabs returned non-audio: {data[:200]!r}")
        return None
    path = home() / "speech.mp3"
    path.write_bytes(data)
    return path
