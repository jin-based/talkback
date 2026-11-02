"""Delete talkback's old temporary files so its folder never grows without bound."""
from __future__ import annotations

import time

from talkback.config import home

SESSION_MAX_AGE_S = 86400   # .seen / .token notes for sessions idle a day
PENDING_MAX_AGE_S = 3600    # permission details never used
AUDIO_MAX_AGE_S = 3600      # speech files left behind by a crashed hook


def prune() -> None:
    now = time.time()
    root = home()
    rules = [(root / "sessions", ("*.seen", "*.token"), SESSION_MAX_AGE_S),
             (root / "pending", ("*.json",), PENDING_MAX_AGE_S),
             (root, ("speech-*",), AUDIO_MAX_AGE_S)]
    for folder, patterns, max_age in rules:
        if not folder.is_dir():
            continue
        for pattern in patterns:
            for path in folder.glob(pattern):
                try:
                    if now - path.stat().st_mtime > max_age:
                        path.unlink()
                except OSError:
                    pass
