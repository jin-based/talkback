---
description: Save (or remove) an API key for talkback in the macOS Keychain, via a hidden pop-up
argument-hint: elevenlabs|anthropic|openai [remove]
allowed-tools: Bash
disable-model-invocation: true
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/set_key.py" $ARGUMENTS`

Repeat the line above to the user in one short sentence. Never ask the user to paste an API key into the chat.
