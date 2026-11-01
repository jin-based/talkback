"""Play audio, and stop whatever talkback is currently playing."""
from __future__ import annotations
import fcntl
import os
from contextlib import contextmanager
import secrets
import signal
import subprocess
from pathlib import Path

from talkback.config import home
from talkback.log import log_error

_popen = subprocess.Popen
PLAYERS = ("afplay",)


def _comm(pid: int) -> str:
    r = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _kill(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)


def claim() -> str:
    token = secrets.token_hex(8)
    (home() / "current.token").write_text(token)
    return token


def is_current(token: str) -> bool:
    try:
        return (home() / "current.token").read_text().strip() == token
    except OSError:
        return False


def stop_current() -> None:
    pid_file = home() / "playback.pid"
    try:
        pid = int(pid_file.read_text().strip())
    except (OSError, ValueError):
        pid_file.unlink(missing_ok=True)
        return
    try:
        if os.path.basename(_comm(pid)) in PLAYERS:
            _kill(pid)
    except Exception as e:
        log_error(f"playback: could not stop {pid}: {e!r}")
    pid_file.unlink(missing_ok=True)


@contextmanager
def locked():
    """One talkback process at a time may claim, stop, or start a player."""
    with open(home() / "lock", "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def claim_and_stop() -> str:
    with locked():
        token = claim()
        stop_current()
        return token


def _run(args: list[str], token: str) -> None:
    with locked():
        if not is_current(token):
            return  # a newer reply or a new message took over
        stop_current()
        proc = _popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (home() / "playback.pid").write_text(str(proc.pid))
    proc.wait()
    _clear_pid(proc.pid)


def _clear_pid(pid: int) -> None:
    pid_file = home() / "playback.pid"
    with locked():
        try:
            if pid_file.read_text().strip() == str(pid):
                pid_file.unlink()
        except OSError:
            pass


def play_file(path: Path, token: str) -> None:
    _run(["afplay", str(path)], token)
