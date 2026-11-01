# talkback: choosable summary and voice models (design)

Date: 2026-11-01
Status: draft, waiting for review
Builds on: `2026-11-01-claude-voice-talkback-design.md` (the working v0.1 plugin). Everything there still holds unless this file changes it.

## Goal

Prepare talkback to be published as a public repo that anyone can use with the models they have or want to pay for:

- **Summary model:** pick any of Ollama (any local model), any OpenAI-compatible server, Claude Haiku, or none.
- **Voice model:** pick any of the Mac voice, Kokoro (free, local), or ElevenLabs (paid).
- **Bring your own key** for any paid option, entered safely: never pasted into the chat, never stored in a plain file.
- **Easy setup:** `/talkback:setup` walks a new user through it, with Claude doing the fiddly part.

**Success:** a stranger on a Mac installs the plugin, hears summaries in the Mac voice with no setup at all, and can switch to Kokoro, ElevenLabs, Haiku or their own Ollama model through `/talkback:setup` without editing files or reading code. The rule from v0.1 still holds: the plugin never slows down or breaks Claude Code.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| How users choose | `/talkback:setup` (Claude-guided) + a settings file they can also edit by hand | Claude can do the setup for the user |
| Summary options | `ollama`, `openai` (OpenAI-compatible), `anthropic`, `none` | User's pick for v1 |
| Voice options | `say`, `kokoro`, `elevenlabs` | User's pick for v1 (OpenAI TTS later) |
| Default summary | `ollama` with `llama3.2:3b` (~2 GB); falls back to the first sentence instant and free when Ollama or the model is missing | Small enough for most laptops; fallback means no setup is required |
| Default voice | `say` | Works with zero setup. README recommends Kokoro as the free upgrade |
| Kokoro | Separate script, run with `uv`, which installs its packages on first use | Core plugin stays install-free; only Kokoro users need `uv` |
| Keys | `/talkback:key <service>` opens a macOS pop-up with a hidden field and saves to the Keychain. Environment variables also work and take priority | Key never enters the chat, Claude's context, or a file |
| Old settings format | Dropped (no users yet) | Simpler |
| Platform | macOS only for now, stated in README | `afplay`, `say`, Keychain, pop-up |
| Visibility | Repo stays private until this work is built and tested | |

## Settings file

`~/.claude/talkback/config.json` (data folder overridable with `TALKBACK_HOME`, as before). Every key is optional; anything missing uses the default.

```json
{
  "summary": { "provider": "ollama", "model": "llama3.2:3b", "url": "http://localhost:11434" },
  "voice":   { "provider": "say", "voice": "" }
}
```

| Field | Values | Default |
|---|---|---|
| `summary.provider` | `ollama`, `openai`, `anthropic`, `none` | `ollama` |
| `summary.model` | any model name for that provider | `ollama`: `llama3.2:3b`; `openai`: `gpt-4o-mini`; `anthropic`: `claude-haiku-5-5` |
| `summary.url` | base URL | `ollama`: `http://localhost:11434`; `openai`: `https://api.openai.com/v1`; not used by `anthropic`/`none` |
| `voice.provider` | `say`, `kokoro`, `elevenlabs` | `say` |
| `voice.voice` | voice name or ID for that provider | `say`: system default (empty); `kokoro`: `af_heart`; `elevenlabs`: `21m00Tcm4TlvDq8ikWAM` |
| `voice.model` | `elevenlabs` only | `eleven_flash_v2_5` |

Validation: an unknown provider, or a section that isn't an object, makes that section fall back to its defaults, with one line in the log. `/talkback:setup` reports it.

## Summary providers

Each lives in `scripts/talkback/summarizers/<name>.py` and exposes `summarize(text: str, settings: SummarySettings, key: str | None) -> str`, raising on any failure. The speaker catches failures and falls back to `first_sentence(text)`. Output from every provider goes through `clean()` then `first_sentence(max_words=30)` (as in v0.1).

All use the same system prompt as v0.1 and send only the last 4000 characters of the cleaned reply.

| Provider | Request | Timeout | Key |
|---|---|---|---|
| `none` | No call; returns `first_sentence(text)` | n/a | none |
| `ollama` | `POST {url}/api/chat`, `stream: false`, `think: false`, `keep_alive: "30m"` (unchanged from v0.1); reply in `message.content` | 5 s | none |
| `openai` | `POST {url}/chat/completions`, body `{model, messages, max_tokens: 100}`; header `Authorization: Bearer <key>` only if a key is set (local servers usually need none); reply in `choices[0].message.content` | 5 s if `url` is localhost/127.0.0.1, else 8 s | optional, service `talkback-openai` / `OPENAI_API_KEY` |
| `anthropic` | `POST https://api.anthropic.com/v1/messages`, headers `x-api-key`, `anthropic-version: 2026-10-21`, `content-type: application/json`; body `{model, max_tokens: 300, system, messages, thinking: {type: "disabled"}, output_config: {effort: "low"}}`; no `temperature`/`top_p`/`top_k` (rejected on this API version); reply = text of the `content` blocks with `type == "text"` | 8 s | required, service `talkback-anthropic` / `ANTHROPIC_API_KEY` |

SessionStart warming applies only to `ollama` (as in v0.1).

Note for the README: if a user's Claude Code itself runs on `ANTHROPIC_API_KEY`, choosing `anthropic` bills summaries to that same key.

## Voice providers

