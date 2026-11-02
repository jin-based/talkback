"""Notification hook (async): speak permission and waiting-for-you alerts."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import alerts, config  # noqa: E402
from talkback.log import log_error  # noqa: E402


def main(stdin_text: str) -> int:
    try:
        if not config.is_enabled():
            return 0
        data = json.loads(stdin_text) if stdin_text.strip() else {}
        if isinstance(data, dict):
            alerts.on_notification(data)
    except Exception as e:
        log_error(f"hook_notification: {e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
