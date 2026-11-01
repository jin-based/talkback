"""No model: the reply's first sentence."""
from __future__ import annotations

from talkback.clean import first_sentence
from talkback.config import SummarySettings


def summarize(text: str, s: SummarySettings, key: str | None) -> str:
    return first_sentence(text)
