"""Play audio, and stop whatever talkback is currently playing."""
import os
import secrets
import signal
import subprocess
from pathlib import Path

from talkback.config import home
from talkback.log import log_error

_popen = subprocess.Popen
PLAYERS = ("afplay", "say")


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


def _run(args: list[str]) -> None:
    proc = _popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (home() / "playback.pid").write_text(str(proc.pid))
    proc.wait()


def play_file(path: Path) -> None:
    _run(["afplay", str(path)])


def play_say(text: str) -> None:
    _run(["say", text])
