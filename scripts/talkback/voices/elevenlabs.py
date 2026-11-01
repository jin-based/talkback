"""ElevenLabs text-to-speech (paid; needs a key)."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from talkback.config import VoiceSettings

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TIMEOUT = 8


def post_audio(url: str, headers: dict, body: dict, timeout: float) -> bytes:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _looks_like_mp3(data: bytes) -> bool:
    return data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)


def synthesize(text: str, s: VoiceSettings, key: str | None, out: Path) -> Path:
    if not key:
        raise RuntimeError("no key (run /talkback:key elevenlabs)")
    headers = {"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    data = post_audio(API.format(voice_id=s.voice), headers, {"text": text, "model_id": s.model}, TIMEOUT)
    if not _looks_like_mp3(data):
        raise RuntimeError(f"non-audio response: {data[:200]!r}")
    path = out.with_name(out.name + ".mp3")
    path.write_bytes(data)
    return path
