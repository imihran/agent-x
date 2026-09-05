---
name: demo-skill
type: skill
description: Demonstration skill proving the wiring loop end-to-end — activates on "run the demo", lists items from the local toolkit store, and walks the confirm-before-execute gate on a demo write. Replace with your first real skill.
version: 1.0
---

# Demo Skill

Proves the package is wired: routing row → activation → tool-surface call →
confirmation gate → verified result. Replace this skill with your first real
capability, following `sops/wire-new-capability.sop.md`.

## When to activate

The user says "run the demo", "try the demo skill", or asks to see the
package working.

## Workflow

1. **Read path:** run `python3 tool/toolkit/toolkit.py list` via the shell
   tool. Present the items as a table.
2. **Write path (gated):** propose adding one demo item. Present the
   pre-execution summary per `context/guardrails/confirm-before-execute.md`
   and wait for confirmation.
3. On confirmation, run
   `python3 tool/toolkit/toolkit.py create --name demo-item --value 1`.
   The toolkit read-back-verifies the write; report the verified result with
   a `[verified: read-back]` label per
   `context/guardrails/verify-before-assert.md`.
4. Offer cleanup: `python3 tool/toolkit/toolkit.py delete --id <id>` (also
   gated).

## Rules

- Tool calls go through the toolkit CLI only —
  `context/guardrails/tool-surface-discipline.md`.
- Never claim the write landed without the read-back result.
