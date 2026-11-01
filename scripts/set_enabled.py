"""Turn talk-back on or off: set_enabled.py on|off"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import config, playback  # noqa: E402


def main(argv: list[str]) -> int:
    arg = (argv[0] if argv else "").strip().lower()
    if arg not in ("on", "off"):
        print("Usage: set_enabled.py on or off")
        return 1
    config.set_enabled(arg == "on")
    if arg == "off":
        playback.claim()
        playback.stop_current()
    print(f"Talk-back is {arg}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
