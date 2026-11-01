from talkback.clean import clean, first_sentence


def test_removes_fenced_code():
    assert clean("Fixed it.\n```ts\nx = 1\n```\nDone.") == "Fixed it. Done."


def test_removes_inline_code_paths_urls():
    out = clean("Edited `login.ts` in src/auth/login.ts, see https://x.dev/a.")
    assert "login.ts" not in out and "https" not in out and "src/" not in out


def test_removes_tables_and_markdown():
    out = clean("## Result\n| a | b |\n|---|---|\n| 1 | 2 |\n- **All** tests pass")
    assert out == "Result All tests pass"


def test_code_only_becomes_empty():
    assert clean("```py\nprint(1)\n```") == ""


def test_removes_html_comments():
    assert clean("Done. <!-- say: hidden -->") == "Done."


def test_first_sentence():
    assert first_sentence("I fixed the bug. Then I ran tests.") == "I fixed the bug."


def test_first_sentence_caps_words():
    assert len(first_sentence("word " * 50).split()) == 30


def test_first_sentence_empty():
    assert first_sentence("") == ""


def test_keeps_ordinary_slash_words():
    assert clean("Use and/or here, or the client/server split.") == "Use and/or here, or the client/server split."


def test_removes_multi_segment_and_rooted_paths():
    out = clean("Look in src/auth/lib and ~/notes and /usr/bin and docs/plan.md today.")
    assert out == "Look in and and and today."
