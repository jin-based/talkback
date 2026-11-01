"""Print talkback's current settings and what's available on this Mac. Never prints key values."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from talkback import config  # noqa: E402
from talkback.voices import kokoro  # noqa: E402


def _ollama_models(url: str) -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=2) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return None


def _keychain_has(service: str) -> bool:
    r = subprocess.run(["security", "find-generic-password", "-s", f"talkback-{service}", "-a", "talkback"],
                       capture_output=True)
    return r.returncode == 0


def main() -> int:
    cfg, problems = config.validate(config.read_raw())
    s, v = cfg.summary, cfg.voice
    ollama_url = s.url if s.provider == "ollama" else config.SUMMARY_URL_DEFAULTS["ollama"]
    models = _ollama_models(ollama_url)
    if s.provider == "ollama" and models is not None:
        names = set(models) | {m[: -len(":latest")] for m in models if m.endswith(":latest")}
        if s.model not in names:
            problems = problems + [f"summary: Ollama model {s.model} is not installed "
                                   f"(run: ollama pull {s.model}); summaries will use the first sentence"]
    print("Settings")
    print(f"  summary: provider={s.provider} model={s.model or '-'} url={s.url or '-'}")
    print(f"  voice:   provider={v.provider} voice={v.voice or '(system default)'}"
          + (f" model={v.model}" if v.provider == "elevenlabs" else ""))
    print(f"  talk-back is {'on' if config.is_enabled() else 'off'}")
    print("Problems")
    for p in problems or ["none"]:
        print(f"  {p}")
    print("Ollama")
    print(f"  {ollama_url}: " + ("not reachable" if models is None else ", ".join(models) or "running, no models"))
    print("uv")
    print(f"  {'installed' if shutil.which('uv') else 'not installed (needed only for Kokoro: brew install uv)'}")
    print("Kokoro model")
    print(f"  {'downloaded' if kokoro.models_present() else 'not downloaded yet (downloads on first use, ~140 MB)'}")
    print("Keys")
    for service in config.KEY_SERVICES:
        has = bool(os.environ.get(config.ENV_VARS[service], "").strip()) or _keychain_has(service)
        print(f"  {service}: {'set' if has else 'not set'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
