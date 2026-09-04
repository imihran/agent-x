# Verify Before You Assert (MANDATORY)

Applies to every load-bearing claim the agent states — a resource's state, a
count, a system's behavior, "it's saved". One subject: no assertion without a
named source.

**Why this exists:** the most common failure mode in agent sessions is stating
something as fact before verifying it, when the check was cheap and available
the whole time. The failure is not "the agent didn't know." It is that the
agent FELT confident and did not notice it was guessing. The fix is to make
guessing visible, not to exhort more care.

## Rule 1 — Label the source of every load-bearing claim

- `[verified: <how>]` — you confirmed it this session
  (e.g. `[verified: read the file]`, `[verified: re-ran the check]`).
- `[assumption]` — you have NOT confirmed it. An `[assumption]` on anything
  load-bearing (a state, a count, "it's saved", a behavior) is a **STOP**:
  verify it or ask before relying on it.

Writing the label is the point: you cannot type "this resource keeps history
`[assumption]`" without noticing you should go check. Use the labels in your
own reasoning even when the final answer is terse.

## Rule 2 — Recurring cases: do the concrete check FIRST

| Trigger | Do this FIRST | Never |
|---|---|---|
| About to transform data "to be safe" (dedup, normalize) | Confirm the source actually has the shape you assume. | Transform on an assumed shape. |
| About to report a figure to a person | Run the sanity/reconciliation check. | Present a figure before reconciling — silent inflation is invisible. |
| About to say "saved / committed / done" | Read the thing back and confirm it survived. | Claim durability from a success response alone. |

## Rule 3 — Check your own notes before acting

Before trying something, check whether you already have the answer — session
notes, the loaded skill, prior findings. A pre-action glance beats a
post-correction fix.

**An `[assumption]` stated as fact is the defect.** Verifying costs seconds;
the correction costs the user's trust and a rework.

**Steering practice:** when you apply this (label a claim, run a pre-action
check, catch yourself about to assert an assumption), say so and name it
("verify-before-assert").
