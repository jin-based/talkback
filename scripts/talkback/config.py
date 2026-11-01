"""Settings, on/off state, and the ElevenLabs key."""
from __future__ import annotations
import json
import os
import subprocess
from dataclasses import dataclass, fields, replace
from pathlib import Path

from talkback.log import log_error

KEYCHAIN_SERVICE = "talkback-elevenlabs"


@dataclass(frozen=True)
class Config:
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    eleven_model: str = "eleven_flash_v2_5"


def home() -> Path:
    p = Path(os.environ.get("TALKBACK_HOME") or Path.home() / ".claude" / "talkback")
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_config() -> Config:
    path = home() / "config.json"
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(Config)}
        return replace(Config(), **{k: str(v) for k, v in data.items() if k in known})
    except Exception as e:
        log_error(f"config: could not read {path}: {e!r}; using defaults")
        return Config()


def is_enabled() -> bool:
    try:
        return bool(json.loads((home() / "state.json").read_text()).get("enabled", True))
    except FileNotFoundError:
        return True
    except Exception as e:
        log_error(f"state: unreadable state.json: {e!r}; treating as on")
        return True


def set_enabled(on: bool) -> None:
    (home() / "state.json").write_text(json.dumps({"enabled": bool(on)}))


def get_api_key(run=subprocess.run) -> str | None:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if key:
        return key
    try:
        r = run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception as e:
        log_error(f"keychain: {e!r}")
    return None
