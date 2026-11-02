"""List, preview and pick voices by name for the current voice provider.

  voices.py list
  voices.py preview <name>
  voices.py use <name> [--project <folder>]
"""
from __future__ import annotations

import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import configure  # noqa: E402
from talkback import queue, sessions, voices  # noqa: E402
from talkback.config import get_key, load_config  # noqa: E402
from talkback.voices.catalog import find, list_voices  # noqa: E402

PREVIEW_SESSION = "talkback-preview"


def _voices(cfg):
    key = get_key("elevenlabs") if cfg.voice.provider == "elevenlabs" else None
    return list_voices(cfg.voice.provider, key)


def _resolve(cfg, name: str):
    matches = find(_voices(cfg), name)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        print(f"No {cfg.voice.provider} voice matches {name!r}. Run /talkback:voices to see the list.")
    else:
        print(f"{name!r} matches several voices; which one?")
        for v in matches:
            print(f"  - {v.name} ({v.id})")
    return None


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("list", "preview", "use"):
        print(__doc__.strip())
        return 1
    cfg = load_config()
    action, args = argv[0], argv[1:]
    project = None
    if "--project" in args:
        i = args.index("--project")
        project = " ".join(args[i + 1:]).strip() or None
        args = args[:i]
    name = " ".join(args).strip()
    try:
        if action == "list":
            vs = _voices(cfg)
            print(f"Voices for {cfg.voice.provider}:")
            for n, v in enumerate(vs, 1):
                current = " (current)" if v.id == cfg.voice.voice else ""
                desc = f" — {v.description}" if v.description else ""
                print(f"{n}. {v.name}{desc} ({v.id}){current}")
            return 0
        if not name:
            print(f"Which voice? Example: voices.py {action} Bella")
            return 1
        v = _resolve(cfg, name)
        if v is None:
            return 1
        if action == "preview":
            token = sessions.claim(PREVIEW_SESSION)
            path, who = voices.render(f"Hi, this is {v.name}.", replace(cfg.voice, voice=v.id), token)
            queue.enqueue(PREVIEW_SESSION, token, path, "alert", front=True)
            queue.run_player()
            print(f"Played a sample of {v.name}." if who == cfg.voice.provider
                  else f"{cfg.voice.provider} failed, so the Mac voice played instead (see the log).")
            return 0
        field = f"projects.{project}.voice" if project else "voice.voice"
        if configure.main([f"{field}={v.id}"]) != 0:
            return 1
        print(f"Now using {v.name}" + (f" for {project}." if project else "."))
        return 0
    except Exception as e:
        print(f"Couldn't get the voice list: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
