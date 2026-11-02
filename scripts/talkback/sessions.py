"""Which Claude session and project an event belongs to; per-session tokens and activity."""
from __future__ import annotations

import os
import re
import secrets
import time
from pathlib import Path

from talkback.config import home

ACTIVE_WINDOW_S = 300


def safe(s: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_-]", "_", s or "")[:64]
    return out or "_"


def _dir() -> Path:
    d = home() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_dir(hook: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or hook.get("cwd") or os.getcwd())


def project_folder(hook: dict) -> str:
    return project_dir(hook).name or "project"


def project_name(folder: str, cfg) -> str:
    p = cfg.projects.get(folder)
    return (p.name if p and p.name else folder) or "project"


def touch(session: str) -> None:
    (_dir() / f"{safe(session)}.seen").touch()


def active_count(window_s: int = ACTIVE_WINDOW_S) -> int:
    cutoff = time.time() - window_s
    return sum(1 for f in _dir().glob("*.seen") if f.stat().st_mtime >= cutoff)


def claim(session: str) -> str:
    token = secrets.token_hex(8)
    (_dir() / f"{safe(session)}.token").write_text(token)
    return token


def current_token(session: str) -> str | None:
    try:
        return (_dir() / f"{safe(session)}.token").read_text().strip() or None
    except OSError:
        return None


def is_current(session: str, token: str) -> bool:
    return current_token(session) == token
