from pathlib import Path

from talkback import playback


class FakeProc:
    def __init__(self, args, **k):
        self.args, self.pid = args, 4242
        FakeProc.started.append(args)

    def wait(self):
        FakeProc.pid_file_during_play = (playback.home() / "playback.pid").read_text()
        return 0


def _fake_popen(monkeypatch):
    FakeProc.started = []
    monkeypatch.setattr(playback, "_popen", FakeProc)


def test_claim_replaces_previous():
    a = playback.claim()
    b = playback.claim()
    assert a != b and not playback.is_current(a) and playback.is_current(b)


def test_stop_current_kills_player(monkeypatch, tmp_path):
    (tmp_path / "playback.pid").write_text("123")
    killed = []
    monkeypatch.setattr(playback, "_comm", lambda pid: "/usr/bin/afplay")
    monkeypatch.setattr(playback, "_kill", killed.append)
    playback.stop_current()
    assert killed == [123] and not (tmp_path / "playback.pid").exists()


def test_stop_current_ignores_unrelated_pid(monkeypatch, tmp_path):
    (tmp_path / "playback.pid").write_text("123")
    killed = []
    monkeypatch.setattr(playback, "_comm", lambda pid: "/Applications/Safari.app/Contents/MacOS/Safari")
    monkeypatch.setattr(playback, "_kill", killed.append)
    playback.stop_current()
    assert killed == []


def test_stop_current_no_file_is_fine():
    playback.stop_current()


def test_stop_current_garbage_pid_file_is_fine(tmp_path):
    (tmp_path / "playback.pid").write_text("not a pid")
    playback.stop_current()


def test_play_say_uses_arg_list(monkeypatch):
    _fake_popen(monkeypatch)
    playback.play_say('He said "hi"; rm -rf')
    assert FakeProc.started == [["say", 'He said "hi"; rm -rf']]
    assert FakeProc.pid_file_during_play == "4242"


def test_play_file_uses_afplay(monkeypatch, tmp_path):
    _fake_popen(monkeypatch)
    playback.play_file(tmp_path / "speech.mp3")
    assert FakeProc.started == [["afplay", str(tmp_path / "speech.mp3")]]
