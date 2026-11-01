import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


@pytest.fixture(autouse=True)
def talkback_home(tmp_path, monkeypatch):
    monkeypatch.setenv("TALKBACK_HOME", str(tmp_path))
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    return tmp_path


@pytest.fixture
def cfg():
    from talkback import config
    return config.load_config()
