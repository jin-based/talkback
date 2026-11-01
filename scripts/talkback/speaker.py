"""Reply text in, spoken summary out. Never raises."""
from __future__ import annotations
from talkback.clean import clean
from talkback.config import get_key, load_config
from talkback.log import log_error
from talkback.playback import claim_and_stop, is_current, play_file, play_say
from talkback.summarize import summarize
from talkback.tts import synthesize


def speak(reply: str) -> None:
    try:
        token = claim_and_stop()
        text = clean(reply)
        if not text:
            return
        cfg = load_config()
        summary = summarize(text, cfg)
        audio = synthesize(summary, cfg, get_key("elevenlabs"))
        if not is_current(token):
            return  # a newer reply took over while we were working
        if audio:
            play_file(audio, token)  # re-checks the token under the lock
        else:
            play_say(summary, token)
    except Exception as e:
        log_error(f"speaker: {e!r}")
