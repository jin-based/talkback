# talkback Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Claude Code plugin named `talkback` that speaks a one-sentence summary of each Claude reply, written by a local Ollama model and voiced by ElevenLabs, with macOS `say` as the fallback.

**Architecture:** Three hooks (SessionStart warms Ollama, async Stop runs the speaker on `last_assistant_message`, UserPromptSubmit stops playback) and two commands (`/talkback:on`, `/talkback:off`). The logic lives in small stdlib-only Python modules under `scripts/talkback/`. Each outside call (Ollama HTTP, ElevenLabs HTTP, Keychain, `afplay`/`say`) sits behind one function, so the tests can fake it.

**Tech Stack:** Python 3 standard library only at runtime (`urllib.request`, `json`, `subprocess`, `re`, `dataclasses`). Tests use pytest via `uv run --with pytest pytest` (pytest is not installed globally). macOS `afplay`, `say`, `security`.

**Spec:** `docs/superpowers/specs/2026-11-01-claude-voice-talkback-design.md`

## Global Constraints

- Plugin name `talkback`. Repo root is the plugin root. Commands appear as `/talkback:on`, `/talkback:off`.
- No runtime dependencies beyond the Python 3 standard library.
- Hooks never block or change Claude's flow: always exit 0, print nothing to stdout, and catch every exception (log it).
- Data dir `~/.claude/talkback/`, overridable with the env var `TALKBACK_HOME` (tests always set it). Files: `config.json`, `state.json`, `log.txt`, `playback.pid`, `current.token`.
- Talk-back is on by default (no `state.json` means on).
- Config defaults: `ollama_url` `http://localhost:11434`, `ollama_model` `qwen3:8b`, `voice_id` `21m00Tcm4TlvDq8ikWAM`, `eleven_model` `eleven_flash_v2_5`.
- ElevenLabs key: env `ELEVENLABS_API_KEY` first, then Keychain service `talkback-elevenlabs` (`security find-generic-password -s talkback-elevenlabs -w`).
- Ollama: `POST {ollama_url}/api/chat`, `stream: false`, `think: false`, `keep_alive: "30m"`, timeout 5 s. Send only the last 4000 characters of the cleaned reply.
- Summary prompt (system message, exact): `Summarize what the assistant just did in one short spoken sentence, under 20 words. Plain words only: no code, no file paths, no markdown.`
- ElevenLabs: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`, headers `xi-api-key`, `Content-Type: application/json`, `Accept: audio/mpeg`, body `{"text": ..., "model_id": eleven_model}`, timeout 8 s.
- Run all tests from repo root: `uv run --with pytest pytest -q`.

## Review Focus

1. **Two replies close together:** speaker A is still summarizing when speaker B starts. A must not play after B has claimed playback. Pinned in Task 6 (`test_stale_speaker_does_not_play`).
2. **Reply that is only code or a table:** cleaning leaves nothing. Expect silence, no Ollama call. Pinned in Task 6 (`test_code_only_reply_is_silent`).
3. **Malformed or partial hook input** (empty stdin, invalid JSON, no `last_assistant_message`): the hook exits 0 silently and logs. Pinned in Task 7 (`test_stop_hook_bad_input_exits_quietly`).
4. **ElevenLabs answers 200 with a JSON error, or 401/429:** treat anything not starting with audio bytes, or any HTTP error, as failure and fall back to `say`. Pinned in Task 4 (`test_non_audio_response_is_failure`).
5. **Stale PID file** pointing at a process that has exited or been reused: stopping playback must not kill an unrelated process. Only kill if the PID's command is `afplay` or `say`. Pinned in Task 5 (`test_stop_current_ignores_unrelated_pid`).

---

### Task 1: Scaffold, config and log

**Files:**
- Create: `.claude-plugin/plugin.json`, `scripts/talkback/__init__.py`, `scripts/talkback/config.py`, `scripts/talkback/log.py`, `tests/conftest.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `config.home() -> pathlib.Path` (reads `TALKBACK_HOME`, else `~/.claude/talkback`; creates the dir)
  - `@dataclass Config(ollama_url: str, ollama_model: str, voice_id: str, eleven_model: str)`
  - `config.load_config() -> Config` (defaults, overridden by keys in `config.json`; a corrupt file gives defaults and a log line)
  - `config.is_enabled() -> bool`, `config.set_enabled(on: bool) -> None` (writes `state.json` as `{"enabled": bool}`)
  - `config.get_api_key(run=subprocess.run) -> str | None`
  - `log.log_error(msg: str) -> None` (appends `<ISO time> <msg>\n` to `log.txt`; never raises)

