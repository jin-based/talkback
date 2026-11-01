"""Turn a Claude reply into plain text that sounds OK spoken aloud."""
import re

_FENCED = re.compile(r"```.*?(```|\Z)", re.S)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TABLE_ROW = re.compile(r"^\s*\|.*$", re.M)
_URL = re.compile(r"https?://\S+")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_EXT = r"(?:py|ts|tsx|js|jsx|json|md|sh|txt|yml|yaml|toml|css|html|go|rs|java|rb|swift|kt|c|h|cpp|lock|cfg|ini)"
_PATH = re.compile(
    r"(?<![\w/])(?:~|\.{1,2})?/[\w.-]+(?:/[\w.-]*)*"      # rooted: /usr/bin, ~/notes, ./x
    r"|(?<![\w/])[\w.-]+(?:/[\w.-]+){2,}/?"                 # 2+ slashes: src/auth/lib
    r"|(?<![\w/])(?:[\w.-]+/)*[\w-]+\." + _EXT + r"\b"     # ends in a file extension
)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+", re.M)
_EMPHASIS = re.compile(r"[*_]{1,3}")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?])")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s")


def clean(text: str) -> str:
    t = _FENCED.sub(" ", text or "")
    t = _HTML_COMMENT.sub(" ", t)
    t = _TABLE_ROW.sub(" ", t)
    t = _URL.sub(" ", t)
    t = _INLINE_CODE.sub(" ", t)
    t = _PATH.sub(" ", t)
    t = _HEADING.sub("", t)
    t = _BULLET.sub("", t)
    t = _EMPHASIS.sub("", t)
    t = " ".join(t.split())
    t = _SPACE_BEFORE_PUNCT.sub(r"\1", t)
    t = re.sub(r"([.,;:!?])(?:\s*[.,;:])+", r"\1", t)  # "in , see ." leftovers
    return t.strip(" ,;:")


def first_sentence(text: str, max_words: int = 30) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    first = _SENTENCE_END.split(text, maxsplit=1)[0]
    return " ".join(first.split()[:max_words])
