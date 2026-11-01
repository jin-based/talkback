"""SessionStart hook (async): load the summary model so the first reply is fast."""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import config, summarize  # noqa: E402
from talkback.log import log_error  # noqa: E402


def main(stdin_text: str) -> int:
    try:
        if config.is_enabled():
            summarize.warm(config.load_config())
    except Exception as e:
        log_error(f"hook_session_start: {e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
