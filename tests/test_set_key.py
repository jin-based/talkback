import subprocess

import pytest

import set_key

KEY = "sk-123secret"


@pytest.fixture
def runs(monkeypatch):
    rec = {"calls": [], "dialog_rc": 0, "dialog_out": KEY + "\n", "security_rc": 0, "delete_rc": 0}

    def fake(args, **k):
        rec["calls"].append({"args": args, "input": k.get("input")})
        if args[0] == "osascript":
            err = "execution error: User canceled. (-128)" if rec["dialog_rc"] else ""
            return subprocess.CompletedProcess(args, rec["dialog_rc"], stdout=rec["dialog_out"], stderr=err)
        if args[:2] == ["security", "-i"]:
            return subprocess.CompletedProcess(args, rec["security_rc"], stdout="", stderr="")
        if args[:2] == ["security", "delete-generic-password"]:
            return subprocess.CompletedProcess(args, rec["delete_rc"], stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(set_key, "_run", fake)
    return rec


def test_saves_key_via_stdin(runs, capsys):
    assert set_key.main(["elevenlabs"]) == 0
    sec = [c for c in runs["calls"] if c["args"][0] == "security"][0]
    assert sec["args"] == ["security", "-i"]
    assert sec["input"] == f'add-generic-password -U -s talkback-elevenlabs -a talkback -w "{KEY}"\n'
    assert capsys.readouterr().out.strip() == "Saved your elevenlabs key in the macOS Keychain."


def test_key_never_in_argv_or_output(runs, capsys, tmp_path):
    set_key.main(["openai"])
    runs["security_rc"] = 1
    set_key.main(["openai"])
    for c in runs["calls"]:
        assert all(KEY not in a for a in c["args"])
    out = capsys.readouterr()
    assert KEY not in out.out and KEY not in out.err
    log = tmp_path / "log.txt"
    assert not log.exists() or KEY not in log.read_text()


def test_cancel_saves_nothing(runs, capsys):
    runs["dialog_rc"] = 1
    assert set_key.main(["anthropic"]) == 0
    assert [c["args"][0] for c in runs["calls"]] == ["osascript"]
    assert capsys.readouterr().out.strip() == "Cancelled, nothing saved."


def test_empty_key_saves_nothing(runs, capsys):
    runs["dialog_out"] = "  \n"
    set_key.main(["anthropic"])
    assert [c["args"][0] for c in runs["calls"]] == ["osascript"]
    assert capsys.readouterr().out.strip() == "Cancelled, nothing saved."


def test_remove(runs, capsys):
    assert set_key.main(["openai", "remove"]) == 0
    assert runs["calls"][0]["args"] == ["security", "delete-generic-password", "-s", "talkback-openai", "-a", "talkback"]
    assert capsys.readouterr().out.strip() == "Removed your openai key."
    runs["delete_rc"] = 44
    set_key.main(["openai", "remove"])
    assert capsys.readouterr().out.strip() == "No openai key was stored."


def test_unknown_service_usage(runs, capsys):
    assert set_key.main(["gemini"]) == 1
    assert set_key.main([]) == 1
    assert "Usage: /talkback:key elevenlabs|anthropic|openai [remove]" in capsys.readouterr().out
    assert runs["calls"] == []


def test_rejects_quote_in_key(runs, capsys):
    runs["dialog_out"] = 'abc"def\n'
    set_key.main(["elevenlabs"])
    assert capsys.readouterr().out.strip() == "Key has unexpected characters; nothing saved."
    assert all(c["args"][0] != "security" for c in runs["calls"])


def test_save_failure_message(runs, capsys):
    runs["security_rc"] = 1
    assert set_key.main(["elevenlabs"]) == 1
    assert capsys.readouterr().out.strip() == "Could not save the key in the Keychain."


def test_dialog_failure_is_not_called_cancel(runs, capsys, monkeypatch):
    def fake(args, **k):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="execution error: No user interaction allowed. (-1713)")
    monkeypatch.setattr(set_key, "_run", fake)
    assert set_key.main(["elevenlabs"]) == 1
    out = capsys.readouterr().out
    assert "Could not open the key pop-up" in out and "-1713" in out and "ELEVENLABS_API_KEY" in out


def test_user_cancel_is_cancel(runs, capsys, monkeypatch):
    def fake(args, **k):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="execution error: User canceled. (-128)")
    monkeypatch.setattr(set_key, "_run", fake)
    assert set_key.main(["elevenlabs"]) == 0
    assert capsys.readouterr().out.strip() == "Cancelled, nothing saved."