- [ ] **Step 1: Write `plugin.json`** with `{"name": "talkback", "version": "0.1.0", "description": "Speaks a short summary of each Claude reply (local model + ElevenLabs)."}`. Write `tests/conftest.py`: put `scripts/` on `sys.path`, and add an autouse fixture that sets `TALKBACK_HOME` to `tmp_path` and deletes `ELEVENLABS_API_KEY`, plus a `cfg` fixture returning `config.load_config()` (later tasks' tests use it).

- [ ] **Step 2: Write failing tests** in `tests/test_config.py`:

```python
def test_defaults_when_no_file():
    c = config.load_config()
    assert c.ollama_model == "qwen3:8b" and c.voice_id == "21m00Tcm4TlvDq8ikWAM"

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
    config.set_enabled(False); assert config.is_enabled() is False
    config.set_enabled(True); assert config.is_enabled() is True

def test_api_key_env_wins(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "env-key")
    assert config.get_api_key(run=lambda *a, **k: 1/0) == "env-key"

def test_api_key_from_keychain():
    fake = lambda args, **k: subprocess.CompletedProcess(args, 0, stdout="kc-key\n", stderr="")
    assert config.get_api_key(run=fake) == "kc-key"

def test_api_key_missing_returns_none():
    fake = lambda args, **k: subprocess.CompletedProcess(args, 44, stdout="", stderr="not found")
    assert config.get_api_key(run=fake) is None
```

- [ ] **Step 3: Run** `uv run --with pytest pytest tests/test_config.py -q`. Expected: FAIL (module not found).
- [ ] **Step 4: Implement** `config.py` and `log.py` to the interfaces above. The Keychain call is `run(["security", "find-generic-password", "-s", "talkback-elevenlabs", "-w"], capture_output=True, text=True)`.
- [ ] **Step 5: Run** the same command. Expected: 7 passed.
- [ ] **Step 6: Commit** `feat: plugin manifest, config and log`.

### Task 2: Cleaning and first-sentence fallback

**Files:**
- Create: `scripts/talkback/clean.py`
- Test: `tests/test_clean.py`

**Interfaces:**
- Produces: `clean.clean(text: str) -> str` (removes fenced code blocks, inline code, URLs, file paths, markdown table rows, headings/bullets/emphasis markers, and HTML comments; collapses whitespace), `clean.first_sentence(text: str, max_words: int = 30) -> str` (first sentence of the already-cleaned text, cut to `max_words`; `""` for empty input)

- [ ] **Step 1: Write failing tests:**

```python
def test_removes_fenced_code():
    assert clean("Fixed it.\n```ts\nx = 1\n```\nDone.") == "Fixed it. Done."

def test_removes_inline_code_paths_urls():
    out = clean("Edited `login.ts` in src/auth/login.ts, see https://x.dev/a.")
    assert "login.ts" not in out and "https" not in out and "src/" not in out

def test_removes_tables_and_markdown():
    out = clean("## Result\n| a | b |\n|---|---|\n| 1 | 2 |\n- **All** tests pass")
    assert out == "Result All tests pass"

def test_code_only_becomes_empty():
    assert clean("```py\nprint(1)\n```") == ""

def test_first_sentence():
    assert first_sentence("I fixed the bug. Then I ran tests.") == "I fixed the bug."

def test_first_sentence_caps_words():
    assert len(first_sentence("word " * 50).split()) == 30
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_clean.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** with `re`. Apply the removals in order: fenced code, HTML comments, table rows (lines starting with `|`), URLs, inline code, paths (tokens containing `/` with a letter on each side, or ending in a dotted extension like `.ts`), then markdown markers (`#`, `*`, `_`, leading `- `). Then collapse whitespace and drop spaces before punctuation.
- [ ] **Step 4: Run** again. Expected: 6 passed.
- [ ] **Step 5: Commit** `feat: clean reply text for speech`.

### Task 3: Summarize with Ollama

**Files:**
- Create: `scripts/talkback/summarize.py`
- Test: `tests/test_summarize.py`

**Interfaces:**
- Consumes: `Config`, `clean.first_sentence`, `log.log_error`
- Produces: `summarize.post_json(url: str, body: dict, timeout: float) -> dict` (the single HTTP seam, using urllib), `summarize.summarize(text: str, cfg: Config) -> str` (input is already cleaned and non-empty), `summarize.warm(cfg: Config) -> None` (posts `{"model": ..., "keep_alive": "30m"}` to `/api/generate` with a 60 s timeout; swallows errors and logs them)

- [ ] **Step 1: Write failing tests** (monkeypatch `summarize.post_json`):

```python
def test_uses_model_reply(monkeypatch):
    seen = {}
    def fake(url, body, timeout):
        seen.update(url=url, body=body, timeout=timeout)
        return {"message": {"content": "Fixed the login bug."}}
    monkeypatch.setattr(summarize, "post_json", fake)
    assert summarize.summarize("long text", cfg) == "Fixed the login bug."
    assert seen["url"].endswith("/api/chat") and seen["timeout"] == 5
    assert seen["body"]["think"] is False and seen["body"]["stream"] is False
    assert seen["body"]["keep_alive"] == "30m"

def test_sends_only_last_4000_chars(monkeypatch): ...  # body user message content == text[-4000:]

def test_falls_back_on_error(monkeypatch):
    monkeypatch.setattr(summarize, "post_json", lambda *a: (_ for _ in ()).throw(OSError("down")))
    assert summarize.summarize("I fixed it. More.", cfg) == "I fixed it."

def test_strips_markdown_and_caps_model_output(monkeypatch):
    # model returns "**Done** — `x`\n\n" + 60 words  →  result has no "*" or "`" and at most 30 words
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_summarize.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Pass the model output through `clean.clean` then `first_sentence(max_words=30)`. If the model returns empty content, use the fallback. Use the exact system prompt from Global Constraints.
- [ ] **Step 4: Run** again. Expected: 4 passed.
- [ ] **Step 5: Commit** `feat: summarize replies with local Ollama model`.

### Task 4: ElevenLabs text-to-speech

**Files:**
- Create: `scripts/talkback/tts.py`
- Test: `tests/test_tts.py`

**Interfaces:**
- Consumes: `Config`, `log.log_error`
- Produces: `tts.post_audio(url: str, headers: dict, body: dict, timeout: float) -> bytes` (the HTTP seam), `tts.synthesize(text: str, cfg: Config, api_key: str | None) -> pathlib.Path | None` (writes `<home>/speech.mp3`; returns None on any failure, including no key)

- [ ] **Step 1: Write failing tests:**

```python
def test_no_key_returns_none(monkeypatch):
    monkeypatch.setattr(tts, "post_audio", lambda *a: 1/0)
    assert tts.synthesize("hi", cfg, None) is None

def test_request_shape_and_file(monkeypatch, tmp_path):
    seen = {}
    def fake(url, headers, body, timeout):
        seen.update(url=url, headers=headers, body=body, timeout=timeout); return b"ID3fakeaudio"
    monkeypatch.setattr(tts, "post_audio", fake)
    p = tts.synthesize("hi", cfg, "k")
    assert p.read_bytes() == b"ID3fakeaudio"
    assert seen["url"] == "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
    assert seen["headers"]["xi-api-key"] == "k" and seen["timeout"] == 8
    assert seen["body"] == {"text": "hi", "model_id": "eleven_flash_v2_5"}

def test_non_audio_response_is_failure(monkeypatch):
    monkeypatch.setattr(tts, "post_audio", lambda *a: b'{"detail":"quota_exceeded"}')
    assert tts.synthesize("hi", cfg, "k") is None

def test_http_error_is_failure(monkeypatch): ...  # post_audio raises urllib.error.HTTPError(401) → None, logged
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_tts.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Treat the response as audio only if it starts with `ID3` or an MPEG frame sync byte (`0xFF` followed by a byte whose top 3 bits are set).
- [ ] **Step 4: Run** again. Expected: 4 passed.
- [ ] **Step 5: Commit** `feat: ElevenLabs text-to-speech`.

### Task 5: Playback and cut-off

**Files:**
- Create: `scripts/talkback/playback.py`
- Test: `tests/test_playback.py`

**Interfaces:**
- Consumes: `config.home`, `log.log_error`
- Produces:
  - `playback.claim() -> str` (writes a new random token to `current.token`, returns it)
  - `playback.is_current(token: str) -> bool`
  - `playback.stop_current() -> None` (reads `playback.pid`; kills with SIGTERM only if `ps -p <pid> -o comm=` ends in `afplay` or `say`; removes the file)
  - `playback.play_file(path: Path) -> None`, `playback.play_say(text: str) -> None` (start `afplay path` / `say text` with `subprocess.Popen` using an argument list, never a shell; write its PID; wait for it to finish)
  - Seams: `playback._popen = subprocess.Popen`, `playback._comm(pid: int) -> str`, `playback._kill(pid: int) -> None`

- [ ] **Step 1: Write failing tests:**

```python
def test_claim_replaces_previous():
    a = playback.claim(); b = playback.claim()
    assert not playback.is_current(a) and playback.is_current(b)

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
    monkeypatch.setattr(playback, "_comm", lambda pid: "/Applications/Safari")
    monkeypatch.setattr(playback, "_kill", killed.append)
    playback.stop_current()
    assert killed == []

def test_stop_current_no_file_is_fine():
    playback.stop_current()

def test_play_say_uses_arg_list(monkeypatch):
    # fake _popen records args; play_say('He said "hi"; rm -rf') → args == ["say", 'He said "hi"; rm -rf']
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_playback.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** to the interfaces. `_comm` returns `""` when the process is gone.
- [ ] **Step 4: Run** again. Expected: 5 passed.
- [ ] **Step 5: Commit** `feat: playback with safe cut-off`.

### Task 6: Speaker (puts it together)

**Files:**
- Create: `scripts/talkback/speaker.py`
- Test: `tests/test_speaker.py`

**Interfaces:**
- Consumes: everything from Tasks 1-5
- Produces: `speaker.speak(reply: str) -> None`. Order: `token = claim()` → `stop_current()` → `text = clean(reply)`; if empty, return → `summary = summarize(text, cfg)` → `audio = synthesize(summary, cfg, get_api_key())` → if `not is_current(token)`, return → `stop_current()` → `play_file(audio)` if audio else `play_say(summary)`. Wrap the whole thing in try/except and log errors.

- [ ] **Step 1: Write failing tests** (monkeypatch `summarize`, `synthesize`, `play_file`, `play_say`, `get_api_key` on the `speaker` module and record calls):

```python
def test_happy_path_plays_elevenlabs_audio(...):   # synthesize returns a Path → play_file called with it, play_say not called
def test_falls_back_to_say_when_tts_fails(...):    # synthesize returns None → play_say(summary)
def test_code_only_reply_is_silent(...):           # speak("```py\nx\n```") → summarize, play_file, play_say never called
def test_stale_speaker_does_not_play(...):         # fake summarize calls playback.claim() (a newer speaker) → nothing played
def test_unexpected_error_is_logged(...):          # summarize raises RuntimeError → no exception escapes, log.txt mentions RuntimeError
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_speaker.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `speak` as ordered above.
- [ ] **Step 4: Run** the full suite `uv run --with pytest pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: speaker pipeline with fallbacks`.

### Task 7: Hooks and commands

**Files:**
- Create: `hooks/hooks.json`, `scripts/hook_session_start.py`, `scripts/hook_stop.py`, `scripts/hook_prompt_submit.py`, `scripts/set_enabled.py`, `commands/on.md`, `commands/off.md`
- Test: `tests/test_hooks.py`

**Interfaces:**
- Consumes: `speaker.speak`, `summarize.warm`, `playback.stop_current`, `config.is_enabled`, `config.set_enabled`, `config.load_config`
- Produces: each hook script has `main(stdin_text: str) -> int` (always returns 0) plus `if __name__ == "__main__": sys.exit(main(sys.stdin.read()))`. Each script inserts its own directory into `sys.path` so `import talkback` works when run by path. `set_enabled.py` takes `on` or `off` as `argv[1]` and prints `Talk-back is on.` or `Talk-back is off.`

- [ ] **Step 1: Write failing tests:**

```python
def test_stop_hook_speaks_reply(monkeypatch):
    said = []; monkeypatch.setattr(hook_stop.speaker, "speak", said.append)
    assert hook_stop.main('{"last_assistant_message": "Done.", "stop_hook_active": false}') == 0
    assert said == ["Done."]

def test_stop_hook_respects_off(monkeypatch):        # set_enabled(False) → speak not called
def test_stop_hook_skips_when_stop_hook_active(...): # stop_hook_active true → speak not called
def test_stop_hook_bad_input_exits_quietly(monkeypatch, capsys):
    for bad in ["", "{nope", '{"other": 1}']:
        assert hook_stop.main(bad) == 0
    assert capsys.readouterr().out == ""
def test_prompt_submit_stops_playback(monkeypatch):  # stop_current called once, returns 0
def test_set_enabled_off_then_on(capsys):            # run main(["off"]) → is_enabled False, prints "Talk-back is off."
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_hooks.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement the scripts.** Write `hooks/hooks.json`:

```json
{"description": "talkback: speak a summary of each Claude reply",
 "hooks": {
  "SessionStart":     [{"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/hook_session_start.py\"", "async": true}]}],
  "Stop":             [{"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/hook_stop.py\"", "async": true}]}],
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/hook_prompt_submit.py\"", "timeout": 5}]}]
 }}
```

  Write `commands/on.md` (and `off.md` the same with `off`):

```markdown
---
description: Turn talkback (spoken reply summaries) on
allowed-tools: Bash
disable-model-invocation: true
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/set_enabled.py" on`

Tell the user in one short line that talk-back is now on.
```

- [ ] **Step 4: Run** `uv run --with pytest pytest -q`. Expected: all pass.
- [ ] **Step 5: Validate** with `claude plugin validate .`. Expected: no errors.
- [ ] **Step 6: Commit** `feat: hooks and on/off commands`.

### Task 8: Real-service checks, end to end, README

**Files:**
- Create: `README.md` (what it does, setup, commands, config keys, log location)
- Modify: `docs/decisions.md` (record results)

- [ ] **Step 1: Ollama, real call:** `cd scripts && python3 -c "from talkback import summarize, config; print(summarize.summarize('I fixed the expiry bug and all 48 tests pass. Then I updated docs.', config.load_config()))"`. Expected: one plain sentence in a few seconds.
- [ ] **Step 2: ElevenLabs key:** the user stores it with `security add-generic-password -s talkback-elevenlabs -a "$USER" -w` (prompts for the key; never paste it into chat). Then `cd scripts && python3 -c "from talkback import speaker; speaker.speak('I fixed the login bug and all tests pass.')"`. Expected: the ElevenLabs voice speaks. If there's no key yet, expect the Mac voice and skip to Step 3.
- [ ] **Step 3: End to end:** `claude --plugin-dir /path/to/talkback`. Ask "what's 2+2, answer in one sentence". Expected: a spoken summary. Run `/talkback:off`, ask again, expect silence. Run `/talkback:on`, ask a long question, send a new message while it's speaking, expect it to stop. Check `~/.claude/talkback/log.txt` for errors.
- [ ] **Step 4: Check** that `${CLAUDE_PLUGIN_ROOT}` expands inside the command files' `!` lines. If it doesn't, switch the command line to an absolute fallback and note it in `docs/decisions.md`.
- [ ] **Step 5: Write `README.md`**, record the results in `docs/decisions.md`, and commit `docs: README and end-to-end results`.
