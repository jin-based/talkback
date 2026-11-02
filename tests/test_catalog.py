import json
import subprocess
from pathlib import Path

import pytest

import voices as voices_cli
from talkback.voices import catalog
from talkback.voices.catalog import Voice

SAY_OUT = """Albert              en_US    # Hello! My name is Albert.
Alice               it_IT    # Ciao! Mi chiamo Alice.
Eddy (English (UK)) en_GB    # Hello! My name is Eddy.
Eddy (English (US)) en_US    # Hello! My name is Eddy.
Samantha            en_US    # Hello! My name is Samantha.
"""


def test_parse_say_voices_english_only(monkeypatch):
    monkeypatch.setattr(catalog, "_run", lambda args, **k: subprocess.CompletedProcess(args, 0, stdout=SAY_OUT, stderr=""))
    vs = catalog.list_voices("say", None)
    assert [v.name for v in vs] == ["Albert", "Eddy (English (UK))", "Eddy (English (US))", "Samantha"]
    assert vs[0] == Voice("Albert", "Albert", "en_US")


def test_elevenlabs_list_parsing_and_headers(monkeypatch):
    seen = {}

    def fake(url, headers, timeout):
        seen.update(url=url, headers=headers, timeout=timeout)
        return {"voices": [{"name": "Rachel", "voice_id": "21m", "labels": {"accent": "american", "gender": "female"}},
                           {"name": "Mine", "voice_id": "abc", "labels": None}]}

    monkeypatch.setattr(catalog, "_get_json", fake)
    vs = catalog.list_voices("elevenlabs", "k")
    assert vs == [Voice("Rachel", "21m", "american, female"), Voice("Mine", "abc", "")]
    assert seen == {"url": "https://api.elevenlabs.io/v1/voices", "headers": {"xi-api-key": "k"}, "timeout": 8}


def test_elevenlabs_list_failure_raises(monkeypatch):
    with pytest.raises(RuntimeError):
        catalog.list_voices("elevenlabs", None)
    monkeypatch.setattr(catalog, "_get_json", lambda *a: {"detail": "unauthorized"})
    with pytest.raises(RuntimeError):
        catalog.list_voices("elevenlabs", "k")


def test_kokoro_table_has_default():
    vs = catalog.list_voices("kokoro", None)
    assert len(vs) == 28 and Voice("Heart", "af_heart", "American female") in vs
    assert Voice("George", "bm_george", "British male") in vs


def test_find_exact_then_contains_case_insensitive():
    vs = [Voice("Bella", "af_bella", ""), Voice("Isabella", "bf_isabella", ""), Voice("Adam", "am_adam", "")]
    assert catalog.find(vs, "bella") == [vs[0]]
    assert catalog.find(vs, "AF_BELLA") == [vs[0]]
    assert catalog.find(vs, "ell") == [vs[0], vs[1]]
    assert catalog.find(vs, "zzz") == []


@pytest.fixture
def kokoro_cfg(tmp_path):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "kokoro"}}')


def test_list_prints_numbered(kokoro_cfg, capsys):
    assert voices_cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "Voices for kokoro" in out and "Bella — American female (af_bella)" in out and "(current)" in out


def test_use_saves_id_main_and_project(kokoro_cfg, tmp_path, capsys):
    assert voices_cli.main(["use", "bella"]) == 0
    assert voices_cli.main(["use", "George", "--project", "horizon"]) == 0
    data = json.loads((tmp_path / "config.json").read_text())
    assert data["voice"]["voice"] == "af_bella" and data["projects"]["horizon"]["voice"] == "bm_george"
    assert "Now using Bella" in capsys.readouterr().out


def test_use_ambiguous_exits_1_saves_nothing(kokoro_cfg, tmp_path, capsys):
    assert voices_cli.main(["use", "ell"]) == 1
    out = capsys.readouterr().out
    assert "Bella" in out and "Isabella" in out
    assert "voice" not in json.loads((tmp_path / "config.json").read_text())["voice"]
    assert voices_cli.main(["use", "nobody"]) == 1


def test_preview_renders_and_plays(kokoro_cfg, monkeypatch, tmp_path, capsys):
    got = {}

    def render(text, s, token):
        got.update(text=text, voice=s.voice, provider=s.provider)
        p = tmp_path / "p.wav"
        p.write_bytes(b"x")
        return p, s.provider

    monkeypatch.setattr(voices_cli.voices, "render", render)
    monkeypatch.setattr(voices_cli.queue, "enqueue", lambda *a, **k: got.update(enqueued=True))
    monkeypatch.setattr(voices_cli.queue, "run_player", lambda: got.update(played=True))
    assert voices_cli.main(["preview", "Bella"]) == 0
    assert got == {"text": "Hi, this is Bella.", "voice": "af_bella", "provider": "kokoro", "enqueued": True, "played": True}


def test_list_failure_exits_1(tmp_path, monkeypatch, capsys):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "elevenlabs"}}')
    monkeypatch.setattr(voices_cli, "get_key", lambda service: None)
    assert voices_cli.main(["list"]) == 1
    assert "/talkback:key elevenlabs" in capsys.readouterr().out


def test_elevenlabs_401_explains_permission(monkeypatch):
    import io
    import urllib.error

    def raise_401(*a):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b""))

    monkeypatch.setattr(catalog, "_get_json", raise_401)
    with pytest.raises(RuntimeError, match="Voices.*Read"):
        catalog.list_voices("elevenlabs", "k")
