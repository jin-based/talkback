"""Append-only error log. Never raises."""
from datetime import datetime


def log_error(msg: str) -> None:
    try:
        from talkback.config import home
        with open(home() / "log.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")
    except Exception:
        pass
