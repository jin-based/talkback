"""Reply text in, spoken summary out. Never raises."""
from __future__ import annotations

from talkback import summarizers, voices
from talkback.clean import clean
from talkback.config import load_config
from talkback.log import log_error
from talkback.playback import claim_and_stop, is_current, play_file


def speak(reply: str) -> None:
    path = None
    try:
        token = claim_and_stop()
        text = clean(reply)
        if not text:
            return
        cfg = load_config()
        summary = summarizers.run(text, cfg.summary)
        path, _ = voices.render(summary, cfg.voice, token)
        if not is_current(token):
            return  # a newer reply or a new message took over while we were working
        play_file(path, token)  # re-checks the token under the lock
    except Exception as e:
        log_error(f"speaker: {e!r}")
    finally:
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
