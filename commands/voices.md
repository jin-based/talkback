---
description: List the voices you can use with talkback, preview one, or pick one by name
allowed-tools: Bash
disable-model-invocation: true
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/voices.py" list`

Show the user this voice list briefly (group or trim it if it's long). Tell them they can say "preview <name>" to hear one, "use <name>" to switch, or "use <name> for <project>" to give one project its own voice. To do those, run:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/voices.py" preview <name>` or `... use <name> [--project <folder>]`.
If the list failed because a key is missing, tell them to run `/talkback:key elevenlabs`. Never ask for a key in the chat.
