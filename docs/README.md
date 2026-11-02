# Design notes

You don't need anything in this folder to use talkback; start with the main [README](../README.md).

These are the design documents talkback was built from, kept for anyone curious about why it works the way it does, or wanting to contribute. Each feature round has a **spec** (what to build and why) and a **plan** (the step-by-step, test-first build). They were written with Claude Code's "superpowers" workflow, which explains the agent instructions at the top of each plan.

| Round | Spec | Plan | What it added |
|---|---|---|---|
| 0.1: first version | [spec](superpowers/specs/2026-11-01-claude-voice-talkback-design.md) | [plan](superpowers/plans/2026-11-01-talkback-plugin.md) | Spoken summaries via a local model and ElevenLabs, with the Mac voice as backup |
| 0.1: choosable models | [spec](superpowers/specs/2026-11-01-talkback-choosable-models-design.md) | [plan](superpowers/plans/2026-11-01-talkback-choosable-models.md) | Pick any summary model and voice, keys in the Keychain, `/talkback:setup`, Kokoro |
| 0.2: sessions and alerts | [spec](superpowers/specs/2026-11-01-talkback-sessions-alerts-voices-design.md) | [plan](superpowers/plans/2026-11-01-talkback-sessions-alerts-voices.md) | Cross-session queue, project names, "Claude needs you" alerts, questions read aloud, voice picker |

Later rounds refine earlier ones. Where they disagree, the newest spec and the code win. For example, the first spec's "newest reply cuts off the old one" became the queue in 0.2. Paths and model names in these notes are examples, not requirements.
