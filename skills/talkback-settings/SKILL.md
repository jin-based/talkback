---
name: talkback-settings
description: Change talkback's spoken-summary settings when the user asks in plain words, such as switching or previewing a voice (Mac voice, Kokoro, ElevenLabs, a voice by name), giving a project its own voice or spoken name, switching the summary model (Ollama model, OpenAI-compatible server, Claude Haiku, none), turning alerts or spoken summaries on or off, or checking why talkback isn't speaking.
when_to_use: The user says things like "switch the voice to ElevenLabs", "use Kokoro", "what voices are there?", "preview Bella", "use Bella", "use Bella for the horizon project", "call this project Horizon", "use Haiku for the summaries", "use my qwen model", "stop the waiting alerts", "turn talkback off/on", "why isn't it speaking?", "what voice is talkback using?".
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*)
---
# Changing talkback settings

talkback speaks a one-sentence summary of each Claude reply. Use the scripts below; don't edit files by hand and don't search for the plugin. Keep replies to the user short.

Current status (its first line, `Scripts:`, is the folder to use wherever it says PLUGIN below):

!`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/status.py`

1. Use the status above. To refresh it: `python3 PLUGIN/status.py`
2. **Change settings:** `python3 PLUGIN/configure.py section.field=value ...`
   - Summary: `summary.provider=` `ollama` | `openai` | `anthropic` | `none`; `summary.model=<name>`; `summary.url=<base URL>` (for `openai`-compatible servers).
   - Voice: `voice.provider=` `say` | `kokoro` | `elevenlabs`; `voice.voice=<ID>`. To pick a voice by name, use `voices.py use <name>` (step 3) instead; it looks up the ID.
   - An empty value (`voice.voice=`) resets that field to its default.
   - Per project (by folder name): `projects.<folder>.voice=<voice>` and `projects.<folder>.name=<spoken name>`.
   - Alerts: `alerts.permission=on|off` (approval needed), `alerts.idle=on|off` (waiting for you), `alerts.questions=on|off` (multiple-choice questions).
3. **Voices by name:** `python3 PLUGIN/voices.py list`, `python3 PLUGIN/voices.py preview <name>`, `python3 PLUGIN/voices.py use <name> [--project <folder>]`. If `use` says a name matches several voices, ask the user which one. The current project's folder is the last part of the working directory.
4. **Turn on or off:** `python3 PLUGIN/set_enabled.py on` (or `off`).
5. **Paid options need a key.** If status shows the key as `not set`, tell the user to run `/talkback:key elevenlabs` (or `anthropic`, `openai`). It opens a private pop-up and saves the key to the macOS Keychain. **Never ask the user to paste a key into the chat, and never put a key in a command.**
6. **After a change, test it:** `python3 PLUGIN/test_voice.py --long`. It plays a sample and reports which summary model and voice actually ran. If it reports a fallback, explain why, using the log file it names.

For a full guided walk-through, suggest `/talkback:setup`.
