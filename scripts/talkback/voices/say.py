"""macOS built-in voice, rendered to a file so every voice plays the same way."""
from __future__ import annotations

import subprocess
from pathlib import Path

from talkback.config import VoiceSettings
from talkback.log import log_error

_run = subprocess.run
TIMEOUT = 8


def _render(text: str, voice: str, out: Path) -> None:
    args = ["say"] + (["-v", voice] if voice else []) + ["-o", str(out), "--", text]
    _run(args, check=True, timeout=TIMEOUT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def synthesize(text: str, s: VoiceSettings, key: str | None, out: Path) -> Path:
    path = out.with_name(out.name + ".aiff")
    try:
        _render(text, s.voice, path)
    except subprocess.CalledProcessError:
        if not s.voice:
            raise
        log_error(f"say: voice {s.voice!r} failed; using the system voice")
        _render(text, "", path)
    if not path.exists():
        raise RuntimeError("say wrote no audio")
    return path
