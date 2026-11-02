import json
import os
import time

import pytest

import hook_ask
import hook_notification
import hook_permission
from talkback import alerts, config, queue, sessions

HOOK = {"session_id": "S1", "cwd": "/work/talkback"}


@pytest.fixture
def said(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    out = []

    def render(text, s, token):
        p = tmp_path / f"a-{len(out)}.aiff"
        p.write_bytes(b"x")
        out.append({"text": text, "voice": s.voice, "token": token})
        return p, s.provider

    monkeypatch.setattr(alerts.voices, "render", render)
    monkeypatch.setattr(alerts.queue, "enqueue",
                        lambda session, token, audio, kind, front: out[-1].update(front=front, kind=kind, session=session))
    monkeypatch.setattr(alerts.queue, "run_player", lambda: None)
    return out


def test_permission_short_bash_edit_other():
    assert alerts.permission_short("Bash", {"command": "git push origin main --force-with-lease now please ok"}) == \
        "run git push origin main --force-with-lease now please ok"
    assert alerts.permission_short("Bash", {"command": "a b c d e f g h i j"}) == "run a b c d e f g h"
    assert alerts.permission_short("Edit", {"file_path": "/x/y/README.md"}) == "edit README.md"
    assert alerts.permission_short("Write", {}) == "edit a file"
    assert alerts.permission_short("WebFetch", {"url": "https://x"}) == "use WebFetch"


def test_permission_short_redacts_long_values():
    out = alerts.permission_short("Bash", {"command": 'curl -H "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz" https://api.x'})
    assert "sk-" not in out and "abcdefghij" not in out and "a long value" in out


def test_permission_prompt_uses_pending(said):
    alerts.on_permission_request({**HOOK, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    alerts.on_notification({**HOOK, "notification_type": "permission_prompt", "message": "Claude needs your permission"})
    assert said[-1]["text"] == "talkback needs approval: run git push"
    assert said[-1]["front"] is True and said[-1]["kind"] == "alert"


def test_permission_prompt_old_pending_uses_message(said, tmp_path):
    alerts.on_permission_request({**HOOK, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    pending = next((tmp_path / "pending").glob("*.json"))
    t = time.time() - 120
    data = json.loads(pending.read_text())
    data["time"] = t
    pending.write_text(json.dumps(data))
    alerts.on_notification({**HOOK, "notification_type": "permission_prompt", "message": "Claude needs your permission to use Bash"})
    assert said[-1]["text"] == "talkback: Claude needs your permission to use Bash"


def test_idle_alert_text(said):
    alerts.on_notification({**HOOK, "notification_type": "idle_prompt", "message": "Claude is waiting for your input"})
    assert said[-1]["text"] == "talkback is waiting for you."


def test_other_notifications_ignored(said):
    alerts.on_notification({**HOOK, "notification_type": "auth_success", "message": "ok"})
    assert said == []


def test_alerts_respect_switches(said, tmp_path):
    (tmp_path / "config.json").write_text('{"alerts": {"permission": false, "idle": false, "questions": false}}')
    alerts.on_notification({**HOOK, "notification_type": "idle_prompt"})
    alerts.on_notification({**HOOK, "notification_type": "permission_prompt", "message": "x"})
    alerts.on_ask_user_question({**HOOK, "tool_input": {"questions": [{"question": "Which?", "options": []}]}})
    assert said == []


def test_alert_uses_project_name_and_voice(said, tmp_path):
    (tmp_path / "config.json").write_text('{"voice": {"provider": "kokoro"}, "projects": {"talkback": {"name": "Talk Back", "voice": "af_bella"}}}')
    alerts.on_notification({**HOOK, "notification_type": "idle_prompt"})
    assert said[-1]["text"] == "Talk Back is waiting for you." and said[-1]["voice"] == "af_bella"


def test_ask_user_question_reads_question_and_options(said):
    alerts.on_ask_user_question({**HOOK, "tool_input": {"questions": [
        {"question": "Which database?", "header": "DB", "options": [{"label": "Postgres", "description": "x"}, {"label": "SQLite"}]}]}})
    assert said[-1]["text"] == "talkback asks: Which database? Option one, Postgres. Option two, SQLite."


def test_ask_unexpected_shape_silent_and_logged(said, tmp_path):
    alerts.on_ask_user_question({**HOOK, "tool_input": {"prompt": "Which?"}})
    assert said == [] and "ask: unexpected tool_input" in (tmp_path / "log.txt").read_text()


def test_alert_cancelled_by_later_prompt_submit(said):
    token = sessions.claim("S1")
    alerts.on_notification({**HOOK, "notification_type": "idle_prompt"})
    assert said[-1]["token"] == token  # alerts never claim a new token
    queue.stop_session("S1")
    assert not sessions.is_current("S1", said[-1]["token"])


def test_hook_scripts_exit_0_no_stdout(capsys, monkeypatch, said):
    for mod in (hook_permission, hook_notification, hook_ask):
        for payload in ("", "{nope", "[1]", json.dumps({**HOOK, "notification_type": "idle_prompt"})):
            assert mod.main(payload) == 0
    assert capsys.readouterr().out == ""


def test_hooks_skip_when_off(said):
    config.set_enabled(False)
    hook_notification.main(json.dumps({**HOOK, "notification_type": "idle_prompt"}))
    assert said == []


@pytest.mark.parametrize("cmd,secret", [
    ("curl -u admin:hunter2 https://x", "hunter2"),
    ("mysql -uroot -pS3cret db", "S3cret"),
    ("PGPASSWORD=pa55 psql", "pa55"),
    ("curl -H 'X-Api-Key: abc123' https://x", "abc123"),
    ("export TOKEN=xyz && deploy", "xyz"),
    ("gh auth login --with-token mysecret", "mysecret"),
])
def test_permission_short_redacts_short_secrets(cmd, secret):
    out = alerts.permission_short("Bash", {"command": cmd})
    assert secret not in out and out.startswith("run ")


def test_permission_short_keeps_plain_commands():
    assert alerts.permission_short("Bash", {"command": "git push origin main"}) == "run git push origin main"
    assert alerts.permission_short("Bash", {"command": "npm run build"}) == "run npm run build"


def test_alerts_not_queued_after_off(said):
    config.set_enabled(False)
    alerts.on_notification({**HOOK, "notification_type": "idle_prompt"})
    assert said == [] or "front" not in said[-1]
