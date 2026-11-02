# Changelog

## 0.2.1

- **New icon.**
- **Cleans up after itself:**
  - Old session notes, unused permission details and leftover audio files are deleted automatically.
  - The log is capped at about 1 MB; the older part moves to `log.old.txt`.
- **Friendlier alerts:** tools are named in plain words (*"fetch a web page"*, *"use the github create issue tool"*) instead of raw names.
- **Clearer question reading:**
  - Nested bullets aren't read as extra options.
  - A final heading isn't treated as a question.
  - Quoted and line-wrapped questions are read in full.
- **Honest voice-picker messages:** previews say when the sample will play after current speech, and failures are reported as failures.
- **Easier troubleshooting:**
  - When a service refuses a request, the log records its reason.
  - A settings typo is logged once instead of on every reply.
  - `/talkback:setup` flags a Mac voice that isn't installed.
- **Key safety:**
  - If an API key is typed into `/talkback:key` itself, talkback warns that it's now in the chat history.
  - "Saved" is shown only after the Keychain confirms the key.
  - The settings file is written in one safe step.

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
