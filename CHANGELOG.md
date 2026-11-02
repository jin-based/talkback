# Changelog

## 0.2.0

- **Several sessions at once:**
  - Speech from different Claude sessions queues instead of cutting each other off.
  - Project names are spoken when more than one session is active.
  - Sending a message stops only that session's speech.
  - Optional per-project voices and names.
- **"Claude needs you" alerts:** spoken permission requests (with the command; secrets are never spoken), a "waiting for you" alert after about a minute, and multiple-choice questions read aloud. Each can be turned off.
- **Questions read word for word:** when a reply ends with a question, you hear the summary and then the question with its options.
- **Voice picker:** `/talkback:voices` lists voices by name (ElevenLabs library, Kokoro, Mac). Preview a voice, or pick it by name, globally or per project.
- **Fix:** each spoken item gets its own audio file, so two alerts never collide.
- **Fix:** nothing is queued after `/talkback:off`.

## 0.1.0

- Spoken one-sentence summary of each Claude reply.
- **Summary models:** Ollama (any local model), any OpenAI-compatible server, Claude Haiku, or none (first sentence).
- **Voices:** the Mac voice, Kokoro (free, local, run through `uv`) or ElevenLabs. Falls back to the Mac voice.
- `/talkback:setup` guided setup, `/talkback:key` (keys saved to the macOS Keychain through a hidden pop-up), `/talkback:on` and `/talkback:off`, and a plain-words settings skill.
- Installable from GitHub as a Claude Code plugin marketplace.
