---
name: session-feedback
type: skill
description: Wraps up the current session into an honest what-worked/what-didn't report with root-cause tags, and delivers it to the configured feedback destination after the user approves the draft. Use when the user says "wrap up", "end session", "I'm done", "send feedback", or asks how the session went.
version: 1.0
---

# Session Feedback

Turns the session into a short, honest report of what worked and what didn't.
The value is entirely in the "what didn't" half — a report that says
everything went fine tells the maintainers nothing. Read
`context/guardrails/self-report-honesty.md` before drafting; it governs
grounding, self-scoring, and the confirm-before-post gate.

## Destinations

| Destination | Role |
|---|---|
| {{fill in: feedback channel / tracker / mailbox}} | Primary |
| {{optional secondary}} | Best-effort |

This table is the only place destinations are named — edit it to retarget.
Treat the primary as required and the secondary as best-effort: if the
secondary fails but the primary succeeded, report the partial outcome, not a
total failure.

**Deferred destination is a supported state.** If no destination is
configured yet, the skill still runs: draft, confirm, then hand the user the
report text to deliver (or file) themselves. Configuring a destination is an
adoption step, not a prerequisite — a solo adopter may point this at a local
notes file and get the same loop.

## When to activate

- Explicit: "wrap up", "end session", "I'm done", "that's all",
  "send feedback".
- Retro question: "how did this session go?", "what did you get wrong?"
- Offer it yourself ONCE at a natural stopping point of a substantial
  session. If declined, do not ask again.

### Do not activate

- No real work happened (greetings, a single lookup). Say "nothing worth
  reporting yet."
- Mid-task ("wrap up this task" is task scope, not session scope).
- A report was already sent this session, unless the user asks again after
  more work.

## Workflow

### 1. Reconstruct the session

Walk the conversation start to end:

| Find | Why |
|---|---|
| What the user was actually trying to accomplish | Groups reports by workload |
| Which skills/routes fired, and whether the right one fired first | Catches routing misses |
| Every point the user corrected, rejected, or re-explained | The core friction metric |
| Agent-fault failures vs environment/tooling failures | Separates fixable from noise |
| Retries — the same thing attempted more than once | Signals a missing rule |
| What went right first try | Prevents regressions |

If early turns are out of context, say the report is partial — never
reconstruct a turn you cannot see.

### 2. Classify each failure — exactly one cause tag

skill-gap | routing-miss | domain-knowledge | missing-guardrail | tooling |
instruction-drift | user-ambiguity

Each tag names where the fix lands (see the taxonomy in the spec/README).
Do not use user-ambiguity to move blame off the agent.

### 3. Draft the report

    *Session Feedback — <date>*

    *Task:* <one line>
    *Duration:* <approx> · *Exchanges:* <n> · *Corrections needed:* <n>

    *Worked*
    - <specific thing that went right first try>

    *Didn't work*
    - [<cause-tag>] <what went wrong, and where the user stepped in>

    *Improvement ask*
    - <concrete change to THIS package — name the file or skill it lands in>

    *Rating:* <n>/5 — <one-line justification>

Rules: corrections-needed is the headline number — count literally; cite
where each failure surfaced so the report is checkable; the improvement ask
must be actionable in this package ("add a citation at step 4 of X", not "be
more careful"); if nothing went wrong, say so — do not invent a flaw for
symmetry; keep it under ~25 lines; no personal data, no secrets, no content
specifics — describe the shape of the work.

### 4. Show the draft and confirm — MANDATORY

Show the draft verbatim and ask what to change before posting. Post only on
affirmative confirmation. The user's edits win over your self-assessment —
including edits that make the agent look worse.

### 5. Deliver and report per destination

Deliver to the configured destinations. Report the actual per-destination
result per `context/guardrails/self-report-honesty.md` rule 7. If delivery
tooling is unreachable, hand the user the report text to deliver manually.

### 6. Offer the knowledge save

Failures tagged domain-knowledge, missing-guardrail, or instruction-drift
are usually worth persisting into `context/knowledge/` or as a guardrail
citation — offer to file them via `sops/wire-new-capability.sop.md`.
