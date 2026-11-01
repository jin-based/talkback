import pytest

from talkback import summarizers
from talkback.config import SummarySettings
from talkback.summarizers import _http

OLLAMA = SummarySettings("ollama", "llama3.2:3b", "http://localhost:11434")
OPENAI = SummarySettings("openai", "gpt-4o-mini", "https://api.openai.com/v1")
LOCAL_OPENAI = SummarySettings("openai", "qwen", "http://localhost:1234/v1")
HAIKU = SummarySettings("anthropic", "claude-haiku-5-5", "")
NONE = SummarySettings("none", "", "")


@pytest.fixture
def http(monkeypatch):
    rec = {"calls": [], "reply": {}}

    def fake(url, headers, body, timeout):
        rec["calls"].append(dict(url=url, headers=headers, body=body, timeout=timeout))
        if isinstance(rec["reply"], Exception):
            raise rec["reply"]
        return rec["reply"]

    monkeypatch.setattr(_http, "post_json", fake)
    return rec


@pytest.fixture
def keys(monkeypatch):
    k = {"openai": "k", "anthropic": "k"}
    monkeypatch.setattr(summarizers, "get_key", lambda service, env=True: k.get(service))
    return k


def test_none_returns_first_sentence(http):
    assert summarizers.run("I fixed it. More.", NONE) == "I fixed it."
    assert http["calls"] == []


def test_ollama_request_unchanged(http):
    http["reply"] = {"message": {"content": "Fixed the bug."}}
    assert summarizers.run("text", OLLAMA) == "Fixed the bug."
    c = http["calls"][0]
    assert c["url"] == "http://localhost:11434/api/chat" and c["timeout"] == 5
    assert c["body"]["model"] == "llama3.2:3b" and c["body"]["think"] is False
    assert c["body"]["stream"] is False and c["body"]["keep_alive"] == "30m"
    assert c["body"]["messages"][0] == {"role": "system", "content": summarizers.SYSTEM_PROMPT}


def test_openai_request_with_key(http, keys):
    http["reply"] = {"choices": [{"message": {"content": "Done."}}]}
    assert summarizers.run("text", OPENAI) == "Done."
    c = http["calls"][0]
    assert c["url"] == "https://api.openai.com/v1/chat/completions" and c["timeout"] == 8
    assert c["headers"]["Authorization"] == "Bearer k"
    assert c["body"]["max_tokens"] == 100 and c["body"]["model"] == "gpt-4o-mini"


def test_openai_local_no_key_short_timeout(http, keys):
    keys.pop("openai")
    http["reply"] = {"choices": [{"message": {"content": "Done."}}]}
    summarizers.run("text", LOCAL_OPENAI)
    c = http["calls"][0]
    assert "Authorization" not in c["headers"] and c["timeout"] == 5
    assert c["url"] == "http://localhost:1234/v1/chat/completions"


def test_openai_missing_choices_falls_back(http, keys):
    http["reply"] = {"error": "x"}
    assert summarizers.run("I fixed it. More.", OPENAI) == "I fixed it."


def test_anthropic_request_shape(http, keys):
    http["reply"] = {"content": [{"type": "text", "text": "Fixed it."}], "stop_reason": "end_turn"}
    summarizers.run("text", HAIKU)
    c = http["calls"][0]
    assert c["url"] == "https://api.anthropic.com/v1/messages" and c["timeout"] == 8
    assert c["headers"]["x-api-key"] == "k" and c["headers"]["anthropic-version"] == "2026-10-21"
    b = c["body"]
    assert b["model"] == "claude-haiku-5-5" and b["max_tokens"] == 300
    assert b["thinking"] == {"type": "disabled"} and b["output_config"] == {"effort": "low"}
    assert b["system"] == summarizers.SYSTEM_PROMPT
    assert not {"temperature", "top_p", "top_k"} & set(b)


def test_anthropic_joins_text_blocks(http, keys):
    http["reply"] = {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "Fixed it."}]}
    assert summarizers.run("x", HAIKU) == "Fixed it."


def test_anthropic_refusal_or_no_text_falls_back(http, keys):
    http["reply"] = {"content": [], "stop_reason": "refusal"}
    assert summarizers.run("I fixed it. More.", HAIKU) == "I fixed it."
    http["reply"] = {"content": [{"type": "text", "text": "Partial"}], "stop_reason": "refusal"}
    assert summarizers.run("I fixed it. More.", HAIKU) == "I fixed it."


def test_anthropic_without_key_falls_back(http, keys, tmp_path):
    keys.pop("anthropic")
    assert summarizers.run("I fixed it. More.", HAIKU) == "I fixed it."
    assert http["calls"] == [] and "no key" in (tmp_path / "log.txt").read_text()


def test_error_falls_back_and_logs(http, tmp_path):
    http["reply"] = OSError("down")
    assert summarizers.run("I fixed it. More.", OLLAMA) == "I fixed it."
    assert "ollama" in (tmp_path / "log.txt").read_text()


def test_run_cleans_and_caps_output(http):
    http["reply"] = {"message": {"content": "**Done** `x` " + "word " * 60}}
    res = summarizers.run("text", OLLAMA)
    assert "*" not in res and "`" not in res and len(res.split()) <= 30


@pytest.mark.parametrize("s,reply", [
    (OLLAMA, {"message": {"content": "ok."}}),
    (OPENAI, {"choices": [{"message": {"content": "ok."}}]}),
    (HAIKU, {"content": [{"type": "text", "text": "ok."}]}),
])
def test_sends_only_last_4000_chars(http, keys, s, reply):
    http["reply"] = reply
    summarizers.run("a" * 3000 + "b" * 4000, s)
    assert http["calls"][0]["body"]["messages"][-1] == {"role": "user", "content": "b" * 4000}


def test_warm(http):
    summarizers.ollama.warm(OLLAMA)
    c = http["calls"][0]
    assert c["url"] == "http://localhost:11434/api/generate" and c["timeout"] == 60
    assert c["body"] == {"model": "llama3.2:3b", "keep_alive": "30m"}
    http["reply"] = OSError("down")
    summarizers.ollama.warm(OLLAMA)  # no exception


def test_env_openai_key_not_sent_to_other_hosts(http, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "real-openai-key")
    monkeypatch.setattr(summarizers, "get_key", lambda service, env=True: "real-openai-key" if env else "router-key")
    http["reply"] = {"choices": [{"message": {"content": "Done."}}]}
    summarizers.run("text", SummarySettings("openai", "m", "https://openrouter.ai/api/v1"))
    assert http["calls"][0]["headers"]["Authorization"] == "Bearer router-key"
    summarizers.run("text", OPENAI)
    assert http["calls"][1]["headers"]["Authorization"] == "Bearer real-openai-key"


def test_non_haiku_claude_model_omits_thinking(http, keys):
    http["reply"] = {"content": [{"type": "text", "text": "ok."}]}
    summarizers.run("text", SummarySettings("anthropic", "claude-sonnet-5-5", ""))
    b = http["calls"][0]["body"]
    assert "thinking" not in b and b["output_config"] == {"effort": "low"}
