import json
from pathlib import Path

import pytest

import configure
import status
import test_voice as tv
from talkback import voices


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(status, "_ollama_models", lambda url: None)
    monkeypatch.setattr(status, "_keychain_has", lambda service: False)


def test_status_never_prints_keys(monkeypatch, capsys):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-secret")
    assert status.main() == 0
    out = capsys.readouterr().out
    assert "elevenlabs: set" in out and "anthropic: not set" in out and "sk-secret" not in out


def test_status_reports_problems_and_sections(tmp_path, capsys):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "bogus"}}')
    status.main()
    out = capsys.readouterr().out
    for section in ("Settings", "Problems", "Ollama", "uv", "Kokoro model", "Keys"):
        assert section in out
    assert "bogus" in out and "not reachable" in out


def test_status_lists_ollama_models(monkeypatch, capsys):
    monkeypatch.setattr(status, "_ollama_models", lambda url: ["llama3.2:3b", "qwen3:8b"])
    status.main()
    assert "llama3.2:3b, qwen3:8b" in capsys.readouterr().out


def test_configure_writes_and_merges(tmp_path, capsys):
    assert configure.main(["summary.provider=anthropic"]) == 0
    assert configure.main(["voice.provider=kokoro", "voice.voice=af_bella"]) == 0
    data = json.loads((tmp_path / "config.json").read_text())
    assert data == {"summary": {"provider": "anthropic"}, "voice": {"provider": "kokoro", "voice": "af_bella"}}
    assert "Saved: voice.provider=kokoro, voice.voice=af_bella" in capsys.readouterr().out


def test_configure_rejects_unknown(tmp_path, capsys):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "say"}}')
    for bad in (["voice.provider=openai"], ["sound.provider=say"], ["voice.url=x"], ["voice.provider"]):
        assert configure.main(bad) == 1
    assert json.loads((tmp_path / "config.json").read_text()) == {"voice": {"provider": "say"}}
    assert "Unknown" in capsys.readouterr().out


def test_configure_all_or_nothing(tmp_path):
    configure.main(["summary.provider=none", "voice.provider=nope"])
    assert not (tmp_path / "config.json").exists()


def test_configure_empty_value_removes_field(tmp_path):
    configure.main(["summary.provider=ollama", "summary.model=qwen3:8b"])
    configure.main(["summary.model="])
    assert json.loads((tmp_path / "config.json").read_text()) == {"summary": {"provider": "ollama"}}


def test_test_voice_reports_fallback(monkeypatch, capsys, tmp_path):
    (tmp_path / "config.json").write_text('{"summary": {"provider": "anthropic"}, "voice": {"provider": "elevenlabs"}}')
    monkeypatch.setattr(tv.summarizers, "get_key", lambda s: None)
    monkeypatch.setattr(tv.voices, "get_key", lambda s: None)

    def fake_say(text, s, key, out):
        p = Path(str(out) + ".aiff")
        p.write_bytes(b"x")
        return p

    monkeypatch.setattr(voices.say, "synthesize", fake_say)
    played = []
    monkeypatch.setattr(tv, "play_file", lambda path, token: played.append(path))
    assert tv.main([]) == 0
    out = capsys.readouterr().out
    assert "Summary by: first sentence (fallback from anthropic)" in out
    assert "Voice: say (fallback from elevenlabs)" in out
    assert len(played) == 1 and not played[0].exists()


def test_test_voice_long_raises_kokoro_timeout(monkeypatch):
    monkeypatch.setattr(tv, "_speak", lambda cfg: ("x", "say"))
    tv.main(["--long"])
    assert voices.kokoro.TIMEOUT == 600 and voices.kokoro.WAIT_FOR_DOWNLOAD is True
    voices.kokoro.TIMEOUT, voices.kokoro.WAIT_FOR_DOWNLOAD = 20, False


def test_status_flags_missing_ollama_model(monkeypatch, capsys):
    monkeypatch.setattr(status, "_ollama_models", lambda url: ["qwen3:8b"])
    status.main()
    out = capsys.readouterr().out
    assert "llama3.2:3b is not installed" in out and "ollama pull llama3.2:3b" in out


def test_status_accepts_latest_tag(monkeypatch, tmp_path, capsys):
    (tmp_path / "config.json").write_text('{"summary": {"model": "mistral"}}')
    monkeypatch.setattr(status, "_ollama_models", lambda url: ["mistral:latest"])
    status.main()
    assert "not installed" not in capsys.readouterr().out


def test_status_prints_scripts_folder(capsys):
    status.main()
    first = capsys.readouterr().out.splitlines()[0]
    assert first == f"Scripts: {Path(status.__file__).resolve().parent}"


def test_configure_projects_and_alerts(tmp_path):
    assert configure.main(["alerts.idle=off", "projects.horizon.voice=af_bella", "projects.horizon.name=Horizon"]) == 0
    data = json.loads((tmp_path / "config.json").read_text())
    assert data == {"alerts": {"idle": False}, "projects": {"horizon": {"voice": "af_bella", "name": "Horizon"}}}
    configure.main(["alerts.idle=on", "projects.horizon.name="])
    data = json.loads((tmp_path / "config.json").read_text())
    assert data["alerts"]["idle"] is True and data["projects"]["horizon"] == {"voice": "af_bella"}


def test_configure_rejects_bad_alert_value(tmp_path):
    assert configure.main(["alerts.idle=maybe"]) == 1
    assert configure.main(["alerts.loud=on"]) == 1
    assert configure.main(["projects.horizon.color=red"]) == 1
    assert not (tmp_path / "config.json").exists()
