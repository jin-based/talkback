# talkback: multi-session queue, "Claude needs you" alerts, questions, voice picker (design)

Date: 2026-11-01
Status: draft, waiting for review
Builds on: `2026-11-01-claude-voice-talkback-design.md` and `2026-11-01-talkback-choosable-models-design.md`. Everything there still holds unless this file changes it.

## Goal

Make talkback the tool for running Claude Code hands-free, including across several sessions at once:

1. **"Claude needs you" alerts:** speak when Claude needs a permission, has been waiting for a reply, or asks a multiple-choice question.
2. **Questions read word for word:** when a reply ends with a question, speak the summary and then the question itself.
3. **Multi-session aware:** summaries from different sessions queue instead of cutting each other off; project names are spoken when more than one session is active; optional per-project voices.
4. **Voice picker:** list voices by name for the current provider, preview one, and pick it by name.

**Success:** with three sessions running, the user hears every session's summary in order, knows which project each came from, hears when any session needs approval or is waiting, and can say "use Bella for horizon" without ever copying a voice ID. The rule from v0.1 still holds: talkback never slows down or breaks Claude Code.

## Decisions

| Topic | Decision |
|---|---|
| Overlapping sessions | Queue in arrival order; never cut off another session |
| Within one session | Newest wins: a newer reply makes that session's unplayed items stale |
| Sending a message | Stops only that session: cancels its queued items, and stops current audio only if it belongs to that session |
| Project names | Spoken only when 2+ sessions were active in the last 5 minutes |
| Project name source | Folder name of `CLAUDE_PROJECT_DIR` (else the hook's `cwd`), renameable in settings |
| Per-project voices | Off by default; the user picks (plain words via the settings skill); same provider as the main voice |
| Alerts | Permission requests, waiting-for-reply, multiple-choice questions; all on by default; each can be turned off |
| Alert priority | Alerts go to the front of the queue and always start with the project name |
| Question read-aloud | Summary, then "It asks: <question>"; >40-word questions summarized; options read as "Option one…" |
| Voice picker | `/talkback:voices` and plain words; list by name, preview on request, pick by name |
| Stale items | Dropped if they waited more than 2 minutes |

## Settings additions

`~/.claude/talkback/config.json` gains two optional sections. Validation follows the existing rule: a bad section falls back to its defaults, logged, without affecting other sections.

```json
{
  "projects": { "horizon": { "name": "Horizon", "voice": "af_bella" } },
  "alerts":   { "permission": true, "idle": true, "questions": true }
}
```

- `projects` keys are project folder names. `name` (spoken name) and `voice` (voice name or ID for the current voice provider) are both optional strings. Unknown fields are ignored.
- `alerts` fields are booleans; anything not a boolean falls back to `true`, with a log line.

## Components

New modules in `scripts/talkback/` (standard library only, `from __future__ import annotations`, import under `/usr/bin/python3`):

### `sessions.py`
- `project_dir(hook: dict) -> Path`: `CLAUDE_PROJECT_DIR` env if set, else `hook["cwd"]`, else the current directory.
- `project_name(folder: str, cfg) -> str`: `cfg.projects[folder].name` if set, else the folder name.
- `touch(session_id: str) -> None`: records "last seen now" in `home()/sessions/<id>.seen`.
- `active_count(window_s: int = 300) -> int`: the number of `.seen` files touched within the window.
- Per-session tokens replace the global `current.token`:
  - `claim(session_id) -> str`
  - `is_current(session_id, token) -> bool`
  - Stored in `home()/sessions/<id>.token`.

### `queue.py`
- An item is a JSON file in `home()/queue/`, named `<priority>-<time_ns>-<session>.json`, where priority is `0` for alerts and `1` for summaries. Sorting the names gives play order.
- Fields: `session`, `token`, `audio` (path), `kind` (`summary` or `alert`), `created` (epoch seconds).
- `enqueue(item: dict, front: bool) -> None` writes the file to a temp name, then renames it.
- `run_player() -> None`:
  - Takes a non-blocking `flock` on `home()/player.lock`. If another player holds it, return.
  - Otherwise loop until the queue is empty: take the first item by name, then delete its JSON.
  - Skip the item, deleting its audio, if it is older than 120 s, its audio is missing, or `is_current(session, token)` is false.
  - Otherwise write `home()/playing.json` `{session, pid}`, play with `afplay`, then delete the audio and `playing.json`.
  - After the loop empties, release the lock, then check once more for items that arrived meanwhile. If any are there, try to become the player again.
- `stop_session(session_id) -> None`: `claim(session_id)` makes its queued items stale. If `playing.json` names this session and its PID's command is `afplay`, send SIGTERM.

### Changes to `speaker.py`
`speak(reply: str, hook: dict) -> None`:

1. `session = hook["session_id"]`, `token = sessions.claim(session)`, `sessions.touch(session)`.
2. Clean the reply. If nothing is left, stop.
3. Get the summary (unchanged).
4. Add the question part (see `question.py`).
5. Prefix `"<project name>: "` if `sessions.active_count() >= 2`.
6. Voice is `cfg.projects[folder].voice` if set, else `cfg.voice.voice`.
7. Render the audio: `voices.render` with the voice override, per-token file as today.
8. If the token is still current, `enqueue(kind="summary", front=False)`. Then `run_player()`.

`playback.py`'s global `claim_and_stop` and `play_file` are replaced by `queue` and `sessions`. Its safe-kill helpers (`_comm`, `_kill`, the lock) are reused.

### `question.py`
- `extract(reply: str) -> tuple[str, list[str]] | None` works on the raw reply, before cleaning, with code blocks removed:
  - The question is the last sentence, if it ends with `?`.
  - Options are list lines (`1.`, `-`, `*`, `a)`) directly after the question, or directly before it if the question asks to choose. At most 6 options, each cleaned.
- `spoken(question, options, cfg) -> str`:
  - `"It asks: <question>"` plus `" Option one, <a>. Option two, <b>."`
  - If the question is over 40 words, pass it to the summary model with the prompt `"Rewrite this question in under 25 plain words:"`. On failure, cut it to 40 words.

### `alerts.py`
- `on_permission_request(hook)` saves `home()/pending/<session>.json` with `{tool_name, short}`. Rules for `short`:
  - Bash: `run ` + the first 8 words of `tool_input.command`.
  - Edit/Write: `edit ` + the file name of `file_path`.
  - Other tools: `use <tool_name>`.
  - It prints nothing and exits 0, so the normal dialog is unchanged.
- `on_notification(hook)`, by `notification_type`:
  - `permission_prompt`: if `alerts.permission`, say `"<project> needs approval: <short>"`, using the pending file if it is under 60 s old, else the notification `message`. Delete the pending file afterwards.
  - `idle_prompt`: if `alerts.idle`, say `"<project> is waiting for you."`
  - Anything else is ignored.
- `on_ask_user_question(hook)`: if `alerts.questions` and `tool_input` contains question text, say `"<project> asks: <question> Option one, …"`.
- Every alert renders with the session's voice and enqueues with `front=True`, then runs `run_player()`.
- Alerts don't claim the session token. They use the current token, so a message the user sends afterwards cancels them too.

### Voice picker
- `voices/catalog.py`: `list_voices(provider, key) -> list[Voice]`, where `Voice(name, id, description)`.
  - `say`: parse `say -v '?'` and keep `en_*` locales.
  - `kokoro`: a fixed table of its English voices, with id, accent and gender (`af_heart`, `af_bella`, `af_nicole`, `af_sarah`, `af_sky`, `am_adam`, `am_michael`, `bf_emma`, `bf_isabella`, `bm_george`, `bm_lewis`). The exact list is confirmed against `voices-v1.0.bin` during the build.
  - `elevenlabs`: `GET https://api.elevenlabs.io/v1/voices` with `xi-api-key` and an 8 s timeout. Each voice's `name`, `voice_id` and `labels` become the description.
- `scripts/voices.py`:
  - `voices.py list` prints a numbered list for the current provider.
  - `voices.py preview <name>` plays the sample sentence `"Hi, this is <name>."` in that voice.
  - `voices.py use <name> [--project <folder>]` resolves the name to an ID and saves it as `voice.voice`, or under `projects.<folder>.voice`.
  - Name matching is case-insensitive, and exact matches win. If several voices match, it prints the matches and exits 1 so Claude can ask which one.
- `commands/voices.md` shows the list. The `talkback-settings` skill gains instructions for preview, use, per-project voices, project renames and the alert switches. `configure.py` gains `projects.<folder>.name|voice` and `alerts.<type>=on|off`.

### Hooks (`hooks/hooks.json` additions)

| Event | Matcher | Script | Mode |
|---|---|---|---|
| PermissionRequest | (all) | `hook_permission.py` (store details, no output) | async |
| Notification | `permission_prompt\|idle_prompt` | `hook_notification.py` | async |
| PreToolUse | `AskUserQuestion` | `hook_ask.py` (no output) | async |

- **Changed:** `hook_stop.py` passes the whole hook input to `speak`.
- **Changed:** `hook_prompt_submit.py` calls `queue.stop_session(session_id)`.
- **Changed:** `/talkback:off` stops all playback and empties the queue.
- All hooks still always exit 0 and print nothing.

## To verify during the build

- **What `AskUserQuestion` passes to PreToolUse in `tool_input`:** run a logging hook once. If question text isn't there, drop `hook_ask.py` and the `alerts.questions` switch, and say so in the README.
- **The `permission_prompt` message text:** log one for use as the fallback.
- **That an async PermissionRequest hook with no output leaves the dialog unchanged:** a real check.

## Error handling

| Situation | Result |
|---|---|
| Queue file unreadable or invalid | Item deleted and logged; the player continues |
| Player crashes mid-queue | Lock released when the process ends; the next hook run becomes the player and continues |
| Item waited over 2 minutes | Dropped |
| Pending permission details missing or old | Speak the notification's own message |
| ElevenLabs voice list fails | `voices.py` says why, with exit 1; other providers unaffected |
| Name matches several voices | List the matches, exit 1; nothing saved |
| Invalid `projects` or `alerts` section | Defaults for that section, logged |

## Testing

- **Unit tests (offline):**
  - Queue: order by priority then time, stale-token skip, over-age drop, a missing audio file, player lock exclusivity, re-check after unlock.
  - `stop_session`: only the session's items, kill only when it's playing.
  - `active_count` window and the project-name prefix rule.
  - Project voice override.
  - Question extraction: plain question, numbered and bulleted options, no question, a question inside code, a long question.
  - Alert text for Bash, Edit and other tools; pending-file age; the idle alert; alert switches off.
  - Catalog parsing for `say -v '?'` output and the ElevenLabs JSON; name matching (exact, case, ambiguous).
  - `configure.py` new fields; settings validation for the new sections.
  - System-Python import test extended to every new module.
- **Real checks:**
  - Two scratch "sessions" finishing at once queue in order.
  - Sending a message cancels only that session.
  - A real permission prompt is spoken.
  - The idle alert fires after about 60 s.
  - The AskUserQuestion logging test.
  - The voice list for each provider, including ElevenLabs with the user's key.
  - Preview and use by name.

## Out of scope

- Mixing voice providers per project
- Volume control
- Speaking subagent completions
- Linux/Windows
