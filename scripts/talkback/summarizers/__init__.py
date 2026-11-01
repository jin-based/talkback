"""Pick the configured summarizer; fall back to the first sentence on any failure."""
from __future__ import annotations

from urllib.parse import urlparse

from talkback.clean import clean, first_sentence
from talkback.config import SummarySettings, get_key
from talkback.log import log_error
from talkback.summarizers import anthropic, none, ollama, openai
from talkback.summarizers.prompt import MAX_CHARS, SYSTEM_PROMPT  # noqa: F401  (re-exported)

PROVIDERS = {"none": none, "ollama": ollama, "openai": openai, "anthropic": anthropic}
KEYED = {"openai", "anthropic"}


def _key_for(s: SummarySettings) -> str | None:
    if s.provider == "openai":
        # An exported OPENAI_API_KEY is only for OpenAI itself; other servers use the Keychain key.
        return get_key("openai", env=urlparse(s.url).hostname == "api.openai.com")
    return get_key(s.provider) if s.provider in KEYED else None


def run(text: str, s: SummarySettings) -> str:
    """`text` is already cleaned and non-empty."""
    return run_detailed(text, s)[0]


def run_detailed(text: str, s: SummarySettings) -> tuple[str, bool]:
    """Returns (summary, used_fallback)."""
    try:
        key = _key_for(s)
        out = first_sentence(clean(PROVIDERS[s.provider].summarize(text, s, key)), max_words=30)
        if out:
            return out, False
        raise RuntimeError("empty summary")
    except Exception as e:
        log_error(f"summarize: {s.provider} failed: {e!r}; using first sentence")
        return first_sentence(text), True
