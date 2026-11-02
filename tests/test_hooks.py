import hook_prompt_submit
import hook_session_start
import hook_stop
import set_enabled
from talkback import config


def _record_speak(monkeypatch):
    said = []
    monkeypatch.setattr(hook_stop.speaker, "speak", lambda reply, hook: said.append(reply))
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


def test_prompt_submit_stops_only_its_session(monkeypatch, capsys):
    stopped = []
    monkeypatch.setattr(hook_prompt_submit.queue, "stop_session", stopped.append)
    assert hook_prompt_submit.main('{"prompt": "hi", "session_id": "S1"}') == 0
    assert hook_prompt_submit.main("{nope") == 0
    assert stopped == ["S1"] and capsys.readouterr().out == ""

def test_session_start_warms_model(monkeypatch):
    warmed = []
    monkeypatch.setattr(hook_session_start.ollama, "warm", warmed.append)
    assert hook_session_start.main("{}") == 0
    assert len(warmed) == 1


def test_session_start_skips_warm_when_off(monkeypatch):
    warmed = []
    monkeypatch.setattr(hook_session_start.ollama, "warm", warmed.append)
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


def test_stop_hook_passes_hook_input(monkeypatch):
    got = []
    monkeypatch.setattr(hook_stop.speaker, "speak", lambda reply, hook: got.append((reply, hook["session_id"])))
    hook_stop.main('{"last_assistant_message": "Done.", "session_id": "S9"}')
    assert got == [("Done.", "S9")]

def test_off_stops_all(monkeypatch):
    stopped = []
    monkeypatch.setattr(set_enabled.queue, "stop_all", lambda: stopped.append(1))
    set_enabled.main(["off"])
    assert stopped == [1]

def test_stop_hook_logs_missing_message(tmp_path):
    hook_stop.main('{"other": 1}')
    assert "no last_assistant_message" in (tmp_path / "log.txt").read_text()


def test_session_start_warms_only_for_ollama(monkeypatch, tmp_path):
    warmed = []
    monkeypatch.setattr(hook_session_start.ollama, "warm", warmed.append)
    (tmp_path / "config.json").write_text('{"summary": {"provider": "anthropic"}}')
    hook_session_start.main("{}")
    assert warmed == []
