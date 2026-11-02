# talkback Sessions, Alerts, Questions and Voice Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Queue spoken items across Claude sessions with per-session cancel and project names. Speak "Claude needs you" alerts. Read trailing questions word for word. Let users list, preview and pick voices by name.

**Architecture:** Speakers render audio as today, then drop a JSON item into `home()/queue/`. A temporary player (whoever gets `player.lock`) plays items in name order, alerts first, skipping stale ones. Per-session tokens in `home()/sessions/` replace the global token. New hook scripts feed alerts into the same queue. A voice catalog per provider powers `scripts/voices.py`.

**Tech Stack:** Python 3.9+ standard library only in `scripts/` (`from __future__ import annotations`; must import under `/usr/bin/python3`). Tests: `uv run --with pytest pytest -q`. macOS `afplay`, `say`, `ps`.

**Spec:** `docs/superpowers/specs/2026-11-01-talkback-sessions-alerts-voices-design.md`

## Global Constraints

- Hooks always exit 0, print nothing to stdout, and catch and log every exception. The new hooks are `async: true`.
- Queue item file name: `f"{priority}-{time.time_ns():020d}-{safe(session)}.json"`, priority `0` for alerts and `1` for summaries. Write to `.tmp`, then `os.replace`. `safe()` keeps `[A-Za-z0-9_-]` and replaces everything else with `_`, capped at 64 chars.
- Constants (exact): stale age `MAX_AGE_S = 120`; active window `ACTIVE_WINDOW_S = 300`; prefix when `active_count() >= 2`; pending permission valid `PENDING_MAX_AGE_S = 60`; question summarized if over `40` words, with the prompt `Rewrite this question in under 25 plain words:`; at most `6` options; permission command shortened to its first `8` words.
- Spoken text (exact): `"<project>: <summary>"` (prefix rule); `" It asks: <question>"`; options `" Option one, <a>. Option two, <b>."` (number words one to six); `"<project> needs approval: <short>"`; `"<project> is waiting for you."`; `"<project> asks: <question>"` + options; preview `"Hi, this is <name>."`.
- Permission `short`: Bash → `run <first 8 words>`; Edit/Write/MultiEdit/NotebookEdit → `edit <file name>`; other → `use <tool_name>`. Any word of 20+ chars from `[A-Za-z0-9_\-+/=.]` is replaced with `a long value` (don't speak or send secrets).
- Settings: new sections `projects` (`{folder: {"name": str, "voice": str}}`) and `alerts` (`permission`, `idle`, `questions`: bool, default `true`), validated per section like the existing ones.
- Plugin version becomes `0.2.0` (installed copies only update when the version changes).
- Work on branch `feat/sessions-alerts-voices`.

## Review Focus

1. **The player exits just as a new item arrives:** the new speaker fails to get the lock and returns, and the player unlocks without having seen the item, so it's stranded. The player must re-check after unlocking. Pinned in Task 3 (`test_item_arriving_during_unlock_is_played`).
2. **A stale `playing.json`** (player crashed; PID reused by another program) must not lead `stop_session` to kill a non-`afplay` process. Pinned in Task 3 (`test_stop_session_ignores_non_afplay_pid`).
3. **Secrets in a permission prompt:** a Bash command like `curl -H "Authorization: Bearer sk-abc…"` must not be spoken or sent to ElevenLabs. Pinned in Task 6 (`test_permission_short_redacts_long_values`).
4. **False question detection:** a `?` inside a code block, inline code or a URL, or a question that isn't the last sentence, must not trigger "It asks". Pinned in Task 5 (`test_question_ignores_code_urls_and_mid_reply`).
5. **Odd session IDs or project folder names** (spaces, slashes, unicode, empty) must not break file names or the spoken prefix. Pinned in Task 2 (`test_safe_names`).

---

### Task 1: Settings for projects and alerts

**Files:** Modify `scripts/talkback/config.py`, `scripts/configure.py`. Test `tests/test_config.py`, `tests/test_setup_scripts.py`.

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) ProjectSettings(name: str, voice: str)`
  - `@dataclass(frozen=True) AlertSettings(permission: bool, idle: bool, questions: bool)`
  - `Config` gains `projects: dict[str, ProjectSettings]` and `alerts: AlertSettings`, defaulting to `{}` and all `True`.
  - `configure.py` accepts `projects.<folder>.name=`, `projects.<folder>.voice=`, and `alerts.<permission|idle|questions>=on|off`. It stores real JSON booleans; empty values remove the field.

- [ ] **Step 1: Branch** with `git switch -c feat/sessions-alerts-voices`.
- [ ] **Step 2: Failing tests:**
  - `test_projects_and_alerts_defaults`
  - `test_projects_parsed`: unknown fields are ignored and non-string values are converted to strings
  - `test_bad_projects_section_falls_back`: a list instead of a dict gives `{}`, logged
  - `test_alert_non_bool_falls_back_true`
  - `test_configure_projects_and_alerts`: `alerts.idle=off` gives `false`; `projects.horizon.voice=af_bella`
  - `test_configure_rejects_bad_alert_value`: `alerts.idle=maybe` exits 1
- [ ] **Step 3: Run** `uv run --with pytest pytest tests/test_config.py tests/test_setup_scripts.py -q`. Expected: the new tests fail.
- [ ] **Step 4: Implement.** **Step 5: Run** `uv run --with pytest pytest -q`. Expected: all pass. **Step 6: Commit** `feat: settings for per-project names/voices and alert switches`.

### Task 2: Sessions

**Files:** Create `scripts/talkback/sessions.py`. Test `tests/test_sessions.py`.

**Interfaces:**
- Produces:
  - `safe(s: str) -> str`
  - `project_dir(hook: dict) -> Path`
  - `project_folder(hook: dict) -> str` (folder name, `"project"` if empty)
  - `project_name(folder: str, cfg) -> str`
  - `touch(session: str) -> None`
  - `active_count(window_s: int = 300) -> int`
  - `claim(session: str) -> str`
  - `is_current(session: str, token: str) -> bool`
  - `current_token(session: str) -> str | None`
  - Files live in `home()/sessions/<safe(session)>.seen|.token`.

- [ ] **Step 1: Failing tests:**
  - `test_project_dir_prefers_env`: `CLAUDE_PROJECT_DIR` wins over `cwd`
  - `test_project_name_override`
  - `test_active_count_window`: set mtimes with `os.utime`; 2 recent plus 1 old gives 2
  - `test_claim_per_session_independent`: claiming A leaves B current
  - `test_safe_names`: `"a/b c"`, `"ünï"`, `""` and a 200-char id give safe, non-empty names of at most 64 chars; `project_folder({"cwd": "/"})` is `"project"`
- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_sessions.py -q`. Expected: FAIL. **Step 3: Implement.** **Step 4: Run** all tests: pass. **Step 5: Commit** `feat: per-session tokens, activity and project names`.

