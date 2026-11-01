"""Change talkback settings: configure.py section.field=value ...  (empty value = back to default)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import config  # noqa: E402

FIELDS = {"summary": ("provider", "model", "url"), "voice": ("provider", "voice", "model")}
PROVIDERS = {"summary": config.SUMMARY_PROVIDERS, "voice": config.VOICE_PROVIDERS}


def _parse(arg: str) -> tuple[str, str, str]:
    if "=" not in arg or "." not in arg.split("=", 1)[0]:
        raise ValueError(f"Unknown setting {arg!r}: use section.field=value, e.g. voice.provider=kokoro")
    name, value = arg.split("=", 1)
    section, field = name.split(".", 1)
    if section not in FIELDS:
        raise ValueError(f"Unknown section {section!r}: choose summary or voice")
    if field not in FIELDS[section]:
        raise ValueError(f"Unknown field {name!r}: {section} has {', '.join(FIELDS[section])}")
    value = value.strip()
    if field == "provider" and value and value not in PROVIDERS[section]:
        raise ValueError(f"Unknown {section} provider {value!r}: choose {', '.join(PROVIDERS[section])}")
    return section, field, value


def main(argv: list[str]) -> int:
    try:
        changes = [_parse(a) for a in argv]
    except ValueError as e:
        print(e)
        return 1
    if not changes:
        print("Nothing to change. Example: configure.py voice.provider=kokoro")
        return 1
    raw = config.read_raw()
    if not isinstance(raw, dict):
        raw = {}
    for section, field, value in changes:
        sec = raw.get(section) if isinstance(raw.get(section), dict) else {}
        if value:
            sec[field] = value
        else:
            sec.pop(field, None)
        raw[section] = sec
    (config.home() / "config.json").write_text(json.dumps(raw, indent=2) + "\n")
    print("Saved: " + ", ".join(f"{s}.{f}={v}" for s, f, v in changes))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
