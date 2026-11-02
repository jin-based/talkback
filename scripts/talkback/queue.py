"""Shared spoken-item queue across all Claude sessions, played by one temporary player at a time."""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import time
from pathlib import Path

from talkback.config import home
from talkback.log import log_error
from talkback.playback import _comm, _kill, _popen  # noqa: F401  (re-exported seams for tests)
from talkback.sessions import claim, is_current, safe

MAX_AGE_S = 120


def _qdir() -> Path:
    d = home() / "queue"
    d.mkdir(parents=True, exist_ok=True)
    return d


def enqueue(session: str, token: str, audio: Path, kind: str, front: bool) -> Path:
    name = f"{0 if front else 1}-{time.time_ns():020d}-{safe(session)}.json"
    item = {"session": session, "token": token, "audio": str(audio), "kind": kind, "created": time.time()}
    path = _qdir() / name
    tmp = path.with_name(name + ".tmp")
    tmp.write_text(json.dumps(item))
    os.replace(tmp, path)
    return path


def _items() -> list[Path]:
    return sorted(_qdir().glob("*.json"))


def _try_lock():
    f = open(home() / "player.lock", "a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except BlockingIOError:
        f.close()
        return None


def _play(session: str, audio: Path) -> None:
    playing = home() / "playing.json"
    proc = _popen(["afplay", str(audio)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    playing.write_text(json.dumps({"session": session, "pid": proc.pid}))
    try:
        proc.wait()
    finally:
        try:
            if json.loads(playing.read_text()).get("pid") == proc.pid:
                playing.unlink()
        except (OSError, ValueError):
            pass
        audio.unlink(missing_ok=True)


def _drain() -> None:
    while True:
        items = _items()
        if not items:
            return
        path = items[0]
        try:
            item = json.loads(path.read_text())
            session, token = item["session"], item["token"]
            audio = Path(item["audio"])
            created = float(item.get("created", 0))
        except Exception as e:
            log_error(f"queue: unreadable item {path.name}: {e!r}; skipped")
            path.unlink(missing_ok=True)
            continue
        path.unlink(missing_ok=True)
        if time.time() - created > MAX_AGE_S or not audio.exists() or not is_current(session, token):
            audio.unlink(missing_ok=True)
            continue
        try:
            _play(session, audio)
        except Exception as e:
            log_error(f"queue: playback failed: {e!r}")


def run_player() -> None:
    while True:
        lock = _try_lock()
        if lock is None:
            return  # another session's player will play our item
        try:
            _drain()
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
        if not _items():  # something may have arrived while we were unlocking
            return


def _stop_playing(only_session: str | None) -> None:
    try:
        playing = json.loads((home() / "playing.json").read_text())
        pid = int(playing["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return
    if only_session is not None and playing.get("session") != only_session:
        return
    try:
        if os.path.basename(_comm(pid)) == "afplay":
            _kill(pid)
    except Exception as e:
        log_error(f"queue: could not stop {pid}: {e!r}")


def stop_session(session: str) -> None:
    claim(session)  # every queued item from this session is now stale
    _stop_playing(session)


def stop_all() -> None:
    for path in _items():
        try:
            Path(json.loads(path.read_text()).get("audio", "")).unlink(missing_ok=True)
        except Exception:
            pass
        path.unlink(missing_ok=True)
    _stop_playing(None)
