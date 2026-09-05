---
name: escalation-handoff
type: skill
description: Builds a structured handoff when the agent has exhausted its documented sources and cannot resolve an in-scope request — quick handoff for small blockers, project variant for multi-hour asks. Use when the agent hits a wall, not before the search order is exhausted.
version: 1.0
---

# Escalation Handoff

Turns "I'm stuck" into a structured, actionable handoff instead of a dead end.

## When to activate

- The agent tried the documented sources and skills and could not resolve an
  in-scope request (routing's escalation ladder, `context/routing/00-core.md`).
- The request is in scope but needs multi-hour effort beyond assistant scope
  (project variant).

Do NOT activate while an unexplored documented source remains.

## Workflow

1. **Summarize the request** in one paragraph — what the user is trying to
   accomplish, in their words.
2. **Document the attempt trail:** what was tried, in order, and what each
   attempt returned. Label claims per
   `context/guardrails/verify-before-assert.md`.
3. **State where it got stuck** — the specific gap: missing access, missing
   data, missing capability, ambiguity that needs a human owner.
4. **Suggest the next step** and the likely owner (from the destination table
   in `context/routing/00-core.md`).
5. **Assemble the handoff** from `templates/handoff.md` (Request / Tried /
   Stuck at / Suggested next step / Requester context).
6. **Confirm with the user** before filing or sending anything —
   `context/guardrails/confirm-before-execute.md` — then deliver through the
   configured destination, reporting per-destination results honestly.
7. If the delivery tooling itself fails: hand the user the completed text and
   the destination — never leave them stuck.

## Destinations

| Destination | Role |
|---|---|
| {{fill in: intake queue, tracker, mailbox}} | Primary |

This table is the only place destinations are named — edit it to retarget.
