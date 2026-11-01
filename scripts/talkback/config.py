"""Settings, on/off state, and API keys."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from talkback.log import log_error

SUMMARY_PROVIDERS = ("ollama", "openai", "anthropic", "none")
VOICE_PROVIDERS = ("say", "kokoro", "elevenlabs")
KEY_SERVICES = ("elevenlabs", "anthropic", "openai")
ENV_VARS = {"elevenlabs": "ELEVENLABS_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

SUMMARY_MODEL_DEFAULTS = {"ollama": "llama3.2:3b", "openai": "gpt-4o-mini", "anthropic": "claude-haiku-5-5", "none": ""}
SUMMARY_URL_DEFAULTS = {"ollama": "http://localhost:11434", "openai": "https://api.openai.com/v1"}
VOICE_DEFAULTS = {"say": "", "kokoro": "af_heart", "elevenlabs": "21m00Tcm4TlvDq8ikWAM"}
ELEVEN_MODEL_DEFAULT = "eleven_flash_v2_5"


@dataclass(frozen=True)
class SummarySettings:
    provider: str
    model: str
    url: str


@dataclass(frozen=True)
class VoiceSettings:
    provider: str
    voice: str
    model: str


@dataclass(frozen=True)
class Config:
    summary: SummarySettings
    voice: VoiceSettings


def home() -> Path:
    p = Path(os.environ.get("TALKBACK_HOME") or Path.home() / ".claude" / "talkback")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _str(section: dict, key: str) -> str:
    v = section.get(key)
    return "" if v is None else str(v).strip()


def _summary(raw, problems: list[str]) -> SummarySettings:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        problems.append(f"summary: expected an object, got {type(raw).__name__}; using defaults")
        raw = {}
    provider = _str(raw, "provider") or "ollama"
    if provider not in SUMMARY_PROVIDERS:
        problems.append(f"summary: unknown provider {provider!r} (choose {', '.join(SUMMARY_PROVIDERS)}); using defaults")
        provider, raw = "ollama", {}
    return SummarySettings(provider,
                           _str(raw, "model") or SUMMARY_MODEL_DEFAULTS[provider],
                           (_str(raw, "url") or SUMMARY_URL_DEFAULTS.get(provider, "")).rstrip("/"))


def _voice(raw, problems: list[str]) -> VoiceSettings:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        problems.append(f"voice: expected an object, got {type(raw).__name__}; using defaults")
        raw = {}
    provider = _str(raw, "provider") or "say"
    if provider not in VOICE_PROVIDERS:
        problems.append(f"voice: unknown provider {provider!r} (choose {', '.join(VOICE_PROVIDERS)}); using defaults")
        provider, raw = "say", {}
    return VoiceSettings(provider,
                         _str(raw, "voice") or VOICE_DEFAULTS[provider],
                         _str(raw, "model") or ELEVEN_MODEL_DEFAULT)


def validate(raw) -> tuple[Config, list[str]]:
    problems: list[str] = []
    if not isinstance(raw, dict):
        problems.append("config: expected a JSON object; using defaults")
        raw = {}
    cfg = Config(_summary(raw.get("summary"), problems), _voice(raw.get("voice"), problems))
    for p in problems:
        log_error(p)
    return cfg, problems


def read_raw() -> dict:
    path = home() / "config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log_error(f"config: could not read {path}: {e!r}; using defaults")
        return {}


def load_config() -> Config:
    return validate(read_raw())[0]


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


def get_key(service: str, run=subprocess.run, env: bool = True) -> str | None:
    if service not in KEY_SERVICES:
        return None
    key = os.environ.get(ENV_VARS[service], "").strip() if env else ""
    if key:
        return key
    try:
        r = run(["security", "find-generic-password", "-s", f"talkback-{service}", "-a", "talkback", "-w"],
                capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception as e:
        log_error(f"keychain: {e!r}")
    return None
