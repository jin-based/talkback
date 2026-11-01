# talkback

A Claude Code plugin that speaks a short summary of each Claude reply out loud.
Pair it with Claude Code's built-in `/voice` (hold Space to talk) and you can work with Claude hands-free:
talk to ask, listen for what it did.

## How it works

When Claude finishes a reply, talkback:

1. cleans the reply (drops code, file paths, tables, markdown),
2. asks a **local model in Ollama** (default `qwen3:8b`) for a one-sentence summary
   (if Ollama is off or slow, it uses the reply's first sentence),
3. turns that sentence into speech with **ElevenLabs**
   (if there's no key, no credits, or no internet, it uses the Mac voice, `say`),
4. plays it. A newer reply cuts off an older one, and sending a message stops it talking.

It runs in the background and never slows down or blocks Claude Code.

## Setup

Requirements: macOS, Python 3, and [Ollama](https://ollama.com) with the summary model pulled
(`ollama pull qwen3:8b`, or set another model in the config).

Store your ElevenLabs API key in the Mac Keychain (you'll be prompted for it, so it never lands in your shell history):

```sh
security add-generic-password -s talkback-elevenlabs -a "$USER" -w
```

Alternatively set `ELEVENLABS_API_KEY` in your environment; it takes priority over the Keychain.
Without a key, talkback still works using the Mac voice.

Try it for one session:

```sh
claude --plugin-dir /path/to/claude-voice
```

## Commands

| Command | What it does |
|---|---|
| `/talkback:on` | Turn spoken summaries on (the default) |
| `/talkback:off` | Turn them off and stop any current speech |

## Config

Optional: `~/.claude/talkback/config.json`. Any key you leave out uses the default.

```json
{
  "ollama_url": "http://localhost:11434",
  "ollama_model": "qwen3:8b",
  "voice_id": "21m00Tcm4TlvDq8ikWAM",
  "eleven_model": "eleven_flash_v2_5"
}
```

`voice_id` is any voice from your ElevenLabs voice library.

## Troubleshooting

Errors are written to `~/.claude/talkback/log.txt`. Set `TALKBACK_HOME` to use a different data folder.

## Development

```sh
uv run --with pytest pytest -q
claude plugin validate .
```

Design notes: `docs/superpowers/specs/2026-11-01-claude-voice-talkback-design.md`.
