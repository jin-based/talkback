"""Shared prompt for every summarizer."""
from __future__ import annotations

SYSTEM_PROMPT = ("Summarize what the assistant just did in one short spoken sentence, "
                 "under 20 words. Plain words only: no code, no file paths, no markdown.")
MAX_CHARS = 4000


def tail(text: str) -> str:
    return text[-MAX_CHARS:]


def messages(text: str, system: str = SYSTEM_PROMPT) -> list[dict]:
    return [{"role": "system", "content": system}, {"role": "user", "content": tail(text)}]
