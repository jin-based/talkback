"""One-sentence summary from a local Ollama model, with a no-model fallback."""
import json
import urllib.request

from talkback.clean import clean, first_sentence
from talkback.config import Config
from talkback.log import log_error

SYSTEM_PROMPT = ("Summarize what the assistant just did in one short spoken sentence, "
                 "under 20 words. Plain words only: no code, no file paths, no markdown.")
TIMEOUT = 5
MAX_CHARS = 4000


def post_json(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def summarize(text: str, cfg: Config) -> str:
    """`text` is already cleaned and non-empty."""
    body = {
        "model": cfg.ollama_model, "stream": False, "think": False, "keep_alive": "30m",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": text[-MAX_CHARS:]}],
    }
    try:
        out = post_json(f"{cfg.ollama_url}/api/chat", body, TIMEOUT)["message"]["content"]
        out = first_sentence(clean(out), max_words=30)
        if out:
            return out
    except Exception as e:
        log_error(f"summarize: Ollama failed: {e!r}; using first sentence")
    return first_sentence(text)


def warm(cfg: Config) -> None:
    try:
        post_json(f"{cfg.ollama_url}/api/generate", {"model": cfg.ollama_model, "keep_alive": "30m"}, 60)
    except Exception as e:
        log_error(f"warm: {e!r}")
