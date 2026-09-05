# Capability Wiring

## Overview

Wires a new capability — a skill, guardrail, knowledge/convention module, SOP, or domain — into this package so the agent will load, route to, and honor it. A file on disk does nothing on its own. Authority for "completely wired" is `context/scripts/validate-wiring.py`; this SOP tells you how, the script tells you whether.

## Parameters

- **capability_name** (required): directory or file stem
- **capability_type** (required): skill | guardrail | knowledge | convention | sop | domain

## Steps

### 1. Establish the baseline

Run `python3 context/scripts/validate-wiring.py` BEFORE making changes.

**Constraints:**
- You MUST record the baseline — because pre-existing findings must not be attributed to your change.

### 2. Author the artifact

Skill: `skills/<name>/SKILL.md` with frontmatter (name, type, description, version). Guardrail: `context/guardrails/<name>.md` — no frontmatter; H1 names the rule; scope in the first paragraph; steering-practice closer.

**Constraints:**
- You MUST make frontmatter `name` byte-identical to the directory name — because activation looks up by name.
- You MUST write a description stating what AND when — because it is the routing signal; a bare label is not routable.
- You MUST keep guardrails short — because they are loaded on every turn and paid for in context on every request.
- You MUST NOT duplicate rule content that lives in another guardrail — cite it by path instead, because copies drift.

### 3. Declare it

Skills: add to `skillNames`. SOPs: add to `sopNames`.

**Constraints:**
- You MUST NOT add manifest entries for guardrails, knowledge, or conventions — because they load through the tier globs; their declaration points are the always-in-effect list and citations.
- You MUST NOT declare allowlisted template artifacts (`example-skill`, `example` SOP) — because they are intentionally inert.

### 4. Route it

One row per user signal in the domain routing file, or `00-core.md` for session/escalation scope.

**Constraints:**
- You MUST phrase rows as user signals — because rows match what users say.
- You MUST add a row for every entry path that could reach the skill — because a signal with no row never fires the gate.
- You MUST add a cross-cutting gate in `00-core.md` when the capability is reachable mid-flow from other skills.
- You MUST register always-on skills in `alwaysOnSkills` in `wiring.config.json` and document their trigger in a prompt partial.

### 5. Wire the prompt layer

Guardrails: add to the always-in-effect list in `context/prompt/00-identity.md`, and cite from the point of use. Skills: add a capability line to the domain partial when the agent must know about the capability unprompted.

**Constraints:**
- You MUST place a rule that constrains an existing instruction directly adjacent to that instruction.
- You MUST cite by path — because one source of truth beats a paraphrase that drifts.

### 6. Wire long-running workflows

Add an inline pointer at the step where the new capability applies inside any multi-step skill or SOP.

**Constraints:**
- You SHOULD add the pointer when a workflow runs long enough to carry momentum past an always-loaded rule.
- You MUST NOT paste the rule into the workflow — point at the path, because copies drift.

### 7. Update the README

Capability list, the `skills/ (N)` count, and the context tree listing.

**Constraints:**
- You MUST update the count — because the validator checks it.

### 8. Verify

Run:

    python3 context/scripts/validate-wiring.py --strict

**Constraints:**
- You MUST reach zero errors — because errors are behavioral defects.
- You MUST resolve every warning your change introduced, or record why it is acceptable.
- You MUST NOT silence a finding via allowlist unless the exemption is genuine and the reason is recorded in `wiring.config.json`.

### 9. Land it

Commit on a feature branch; open a review per `sops/adversarial-review.sop.md` for non-trivial changes.

**Constraints:**
- You MUST run the CI validation before merging — because a half-wired capability must fail loudly.
