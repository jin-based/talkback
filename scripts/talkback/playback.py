"""Low-level helpers for stopping talkback's audio player safely."""
from __future__ import annotations

import os
import signal
import subprocess

_popen = subprocess.Popen


def _comm(pid: int) -> str:
    r = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _kill(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)
