"""Claude via the Anthropic Messages API (raw HTTP: the plugin uses no third-party packages)."""
from __future__ import annotations

from talkback.config import SummarySettings
from talkback.summarizers import _http
from talkback.summarizers.prompt import SYSTEM_PROMPT, tail

URL = "https://api.anthropic.com/v1/messages"
TIMEOUT = 8


def summarize(text: str, s: SummarySettings, key: str | None) -> str:
    if not key:
        raise RuntimeError("no key (run /talkback:key anthropic)")
    headers = {"x-api-key": key, "anthropic-version": "2026-10-21"}
    body = {
        "model": s.model, "max_tokens": 300, "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": tail(text)}],
        "thinking": {"type": "disabled"}, "output_config": {"effort": "low"},
    }
    data = _http.post_json(URL, headers, body, TIMEOUT)
    if data.get("stop_reason") == "refusal":
        raise RuntimeError("refused")
    out = " ".join(b.get("text", "") for b in data.get("content") or [] if b.get("type") == "text").strip()
    if not out:
        raise RuntimeError(f"no text in response: {str(data)[:200]}")
    return out
