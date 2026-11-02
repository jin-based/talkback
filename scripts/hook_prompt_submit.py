"""UserPromptSubmit hook: stop talking when the user sends a new message."""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json  # noqa: E402

from talkback import queue  # noqa: E402
from talkback.log import log_error  # noqa: E402


def main(stdin_text: str) -> int:
    try:
        data = json.loads(stdin_text) if stdin_text.strip() else {}
        session = str(data.get("session_id") or "default") if isinstance(data, dict) else "default"
        queue.stop_session(session)  # only this session's speech stops
    except Exception as e:
        log_error(f"hook_prompt_submit: {e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
