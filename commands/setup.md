---
description: Choose talkback's summary model and voice, add keys, and test it
allowed-tools: Bash
disable-model-invocation: true
---
Current talkback status:

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/status.py"`

You are helping the user set up talkback, a plugin that speaks a short summary of each Claude reply. Be brief and friendly.

1. Summarize the status above in a few plain lines. Point out any Problems.
2. Explain the choices and ask what the user wants. Recommend the free path first.

   **Summary model** (turns the reply into one sentence):
   - `ollama`: a local model. Free and private; needs Ollama. The default model is `llama3.2:3b` (`ollama pull llama3.2:3b`). Any installed model works.
   - `openai`: any OpenAI-compatible server. LM Studio and llama.cpp are free and local; OpenAI and OpenRouter are paid and need a key. Set `summary.url` and `summary.model`.
   - `anthropic`: Claude Haiku (`claude-haiku-5-5`). Paid, a fraction of a cent per reply; needs an Anthropic API key.
   - `none`: just reads the reply's first sentence. Free, nothing to install.

   **Voice:**
   - `say`: the built-in Mac voice. Free, the default.
   - `kokoro`: a natural-sounding free voice that runs on this Mac. Needs `uv` (`brew install uv`); downloads a ~140 MB model the first time. Voices include `af_heart` (default), `af_bella`, `am_michael`, `bf_emma`.
   - `elevenlabs`: the most natural voice. Paid (free credits to start); needs an ElevenLabs API key. `voice.voice` is any voice ID from the user's ElevenLabs library.
3. Apply the choice with:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/configure.py" section.field=value ...`
   For example: `summary.provider=ollama summary.model=qwen3:8b` or `voice.provider=kokoro`. An empty value (`voice.voice=`) resets that field to its default.
4. If the choice needs a key that status shows as `not set`, tell the user to run `/talkback:key <service>` (`elevenlabs`, `anthropic` or `openai`). It opens a private pop-up and saves the key to the macOS Keychain. **Never ask the user to paste a key into this chat, and never put a key on a command line.**
5. When the settings are done, run:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/test_voice.py" --long`
   This plays a test sentence. Tell the user what it reports. If it says "fallback", explain why (missing key, Ollama not running, etc.), using the log file it names if needed.
