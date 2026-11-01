"""Store or remove an API key in the macOS Keychain via a hidden-input dialog.

The key is only ever passed to `security` on stdin: never in argv, output, logs or files.
Usage: set_key.py elevenlabs|anthropic|openai [remove]
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback.config import ENV_VARS, KEY_SERVICES  # noqa: E402

_run = subprocess.run
USAGE = "Usage: /talkback:key elevenlabs|anthropic|openai [remove]"
NAMES = {"elevenlabs": "ElevenLabs", "anthropic": "Anthropic", "openai": "OpenAI"}


class DialogError(Exception):
    pass


def _ask(service: str) -> str | None:
    script = (f'text returned of (display dialog "Paste your {NAMES[service]} API key" '
              f'with title "talkback" default answer "" with hidden answer)')
    r = _run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or "").strip()
        if "-128" in err:  # the user pressed Cancel
            return None
        raise DialogError(err[-200:] or f"osascript exit {r.returncode}")
    return r.stdout.strip() or None


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in KEY_SERVICES or argv[1:] not in ([], ["remove"]):
        print(USAGE)
        return 1
    service = argv[0]
    if argv[1:] == ["remove"]:
        r = _run(["security", "delete-generic-password", "-s", f"talkback-{service}", "-a", "talkback"],
                 capture_output=True)
        print(f"Removed your {service} key." if r.returncode == 0 else f"No {service} key was stored.")
        return 0
    try:
        key = _ask(service)
    except DialogError as e:
        print(f"Could not open the key pop-up ({e}). "
              f"Instead, you can set {ENV_VARS[service]} in your shell environment.")
        return 1
    if not key:
        print("Cancelled, nothing saved.")
        return 0
    if any(ch in key for ch in '"\\\n\r'):
        print("Key has unexpected characters; nothing saved.")
        return 0
    r = _run(["security", "-i"], input=f'add-generic-password -U -s talkback-{service} -a talkback -w "{key}"\n',
             capture_output=True, text=True)
    if r.returncode != 0:
        print("Could not save the key in the Keychain.")
        return 1
    print(f"Saved your {service} key in the macOS Keychain.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
