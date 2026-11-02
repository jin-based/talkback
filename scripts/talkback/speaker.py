"""Reply text in, spoken summary queued. Never raises."""
from __future__ import annotations

from dataclasses import replace

from talkback import question, queue, sessions, summarizers, voices
from talkback.clean import clean
from talkback.config import Config, VoiceSettings, is_enabled, load_config
from talkback.log import log_error


def compose(summary: str, question_part: str, project: str, active: int) -> str:
    text = summary + question_part
    return f"{project}: {text}" if active >= 2 else text


def voice_for(cfg: Config, folder: str) -> VoiceSettings:
    p = cfg.projects.get(folder)
    return replace(cfg.voice, voice=p.voice) if p and p.voice else cfg.voice


def question_part(reply: str, cfg: Config) -> str:
    q = question.extract(reply)
    return " " + question.spoken(q[0], q[1], cfg.summary) if q else ""


def speak(reply: str, hook: dict) -> None:
    path = None
    try:
        session = str(hook.get("session_id") or "default")
        token = sessions.claim(session)  # this session's older, unplayed items are now stale
        sessions.touch(session)
        text = clean(reply)
        if not text:
            return
        cfg = load_config()
        summary = summarizers.run(text, cfg.summary)
        folder = sessions.project_folder(hook)
        spoken = compose(summary, question_part(reply, cfg), sessions.project_name(folder, cfg),
                         sessions.active_count())
        path, _ = voices.render(spoken, voice_for(cfg, folder), token)
        if not sessions.is_current(session, token) or not is_enabled():
            return  # a newer reply or a new message took over, or talk-back was turned off meanwhile
        queue.enqueue(session, token, path, "summary", front=False)
        path = None  # the queue owns the audio file now
        queue.run_player()
    except Exception as e:
        log_error(f"speaker: {e!r}")
    finally:
        if path is not None:
            path.unlink(missing_ok=True)
