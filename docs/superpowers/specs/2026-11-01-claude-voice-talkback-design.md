# claude-voice: talk-back plugin for Claude Code (design)

Date: 2026-11-01
Status: draft, waiting for review

## Goal

Talk to Claude Code by voice and have it talk back.

- **Talking to Claude:** use Claude Code's built-in `/voice` (hold Space to talk, release to insert the text). We don't build this.
- **Claude talking back:** this plugin. When Claude finishes a reply, you hear a short spoken summary of what it did.

The Claude desktop app comes later, as a separate project (see "Out of scope").

**Success:** with `/voice` and this plugin on, you can hold Space, ask for something, and hear a one- or two-sentence summary when Claude finishes, without looking at the screen. The plugin never slows down or breaks Claude Code.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| What is spoken | A 1-2 sentence summary of Claude's last reply, not the full text | Replies are long and full of code; a summary is easy to follow and cheap on ElevenLabs credits |
| Who writes the summary | A local model via Ollama, default `qwen3:8b` | Free and private. Measured ~0.6 s once loaded, ~6.6 s cold |
| Summary fallback | First sentence of the reply, with code and paths removed | Works with no model |
| Voice | ElevenLabs | Best quality |
| Voice fallback | macOS `say` | Always available, works offline |
| Controls | `/speak on`, `/speak off`; a new summary cuts off the old one; talking stops when the user sends the next message | Smallest useful set |
| Language | Python 3 standard library only | Ships with macOS, so nothing to install |
| ElevenLabs key | Stored in the macOS Keychain | Not in a plain file |

## Architecture

```
You hold Space ──► /voice (built in) ──► prompt ──► Claude works
                                                        │
                                          Claude finishes (Stop hook)
                                                        │
                  ┌─────────────────────────────────────▼───────────────┐
                  │ speaker (background process, detached from Claude)   │
                  │ 1. stop anything still playing                       │
                  │ 2. summarize the reply  ── Ollama                     │
                  │       fallback: first sentence, code removed         │
                  │ 3. text to audio ── ElevenLabs                        │
                  │       fallback: macOS say                             │
                  │ 4. play (afplay)                                      │
                  └─────────────────────────────────────────────────────┘
```

### Plugin layout

```
claude-voice/
  .claude-plugin/plugin.json      plugin manifest
  hooks/hooks.json                registers the three hooks below
  commands/speak.md               the /speak on|off command
  scripts/
    hook_session_start.py         warm the Ollama model (non-blocking)
    hook_stop.py                  read the reply, launch the speaker, exit
    hook_prompt_submit.py         stop any playback
    speak_cmd.py                  flip the on/off setting
    speaker.py                    summarize → audio → play
    voicelib/                     small, separately testable units
      transcript.py               get the last assistant text from a transcript
      clean.py                    remove code blocks, paths, markdown
      summarize.py                Ollama call + first-sentence fallback
      tts.py                      ElevenLabs call + `say` fallback
      playback.py                 play audio, stop current playback (PID file)
      config.py                   settings, on/off state, Keychain lookup
      log.py                      append errors to the log file
  tests/
```

Note: Claude Code may show the plugin command as `/claude-voice:speak` instead of `/speak`. Confirm during the build.

### Units

- **transcript:** given the hook's `transcript_path`, return the text of the last assistant message. Return nothing if that message has no text (for example, only a tool call).
- **clean:** remove fenced code, inline code, file paths, URLs, tables and markdown symbols.
- **summarize:** send the cleaned reply to Ollama (`/api/chat`, `think: false`, `keep_alive` 30m) with a prompt asking for one short spoken sentence under 20 words. For long replies, send only the last ~4,000 characters, where Claude usually says what it did. On error or a timeout over ~5 s, return the first sentence of the cleaned text.
- **tts:** call ElevenLabs text-to-speech with the configured voice, save an mp3 to a temp file. On error or a timeout over ~8 s, use `say` instead.
- **playback:** before playing, stop the previous playback using a PID file. Play with `afplay` (or `say`).
- **config:** read `~/.claude/claude-voice/config.json` (Ollama model, Ollama URL, ElevenLabs voice ID) and the on/off state in `~/.claude/claude-voice/state.json`. Talk-back is on by default. Get the ElevenLabs key from the Keychain (service `claude-voice-elevenlabs`). An `ELEVENLABS_API_KEY` environment variable takes priority if set.

### Hooks

| Event | Script | Behavior |
|---|---|---|
| SessionStart | `hook_session_start.py` | Start a background request that loads the model into Ollama, then exit right away |
| Stop | `hook_stop.py` | If talk-back is off, exit. Otherwise get the last reply, start `speaker.py` detached with the text, and exit right away. Always exits 0 with no output, so Claude's flow is never changed |
| UserPromptSubmit | `hook_prompt_submit.py` | Stop any playback. Exit 0, no output |

**To verify during planning:** whether Claude Code has a hook for "the user started voice input" (pressing Space). If it does, stop playback there too. If not, sending the next message is the interrupt point.

## Error handling

Rule: the plugin never breaks or slows down Claude Code. All failures stay in the background speaker. The worst case is the Mac voice, or silence.

| Situation | What happens |
|---|---|
| Ollama not running, or summary over ~5 s | First sentence of the cleaned reply |
| Very long reply | Only the last ~4,000 characters go to the model |
| Empty reply or tool-call only | Say nothing |
| No ElevenLabs key, out of credits, offline | `say` reads the summary |
| ElevenLabs over ~8 s | Give up, use `say` |
| Two replies finish close together | The newer one cuts off the older one |
| Talk-back off | Stop hook exits immediately |
| Any unexpected error | Logged to `~/.claude/claude-voice/log.txt`; hook still exits 0 |

## Testing

- **Unit tests (pytest, offline):** transcript parsing (using sample transcript files), cleaning, the first-sentence fallback, config and on/off state, and the fallback chains, with Ollama, ElevenLabs and playback faked.
- **Manual service checks:** one real Ollama call and one real ElevenLabs call, run by hand.
- **End to end:** install the plugin locally, ask Claude something, confirm the summary is heard. Then `/speak off` and confirm silence. Send a message while it's talking and confirm it stops.

## Out of scope (for now)

- Our own press-to-talk (we use `/voice`)
- A chime when Claude needs approval or input
- Switching voices with a command (it's in the config file)
- A fully local voice model (for example, Kokoro)
- Claude desktop app support. Later idea: a Mac helper app that adds a keyboard shortcut for the mic in the main chat window, which the app lacks today.

## Open items

- Does the user have an ElevenLabs API key and a preferred voice?
