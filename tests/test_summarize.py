from talkback import summarize


def _boom(*a, **k):
    raise OSError("down")


def test_uses_model_reply(monkeypatch, cfg):
    seen = {}

    def fake(url, body, timeout):
        seen.update(url=url, body=body, timeout=timeout)
        return {"message": {"content": "Fixed the login bug."}}

    monkeypatch.setattr(summarize, "post_json", fake)
    assert summarize.summarize("long text", cfg) == "Fixed the login bug."
    assert seen["url"] == "http://localhost:11434/api/chat" and seen["timeout"] == 5
    body = seen["body"]
    assert body["model"] == "llama3.2:3b"
    assert body["think"] is False and body["stream"] is False and body["keep_alive"] == "30m"
    assert body["messages"][0] == {"role": "system", "content": summarize.SYSTEM_PROMPT}
    assert summarize.SYSTEM_PROMPT == ("Summarize what the assistant just did in one short spoken sentence, "
                                       "under 20 words. Plain words only: no code, no file paths, no markdown.")


def test_sends_only_last_4000_chars(monkeypatch, cfg):
    seen = {}
    monkeypatch.setattr(summarize, "post_json",
                        lambda url, body, timeout: seen.update(body=body) or {"message": {"content": "ok."}})
    text = "a" * 3000 + "b" * 4000
    summarize.summarize(text, cfg)
    assert seen["body"]["messages"][1] == {"role": "user", "content": "b" * 4000}


def test_falls_back_on_error(monkeypatch, cfg, tmp_path):
    monkeypatch.setattr(summarize, "post_json", _boom)
    assert summarize.summarize("I fixed it. More.", cfg) == "I fixed it."
    assert "summarize" in (tmp_path / "log.txt").read_text()


def test_falls_back_on_empty_model_output(monkeypatch, cfg):
    monkeypatch.setattr(summarize, "post_json", lambda *a: {"message": {"content": "  "}})
    assert summarize.summarize("I fixed it. More.", cfg) == "I fixed it."


def test_strips_markdown_and_caps_model_output(monkeypatch, cfg):
    out = "**Done** with `x` " + "word " * 60
    monkeypatch.setattr(summarize, "post_json", lambda *a: {"message": {"content": out}})
    res = summarize.summarize("text", cfg)
    assert "*" not in res and "`" not in res and len(res.split()) <= 30


def test_warm_posts_keep_alive_and_swallows_errors(monkeypatch, cfg):
    seen = {}
    monkeypatch.setattr(summarize, "post_json",
                        lambda url, body, timeout: seen.update(url=url, body=body, timeout=timeout) or {})
    summarize.warm(cfg)
    assert seen == {"url": "http://localhost:11434/api/generate",
                    "body": {"model": "llama3.2:3b", "keep_alive": "30m"}, "timeout": 60}
    monkeypatch.setattr(summarize, "post_json", _boom)
    summarize.warm(cfg)  # no exception
