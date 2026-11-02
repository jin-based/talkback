"""Find a question at the end of Claude's reply, and say it word for word."""
from __future__ import annotations

import re

from talkback import summarizers
from talkback.clean import clean
from talkback.config import SummarySettings

NUMBER_WORDS = ("one", "two", "three", "four", "five", "six")
MAX_OPTIONS = 6
MAX_WORDS = 40
REWRITE_PROMPT = "Rewrite this question in under 25 plain words:"

_FENCED = re.compile(r"```.*?(```|\Z)", re.S)
_INLINE = re.compile(r"`[^`\n]*`")
_URL = re.compile(r"https?://\S+")
_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*•+]|[a-fA-F][.)])\s+(.+?)\s*$")
_CHOICE = re.compile(r"\b(which|choose|pick|prefer|option|options|or)\b", re.I)


def _strip_blank_tail(lines: list[str]) -> None:
    while lines and not lines[-1].strip():
        lines.pop()


def _take_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    while lines and _ITEM.match(lines[-1]):
        items.insert(0, _ITEM.match(lines.pop()).group(1))
    return items


def extract(reply: str) -> tuple[str, list[str]] | None:
    text = _URL.sub(" ", _INLINE.sub(" ", _FENCED.sub("", reply or "")))
    lines = [line.rstrip() for line in text.splitlines()]
    _strip_blank_tail(lines)
    after = _take_items(lines)
    _strip_blank_tail(lines)
    if not lines:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", clean(lines[-1]))
    q = sentences[-1].strip() if sentences else ""
    if not q.endswith("?"):
        return None
    options = after
    if not options and _CHOICE.search(q):
        before = lines[:-1]
        _strip_blank_tail(before)
        options = _take_items(before)
    options = [o for o in (clean(x) for x in options) if o][:MAX_OPTIONS]
    return q, options


def spoken(question: str, options: list[str], s: SummarySettings) -> str:
    words = question.split()
    if len(words) > MAX_WORDS:
        rewritten, fell_back = summarizers.run_detailed(question, s, system=REWRITE_PROMPT)
        question = " ".join(words[:MAX_WORDS]) if fell_back else rewritten
    out = f"It asks: {question}"
    for word, opt in zip(NUMBER_WORDS, options):
        out += f" Option {word}, {opt.rstrip('.')}."
    return out
