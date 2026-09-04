---
name: example-skill
type: skill
description: Example skill template. Never use directly — copy it as the starting point for a new skill, then wire the copy per sops/wire-new-capability.sop.md.
version: 1.0
---

# Example Skill Template

## Overview
{{What the skill accomplishes and the problem it solves.}}

## When to activate
- {{User signal 1 — phrase it as what the user says}}
- {{User signal 2}}

## Workflow
1. {{Step — name the tool surface it uses}}
2. {{Step — cite any guardrail that applies at this step, by path}}

## Rules
- {{Constraints — cite guardrails rather than restating them}}

## Supporting files
- `scripts/` — {{executable helpers}}
- `templates/` — {{output templates}}
- `references/` — {{extended reference material}}
