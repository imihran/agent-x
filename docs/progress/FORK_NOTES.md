# Fork-Specific Development Notes

This file is intentionally a placeholder in the `agent-x` template itself.
`agent-x` is the template, not a fork — it has no fork-specific history to
record here, and it will never add real content to this path after this
initial commit.

**If you are a fork** (e.g. `agent-x-mish`, `agent-x-john`, or any other
personalized clone created by linking a `template` remote back to
`agent-x` — see `docs/sync-workflow.md`): replace this file's content with
your own running log of *fork-specific* development. Follow the same
style as `docs/progress/PROJECT_PROGRESS.md` (dated entries: what changed,
why, what verified it) — but this file is for facts that are true of your
fork alone: personalizations (manifest name, welcome message, identity
prompt), fork-local skills you've added, decisions specific to you.

`docs/progress/PROJECT_PROGRESS.md` will keep arriving via
`build/sync_template.py` and describes the *template's* history — useful
context, but not a record of your own work. This file is yours alone:
because the template commits it once and never changes it again, it can
never generate a sync conflict the way `agent.manifest.json` or a shared
doc can — edit it freely.
