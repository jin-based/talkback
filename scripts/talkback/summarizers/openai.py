"""Any OpenAI-compatible chat completions server (OpenAI, LM Studio, llama.cpp, OpenRouter...)."""
from __future__ import annotations

from urllib.parse import urlparse

from talkback.config import SummarySettings
from talkback.summarizers import _http
from talkback.summarizers.prompt import SYSTEM_PROMPT, messages

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def summarize(text: str, s: SummarySettings, key: str | None, system: str = SYSTEM_PROMPT) -> str:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    timeout = 5 if urlparse(s.url).hostname in LOCAL_HOSTS else 8
    body = {"model": s.model, "max_tokens": 100, "messages": messages(text, system)}
    data = _http.post_json(f"{s.url}/chat/completions", headers, body, timeout)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"unexpected response: {str(data)[:200]}")
