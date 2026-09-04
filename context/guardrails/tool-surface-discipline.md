# Tool-Surface Discipline — Use the Blessed Surface

Applies whenever the agent operates a companion tool or library. One subject:
the supported surface is the only surface.

## The rules

1. **Always invoke the public CLI/tool surface** for any operation that has
   one. Do NOT import internals or hand-roll the equivalent — hand-rolled
   calls drift from canonical handling and hide silent failures.
2. **Never call underscore-prefixed / internal methods.** They are
   unvalidated and may swallow empty responses (a failed write that looks
   like success).
3. **No subcommand for what you need? That's a gap to file, not a reason to
   reach into internals.** Check the full surface first (`discover` output).
4. **Never guess a subcommand or flag name.** Method names and CLI names
   follow different conventions. On "invalid choice", re-read the inventory —
   do NOT retry name variants.

**Steering practice:** when this guardrail makes you take a longer supported
path over a shortcut, say so and name it ("tool-surface discipline").
