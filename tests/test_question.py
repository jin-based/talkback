import pytest

from talkback import question, speaker
from talkback.config import SummarySettings

NONE = SummarySettings("none", "", "")


def test_plain_trailing_question():
    assert question.extract("I fixed the bug. Should I also update the docs?") == ("Should I also update the docs?", [])


def test_numbered_options_after_question():
    reply = "Done with the API.\n\nWhich database should I use?\n1. **Postgres**\n2. SQLite\n"
    assert question.extract(reply) == ("Which database should I use?", ["Postgres", "SQLite"])


def test_bulleted_options_before_choose_question():
    reply = "There are two ways:\n- Keep the cache\n- Drop the cache\n\nWhich do you prefer?"
    assert question.extract(reply) == ("Which do you prefer?", ["Keep the cache", "Drop the cache"])


def test_no_question():
    assert question.extract("All tests pass.") is None
    assert question.extract("") is None


@pytest.mark.parametrize("reply", [
    "Here is the code:\n```py\nx = input('ok?')\n```",
    "I used `is_ready?` in Ruby.",
    "See https://example.com/search?q=talkback",
    "Should I continue? I went ahead and finished it anyway.",
])
def test_question_ignores_code_urls_and_mid_reply(reply):
    assert question.extract(reply) is None


def test_options_capped_at_six():
    reply = "Pick one?\n" + "\n".join(f"- opt{i}" for i in range(9))
    assert question.extract(reply)[1] == [f"opt{i}" for i in range(6)]


def test_spoken_format():
    assert question.spoken("Which one?", ["Postgres", "SQLite"], NONE) == \
        "It asks: Which one? Option one, Postgres. Option two, SQLite."
    assert question.spoken("Continue?", [], NONE) == "It asks: Continue?"


def test_long_question_summarized(monkeypatch):
    seen = {}

    def fake(text, s, system=None):
        seen["system"] = system
        return "Should I refactor the parser?", False

    monkeypatch.setattr(question.summarizers, "run_detailed", fake)
    long_q = "Should I " + "really " * 45 + "refactor the parser?"
    assert question.spoken(long_q, [], NONE) == "It asks: Should I refactor the parser?"
    assert seen["system"] == question.REWRITE_PROMPT


def test_long_question_fallback_cuts_to_40_words(monkeypatch):
    monkeypatch.setattr(question.summarizers, "run_detailed", lambda text, s, system=None: ("x", True))
    out = question.spoken("word " * 60 + "end?", [], NONE)
    assert len(out.replace("It asks: ", "").split()) == 40


def test_speaker_appends_question_part(tmp_path):
    from talkback.config import load_config
    assert speaker.question_part("Done. Want me to push?", load_config()) == " It asks: Want me to push?"
    assert speaker.question_part("Done.", load_config()) == ""


def test_list_before_non_choice_question_is_not_options():
    reply = "Changes:\n- Fixed login\n- Added tests\n\nWant me to push?"
    assert question.extract(reply) == ("Want me to push?", [])
