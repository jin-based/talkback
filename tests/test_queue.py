import fcntl
import json
import time
from pathlib import Path

import pytest

from talkback import queue, sessions


class Proc:
    played = []
    during_wait = None
    pid_seq = 1000

    def __init__(self, args, **k):
        Proc.pid_seq += 1
        self.pid = Proc.pid_seq
        self.audio = Path(args[1])
        Proc.played.append(self.audio.name)

    def wait(self):
        if Proc.during_wait:
            fn, Proc.during_wait = Proc.during_wait, None
            fn(self)
        return 0


@pytest.fixture(autouse=True)
def fake_player(monkeypatch):
    Proc.played, Proc.during_wait = [], None
    monkeypatch.setattr(queue, "_popen", Proc)


def _audio(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"x")
    return p


def _add(tmp_path, session, name, front=False, token=None):
    token = token or sessions.current_token(session) or sessions.claim(session)
    return queue.enqueue(session, token, _audio(tmp_path, name), "alert" if front else "summary", front)


def test_plays_in_order_alerts_first(tmp_path):
    _add(tmp_path, "A", "a.aiff")
    _add(tmp_path, "B", "b.aiff")
    _add(tmp_path, "C", "c.aiff", front=True)
    queue.run_player()
    assert Proc.played == ["c.aiff", "a.aiff", "b.aiff"]
    assert not list((tmp_path / "queue").glob("*")) and not (tmp_path / "a.aiff").exists()


def test_stale_token_skipped_and_audio_deleted(tmp_path):
    _add(tmp_path, "A", "old.aiff")
    sessions.claim("A")
    _add(tmp_path, "A", "new.aiff")
    queue.run_player()
    assert Proc.played == ["new.aiff"] and not (tmp_path / "old.aiff").exists()


def test_old_item_dropped(tmp_path):
    p = _add(tmp_path, "A", "a.aiff")
    data = json.loads(p.read_text())
    data["created"] = time.time() - 500
    p.write_text(json.dumps(data))
    queue.run_player()
    assert Proc.played == []


def test_missing_audio_skipped(tmp_path):
    _add(tmp_path, "A", "a.aiff")
    (tmp_path / "a.aiff").unlink()
    _add(tmp_path, "B", "b.aiff")
    queue.run_player()
    assert Proc.played == ["b.aiff"]


def test_only_one_player(tmp_path):
    _add(tmp_path, "A", "a.aiff")
    with open(tmp_path / "player.lock", "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        queue.run_player()
    assert Proc.played == [] and list((tmp_path / "queue").glob("*.json"))


def test_item_arriving_during_unlock_is_played(tmp_path, monkeypatch):
    _add(tmp_path, "A", "a.aiff")
    real_drain = queue._drain
    calls = []

    def drain_then_late_arrival():
        real_drain()
        if not calls:
            calls.append(1)
            _add(tmp_path, "B", "late.aiff")  # its speaker couldn't get the lock and left

    monkeypatch.setattr(queue, "_drain", drain_then_late_arrival)
    queue.run_player()
    assert Proc.played == ["a.aiff", "late.aiff"]


def test_corrupt_item_deleted_and_logged(tmp_path):
    (tmp_path / "queue").mkdir(exist_ok=True)
    (tmp_path / "queue" / "1-00000000000000000001-X.json").write_text("{nope")
    _add(tmp_path, "B", "b.aiff")
    queue.run_player()
    assert Proc.played == ["b.aiff"] and "queue" in (tmp_path / "log.txt").read_text()


def test_stop_session_only_its_items_and_audio(tmp_path, monkeypatch):
    killed = []
    monkeypatch.setattr(queue, "_comm", lambda pid: "/usr/bin/afplay")
    monkeypatch.setattr(queue, "_kill", killed.append)
    _add(tmp_path, "A", "a1.aiff")
    _add(tmp_path, "A", "a2.aiff")
    _add(tmp_path, "B", "b.aiff")

    def user_sends_message_in_A(proc):
        queue.stop_session("A")

    Proc.during_wait = user_sends_message_in_A  # while a1 plays
    queue.run_player()
    assert Proc.played == ["a1.aiff", "b.aiff"] and len(killed) == 1

    killed.clear()
    _add(tmp_path, "B", "b2.aiff")
    Proc.during_wait = lambda proc: queue.stop_session("A")  # A's message while B plays
    queue.run_player()
    assert killed == []


def test_stop_session_ignores_non_afplay_pid(tmp_path, monkeypatch):
    (tmp_path / "playing.json").write_text(json.dumps({"session": "A", "pid": 4242}))
    killed = []
    monkeypatch.setattr(queue, "_comm", lambda pid: "/Applications/Safari.app/Contents/MacOS/Safari")
    monkeypatch.setattr(queue, "_kill", killed.append)
    queue.stop_session("A")
    assert killed == []


def test_stop_all_empties_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "_comm", lambda pid: "")
    _add(tmp_path, "A", "a.aiff")
    _add(tmp_path, "B", "b.aiff", front=True)
    queue.stop_all()
    assert not list((tmp_path / "queue").glob("*.json")) and not (tmp_path / "a.aiff").exists()
    queue.run_player()
    assert Proc.played == []
