# talkback

**Hear what Claude did.** talkback is a Claude Code plugin that speaks a one-sentence summary of each Claude reply out loud.

Pair it with Claude Code's built-in `/voice` (hold Space to talk) and you can work hands-free. Ask out loud, keep your eyes on something else, and listen for "Fixed the login bug, and all tests pass."

> **macOS only** for now: it uses the Mac's audio player, voices and Keychain.

## Install

In Claude Code (2.1.275 or later):

```
/plugin install talkback --marketplace jin-based/talkback
```

Or in two steps (any recent version):

```
/plugin marketplace add jin-based/talkback
/plugin install talkback@talkback
```

From your shell: `claude plugin install talkback --marketplace jin-based/talkback` (2.1.292 or later).

To try a local copy without installing: `claude --plugin-dir /path/to/talkback`.

## Quick start

Once installed, there's nothing else to do. With no setup at all, talkback reads the first sentence of each reply in the built-in Mac voice. Run **`/talkback:setup`** inside Claude Code to choose a better summary model or voice. Claude walks you through it and plays a test sentence.

## How it works

When Claude finishes a reply, talkback:

1. strips code, file paths, tables and markdown from the reply,
2. asks your **summary model** for one short sentence about what Claude did,
3. turns that sentence into speech with your **voice**,
4. plays it.

If any step fails (model not running, no key, no internet), talkback falls back quietly. A summary falls back to the reply's first sentence; a voice falls back to the Mac voice. It runs in the background and never slows Claude Code down. A newer reply cuts off an older one, and sending a message stops it talking.

## Choose your models

### Summary model

| Option | Cost | Setup | Notes |
|---|---|---|---|
| `ollama` (default) | Free | [Ollama](https://ollama.com) + `ollama pull llama3.2:3b` | Private, runs on your Mac. Any Ollama model works |
| `openai` | Free (local) or paid | Set a URL and model; key only for paid services | Any OpenAI-compatible server: LM Studio, llama.cpp, OpenRouter, OpenAI. Uses the classic `max_tokens` field, so pick a chat model such as `gpt-4o-mini` (some newer reasoning models reject it) |
| `anthropic` | Paid (a fraction of a cent per reply) | Anthropic API key | Claude Haiku (`claude-haiku-5-5`) by default; any Claude model works |
| `none` | Free | Nothing | Reads the reply's first sentence |

### Voice

| Option | Cost | Setup | Notes |
|---|---|---|---|
| `say` (default) | Free | Nothing | Built-in Mac voice. Downloaded "Premium" voices in System Settings sound better |
| `kokoro` | Free | [`uv`](https://docs.astral.sh/uv/) (`brew install uv`); ~140 MB model downloads on first use | **Recommended upgrade.** Natural-sounding, runs on your Mac, about 1 s per sentence. `/talkback:setup` does the first download for you; if you switch to it by hand, the Mac voice fills in while it downloads in the background |
| `elevenlabs` | Paid (free credits to start) | ElevenLabs API key | The most natural voice; pick any voice from your ElevenLabs library |

**Suggested path:** start with the defaults, then switch the voice to Kokoro (free). Add a paid option only if you want it.

## Commands

| Command | What it does |
|---|---|
| `/talkback:setup` | See what's set, choose models, test the voice |
| `/talkback:key <service>` | Save an API key (`elevenlabs`, `anthropic` or `openai`) through a private pop-up |
| `/talkback:key <service> remove` | Delete a saved key |
| `/talkback:on` / `/talkback:off` | Turn spoken summaries on or off |

You can also just ask in plain words, for example "switch the voice to Kokoro", "use Haiku for the summaries" or "turn talkback off". The plugin's `talkback-settings` skill handles it.

## API keys and privacy

- `/talkback:key` opens a macOS pop-up with a hidden field and stores the key in your **macOS Keychain**. The key never goes into the chat, into Claude's context, or into a file.
- You can use environment variables instead: `ELEVENLABS_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. They take priority over the Keychain. `OPENAI_API_KEY` is only used when `summary.url` is OpenAI itself; for OpenRouter or other servers, save that service's key with `/talkback:key openai`.
- With `ollama`, `none`, `say` and `kokoro`, your text never leaves your Mac. (Kokoro downloads its packages and model from PyPI and GitHub the first time.)
- Online summary options (`anthropic`, or `openai` pointed at a hosted service) receive the cleaned text of Claude's reply, up to its last 4,000 characters. `elevenlabs` receives only the one summary sentence.
- Note: if your Claude Code itself runs on `ANTHROPIC_API_KEY`, choosing `anthropic` bills summaries to that same key.

## Settings file

`/talkback:setup` edits this for you, but you can also edit `~/.claude/talkback/config.json` by hand. Leave out any field to use its default.

```json
{
  "summary": { "provider": "ollama", "model": "llama3.2:3b", "url": "http://localhost:11434" },
  "voice":   { "provider": "kokoro", "voice": "af_heart" }
}
```

| Field | Default |
|---|---|
| `summary.model` | `ollama`: `llama3.2:3b` · `openai`: `gpt-4o-mini` · `anthropic`: `claude-haiku-5-5` |
| `summary.url` | `ollama`: `http://localhost:11434` · `openai`: `https://api.openai.com/v1` |
| `voice.voice` | `say`: system voice · `kokoro`: `af_heart` · `elevenlabs`: `21m00Tcm4TlvDq8ikWAM` |
| `voice.model` | `elevenlabs`: `eleven_flash_v2_5` |

## Troubleshooting

- Not hearing the voice or model you chose? Run `/talkback:setup`. It shows what's working, and its test reports any fallback and why.
- Errors are logged to `~/.claude/talkback/log.txt`.
- Set `TALKBACK_HOME` to use a different data folder.
- All Claude Code sessions share one voice: the latest reply from any session plays, and a message in any session stops it.

## Development

```sh
uv run --with pytest pytest -q     # tests (offline, no services needed)
claude plugin validate .
```

The plugin itself uses only the Python standard library and runs on the Python that ships with macOS. Kokoro runs in its own `uv` environment. Design notes are in `docs/superpowers/specs/`.

## License

MIT
