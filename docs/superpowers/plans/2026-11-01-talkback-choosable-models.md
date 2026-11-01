# talkback Choosable Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any user pick the summary model (Ollama, OpenAI-compatible, Claude Haiku, none) and the voice (Mac `say`, Kokoro, ElevenLabs), enter their own keys safely, and set it all up through `/talkback:setup`.

**Architecture:** Settings become two nested sections, `summary` and `voice`. Each provider is one module in `scripts/talkback/summarizers/` or `scripts/talkback/voices/`, all with the same function shape. A small registry in each package picks the configured provider and applies the fixed fallback (first sentence for summaries; Mac voice for speech). Every voice renders to a per-token audio file that `afplay` plays. Kokoro runs as a separate `uv run --script`. Keys come from env vars, then the Keychain, entered via a macOS hidden-input dialog.

**Tech Stack:** Python 3.9+ standard library for everything in `scripts/talkback/` (must import under `/usr/bin/python3`). `scripts/kokoro_tts.py` is the only file with dependencies (`kokoro-onnx`, `soundfile`), run with `uv`. Tests: `uv run --with pytest pytest -q`. macOS `afplay`, `say`, `security`, `osascript`.

**Spec:** `docs/superpowers/specs/2026-11-01-talkback-choosable-models-design.md` (builds on `docs/superpowers/specs/2026-11-01-claude-voice-talkback-design.md`)

## Global Constraints

