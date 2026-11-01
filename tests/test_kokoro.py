import subprocess
from pathlib import Path

import pytest

from talkback import voices
from talkback.config import VoiceSettings
from talkback.voices import kokoro, say

KOKORO = VoiceSettings("kokoro", "af_heart", "")


class FakeProc:
    def __init__(self, args, writes=True, rc=0, hang=False):
        self.args, self.pid, self.returncode = args, 777, rc
        self.writes, self.hang, self.input = writes, hang, None

    def communicate(self, input=None, timeout=None):
        self.input, self.timeout = input, timeout
        if self.hang:
            raise subprocess.TimeoutExpired(self.args, timeout)
        if self.writes:
            Path(self.args[self.args.index("--out") + 1]).write_bytes(b"RIFFwav")
        return "", "" if self.rc_ok else "boom"

    @property
    def rc_ok(self):
        return self.returncode == 0

    def wait(self, timeout=None):
        return self.returncode


@pytest.fixture
def procs(monkeypatch):
    made = []
    opts = {}

    def popen(args, **k):
        p = FakeProc(args, **opts)
        p.kwargs = k
        made.append(p)
        return p

    monkeypatch.setattr(kokoro, "_popen", popen)
    return made, opts


@pytest.fixture
def say_ok(monkeypatch):
    def fake(args, **k):
        Path(args[args.index("-o") + 1]).write_bytes(b"x")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(say, "_run", fake)


def test_kokoro_command_line(procs, tmp_path):
    made, _ = procs
    p = kokoro.synthesize("Hello there.", KOKORO, None, tmp_path / "s")
    assert p == tmp_path / "s.wav" and p.exists()
    args = made[0].args
    assert args[:3] == ["uv", "run", "--script"] and args[3].endswith("scripts/kokoro_tts.py")
    assert args[args.index("--voice") + 1] == "af_heart"
    assert args[args.index("--out") + 1] == str(tmp_path / "s.wav")
    assert args[args.index("--home") + 1] == str(tmp_path)
    assert made[0].input == "Hello there." and made[0].timeout == 20
    assert made[0].kwargs.get("start_new_session") is True


def test_kokoro_without_uv_falls_back(monkeypatch, say_ok, tmp_path):
    def no_uv(args, **k):
        raise FileNotFoundError("uv")

    monkeypatch.setattr(kokoro, "_popen", no_uv)
    assert voices.render("hi", KOKORO, "t") == (tmp_path / "speech-t.aiff", "say")
    assert "kokoro" in (tmp_path / "log.txt").read_text()


def test_kokoro_timeout_kills_process_and_falls_back(procs, monkeypatch, say_ok, tmp_path):
    made, opts = procs
    opts["hang"] = True
    killed = []
    monkeypatch.setattr(kokoro, "_killpg", killed.append)
    assert voices.render("hi", KOKORO, "t") == (tmp_path / "speech-t.aiff", "say")
    assert killed == [777]


def test_kokoro_nonzero_exit_raises(procs, tmp_path):
    _, opts = procs
    opts.update(rc=1, writes=False)
    with pytest.raises(RuntimeError):
        kokoro.synthesize("hi", KOKORO, None, tmp_path / "s")


def test_models_present(tmp_path):
    assert kokoro.models_present() is False
    (tmp_path / "kokoro").mkdir()
    for name in kokoro.MODEL_FILES:
        (tmp_path / "kokoro" / name).write_bytes(b"x")
    assert kokoro.models_present() is True
