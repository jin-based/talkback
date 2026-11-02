"""Spoken "Claude needs you" alerts: permission prompts, waiting for a reply, multiple-choice questions."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from talkback import queue, sessions, voices
from talkback.clean import clean
from talkback.config import home, is_enabled, load_config
from talkback.log import log_error
from talkback.question import NUMBER_WORDS, MAX_OPTIONS
from talkback.speaker import voice_for

PENDING_MAX_AGE_S = 60
MAX_COMMAND_WORDS = 8
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
_LONG = re.compile(r"[A-Za-z0-9_\-+/=.]{20,}")
_ATTACHED = re.compile(r"^-[pPu].+")  # -pS3cret, -uroot
SECRET_FLAGS = {"-p", "-P", "-u", "--user", "--password", "--pass", "-H", "--header", "--token", "--with-token",
                "--api-key", "--key", "--secret", "--auth", "bearer", "authorization:", "basic"}


def _redact(word: str) -> str:
    return "a long value" if _LONG.search(word) else word


def _redact_command(words: list[str]) -> list[str]:
    """Never speak (or send to a voice service) anything that could be a password, token or key."""
    out: list[str] = []
    skip_next = False
    for w in words:
        bare = w.strip("'\"")
        if skip_next:
            word, skip_next = "a value", bare.endswith(":")
        elif bare.lower() in SECRET_FLAGS:
            word, skip_next = bare, True
        elif bare.lower().startswith(("http://", "https://")):
            word = "a web address"
        elif "=" in bare or ":" in bare or "@" in bare or _ATTACHED.match(bare):
            word, skip_next = "a value", bare.endswith(":")
        else:
            word = _redact(w)
        if not (word == "a value" and out and out[-1] == "a value"):
            out.append(word)
    return out


def permission_short(tool_name: str, tool_input: dict) -> str:
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool_name == "Bash":
        words = str(tool_input.get("command", "")).split()[:MAX_COMMAND_WORDS]
        return "run " + " ".join(_redact_command(words)) if words else "run a command"
    if tool_name in EDIT_TOOLS:
        name = Path(str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")).name
        return f"edit {_redact(name)}" if name else "edit a file"
    return f"use {tool_name or 'a tool'}"


def _pending_path(session: str) -> Path:
    d = home() / "pending"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{sessions.safe(session)}.json"


def _session(hook: dict) -> str:
    return str(hook.get("session_id") or "default")


def _say(hook: dict, text: str) -> None:
    session = _session(hook)
    token = sessions.current_token(session) or sessions.claim(session)
    cfg = load_config()
    path, _ = voices.render(text, voice_for(cfg, sessions.project_folder(hook)), token)
    if not is_enabled():  # turned off while we were rendering
        path.unlink(missing_ok=True)
        return
    queue.enqueue(session, token, path, "alert", front=True)
    queue.run_player()


def _project(hook: dict) -> str:
    return sessions.project_name(sessions.project_folder(hook), load_config())


def on_permission_request(hook: dict) -> None:
    short = permission_short(str(hook.get("tool_name") or ""), hook.get("tool_input") or {})
    _pending_path(_session(hook)).write_text(json.dumps({"short": short, "time": time.time()}))


def on_notification(hook: dict) -> None:
    kind = hook.get("notification_type")
    cfg = load_config()
    if kind == "permission_prompt" and cfg.alerts.permission:
        pending = _pending_path(_session(hook))
        short = None
        try:
            data = json.loads(pending.read_text())
            if time.time() - float(data["time"]) <= PENDING_MAX_AGE_S:
                short = str(data["short"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        pending.unlink(missing_ok=True)
        message = clean(str(hook.get("message") or "")) or "Claude needs your approval."
        _say(hook, f"{_project(hook)} needs approval: {short}" if short else f"{_project(hook)}: {message}")
    elif kind == "idle_prompt" and cfg.alerts.idle:
        _say(hook, f"{_project(hook)} is waiting for you.")


def on_ask_user_question(hook: dict) -> None:
    if not load_config().alerts.questions:
        return
    tool_input = hook.get("tool_input") if isinstance(hook.get("tool_input"), dict) else {}
    try:
        first = tool_input["questions"][0]
        q = clean(str(first["question"]))
        labels = [clean(str(o["label"])) for o in first.get("options", [])][:MAX_OPTIONS]
    except (KeyError, IndexError, TypeError):
        log_error(f"ask: unexpected tool_input keys {sorted(tool_input)}; not speaking it")
        return
    if not q:
        return
    text = f"{_project(hook)} asks: {q}"
    for word, label in zip(NUMBER_WORDS, labels):
        text += f" Option {word}, {label.rstrip('.')}."
    _say(hook, text)
