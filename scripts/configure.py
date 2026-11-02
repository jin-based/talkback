"""Change talkback settings: configure.py section.field=value ...  (empty value = back to default)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import config  # noqa: E402

FIELDS = {"summary": ("provider", "model", "url"), "voice": ("provider", "voice", "model")}
PROVIDERS = {"summary": config.SUMMARY_PROVIDERS, "voice": config.VOICE_PROVIDERS}


PROJECT_FIELDS = ("name", "voice")
ON_OFF = {"on": True, "off": False, "true": True, "false": False}


def _parse(arg: str):
    if "=" not in arg or "." not in arg.split("=", 1)[0]:
        raise ValueError(f"Unknown setting {arg!r}: use section.field=value, e.g. voice.provider=kokoro")
    name, value = arg.split("=", 1)
    section, field = name.split(".", 1)
    value = value.strip()
    if section == "projects":
        folder, _, pfield = field.rpartition(".")
        if not folder or pfield not in PROJECT_FIELDS:
            raise ValueError(f"Unknown setting {name!r}: use projects.<folder>.name or projects.<folder>.voice")
        return ("projects", folder, pfield), value
    if section == "alerts":
        if field not in config.ALERT_TYPES:
            raise ValueError(f"Unknown alert {field!r}: choose {', '.join(config.ALERT_TYPES)}")
        if value and value.lower() not in ON_OFF:
            raise ValueError(f"Unknown value {value!r} for {name}: use on or off")
        return ("alerts", field), (ON_OFF[value.lower()] if value else "")
    if section not in FIELDS:
        raise ValueError(f"Unknown section {section!r}: choose summary, voice, projects or alerts")
    if field not in FIELDS[section]:
        raise ValueError(f"Unknown field {name!r}: {section} has {', '.join(FIELDS[section])}")
    if field == "provider" and value and value not in PROVIDERS[section]:
        raise ValueError(f"Unknown {section} provider {value!r}: choose {', '.join(PROVIDERS[section])}")
    return (section, field), value


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
    for path, value in changes:
        node = raw
        for key in path[:-1]:
            node[key] = node.get(key) if isinstance(node.get(key), dict) else {}
            node = node[key]
        if value == "":
            node.pop(path[-1], None)
        else:
            node[path[-1]] = value
    target = config.home() / "config.json"
    tmp = target.with_name(f"config.json.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(raw, indent=2) + "\n")
    os.replace(tmp, target)  # readers never see a half-written file
    shown = lambda v: ("on" if v else "off") if isinstance(v, bool) else v
    print("Saved: " + ", ".join(".".join(p) + "=" + str(shown(v)) for p, v in changes))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
