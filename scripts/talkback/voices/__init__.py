"""Pick the configured voice; fall back to the Mac voice on any failure."""
from __future__ import annotations

from pathlib import Path

from talkback.config import VoiceSettings, get_key, home
from talkback.log import log_error
from talkback.voices import elevenlabs, kokoro, say

PROVIDERS = {"say": say, "kokoro": kokoro, "elevenlabs": elevenlabs}
KEYED = {"elevenlabs"}
SYSTEM_SAY = VoiceSettings("say", "", "")


def audio_stem(token: str) -> Path:
    return home() / f"speech-{token}"


def render(text: str, s: VoiceSettings, token: str) -> tuple[Path, str]:
    """Write audio for `text`; returns (path, provider that spoke). Raises only if the Mac voice fails too."""
    stem = audio_stem(token)
    if s.provider != "say":
        try:
            key = get_key(s.provider) if s.provider in KEYED else None
            return PROVIDERS[s.provider].synthesize(text, s, key, stem), s.provider
        except Exception as e:
            log_error(f"voice: {s.provider} failed: {e!r}; using the Mac voice")
            s = SYSTEM_SAY
    return say.synthesize(text, s, None, stem), "say"
