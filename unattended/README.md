# Unattended Operation Templates

This optional layer supports scheduled operation: health checks, sweeps, and routine read-only reviews.

Everything ships disabled. Enabling unattended work is an explicit operator action.

## Files

- `jobs.template.json` — example scheduled jobs. Every job MUST ship with `enabled: false`.
- `policy.template.json` — operator policy and budgets. Empty lists mean CLEAR, not "use defaults".

## Safety defaults

Every key is optional for an operator copy because the runtime should have a working default, but the shipped templates keep the defaults visible:

- `max_mutations_per_session`: 5
- `max_tool_calls_per_session`: 50
- `graduation_threshold`: 3
- `auto_approved_actions`: []
- `non_retryable_markers`: []

The empty lists are deliberate. Which actions are safe to auto-approve and which errors are permanent is operator judgement. An empty list means CLEAR.

## Before scheduling

Run the read-only transport proof first:

    python3 tool/toolkit/toolkit.py authcheck

A transport reported unproven has not been shown to work. Do not treat an empty sweep result as clean if authentication or transport proof failed.

## Budget rationale

An unpaced sweep can overwhelm the very service it checks, after which the sweep fails and reports an outage it caused. Leave the pacing keys set unless the operator explicitly raises them.