- Every module under `scripts/` except `kokoro_tts.py` starts with `from __future__ import annotations` and uses only the standard library. `tests/test_system_python.py` must keep passing and must import every new module.
- Hooks always exit 0, print nothing to stdout, and catch every exception (log it). The speaker never raises.
- Defaults (exact): summary `provider` `ollama`, `model` `llama3.2:3b`, `url` `http://localhost:11434`. Model defaults per provider: `openai` `gpt-4o-mini`, `anthropic` `claude-haiku-5-5`. URL default for `openai`: `https://api.openai.com/v1`. Voice `provider` `say`, `voice` defaults: `say` `""` (system voice), `kokoro` `af_heart`, `elevenlabs` `21m00Tcm4TlvDq8ikWAM`. ElevenLabs `model` `eleven_flash_v2_5`.
- Providers (exact names): summary `ollama`, `openai`, `anthropic`, `none`. Voice `say`, `kokoro`, `elevenlabs`.
- Keys: services `elevenlabs`, `anthropic`, `openai`. Env vars `ELEVENLABS_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` win over Keychain items `talkback-elevenlabs`, `talkback-anthropic`, `talkback-openai` (account `talkback`). A key never appears in argv, stdout, logs, or a file.
- Timeouts: Ollama 5 s; `openai` 5 s for localhost/127.0.0.1 URLs, else 8 s; `anthropic` 8 s; ElevenLabs 8 s; `say` render 8 s; Kokoro 20 s (setup's test run: 600 s).
- Anthropic request: `POST https://api.anthropic.com/v1/messages`, headers `x-api-key`, `anthropic-version: 2026-10-21`, `content-type: application/json`; body `model`, `max_tokens: 300`, `system`, `messages`, `thinking: {"type": "disabled"}`, `output_config: {"effort": "low"}`; never `temperature`/`top_p`/`top_k`.
- System prompt and the 4000-character tail are unchanged from v0.1 (`SYSTEM_PROMPT`, `MAX_CHARS` in the current `summarize.py`).
- Kokoro files: `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.int8.onnx` and `.../model-files-v1.1/voices-v1.0.bin`, saved in `<home>/kokoro/`. The script's PEP 723 header pins `requires-python = ">=3.10,<3.14"` (kokoro-onnx 0.6.1 requires it).
- Work on branch `feat/choosable-models`.

## Review Focus

1. **Settings file with wrong shapes** (`"voice": "kokoro"` as a string, `"summary": null`, a number for `model`, an unknown provider): that section falls back to defaults, logged; the other section is unaffected. Pinned in Task 1 (`test_bad_section_shapes_fall_back_per_section`).
2. **A summary service returning an unexpected body** (OpenAI-compatible without `choices`, Anthropic with `stop_reason: "refusal"` or no text blocks): treat as failure → first sentence. Pinned in Task 2 (`test_openai_missing_choices_falls_back`, `test_anthropic_refusal_or_no_text_falls_back`).
3. **The key leaking:** `set_key.py` must send the key to `security` on stdin only, and print nothing containing it, even when `security` fails. Pinned in Task 6 (`test_key_never_in_argv_or_output`).
4. **Kokoro unavailable or stuck** (`uv` not installed, first-run download in progress, the process hanging): the voice registry falls back to `say` within the 20 s limit and kills the Kokoro process it started. Pinned in Task 4 (`test_kokoro_timeout_kills_process_and_falls_back`, `test_kokoro_without_uv_falls_back`).
5. **A `say` voice name that isn't installed:** `say -v Nonexistent` fails; retry once with the system voice instead of going silent. Pinned in Task 3 (`test_say_unknown_voice_retries_with_system_voice`).

---

### Task 1: Nested settings and per-service keys

**Files:**
- Modify: `scripts/talkback/config.py`, `scripts/talkback/summarize.py`, `scripts/talkback/tts.py`, `scripts/hook_session_start.py` (only to read the new settings shape)
- Test: `tests/test_config.py` (rewrite), existing tests adjusted for the new shape

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) SummarySettings(provider: str, model: str, url: str)` and `VoiceSettings(provider: str, voice: str, model: str)`; `@dataclass(frozen=True) Config(summary: SummarySettings, voice: VoiceSettings)`
  - `config.load_config() -> Config` (per-provider defaults are filled in, so `summary.model` is never empty)
  - `config.validate(raw: dict) -> tuple[Config, list[str]]` (the problems list feeds `status.py`)
  - `config.get_key(service: str, run=subprocess.run) -> str | None` (replaces `get_api_key`; `security find-generic-password -s talkback-<service> -a talkback -w`)
  - `config.KEY_SERVICES = ("elevenlabs", "anthropic", "openai")`, `config.ENV_VARS = {"elevenlabs": "ELEVENLABS_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}`
  - `config.SUMMARY_PROVIDERS`, `config.VOICE_PROVIDERS` (tuples of the exact names)

- [ ] **Step 1: Create the branch** `git switch -c feat/choosable-models`.
- [ ] **Step 2: Write failing tests:**

```python
def test_defaults(): c = config.load_config(); assert c.summary == SummarySettings("ollama", "llama3.2:3b", "http://localhost:11434"); assert c.voice == VoiceSettings("say", "", "eleven_flash_v2_5")
def test_provider_defaults_fill_in(tmp_path):  # {"summary": {"provider": "anthropic"}, "voice": {"provider": "kokoro"}} → model "claude-haiku-5-5", voice "af_heart"
def test_openai_default_url(tmp_path):         # {"summary": {"provider": "openai"}} → url "https://api.openai.com/v1", model "gpt-4o-mini"
def test_bad_section_shapes_fall_back_per_section(tmp_path):
    # {"summary": {"provider": "nope"}, "voice": "kokoro"} → both defaults, 2 problems, log mentions both
    # {"summary": null, "voice": {"provider": "elevenlabs", "model": 5}} → summary default; voice elevenlabs with model "5"
def test_get_key_env_wins(monkeypatch)        # OPENAI_API_KEY set → returned, run never called
def test_get_key_keychain_args()              # args == ["security","find-generic-password","-s","talkback-anthropic","-a","talkback","-w"]
def test_get_key_unknown_service_is_none()
```

- [ ] **Step 3: Run** `uv run --with pytest pytest tests/test_config.py -q`. Expected: FAIL.
- [ ] **Step 4: Implement** the new `config.py`. Update `summarize.py`, `tts.py` and `hook_session_start.py` to read `cfg.summary.*` / `cfg.voice.*` and call `get_key("elevenlabs")`. These are thin edits; Tasks 2-3 replace those modules.
- [ ] **Step 5: Run** `uv run --with pytest pytest -q`. Expected: all pass (adjust fixtures that build the old flat `Config`).
- [ ] **Step 6: Commit** `feat: nested summary/voice settings and per-service keys`.

### Task 2: Summary providers

**Files:**
- Create: `scripts/talkback/summarizers/__init__.py`, `none.py`, `ollama.py`, `openai.py`, `anthropic.py`, `_http.py`
- Delete: `scripts/talkback/summarize.py` (contents move to `summarizers/ollama.py` and `__init__.py`)
- Test: `tests/test_summarizers.py` (replaces `tests/test_summarize.py`)

**Interfaces:**
- Consumes: `SummarySettings`, `config.get_key`, `clean.clean`, `clean.first_sentence`, `log.log_error`
- Produces:
  - `_http.post_json(url: str, headers: dict, body: dict, timeout: float) -> dict`, the single HTTP seam for all summarizers
  - each provider module: `summarize(text: str, s: SummarySettings, key: str | None) -> str` (raises on failure; returns raw model text)
  - `summarizers.SYSTEM_PROMPT`, `summarizers.MAX_CHARS` (moved from `summarize.py`)
  - `summarizers.run(text: str, s: SummarySettings) -> str`: looks up the key (`openai` → `get_key("openai")`, `anthropic` → `get_key("anthropic")`), calls the provider, passes its output through `clean` then `first_sentence(max_words=30)`, and on any exception or empty result logs `summarize: <provider> failed: <repr>` and returns `first_sentence(text)`
  - `summarizers.ollama.warm(s: SummarySettings) -> None` (moved; unchanged behavior)

- [ ] **Step 1: Write failing tests** (monkeypatch `_http.post_json`; record url/headers/body/timeout):

```python
def test_none_returns_first_sentence()
def test_ollama_request_unchanged(...)          # /api/chat, think False, stream False, keep_alive "30m", timeout 5, model from settings
def test_openai_request_with_key(...)           # url "https://api.openai.com/v1/chat/completions", headers["Authorization"] == "Bearer k", body max_tokens 100, timeout 8
def test_openai_local_no_key_short_timeout(...) # url http://localhost:1234/v1 → no Authorization header, timeout 5
def test_openai_missing_choices_falls_back(...) # post_json returns {"error": "x"} → run() == first sentence
def test_anthropic_request_shape(...)
    # url https://api.anthropic.com/v1/messages; headers x-api-key "k", anthropic-version "2026-10-21"
    # body: model "claude-haiku-5-5", max_tokens 300, thinking {"type": "disabled"}, output_config {"effort": "low"}
    # "temperature" not in body; system == SYSTEM_PROMPT; timeout 8
def test_anthropic_joins_text_blocks(...)       # content [{"type":"thinking",...},{"type":"text","text":"Fixed it."}] → "Fixed it."
def test_anthropic_refusal_or_no_text_falls_back(...)  # stop_reason "refusal" with no text, and content [] → first sentence
def test_anthropic_without_key_falls_back(...)  # get_key returns None → first sentence, post_json never called, log mentions "no key"
def test_run_cleans_and_caps_output(...)        # model returns markdown + 60 words → no "*", ≤ 30 words
def test_sends_only_last_4000_chars(...)        # for ollama, openai, anthropic
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_summarizers.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** `anthropic.py` raises `RuntimeError("no key")` when `key` is None; `openai.py` raises when `choices` is missing. Point `speaker.py` and `hook_session_start.py` at `summarizers.run` / `summarizers.ollama.warm`. Delete `summarize.py` and `tests/test_summarize.py`.
- [ ] **Step 4: Run** `uv run --with pytest pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: Ollama, OpenAI-compatible, Anthropic and none summarizers`.

### Task 3: Voice registry, Mac voice and ElevenLabs as providers

**Files:**
- Create: `scripts/talkback/voices/__init__.py`, `say.py`, `elevenlabs.py`
- Delete: `scripts/talkback/tts.py` (moves to `voices/elevenlabs.py`)
- Test: `tests/test_voices.py` (replaces `tests/test_tts.py`)

**Interfaces:**
- Consumes: `VoiceSettings`, `config.get_key`, `config.home`, `log.log_error`
- Produces:
  - each provider: `synthesize(text: str, s: VoiceSettings, key: str | None, out: Path) -> Path` (writes the audio file, returns its path, raises on failure). `out` is a stem without extension; the provider adds `.aiff` / `.mp3` / `.wav`.
  - `voices.audio_stem(token: str) -> Path` = `home() / f"speech-{token}"`
  - `voices.render(text: str, s: VoiceSettings, token: str) -> tuple[Path, str]`: tries the configured provider, and on failure logs and falls back to `say` with the system voice. Returns `(path, provider_that_spoke)`. Raises only if `say` itself fails.
  - `voices.say._run = subprocess.run` (seam). `say.synthesize` runs `["say", "-v", voice, "-o", f"{out}.aiff", "--", text]`, omitting `-v voice` when empty, with timeout 8. If it fails with a voice set, it retries once without `-v`.

- [ ] **Step 1: Write failing tests:**

```python
def test_say_args_and_dash_text(...)            # text "-5 tests" → args end with ["--", "-5 tests"]; no "-v" when voice ""
def test_say_unknown_voice_retries_with_system_voice(...)  # first _run raises CalledProcessError, second succeeds without "-v"
def test_elevenlabs_request_unchanged(...)      # same URL/headers/body/timeout checks as v0.1 test_tts.py, file is <stem>.mp3
def test_elevenlabs_non_audio_raises(...)
def test_render_falls_back_to_say(...)          # elevenlabs raises → returns (<stem>.aiff, "say"), log mentions elevenlabs
def test_render_uses_configured_provider(...)   # elevenlabs ok → (<stem>.mp3, "elevenlabs")
def test_audio_stem_is_per_token()              # audio_stem("abc") == home()/"speech-abc"
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_voices.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Delete `tts.py` and `tests/test_tts.py`. Leave `speaker.py` unchanged until Task 5, except for what's needed to keep the suite green.
- [ ] **Step 4: Run** `uv run --with pytest pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: voice registry with Mac voice and ElevenLabs providers`.

### Task 4: Kokoro

**Files:**
- Create: `scripts/kokoro_tts.py`, `scripts/talkback/voices/kokoro.py`
- Test: `tests/test_kokoro.py`

**Interfaces:**
- Consumes: voice provider shape (Task 3), `config.home`
- Produces:
  - `kokoro_tts.py`: PEP 723 header (`requires-python = ">=3.10,<3.14"`, `dependencies = ["kokoro-onnx==0.6.1", "soundfile"]`). CLI `--voice V --out PATH --home DIR`, text on stdin. Downloads any missing model files (URLs from Global Constraints) into `DIR/kokoro/` by writing to `.part` and then renaming. Writes a wav file. Exits non-zero on error with a one-line message on stderr.
  - `voices.kokoro.synthesize(text, s, key, out) -> Path`: runs `["uv", "run", "--script", <scripts>/kokoro_tts.py, "--voice", s.voice, "--out", f"{out}.wav", "--home", str(home())]` with `input=text`, timeout `voices.kokoro.TIMEOUT` (20). On timeout it kills the process group. Raises on a non-zero exit or missing output. Seam: `voices.kokoro._popen = subprocess.Popen`.
  - `voices.kokoro.models_present() -> bool` (both files exist in `home()/kokoro/`)

- [ ] **Step 1: Write failing tests** (fake `_popen`):

```python
def test_kokoro_command_line(...)               # args start ["uv","run","--script"], include --voice af_heart, --out <stem>.wav; text on stdin
def test_kokoro_without_uv_falls_back(...)      # _popen raises FileNotFoundError → voices.render returns (<stem>.aiff, "say")
def test_kokoro_timeout_kills_process_and_falls_back(...)  # fake proc whose communicate raises TimeoutExpired → killpg called; render falls back to say
def test_kokoro_nonzero_exit_raises(...)
def test_models_present(tmp_path)
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_kokoro.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** both files. Kokoro API for the script: `Kokoro(model_path, voices_path).create(text, voice=voice, speed=1.0, lang="en-us")` returns `(samples, sample_rate)`, and `soundfile.write(out, samples, sample_rate)` saves it. Confirm against the installed package in Step 5.
- [ ] **Step 4: Run** `uv run --with pytest pytest -q`. Expected: all pass.
- [ ] **Step 5: Real check:** `echo "Kokoro is working." | uv run --script scripts/kokoro_tts.py --voice af_heart --out /tmp/talkback-scratch/k.wav --home /tmp/talkback-scratch/khome`. The first run downloads about 140 MB. Expected: exit 0 and a non-empty wav. Run it a second time and record the time per sentence in `docs/decisions.md`.
- [ ] **Step 6: Commit** `feat: Kokoro local voice via uv`.

### Task 5: Speaker and playback on the new providers

**Files:**
- Modify: `scripts/talkback/speaker.py`, `scripts/talkback/playback.py`, `scripts/hook_stop.py`, `scripts/hook_session_start.py`
- Test: `tests/test_speaker.py`, `tests/test_playback.py`, `tests/test_hooks.py`

**Interfaces:**
- Consumes: `summarizers.run`, `voices.render`, `playback.claim_and_stop`, `playback.is_current`
- Produces:
  - `speaker.speak(reply: str) -> None`. Order: `token = claim_and_stop()`, `clean`, return if empty, `summary = summarizers.run(text, cfg.summary)`, `path, _ = voices.render(summary, cfg.voice, token)`, return if `not is_current(token)`, `playback.play_file(path, token)`. Always delete `path` afterwards (in `finally`).
  - `playback.play_file(path, token)` unchanged signature. After `proc.wait()`, remove `playback.pid` if it still contains this process's PID. `play_say` is removed (the Mac voice now renders to a file).
  - `hook_stop`: logs `hook_stop: no last_assistant_message` when the field is missing or empty.
  - `hook_session_start`: calls `summarizers.ollama.warm` only when `summary.provider == "ollama"`.

- [ ] **Step 1: Write failing tests:**

```python
def test_speaker_plays_rendered_file_and_deletes_it(...)
def test_speaker_stale_after_render_does_not_play_and_deletes(...)
def test_speaker_code_only_is_silent(...)        # keep from v0.1
def test_pid_file_removed_after_playback(...)    # fake proc pid 4242 → after play_file, playback.pid gone
def test_pid_file_kept_if_overwritten(...)       # during wait another pid written → file left alone
def test_stop_hook_logs_missing_message(...)     # '{"other":1}' → log has "no last_assistant_message"
def test_session_start_warms_only_for_ollama(...)
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_speaker.py tests/test_playback.py tests/test_hooks.py -q`. Expected: the new tests fail.
- [ ] **Step 3: Implement.** Remove `play_say` and its tests.
- [ ] **Step 4: Run** `uv run --with pytest pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: speaker uses chosen providers; per-token audio and pid clean-up`.

### Task 6: `/talkback:key`

**Files:**
- Create: `scripts/set_key.py`, `commands/key.md`
- Test: `tests/test_set_key.py`

**Interfaces:**
- Consumes: `config.KEY_SERVICES`
- Produces: `set_key.main(argv: list[str]) -> int`. `argv` is `[service]` or `[service, "remove"]`. Seams: `set_key._run = subprocess.run`.
  - Dialog: `_run(["osascript", "-e", <script>], capture_output=True, text=True)`. The AppleScript is `text returned of (display dialog "Paste your <Service> API key" with title "talkback" default answer "" with hidden answer)`. A non-zero exit means cancelled.
  - Save: `_run(["security", "-i"], input=f'add-generic-password -U -s talkback-{service} -a talkback -w "{key}"\n', capture_output=True, text=True)`. Reject keys containing `"`, `\` or newlines (`Key has unexpected characters; nothing saved.`).
  - Remove: `_run(["security", "delete-generic-password", "-s", f"talkback-{service}", "-a", "talkback"], capture_output=True)`.
  - Output (exact): `Saved your <service> key in the macOS Keychain.` / `Cancelled, nothing saved.` / `Removed your <service> key.` / `No <service> key was stored.` / `Usage: /talkback:key elevenlabs|anthropic|openai [remove]`. Exit codes 0/0/0/0/1.

- [ ] **Step 1: Write failing tests:**

```python
def test_saves_key_via_stdin(...)            # fake osascript returns "sk-123\n"; security called with ["security","-i"] and "sk-123" only in input
def test_key_never_in_argv_or_output(...)    # across save, and save where security returns 1: "sk-123" not in any argv, not in capsys out/err, not in log.txt
def test_cancel_saves_nothing(...)           # osascript returncode 1 → no security call, prints "Cancelled, nothing saved."
def test_remove(...)
def test_unknown_service_usage(...)          # exit 1
def test_rejects_quote_in_key(...)
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_set_key.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `set_key.py` and `commands/key.md`. The command file has `allowed-tools: Bash`, `disable-model-invocation: true`, and `argument-hint: elevenlabs|anthropic|openai [remove]`. Its body is ``!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/set_key.py" $ARGUMENTS` `` followed by `Repeat the line above to the user. Never ask the user to paste a key into the chat.`
- [ ] **Step 4: Run** `uv run --with pytest pytest -q`. Expected: all pass.
- [ ] **Step 5: Real check:** run `python3 scripts/set_key.py openai`, and cancel the pop-up. Expected: the dialog appears with a hidden field, and the script prints `Cancelled, nothing saved.`
- [ ] **Step 6: Commit** `feat: /talkback:key stores API keys via a hidden macOS dialog`.

### Task 7: `/talkback:setup`

**Files:**
- Create: `scripts/status.py`, `scripts/configure.py`, `scripts/test_voice.py`, `commands/setup.md`
- Test: `tests/test_setup_scripts.py`

**Interfaces:**
- Consumes: `config.validate`, `config.get_key`, `config.KEY_SERVICES`, `summarizers.run`, `voices.render`, `voices.kokoro.models_present`, `playback`
- Produces:
  - `status.main() -> int`: prints sections `Settings`, `Problems`, `Ollama` (reachable or not, and model names, via `GET {url}/api/tags` with a 2 s timeout), `uv` (found via `shutil.which`), `Kokoro model` (present or not), and `Keys` (`elevenlabs: set` / `not set` for each). It never prints key values.
  - `configure.main(argv: list[str]) -> int`: each arg is `section.field=value`. Valid sections are `summary` and `voice`. Valid fields: `provider`, `model`, `url` for summary; `provider`, `voice`, `model` for voice. Providers must be from the exact lists. Writes merged JSON to `config.json` and prints `Saved: summary.provider=anthropic, …`. Errors print `Unknown …` and exit 1, writing nothing. `field=` with an empty value removes that field, so the default applies.
  - `test_voice.main(argv) -> int`: runs the configured summary on a fixed sample reply, then renders and plays it. It prints `Summary by: <provider or "first sentence (fallback)">` and `Voice: <provider>[ (fallback from <configured>)]`. `--long` sets `voices.kokoro.TIMEOUT = 600` for the first Kokoro download.
  - `commands/setup.md`: tells Claude to run `status.py`, explain the options with their costs (from the README table), ask what the user wants, apply it with `configure.py`, send the user to `/talkback:key <service>` for paid options, and finish with `test_voice.py --long`. It must never ask for a key in the chat.

- [ ] **Step 1: Write failing tests:**

```python
def test_status_never_prints_keys(monkeypatch, capsys)  # ELEVENLABS_API_KEY="sk-secret" → output has "elevenlabs: set", not "sk-secret"
def test_status_reports_problems(tmp_path, capsys)     # bad provider in config.json → listed under Problems
def test_configure_writes_and_merges(tmp_path)         # two calls merge; file valid JSON
def test_configure_rejects_unknown(tmp_path, capsys)   # "voice.provider=openai" → exit 1, file unchanged
def test_configure_empty_value_removes_field(tmp_path)
def test_test_voice_reports_fallback(monkeypatch, capsys)  # summarizers fail, voice falls back → both lines say fallback
```

- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_setup_scripts.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the three scripts and `commands/setup.md` (`allowed-tools: Bash`, `disable-model-invocation: true`).
- [ ] **Step 4: Run** `uv run --with pytest pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: /talkback:setup with status, configure and voice test`.

### Task 8: README, real checks, clean install

**Files:**
- Modify: `README.md` (rewrite), `docs/decisions.md`

- [ ] **Step 1: README.** Cover:
  - what talkback is, with a macOS-only note
  - quick start (zero setup)
  - a table of summary and voice options with cost and setup
  - the recommended path: Mac voice → Kokoro → paid
  - commands: `on`, `off`, `setup`, `key`
  - settings reference
  - keys and privacy, including the note about `ANTHROPIC_API_KEY` billing
  - troubleshooting (log location)
  - development
- [ ] **Step 2: Real checks** (in `TALKBACK_HOME` scratch folders, not the user's real settings):
  - Ollama with `qwen3:8b`
  - `none`
  - the Mac voice with text starting with "-"
  - Kokoro through `test_voice.py --long`
  - the key dialog (cancel)
  - `claude -p --plugin-dir . "/talkback:setup"` reaching the status output

  Expected: each works, or falls back as designed. Record results in `docs/decisions.md`.
- [ ] **Step 3: Clean install:** with an empty `TALKBACK_HOME`, run the Stop hook by path on the built-in Python. Expected: the Mac voice speaks a summary (or the first sentence if `llama3.2:3b` isn't pulled), with no errors in the log.
- [ ] **Step 4: Validate** with `claude plugin validate .`. Expected: passes, with no README or license problems.
- [ ] **Step 5: Run** `uv run --with pytest pytest -q`. Expected: all pass.
- [ ] **Step 6: Commit** `docs: README for choosable models; record real-check results`.
