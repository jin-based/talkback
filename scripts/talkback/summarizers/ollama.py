"""Local Ollama model."""
from __future__ import annotations

from talkback.config import SummarySettings
from talkback.log import log_error
from talkback.summarizers import _http
from talkback.summarizers.prompt import messages

TIMEOUT = 5


def summarize(text: str, s: SummarySettings, key: str | None) -> str:
    body = {"model": s.model, "stream": False, "think": False, "keep_alive": "30m", "messages": messages(text)}
    return _http.post_json(f"{s.url}/api/chat", {}, body, TIMEOUT)["message"]["content"]


def warm(s: SummarySettings) -> None:
    try:
        _http.post_json(f"{s.url}/api/generate", {}, {"model": s.model, "keep_alive": "30m"}, 60)
    except Exception as e:
        log_error(f"warm: {e!r}")
