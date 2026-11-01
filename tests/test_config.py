import subprocess

from talkback import config


def test_defaults_when_no_file():
    c = config.load_config()
    assert c.ollama_model == "qwen3:8b" and c.voice_id == "21m00Tcm4TlvDq8ikWAM"
    assert c.ollama_url == "http://localhost:11434" and c.eleven_model == "eleven_flash_v2_5"


def test_file_overrides_one_key(tmp_path):
    (tmp_path / "config.json").write_text('{"ollama_model": "x"}')
    c = config.load_config()
    assert c.ollama_model == "x" and c.ollama_url == "http://localhost:11434"


def test_corrupt_config_gives_defaults(tmp_path):
    (tmp_path / "config.json").write_text("{nope")
    assert config.load_config().ollama_model == "qwen3:8b"
    assert "config" in (tmp_path / "log.txt").read_text()


def test_enabled_by_default_and_toggles():
    assert config.is_enabled() is True
    config.set_enabled(False)
    assert config.is_enabled() is False
    config.set_enabled(True)
    assert config.is_enabled() is True


def test_api_key_env_wins(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "env-key")
    assert config.get_api_key(run=lambda *a, **k: 1 / 0) == "env-key"


def test_api_key_from_keychain():
    seen = {}

    def fake(args, **k):
        seen["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout="kc-key\n", stderr="")

    assert config.get_api_key(run=fake) == "kc-key"
    assert seen["args"] == ["security", "find-generic-password", "-s", "talkback-elevenlabs", "-w"]


def test_api_key_missing_returns_none():
    fake = lambda args, **k: subprocess.CompletedProcess(args, 44, stdout="", stderr="not found")
    assert config.get_api_key(run=fake) is None
