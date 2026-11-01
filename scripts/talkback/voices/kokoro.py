"""Kokoro: free voice model that runs on this Mac, via `uv run --script` (installs itself on first use)."""
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from talkback.config import VoiceSettings, home

SCRIPT = Path(__file__).resolve().parents[2] / "kokoro_tts.py"
MODEL_FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")
TIMEOUT = 20
WAIT_FOR_DOWNLOAD = False  # /talkback:setup's test sets this so the first download happens in the foreground
DOWNLOAD_GRACE = 900
_popen = subprocess.Popen


def _killpg(pid: int) -> None:
    os.killpg(pid, signal.SIGTERM)


def models_present() -> bool:
    return all((home() / "kokoro" / name).exists() for name in MODEL_FILES)


def _start_background_download() -> None:
    """Fetch Kokoro's packages and model once, detached, so a slow connection can finish."""
    marker = home() / "kokoro" / ".downloading"
    if marker.exists() and time.time() - marker.stat().st_mtime < DOWNLOAD_GRACE:
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(time.time()))
    _popen(["uv", "run", "--script", str(SCRIPT), "--download-only", "--home", str(home())],
           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def synthesize(text: str, s: VoiceSettings, key: str | None, out: Path) -> Path:
    if not models_present() and not WAIT_FOR_DOWNLOAD:
        _start_background_download()
        raise RuntimeError("Kokoro model is still downloading in the background; using the Mac voice for now")
    path = out.with_name(out.name + ".wav")
    args = ["uv", "run", "--script", str(SCRIPT), "--voice", s.voice, "--out", str(path), "--home", str(home())]
    proc = _popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                  text=True, start_new_session=True)
    try:
        _, err = proc.communicate(input=text, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            _killpg(proc.pid)
        except OSError:
            pass
        raise RuntimeError(f"kokoro took longer than {TIMEOUT}s (first run downloads the model; try /talkback:setup)")
    if proc.returncode != 0 or not path.exists():
        raise RuntimeError(f"kokoro failed (exit {proc.returncode}): {(err or '').strip()[-300:]}")
    return path
