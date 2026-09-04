# Routing — {{DOMAIN_NAME}} Domain

One row per skill, phrased as the user's signal. The gate, precedence, session
rows, and escalation live in `00-core.md`.

## Read

| User signal / intent | Activate skill |
|---|---|
| "{{lookup phrasing}}", "{{explain phrasing}}" | `{{skill}}` |
| Anything handled by the shipped demo — "run the demo", "try the demo skill" | `demo-skill` |

## Diagnostic

| User signal / intent | Activate skill |
|---|---|
| "{{investigate phrasing}}" | `{{skill}}` |

## Mutation

| User signal / intent | Activate skill | Evidence required before proposing |
|---|---|---|
| "{{change phrasing}}" | `{{skill}}` | {{what must be verified, with which tool}} |

## Execution rule

{{Name the skill that owns execution.}} Every execution path routes through
that skill; there is no direct-execution shortcut.