### Task 3: Queue and player

**Files:** Create `scripts/talkback/queue.py`. Modify `scripts/talkback/playback.py`, keeping `_comm`, `_kill`, `locked`, `_popen` and removing `claim`, `is_current`, `claim_and_stop`, `play_file`, `stop_current`. Test `tests/test_queue.py`, replacing the playback tests that cover removed functions.

**Interfaces:**
- Consumes: `sessions.is_current`, `sessions.claim`, `playback._comm`, `playback._kill`, `playback._popen`
- Produces:
  - `enqueue(session: str, token: str, audio: Path, kind: str, front: bool) -> Path`
  - `run_player() -> None`
  - `stop_session(session: str) -> None`
  - `stop_all() -> None` (empties the queue and stops `afplay` if playing)
  - `MAX_AGE_S = 120`
  - `playing.json` holds `{"session", "pid"}`.

- [ ] **Step 1: Failing tests** (fake `_popen` records plays and offers a hook to run code during `wait()`):
  - `test_plays_in_order_alerts_first`: summary A, summary B, then alert C play as C, A, B
  - `test_stale_token_skipped_and_audio_deleted`
  - `test_old_item_dropped`: patch `created`
  - `test_missing_audio_skipped`
  - `test_only_one_player`: while the lock is held by another fd, `run_player` returns without playing
  - `test_item_arriving_during_unlock_is_played`: simulate an enqueue right after the loop sees an empty queue; it still plays
  - `test_corrupt_item_deleted_and_logged`
  - `test_stop_session_only_its_items_and_audio`: session A's queued items go stale and B's stay; playing A gets killed, playing B doesn't
  - `test_stop_session_ignores_non_afplay_pid`
  - `test_stop_all_empties_queue`
- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_queue.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** In `run_player`, loop as `while True: with player lock (non-blocking, else return): drain; then if queue still empty, return`.
- [ ] **Step 4: Run** all tests. Expected: pass, after Task 4 rewires the speaker. If the speaker tests break here, fold the minimum rewiring into this task and ledger it. **Step 5: Commit** `feat: cross-session queue and player`.

### Task 4: Speaker and hooks on the queue

**Files:** Modify `scripts/talkback/speaker.py`, `scripts/hook_stop.py`, `scripts/hook_prompt_submit.py`, `scripts/set_enabled.py`, `scripts/test_voice.py`. Test `tests/test_speaker.py`, `tests/test_hooks.py`.

**Interfaces:**
- Consumes: Tasks 1–3, `voices.render(text, s, token)` (pass a `VoiceSettings` with the project voice override)
- Produces:
  - `speaker.speak(reply: str, hook: dict) -> None` (order as in the spec; `front=False`)
  - `speaker.compose(summary: str, question_part: str, project: str, active: int) -> str`
  - `hook_prompt_submit` calls `queue.stop_session(hook["session_id"])`
  - `/talkback:off` calls `queue.stop_all()`
  - `test_voice.py` enqueues and plays through the queue

- [ ] **Step 1: Failing tests:**
  - `test_speak_enqueues_summary_and_runs_player`
  - `test_prefix_only_when_two_sessions_active`
  - `test_project_voice_override_used`
  - `test_newer_reply_makes_older_stale`
  - `test_prompt_submit_stops_only_its_session`
  - `test_off_stops_all`
  - `test_stop_hook_passes_hook_input`
- [ ] **Step 2: Run** the speaker and hook tests. Expected: FAIL. **Step 3: Implement.** **Step 4: Run** all tests: pass. **Step 5: Commit** `feat: speaker uses the queue, project names and per-project voices`.

### Task 5: Questions read word for word

**Files:** Create `scripts/talkback/question.py`. Modify `speaker.py`. Test `tests/test_question.py`.

**Interfaces:**
- Produces:
  - `extract(reply: str) -> tuple[str, list[str]] | None`
  - `spoken(question: str, options: list[str], s: SummarySettings) -> str` (uses `summarizers.run` with the rewrite prompt for long questions; cuts to 40 words on fallback)
  - `NUMBER_WORDS = ("one", …, "six")`

- [ ] **Step 1: Failing tests:**
  - `test_plain_trailing_question`
  - `test_numbered_options_after_question`
  - `test_bulleted_options_before_choose_question`
  - `test_no_question`
  - `test_question_ignores_code_urls_and_mid_reply`: `?` in fenced code, inline code, a URL query, or a non-final sentence all give `None`
  - `test_options_capped_at_six`
  - `test_long_question_summarized` (fake `summarizers.run`)
  - `test_spoken_format`
  - `test_speaker_appends_question_part`
- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_question.py -q`. Expected: FAIL. **Step 3: Implement.** **Step 4: Run** all tests: pass. **Step 5: Commit** `feat: read trailing questions and options word for word`.

### Task 6: Alerts

**Files:** Create `scripts/talkback/alerts.py`, `scripts/hook_permission.py`, `scripts/hook_notification.py`, `scripts/hook_ask.py`. Modify `hooks/hooks.json`. Test `tests/test_alerts.py`.

**Interfaces:**
- Consumes: `sessions`, `queue.enqueue(front=True)`, `queue.run_player`, `voices.render`, `config.load_config`
- Produces:
  - `alerts.permission_short(tool_name: str, tool_input: dict) -> str`
  - `alerts.on_permission_request(hook) -> None`
  - `alerts.on_notification(hook) -> None`
  - `alerts.on_ask_user_question(hook) -> None`, which reads `tool_input["questions"][0]["question"]` and `[...]["options"][i]["label"]`. If those are missing, it logs `ask: unexpected tool_input keys …` and stays silent.
  - Hook scripts each have `main(stdin_text) -> int`, return 0, print nothing.
  - `hooks.json` gains PermissionRequest (all), Notification (`permission_prompt|idle_prompt`) and PreToolUse (`AskUserQuestion`), all `async: true`.
  - Alerts use `sessions.current_token(session)`, claiming one if there is none, and never claim a new one if a token exists.

- [ ] **Step 1: Failing tests:**
  - `test_permission_short_bash_edit_other`
  - `test_permission_short_redacts_long_values`: `curl -H "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz"` gives text without `sk-`
  - `test_permission_prompt_uses_pending`
  - `test_permission_prompt_old_pending_uses_message`
  - `test_idle_alert_text`
  - `test_alerts_respect_switches`
  - `test_alert_enqueued_front_with_project_prefix_always`
  - `test_ask_user_question_reads_question_and_options`
  - `test_ask_unexpected_shape_silent_and_logged`
  - `test_alert_cancelled_by_later_prompt_submit`
  - `test_hook_scripts_exit_0_no_stdout` (bad JSON included)
- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_alerts.py -q`. Expected: FAIL. **Step 3: Implement.** **Step 4: Run** all tests: pass. **Step 5: Commit** `feat: spoken alerts for permissions, waiting and questions`.

