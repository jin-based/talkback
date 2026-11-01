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



def test_play_file_uses_afplay(monkeypatch, tmp_path):
    _fake_popen(monkeypatch)
    playback.play_file(tmp_path / "speech.mp3", playback.claim())
    assert FakeProc.started == [["afplay", str(tmp_path / "speech.mp3")]]


def _lock_is_held() -> bool:
    import fcntl
    with open(playback.home() / "lock", "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(f, fcntl.LOCK_UN)
        return False


def test_player_starts_while_holding_lock(monkeypatch):
    held = []

    class P(FakeProc):
        def __init__(self, args, **k):
            held.append(_lock_is_held())
            super().__init__(args, **k)

    FakeProc.started = []
    monkeypatch.setattr(playback, "_popen", P)
    playback.play_file(Path("/tmp/x.aiff"), playback.claim())
    assert held == [True]
    assert _lock_is_held() is False  # released before waiting/after


def test_stale_token_never_starts_player(monkeypatch):
    _fake_popen(monkeypatch)
    old = playback.claim()
    playback.claim()
    playback.play_file(Path("/tmp/x.mp3"), old)
    assert FakeProc.started == []


def test_claim_and_stop_holds_lock(monkeypatch):
    held = []
    monkeypatch.setattr(playback, "stop_current", lambda: held.append(_lock_is_held()))
    token = playback.claim_and_stop()
    assert held == [True] and playback.is_current(token)


def test_pid_file_removed_after_playback(monkeypatch, tmp_path):
    _fake_popen(monkeypatch)
    playback.play_file(tmp_path / "a.aiff", playback.claim())
    assert not (tmp_path / "playback.pid").exists()


def test_pid_file_kept_if_overwritten(monkeypatch, tmp_path):
    class P(FakeProc):
        def wait(self):
            (playback.home() / "playback.pid").write_text("999")  # a newer player took over
            return 0

    FakeProc.started = []
    monkeypatch.setattr(playback, "_popen", P)
    playback.play_file(tmp_path / "a.aiff", playback.claim())
    assert (tmp_path / "playback.pid").read_text() == "999"


def test_play_say_is_gone():
    assert not hasattr(playback, "play_say")
