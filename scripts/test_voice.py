"""Speak a test sentence with the current settings and report which providers actually ran.

--long allows Kokoro up to 10 minutes (first run downloads its model)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import config, summarizers, voices  # noqa: E402
from talkback.clean import clean  # noqa: E402
from talkback.playback import claim_and_stop, play_file  # noqa: E402

SAMPLE = ("I found the bug: the session timer compared seconds to milliseconds, so every login expired at once. "
          "I fixed the comparison, added a regression test, and the whole test suite passes now.")


def _speak(cfg: config.Config) -> tuple[str, str]:
    summary, fell_back = summarizers.run_detailed(clean(SAMPLE), cfg.summary)
    token = claim_and_stop()
    path, voice_used = voices.render(summary, cfg.voice, token)
    try:
        play_file(path, token)
    finally:
        path.unlink(missing_ok=True)
    s_label = f"first sentence (fallback from {cfg.summary.provider})" if fell_back else cfg.summary.provider
    if cfg.summary.provider == "none":
        s_label = "first sentence (none)"
    v_label = voice_used if voice_used == cfg.voice.provider else f"{voice_used} (fallback from {cfg.voice.provider})"
    print(f"Summary: {summary}")
    return s_label, v_label


def main(argv: list[str]) -> int:
    if "--long" in argv:
        voices.kokoro.TIMEOUT = 600
        voices.kokoro.WAIT_FOR_DOWNLOAD = True
    s_label, v_label = _speak(config.load_config())
    print(f"Summary by: {s_label}")
    print(f"Voice: {v_label}")
    if "fallback" in s_label + v_label:
        print(f"Details are in {config.home() / 'log.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
