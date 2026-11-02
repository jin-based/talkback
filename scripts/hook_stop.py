"""Stop hook (async): speak a summary of Claude's last reply."""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import config, speaker  # noqa: E402
from talkback.log import log_error  # noqa: E402


def main(stdin_text: str) -> int:
    try:
        if not config.is_enabled():
            return 0
        data = json.loads(stdin_text) if stdin_text.strip() else {}
        if not isinstance(data, dict) or data.get("stop_hook_active"):
            return 0
        reply = data.get("last_assistant_message")
        if isinstance(reply, str) and reply.strip():
            speaker.speak(reply, data)
        else:
            log_error("hook_stop: no last_assistant_message in hook input")
    except Exception as e:
        log_error(f"hook_stop: {e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
