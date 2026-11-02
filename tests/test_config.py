import json
import subprocess

from talkback import config
from talkback.config import SummarySettings, VoiceSettings


def _write(tmp_path, data):
    (tmp_path / "config.json").write_text(json.dumps(data))


def test_defaults():
    c = config.load_config()
    assert c.summary == SummarySettings("ollama", "llama3.2:3b", "http://localhost:11434")
    assert c.voice == VoiceSettings("say", "", "eleven_flash_v2_5")


def test_provider_defaults_fill_in(tmp_path):
    _write(tmp_path, {"summary": {"provider": "anthropic"}, "voice": {"provider": "kokoro"}})
    c = config.load_config()
    assert c.summary.model == "claude-haiku-5-5" and c.voice.voice == "af_heart"


def test_elevenlabs_default_voice(tmp_path):
    _write(tmp_path, {"voice": {"provider": "elevenlabs"}})
    assert config.load_config().voice.voice == "21m00Tcm4TlvDq8ikWAM"


def test_openai_default_url(tmp_path):
    _write(tmp_path, {"summary": {"provider": "openai"}})
    s = config.load_config().summary
    assert s.url == "https://api.openai.com/v1" and s.model == "gpt-4o-mini"


def test_user_values_win(tmp_path):
    _write(tmp_path, {"summary": {"provider": "ollama", "model": "qwen3:8b"}})
    assert config.load_config().summary.model == "qwen3:8b"


def test_bad_section_shapes_fall_back_per_section(tmp_path):
    _write(tmp_path, {"summary": {"provider": "nope"}, "voice": "kokoro"})
    c, problems = config.validate(json.loads((tmp_path / "config.json").read_text()))
    assert c == config.load_config() and c.summary.provider == "ollama" and c.voice.provider == "say"
    assert len(problems) == 2
    log = (tmp_path / "log.txt").read_text()
    assert "summary" in log and "voice" in log

    _write(tmp_path, {"summary": None, "voice": {"provider": "elevenlabs", "model": 5}})
    c = config.load_config()
    assert c.summary.provider == "ollama" and c.voice == VoiceSettings("elevenlabs", "21m00Tcm4TlvDq8ikWAM", "5")


def test_corrupt_file_gives_defaults(tmp_path):
    (tmp_path / "config.json").write_text("{nope")
    assert config.load_config().summary.provider == "ollama"


def test_enabled_by_default_and_toggles():
    assert config.is_enabled() is True
    config.set_enabled(False)
    assert config.is_enabled() is False
    config.set_enabled(True)
    assert config.is_enabled() is True


def test_get_key_env_wins(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    assert config.get_key("openai", run=lambda *a, **k: 1 / 0) == "env-key"


def test_get_key_keychain_args():
    seen = {}

    def fake(args, **k):
        seen["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout="kc\n", stderr="")

    assert config.get_key("anthropic", run=fake) == "kc"
    assert seen["args"] == ["security", "find-generic-password", "-s", "talkback-anthropic", "-a", "talkback", "-w"]


def test_get_key_missing_is_none():
    fake = lambda args, **k: subprocess.CompletedProcess(args, 44, stdout="", stderr="")
    assert config.get_key("elevenlabs", run=fake) is None


def test_get_key_unknown_service_is_none():
    assert config.get_key("nope", run=lambda *a, **k: 1 / 0) is None


def test_get_key_env_false_skips_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    fake = lambda args, **k: subprocess.CompletedProcess(args, 0, stdout="kc\n", stderr="")
    assert config.get_key("openai", run=fake, env=False) == "kc"


def test_projects_and_alerts_defaults():
    c = config.load_config()
    assert c.projects == {} and c.alerts == config.AlertSettings(True, True, True)


def test_projects_parsed(tmp_path):
    _write(tmp_path, {"projects": {"horizon": {"name": "Horizon", "voice": "af_bella", "x": 1}, "t": {"voice": 5}}})
    p = config.load_config().projects
    assert p["horizon"] == config.ProjectSettings("Horizon", "af_bella") and p["t"] == config.ProjectSettings("", "5")


def test_bad_projects_section_falls_back(tmp_path):
    _write(tmp_path, {"projects": ["horizon"], "voice": {"provider": "kokoro"}})
    c = config.load_config()
    assert c.projects == {} and c.voice.provider == "kokoro"
    assert "projects" in (tmp_path / "log.txt").read_text()


def test_alert_non_bool_falls_back_true(tmp_path):
    _write(tmp_path, {"alerts": {"idle": False, "permission": "nope"}})
    a = config.load_config().alerts
    assert a == config.AlertSettings(True, False, True)
    assert "alerts" in (tmp_path / "log.txt").read_text()