Each lives in `scripts/talkback/voices/<name>.py` and exposes `synthesize(text: str, settings: VoiceSettings, key: str | None, out: Path) -> Path`, writing an audio file and returning its path, raising on any failure. The speaker catches failures and falls back to `say`.

| Provider | How | Timeout | Key |
|---|---|---|---|
| `say` | `say [-v <voice>] -o <out>.aiff -- <text>` (writes a file, so all voices play the same way through `afplay`) | 8 s | none |
| `kokoro` | `uv run --script scripts/kokoro_tts.py --voice <voice> --out <out>.wav`, text on stdin. The script declares its own packages (PEP 723 inline metadata: `kokoro-onnx`, `soundfile`). Model files go in `~/.claude/talkback/kokoro/` and are downloaded on first use | 20 s (first-ever run happens in `/talkback:setup`, which allows several minutes) | none |
| `elevenlabs` | Unchanged from v0.1 (`POST https://api.elevenlabs.io/v1/text-to-speech/{voice}`, audio check on the reply) | 8 s | required, service `talkback-elevenlabs` / `ELEVENLABS_API_KEY` |

Audio files are named per speaker token (`speech-<token>.<ext>`) and deleted after playback. This fixes the v0.1 review issue where a late, outdated speaker could overwrite the file being played.

Missing `uv` or a Kokoro failure → Mac voice, with the reason in the log.

## Keys: `/talkback:key <service> [remove]`

- `<service>` is `elevenlabs`, `anthropic` or `openai`.
- Runs `scripts/set_key.py`, which:
  1. shows a macOS dialog (`osascript`, `display dialog … default answer "" with hidden answer`) titled "talkback: <service> API key";
  2. saves the key with `security -i`, sending the `add-generic-password -U -s talkback-<service> -a talkback -w <key>` command on **stdin**, so the key never appears in a process list or shell history;
  3. prints only `Saved.` / `Cancelled, nothing saved.` / `Removed.`, and never prints the key.
- `remove` deletes the Keychain item.
- Lookup order everywhere: environment variable, then Keychain, then none.

## `/talkback:setup`

A command file with instructions for Claude, plus three helper scripts:

1. `scripts/status.py` prints, as plain text:
   - current settings and any validation problems
   - whether Ollama is reachable, and its installed models
   - whether `uv` is installed
   - whether Kokoro's model files are present
   - for each key, set or not set (never the value)
2. Claude shows this, explains the options and their costs, and asks what the user wants.
3. `scripts/configure.py <section>.<field>=<value> …` writes the settings, rejecting unknown sections, fields and providers with a clear message.
4. For a paid option without a key, Claude tells the user to run `/talkback:key <service>`.
5. `scripts/test_voice.py` speaks a fixed test sentence through the configured summary and voice path, then prints which provider actually spoke and whether a fallback was used. For Kokoro this first run also downloads the model, with a longer time limit.

## Changes to existing v0.1 code

- `config.py`: new nested settings (`SummarySettings`, `VoiceSettings`), per-service key lookup (`get_key(service)`), validation.
- `summarize.py` → `summarizers/` package; `tts.py` → `voices/` package.
- `speaker.py`: picks providers from the settings and keeps the same fallback rules and token and lock handling.
- `playback.py`: always plays a file through `afplay` (the Mac voice also renders to a file first), removes `playback.pid` after playback ends if it still holds its own PID, and deletes the speaker's audio file.
- `hook_session_start.py`: warms the model only when `summary.provider` is `ollama`.

## Error handling

Same rule as v0.1: everything stays inside the background speaker; the worst case is the Mac voice or the first sentence.

| Situation | Result |
|---|---|
| Summary provider fails (unreachable, wrong model, 401/403, quota, timeout) | First sentence; reason logged |
| Voice provider fails (no key, quota, `uv` missing, Kokoro error, timeout, non-audio reply) | Mac voice; reason logged |
| Kokoro first run outside setup (still downloading) | Mac voice this time |
| Invalid settings section | Defaults for that section; logged; shown by setup |
| Key dialog cancelled | Nothing saved; says so |
| `say` text starting with `-` | Safe: `--` ends option parsing |

## Testing

- **Unit tests (offline, free):** each provider's request (URL, headers, body, timeout) and response parsing with HTTP faked; failure → fallback for each; settings defaults and validation; key lookup order; `configure.py` rejections; `set_key.py` sending the key on stdin, never argv, with `osascript`/`security` faked; per-token audio file naming and clean-up; `say --`.
- **System Python:** keep the test that imports every module under `/usr/bin/python3`.
- **Real checks by hand:** Ollama, `say`, Kokoro first install and speech; ElevenLabs and Haiku once the user adds keys; the key dialog; a full `/talkback:setup` run in Claude Code.

## Before making the repo public

- README: what it does, macOS-only note, every option with cost and setup, the recommended path (Mac voice, then Kokoro, then paid options), commands, troubleshooting.
- The small issues from the v0.1 review that strangers would hit are fixed:
  - `say --`
  - per-token audio files
  - `playback.pid` clean-up
  - logging a missing `last_assistant_message`
- A clean-install run-through: remove `~/.claude/talkback/`, install the plugin, confirm the zero-setup Mac voice, then switch to Kokoro through setup.
- `claude plugin validate .` passes.

## Out of scope (for now)

- OpenAI TTS, Piper, other voices (one file each later)
- Linux and Windows
- Claude desktop app helper
- A persistent Kokoro helper (only if `uv run` proves too slow)
