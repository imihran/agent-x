# Agent X Project Progress

Last updated: after README Section 20 Task 10.

## Current goal

Build the Agent Capability Package from the README rebuild specification. This is primarily a Kiro agent/capability package; Claude Code support is secondary. Claude Code is being used as the implementation agent. Kiro should be used later to validate that the generated/base agent can actually load.

## Repository state

- Local repo: `/home/mish/Documents/GitHub/agent-x`
- Remote: `https://github.com/imihran/agent-x`
- Working branch: `build/rebuild-spec-task-1`
- Main spec: `README.md`
- Current latest pushed commit: `988fd92 feat: add anti-drift guard validation`
- All completed implementation steps have been committed and pushed to `origin/build/rebuild-spec-task-1`.

## User instructions / operating rules

- Commit and push after every implementation step so rollback is easy.
- After every step, give a short summary of what changed and anything material.
- Small updates do not require waiting for review.
- Maintain this progress file as work proceeds so a new session can resume if context runs out.
- Keep `agent-x` generic: no Mish-specific data, no secrets, no hardcoded personal paths in shipped source.
- `agent-x` is a placeholder/codename; keep naming easy to change.
- Primary runtime target is Kiro. Claude Code is the implementer and secondary artifact target.
- Validate Kiro loading once a very base agent / Kiro target exists, likely after Task 11 or Task 12.

## Completed rebuild tasks

### Task 1 — Skeleton and test harness

Commit: `b39194e chore: add task 1 skeleton and validator floor`

Created the repository skeleton, empty valid manifest/config, initial validator floor, and first pytest test proving the incomplete package fails for missing routing core.

### Task 2 — Manifest schema and loader

Commit: `b61bbc1 test: add manifest loader missing declaration checks`

Extended validator for declared-but-missing checks:
- missing declared skills
- missing declared SOPs
- README-advertised agent without manifest

### Task 3 — Skill contract

Commit: `aa5bf3d test: add skill contract validator checks`

Added skill contract checks #1–#5 and the intentionally undeclared `skills/example-skill/SKILL.md` template with allowlist entry.

### Task 4 — Prompt tier and include resolution

Commit: `0e09bf8 feat: add prompt tier assembly`

Added prompt partials, manifest `systemPromptIncludes`, minimal generic assembler, and validator checks #15–#16 for prompt includes.

### Task 5 — Routing tier

Commit: `6175378 feat: add routing tier validator checks`

Added routing core/domain templates and validator check #6 proving declared skills are reachable via routing or always-on prompt invocation.

### Task 6 — Guardrail tier

Commit: `92e7265 feat: add guardrail tier validation`

Added seven guardrail files and validator checks #8–#10.

### Task 7 — Knowledge/conventions tiers and eager context assembly

Commit: `7e4daf9 feat: add eager context tier assembly`

Added knowledge/convention templates, manifest `contextGlobs`, and generic assembler eager-tier expansion with double-load protection.

### Task 8 — Wiring-loop acceptance test

Commit: `380829e test: add wiring loop acceptance coverage`

Added tests that create a zero-wiring skill, fix one attachment point at a time, and prove validator messages progress to PASS.

### Task 9 — Toolkit CLI

Commit: `751683a feat: add toolkit cli contract`

Implemented `tool/toolkit/toolkit.py`, `tool/toolkit/README.md`, and toolkit contract tests covering JSON success/error, exit codes, retryable/hint errors, read-back write verification, discover completeness, and read-only authcheck behavior.

### Task 10 — Anti-drift guards

Commit: `988fd92 feat: add anti-drift guard validation`

Implemented `guards/check-tool-contract.py`, `guards/check-cli-references.py`, and discriminate tests proving the guards return 0 for agreement, 1 for drift, and 2 for unverifiable inputs. Also fixed one README prose collision where the CLI reference guard correctly treated `toolkit.py missing` as a bad command reference.

## Current verification status

Latest verified after Task 8:

```text
/tmp/agent-x-venv/bin/python -m pytest tests/ -q
53 passed

python3 context/scripts/validate-wiring.py --strict
WIRING VALIDATION: PASS (all capabilities) — fully wired

python3 guards/check-tool-contract.py
TOOL CONTRACT: AGREE

python3 guards/check-cli-references.py
CLI REFERENCES: AGREE

python3 build/assemble.py --target generic --out /tmp/agent-x-summary-assemble
assembled successfully
```

System Python does not have pytest installed. Current test venv is `/tmp/agent-x-venv`.

## Material blockers / gotchas

- GitHub token lacks `workflow` scope. A previous push containing `.github/workflows/.gitkeep` was rejected. Avoid adding `.github/workflows/*` until Task 14 and/or token scope is fixed.
- Kiro validation has not run yet because Kiro target artifacts are not implemented until Task 11.
- Generated/cache files should be removed before commits: `dist/`, `.pytest_cache/`, `tests/__pycache__/`.

## Next task

Proceed with README Section 20 Task 11 — Target adapters.

Expected scope:
- Complete `build/assemble.py` for `claude-code`, `kiro`, and `generic` targets per README Section 13.2/13.3.
- Kiro is the primary target; after Task 11, perform an initial Kiro artifact/layout validation.
- Verify deterministic output across two runs.
- Do not implement generic capabilities, optional layers, SOPs, hooks, CI, or GitHub workflow yet.
- After implementation, verify with pytest, validator strict, both anti-drift guards, and assembler smoke for all targets, then commit and push.

## Suggested skills for next session

- `github-repo-management`
- `claude-code`
- `ai-product-team`
- `writing-plans`
- `subagent-driven-development`
- `handoff` if creating a temporary handoff document
