"""Append-only error log, capped in size. Never raises."""
from __future__ import annotations

import os
import urllib.error
from datetime import datetime

MAX_BYTES = 1_000_000


def describe(e: BaseException) -> str:
    """repr of an error, plus the service's reason for HTTP errors (response bodies never contain our key)."""
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read()[:200].decode("utf-8", "replace").strip()
        except Exception:
            body = ""
        return f"HTTP {e.code} {e.reason}" + (f": {body}" if body else "")
    return repr(e)


def log_error(msg: str) -> None:
    try:
        from talkback.config import home
        path = home() / "log.txt"
        if path.exists() and path.stat().st_size > MAX_BYTES:
            os.replace(path, home() / "log.old.txt")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")
    except Exception:
        pass
