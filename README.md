# talkback

**Hear what Claude did.** talkback is a [Claude Code](https://claude.com/claude-code) plugin that speaks a short summary of each Claude reply out loud. It also speaks up when Claude needs you.

Pair it with Claude Code's built-in voice input and you can work hands-free:

- **Talk:** hold Space and speak your request.
- **Listen:** hear *"Fixed the login bug, and all tests pass."*
- **Get alerts:** hear *"my-app needs approval: run git push"* when Claude is waiting on you.

It works with free, local models or with paid services; you choose. If anything fails, it falls back quietly and never slows Claude Code down.

> **macOS only** for now. talkback uses the Mac's audio player, voices and Keychain.

**Contents:** [Requirements](#requirements) · [Install](#install) · [Quick start](#quick-start) · [What you'll hear](#what-youll-hear) · [Choose your models](#choose-your-models) · [Commands](#commands) · [Several sessions](#several-sessions-at-once) · [Keys and privacy](#api-keys-and-privacy) · [Settings file](#settings-file) · [Troubleshooting](#troubleshooting) · [Update and uninstall](#update-and-uninstall) · [How it works](#how-it-works) · [Development](#development)

## Requirements

- macOS, with the Python 3 that comes with it. talkback needs no other packages.
- Claude Code 2.1.275 or later for the one-step install; any recent version for the two-step install.
- **Optional,** for better summaries: [Ollama](https://ollama.com) with a small model (`ollama pull llama3.2:3b`).
- **Optional,** for the free natural voice (Kokoro): [`uv`](https://docs.astral.sh/uv/) (`brew install uv`).
- **Optional,** for paid options: an ElevenLabs, Anthropic or OpenAI API key.

## Install

In Claude Code:

```
/plugin install talkback --marketplace jin-based/talkback
```

Or in two steps:

```
/plugin marketplace add jin-based/talkback
/plugin install talkback@talkback
```

From your shell (Claude Code 2.1.292 or later): `claude plugin install talkback --marketplace jin-based/talkback`

Then **start a new Claude Code session.** Plugins load when a session starts.

## Quick start

1. **Just use Claude.** When Claude finishes a reply, you'll hear it.
   - With no setup, talkback reads the reply's first sentence in the built-in Mac voice.
   - If Ollama is running with `llama3.2:3b`, you hear a real one-sentence summary instead.
2. **Make it sound better:** run **`/talkback:setup`**. Claude shows what's available, helps you choose a summary model and voice, and plays a test sentence. The free upgrade is the Kokoro voice.
3. **Talk to Claude too:** type `/voice` to turn on Claude Code's voice input, then hold **Space** while you speak and release to insert the text.

## What you'll hear

| When | Example | Turn off with |
|---|---|---|
| Claude finishes a reply | *"Fixed the login bug and all tests pass."* | `/talkback:off` |
| The reply ends with a question for you | *"Updated the API. It asks: should I also update the docs?"* | (part of the summary) |
| Claude needs permission (after the prompt has waited ~6 s) | *"my-app needs approval: run git push"* | `alerts.permission` |
| Claude is waiting for your reply (~60 s after it finished) | *"my-app is waiting for you."* | `alerts.idle` |
| Claude asks you a multiple-choice question | *"my-app asks: which database? Option one, Postgres. Option two, SQLite."* | `alerts.questions` |

Alerts are all on by default and jump ahead of summaries. To turn one off, ask in plain words (*"stop the waiting alerts"*) or use `/talkback:setup`.

Questions are read word for word, including their options. Very long questions are shortened by your summary model.

## Choose your models

talkback uses two models: a **summary model** that turns Claude's reply into one sentence, and a **voice** that reads it aloud. Change either with `/talkback:setup`, or just ask (*"use Kokoro"*, *"use Haiku for the summaries"*).

### Summary model

| Option | Cost | Setup | Notes |
|---|---|---|---|
| `ollama` (default) | Free | [Ollama](https://ollama.com) + `ollama pull llama3.2:3b` | Private, runs on your Mac. Any Ollama model works |
| `openai` | Free (local) or paid | A server URL and model name; a key only for paid services | Any OpenAI-compatible server: LM Studio, llama.cpp, OpenRouter, OpenAI. Pick a chat model such as `gpt-4o-mini`; some newer reasoning models reject the `max_tokens` field |
| `anthropic` | Paid (a fraction of a cent per reply) | Anthropic API key | Claude Haiku (`claude-haiku-5-5`) by default; any Claude model works |
| `none` | Free | Nothing | Reads the reply's first sentence |

If the summary model isn't available, talkback uses the first sentence instead.

### Voice

| Option | Cost | Setup | Notes |
|---|---|---|---|
| `say` (default) | Free | Nothing | Built-in Mac voice. "Premium" voices downloaded in System Settings sound better |
| `kokoro` | Free | `uv`; a ~140 MB model downloads on first use | **Recommended upgrade.** Natural-sounding, runs on your Mac, about 1 s per sentence. `/talkback:setup` does the first download. If you switch by hand, the Mac voice fills in while it downloads |
| `elevenlabs` | Paid (free credits to start) | ElevenLabs API key | The most natural voice. Pick from your library by name with `/talkback:voices`. For the list, the key needs the **Voices: Read** permission, as well as Text to Speech |

If the chosen voice fails (no key, no credits, offline), talkback uses the Mac voice instead.

**Suggested path:** start with the defaults, switch the voice to Kokoro (free), and add a paid option only if you want it.

### Picking a voice by name

Run **`/talkback:voices`** to list the voices for your current provider: your ElevenLabs library, Kokoro's 28 English voices, or your Mac's English voices. Then say:

- *"preview Bella"* to hear a short sample,
- *"use Bella"* to switch,
- *"use Bella for the my-app project"* to give one project its own voice.

## Commands

| Command | What it does |
|---|---|
| `/talkback:setup` | See what's set and what's available, choose models, test the voice |
| `/talkback:voices` | List voices by name; then preview or pick one |
| `/talkback:key <service>` | Save an API key (`elevenlabs`, `anthropic` or `openai`) through a private pop-up |
| `/talkback:key <service> remove` | Delete a saved key |
| `/talkback:on` / `/talkback:off` | Turn talkback on or off (off also stops anything playing) |

You don't have to remember these. Ask in plain words, such as *"switch the voice to Kokoro"*, *"what voices are there?"* or *"turn talkback off"*, and talkback's settings skill handles it.

## Several sessions at once

Running Claude in more than one project? talkback keeps them apart:

- **Nothing gets cut off.** Speech from different sessions waits in line and plays in order.
- **You know which project spoke.** When two or more sessions have been active in the last 5 minutes, each summary starts with the project's folder name: *"my-app: the build passes."*
- **Newest wins within a session.** If a session finishes again before its last summary played, you only hear the newer one.
- **Sending a message stops only that session's speech.** The other sessions keep their place in line.
- **Optional per-project voices and names:** *"use Bella for my-app"*, *"call this project My App"*.

## API keys and privacy

- `/talkback:key` opens a macOS pop-up with a hidden field and stores the key in your **macOS Keychain**. The key never goes into the chat, into Claude's context, or into a file. Never paste a key into the chat.
- **Environment variables work too:** `ELEVENLABS_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. They take priority over the Keychain.
  - `OPENAI_API_KEY` is used only when `summary.url` is OpenAI itself. For OpenRouter or other servers, save that service's key with `/talkback:key openai`.
  - If your Claude Code itself runs on `ANTHROPIC_API_KEY`, choosing `anthropic` bills summaries to that same key.
- **What leaves your Mac:**
  - With `ollama`, `none`, `say` and `kokoro`, your text never leaves your Mac. Kokoro downloads its packages and model from PyPI and GitHub the first time.
  - Online summary options (`anthropic`, or `openai` pointed at a hosted service) receive the cleaned text of Claude's reply, up to its last 4,000 characters.
  - `elevenlabs` receives only the one sentence it speaks.
- **Secrets in commands are never spoken.** In permission alerts, anything that could be a password, token or key is spoken as "a value": values after `-p`, `--token`, `-H` or `Bearer`, `NAME=value`, `user:pass`, and long strings. Web addresses are spoken as "a web address".

## Settings file

`/talkback:setup` and plain-word requests edit this for you, but you can also edit `~/.claude/talkback/config.json` by hand. Leave out any field to use its default.

```json
{
  "summary":  { "provider": "ollama", "model": "llama3.2:3b", "url": "http://localhost:11434" },
  "voice":    { "provider": "kokoro", "voice": "af_heart" },
  "projects": { "my-app": { "name": "My App", "voice": "af_bella" } },
  "alerts":   { "permission": true, "idle": true, "questions": true }
}
```

| Field | Default |
|---|---|
| `summary.provider` | `ollama` (or `openai`, `anthropic`, `none`) |
| `summary.model` | `ollama`: `llama3.2:3b` · `openai`: `gpt-4o-mini` · `anthropic`: `claude-haiku-5-5` |
| `summary.url` | `ollama`: `http://localhost:11434` · `openai`: `https://api.openai.com/v1` |
| `voice.provider` | `say` (or `kokoro`, `elevenlabs`) |
| `voice.voice` | `say`: system voice · `kokoro`: `af_heart` · `elevenlabs`: `21m00Tcm4TlvDq8ikWAM` |
| `voice.model` | `elevenlabs`: `eleven_flash_v2_5` |
| `projects.<folder>` | none. `name` is the spoken project name and `voice` is that project's voice (same provider) |
| `alerts.permission` / `idle` / `questions` | `true` |

A typo or unknown value resets only that section to its defaults, and `/talkback:setup` points it out.

## Troubleshooting

| Problem | What to do |
|---|---|
| I hear nothing | Start a new session after installing. Check talkback is on (`/talkback:on`) and your Mac's volume is up. Run `/talkback:setup`: its test reports what actually played |
| I hear the Mac voice instead of my chosen voice | The chosen voice failed, so talkback fell back. `/talkback:setup` says why (missing key, no credits, Kokoro still downloading) |
| I hear the first sentence instead of a summary | The summary model wasn't available: Ollama not running, model not pulled, or a key missing. `/talkback:setup` shows which |
| I hear everything twice | talkback is loaded twice, for example installed **and** started with `--plugin-dir`. Use one or the other |
| `/talkback:voices` fails for ElevenLabs | Edit your key on elevenlabs.io (Developers, API Keys) to allow **Voices: Read** |
| The key pop-up doesn't appear | Use an environment variable instead (see [Keys and privacy](#api-keys-and-privacy)) |

Errors are logged to `~/.claude/talkback/log.txt`. Set `TALKBACK_HOME` to use a different data folder.

## Update and uninstall

- **Update:** from your shell, `claude plugin marketplace update talkback && claude plugin update talkback@talkback`, or use the `/plugin` menu in Claude Code. Then start a new session. See [CHANGELOG.md](CHANGELOG.md) for what changed.
- **Uninstall:** `/plugin uninstall talkback@talkback` (and optionally `/plugin marketplace remove talkback`).
- **Remove its data:** delete `~/.claude/talkback/`, which holds settings, the log, the Kokoro model and temporary audio.
- **Remove saved keys:** run `/talkback:key <service> remove` before uninstalling, or delete the `talkback-elevenlabs`, `talkback-anthropic` and `talkback-openai` items in the Keychain Access app.

## How it works

talkback is a set of Claude Code hooks plus a few commands:

1. **When Claude finishes** (Stop hook), talkback takes the reply, strips code, file paths, tables and markdown, asks the summary model for one sentence, and adds the question if the reply ends with one.
2. **It renders the speech** with your voice. Then it drops the audio into a small **queue** in `~/.claude/talkback/queue/`.
3. **One player at a time** plays the queue in order, alerts first. Whichever session adds an item starts the player if none is running, and the player exits when the queue is empty. Nothing runs in the background otherwise.
4. **Alerts** come from Claude Code's permission, notification and question hooks.
5. **Sending a message** (UserPromptSubmit hook) marks that session's queued speech as outdated and stops it if it's playing.

Everything runs in the background; Claude Code never waits for talkback.

## Development

```sh
uv run --with pytest pytest -q     # tests: offline, no services or audio needed
claude plugin validate .
claude --plugin-dir .              # try your local copy (uninstall the marketplace copy first, or you'll hear everything twice)
```

| Path | What's there |
|---|---|
| `scripts/talkback/` | The plugin's code. `speaker.py` turns a reply into queued speech; `queue.py` handles the shared queue and player; `alerts.py`, `question.py`, `sessions.py` and `clean.py` do what their names say; `summarizers/` and `voices/` hold one module per provider |
| `scripts/*.py` | Entry points: hook scripts (`hook_*.py`) and the scripts behind the commands (`configure.py`, `status.py`, `voices.py`, `set_key.py`, `test_voice.py`, `set_enabled.py`); `kokoro_tts.py` runs Kokoro in its own `uv` environment |
| `hooks/hooks.json` | Which hook runs which script |
| `commands/`, `skills/` | The slash commands and the plain-words settings skill |
| `tests/` | The test suite |
| `docs/` | Design notes; see [docs/README.md](docs/README.md) |

The plugin uses only the Python standard library and runs on the Python that ships with macOS (3.9+). Issues and pull requests are welcome.

## License

[MIT](LICENSE)
