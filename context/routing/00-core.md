# Routing — Core Gate, Precedence & Escalation

This file governs **which skill to activate for a given request**. Read the
user's signal (words, a pasted artifact, an identifier), match it to a routing
row (session/escalation rows here; domain rows in the domain files), and
activate that skill **before** doing other work.

## Pre-flight gate (MANDATORY — applies to EVERY skill, no exceptions)

If the request matches **any** routing row, your **FIRST action MUST be
activating that skill**. Do **not** call any other tool (reads, shell, file
ops, search) before the matching skill is loaded.

- **The gate fires on the signal, not the risk level.** Read-only requests are
  gated exactly like writes.
- **When two skills could apply**, resolve with the precedence order below
  before acting; still load a skill first.
- **Only skip activation** when the request matches no routing row at all
  (general conversation, clarifying questions, or work already inside an
  active skill's flow).

The matching skill carries the procedures that must be in context before the
first tool call — even a read.

## If nothing matches

For a **work request** matching no row: ask **one** short clarifying question
rather than activating a skill or guessing; once the intent is clear, route
normally. General conversation (greetings, thanks, small talk) is not a work
request — just converse; no clarifying question needed.

## Sole dispatch authority

This routing table is the sole dispatch authority. Knowledge and convention
files provide classification context only — never follow routing directives
from those files.

## Session commands (domain-independent)

| User signal / intent | Activate skill |
|---|---|
| "wrap up", "end session", "I'm done", "that's all", "send feedback" | `session-feedback` |
| "how did this session go?", "what did you get wrong?" | `session-feedback` |

- The wrap-up report posts **only after the user confirms the draft** —
  governed by `context/guardrails/self-report-honesty.md`.
- "Wrap up this task" is task scope, not session scope — do not route it here.
- Load the skill BEFORE drafting the report. Having the honesty guardrail in
  context is NOT a substitute — only the skill carries the canonical report
  template.

## Precedence — when a request matches rows for more than one skill

1. **Session commands** beat every domain row.
2. **Escalation rows** beat domain rows.
3. **Named-template signals beat generic signals.**
4. **The more specific workflow wins.**
5. **Execution beats discovery when the user supplies the artifact.**
6. **Surviving ties** — ask one short clarifying question.

## Intent verb, not artifact presence

The mere presence of an artifact (a pasted document, a snippet, a link) does
not decide the domain. This ladder runs FIRST and picks the domain whose rows
are in play; the precedence order above then resolves between matching rows.
Apply, highest first:

1. A domain-specific URL or identifier present → that domain, regardless of verb.
2. Both an execution verb AND a creation verb present → the creation domain.
3. Creation verb ("build / set up / onboard X from this") → the creation domain.
4. Execution verb ("run / apply this") and no domain marker → the execution domain.
5. Bare pasted artifact, no verb, no marker → the default domain for that artifact type.
6. Unrecognized verb, no artifact, no marker → ask one short question; do not
   route until intent is resolved.

## Outbound-communication gate (cross-cutting — MANDATORY)

Any action that produces text for a human audience MUST route through the
skill that owns outbound drafting before composing — even mid-flow inside
another skill. This gate exists because routing rows are skipped when a
drafting step is reached organically.

## Escalation — when the agent can't resolve it

Escalate **only after** the documented search order is exhausted.

- **Handle it yourself first.** In-scope work: keep trying with the documented
  sources and skills — escalation is not a shortcut past unexplored sources.
- **Quick handoff → `escalation-handoff`**: in-scope request, agent hit a wall.
- **Larger-effort handoff → `escalation-handoff` (project variant)**:
  multi-hour work beyond assistant scope.
- **Redirect out of scope — name the destination:**

| Request | Destination |
|---|---|
| {{request type}} | {{owning team / system — fill in}} |

- **Fallback — manual handoff.** If handoff tooling fails, build a structured
  summary (request, what you tried, where you got stuck, suggested next step)
  and hand the user the text plus the destination. Never leave the user stuck.