### Task 7: Voice picker

**Files:** Create `scripts/talkback/voices/catalog.py`, `scripts/voices.py`, `commands/voices.md`. Modify `skills/talkback-settings/SKILL.md`. Test `tests/test_catalog.py`.

**Interfaces:**
- Consumes: `config.get_key`, `voices.render`, the queue for preview playback
- Produces:
  - `@dataclass Voice(name: str, id: str, description: str)`
  - `catalog.list_voices(provider: str, key: str | None) -> list[Voice]`
  - `catalog.find(voices: list[Voice], name: str) -> list[Voice]` (exact case-insensitive name match first, else names containing the text)
  - Seams: `catalog._run` for `say -v '?'` and `catalog._get_json(url, headers, timeout)`
  - `scripts/voices.py`:
    - `list` prints `1. Bella — American female (af_bella)`
    - `preview <name>`
    - `use <name> [--project <folder>]`, with exit codes 0 (ok) / 1 (no match, ambiguous, or list failed)
  - `KOKORO_VOICES` table

- [ ] **Step 1: Failing tests:**
  - `test_parse_say_voices_english_only` (sample `say -v '?'` text)
  - `test_elevenlabs_list_parsing_and_headers`
  - `test_elevenlabs_list_failure_raises`
  - `test_kokoro_table_has_default`
  - `test_find_exact_then_contains_case_insensitive`
  - `test_use_saves_id_main_and_project`
  - `test_use_ambiguous_exits_1_saves_nothing`
  - `test_preview_renders_and_plays` (fakes)
- [ ] **Step 2: Run** `uv run --with pytest pytest tests/test_catalog.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Confirm the Kokoro voice names against the downloaded `voices-v1.0.bin` keys, by running a short `uv run --with numpy python -c` against the npz-style file in the scratch Kokoro home. Update the skill: list, preview, use, per-project voices and names, alert switches.
- [ ] **Step 4: Run** all tests: pass. **Step 5: Commit** `feat: list, preview and pick voices by name`.

### Task 8: Version, README, real checks

**Files:** Modify `.claude-plugin/plugin.json` (`"version": "0.2.0"`), `README.md`.

- [ ] **Step 1: README:** a "Several sessions" section (queue, names, per-project voices), "Alerts" (with switches), "Questions", "Voices" (`/talkback:voices`, preview, use), and the new commands.
- [ ] **Step 2: Real checks** (scratch `TALKBACK_HOME`; Python 3.9 built in):
  - Two Stop-hook runs with different session IDs started together: both play in order, the second with a project prefix.
  - A prompt-submit for one session while its item is queued: only that item is dropped.
  - `voices.py list` for `say`, `kokoro`, and `elevenlabs` (with the user's key).
  - `voices.py preview` for Kokoro.
- [ ] **Step 3: Live checks with the user** (needs a real interactive session; ask the user):
  - A permission prompt is spoken and the dialog still works.
  - The idle alert fires after about 60 s.
  - An `AskUserQuestion` is read aloud.
  - Log one `permission_prompt` message. If the `AskUserQuestion` shape differs, fix the parser, or drop the feature and note it in the README.
- [ ] **Step 4: Run** `uv run --with pytest pytest -q` and `claude plugin validate .`. Expected: all pass.
- [ ] **Step 5: Commit** `docs: README for sessions, alerts, questions and voices; v0.2.0`.
