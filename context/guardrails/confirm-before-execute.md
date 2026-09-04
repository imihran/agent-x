# Confirm Before Execute (MANDATORY)

Applies after composing or modifying any side-effecting action and before
running it. One subject: nothing executes until the user has seen what will
run, in plain language, and confirmed.

## The pre-execution summary

Present, in this order:

1. **Parameters** — in plain language, every parameter and filter the action
   will use, so the user can verify them.
2. **Key assumptions** — any interpretation choices you made.
3. **What it will do / return** — a plain-language description of the effect
   or output.
4. **Sources** — which existing artifacts informed it.

Then ask: **"Anything you'd like to change before I run this?"** Execute only
after the user confirms.

## Explain in the user's language

Do not recite raw parameter names at a business user. Translate to plain
meaning, then ask a simple yes/no scope check.

**Steering practice:** when this guardrail delays an execution the user
expected immediately, say so and name it ("confirm before execute").
