"""The plugin must run on the Python that ships with macOS (3.9), not just newer ones."""
import subprocess
from pathlib import Path

import pytest

SYSTEM_PY = "/usr/bin/python3"
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.mark.skipif(not Path(SYSTEM_PY).exists(), reason="no system python")
def test_all_modules_import_under_system_python():
    code = ("import sys; sys.path.insert(0, %r); "
            "import talkback.speaker, talkback.summarizers, talkback.voices, talkback.voices.kokoro, talkback.sessions, talkback.queue, talkback.question, set_key, hook_stop, hook_prompt_submit, hook_session_start, set_enabled") % str(SCRIPTS)
    r = subprocess.run([SYSTEM_PY, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
