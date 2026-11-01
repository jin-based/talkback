"""SessionStart hook (async): load the summary model so the first reply is fast."""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import config  # noqa: E402
from talkback.summarizers import ollama  # noqa: E402
from talkback.log import log_error  # noqa: E402


def main(stdin_text: str) -> int:
    try:
        cfg = config.load_config()
        if config.is_enabled() and cfg.summary.provider == "ollama":
            ollama.warm(cfg.summary)
    except Exception as e:
        log_error(f"hook_session_start: {e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
