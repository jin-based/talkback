"""Voices available for each provider, by name."""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from dataclasses import dataclass

_run = subprocess.run
ELEVEN_VOICES_URL = "https://api.elevenlabs.io/v1/voices"

KOKORO_IDS = (
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river",
    "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx",
    "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george",
    "bm_lewis",
)
_ACCENT = {"a": "American", "b": "British"}
_GENDER = {"f": "female", "m": "male"}
_SAY_LINE = re.compile(r"^(.+?)\s+([a-z]{2,3}_[A-Z0-9]{2,3})\s+#")


@dataclass(frozen=True)
class Voice:
    name: str
    id: str
    description: str


def _get_json(url: str, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _kokoro() -> list[Voice]:
    return [Voice(i[3:].capitalize(), i, f"{_ACCENT[i[0]]} {_GENDER[i[1]]}") for i in KOKORO_IDS]


def _say() -> list[Voice]:
    out = _run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
    voices = []
    for line in out.splitlines():
        m = _SAY_LINE.match(line)
        if m and m.group(2).startswith("en_"):
            voices.append(Voice(m.group(1).strip(), m.group(1).strip(), m.group(2)))
    return voices


def _elevenlabs(key: str | None) -> list[Voice]:
    if not key:
        raise RuntimeError("no ElevenLabs key (run /talkback:key elevenlabs)")
    data = _get_json(ELEVEN_VOICES_URL, {"xi-api-key": key}, 8)
    if not isinstance(data, dict) or "voices" not in data:
        raise RuntimeError(f"unexpected response from ElevenLabs: {str(data)[:200]}")
    out = []
    for v in data["voices"]:
        labels = v.get("labels") or {}
        desc = ", ".join(str(x) for x in labels.values() if x) if isinstance(labels, dict) else ""
        out.append(Voice(str(v.get("name", "")), str(v.get("voice_id", "")), desc))
    return out


def list_voices(provider: str, key: str | None) -> list[Voice]:
    if provider == "kokoro":
        return _kokoro()
    if provider == "elevenlabs":
        return _elevenlabs(key)
    return _say()


def find(voices: list[Voice], name: str) -> list[Voice]:
    n = name.strip().lower()
    exact = [v for v in voices if v.name.lower() == n or v.id.lower() == n]
    return exact or [v for v in voices if n and n in v.name.lower()]
