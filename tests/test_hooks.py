import hook_prompt_submit
import hook_session_start
import hook_stop
import set_enabled
from talkback import config


def _record_speak(monkeypatch):
    said = []
    monkeypatch.setattr(hook_stop.speaker, "speak", said.append)
    return said


def test_stop_hook_speaks_reply(monkeypatch):
    said = _record_speak(monkeypatch)
    assert hook_stop.main('{"last_assistant_message": "Done.", "stop_hook_active": false}') == 0
    assert said == ["Done."]


def test_stop_hook_respects_off(monkeypatch):
    said = _record_speak(monkeypatch)
    config.set_enabled(False)
    assert hook_stop.main('{"last_assistant_message": "Done."}') == 0
    assert said == []


def test_stop_hook_skips_when_stop_hook_active(monkeypatch):
    said = _record_speak(monkeypatch)
    assert hook_stop.main('{"last_assistant_message": "Done.", "stop_hook_active": true}') == 0
    assert said == []


def test_stop_hook_bad_input_exits_quietly(monkeypatch, capsys):
    said = _record_speak(monkeypatch)
    for bad in ["", "{nope", '{"other": 1}', "[1, 2]", '{"last_assistant_message": null}']:
        assert hook_stop.main(bad) == 0
    assert said == [] and capsys.readouterr().out == ""


def test_prompt_submit_stops_playback(monkeypatch, capsys):
    stopped = []
    monkeypatch.setattr(hook_prompt_submit.playback, "stop_current", lambda: stopped.append(1))
    assert hook_prompt_submit.main('{"prompt": "hi"}') == 0
    assert stopped == [1] and capsys.readouterr().out == ""


def test_session_start_warms_model(monkeypatch):
    warmed = []
    monkeypatch.setattr(hook_session_start.summarize, "warm", warmed.append)
    assert hook_session_start.main("{}") == 0
    assert len(warmed) == 1


def test_session_start_skips_warm_when_off(monkeypatch):
    warmed = []
    monkeypatch.setattr(hook_session_start.summarize, "warm", warmed.append)
    config.set_enabled(False)
    assert hook_session_start.main("{}") == 0
    assert warmed == []


def test_set_enabled_off_then_on(capsys):
    assert set_enabled.main(["off"]) == 0
    assert config.is_enabled() is False and capsys.readouterr().out.strip() == "Talk-back is off."
    assert set_enabled.main(["on"]) == 0
    assert config.is_enabled() is True and capsys.readouterr().out.strip() == "Talk-back is on."


def test_set_enabled_bad_arg(capsys):
    assert set_enabled.main(["maybe"]) == 1
    assert "on or off" in capsys.readouterr().out


def test_prompt_submit_makes_in_flight_speaker_stale(monkeypatch):
    monkeypatch.setattr(hook_prompt_submit.playback, "stop_current", lambda: None)
    from talkback import playback
    token = playback.claim()  # a speaker still summarizing
    hook_prompt_submit.main("{}")
    assert not playback.is_current(token)


def test_set_enabled_off_stops_talking(monkeypatch):
    stopped = []
    monkeypatch.setattr(set_enabled.playback, "stop_current", lambda: stopped.append(1))
    set_enabled.main(["off"])
    assert stopped == [1]
