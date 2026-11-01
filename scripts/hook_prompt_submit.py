"""UserPromptSubmit hook: stop talking when the user sends a new message."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import playback  # noqa: E402
from talkback.log import log_error  # noqa: E402


def main(stdin_text: str) -> int:
    try:
        playback.claim()  # any speaker still summarizing is now stale
        playback.stop_current()
    except Exception as e:
        log_error(f"hook_prompt_submit: {e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
