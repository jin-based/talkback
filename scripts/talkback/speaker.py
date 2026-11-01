"""Reply text in, spoken summary out. Never raises."""
from talkback.clean import clean
from talkback.config import get_api_key, load_config
from talkback.log import log_error
from talkback.playback import claim, is_current, play_file, play_say, stop_current
from talkback.summarize import summarize
from talkback.tts import synthesize


def speak(reply: str) -> None:
    try:
        token = claim()
        stop_current()
        text = clean(reply)
        if not text:
            return
        cfg = load_config()
        summary = summarize(text, cfg)
        audio = synthesize(summary, cfg, get_api_key())
        if not is_current(token):
            return  # a newer reply took over while we were working
        stop_current()
        if audio:
            play_file(audio)
        else:
            play_say(summary)
    except Exception as e:
        log_error(f"speaker: {e!r}")
