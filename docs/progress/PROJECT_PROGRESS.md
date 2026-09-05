# Agent X Project Progress

Last updated: after README Section 20 Task 12.

## Current goal

Build the Agent Capability Package from the rebuild specification. This is primarily a Kiro agent/capability package; Claude Code support is secondary. Claude Code is being used as the implementation agent. Kiro layout validation has begun and should become fuller runtime/load validation as the base package matures.

## Repository state

- Local repo: `/home/mish/Documents/GitHub/agent-x`
- Remote: `https://github.com/imihran/agent-x`
- Working branch: `build/rebuild-spec-task-1`
- Main README: `README.md`
- Preserved rebuild spec: `docs/spec/rebuild-spec.md`
- Current latest pushed commit: `b453ec7 feat: add generic base capabilities`
- All completed implementation steps have been committed and pushed to `origin/build/rebuild-spec-task-1`.

## User instructions / operating rules

- Commit and push after every implementation step so rollback is easy.
- After every step, give a short summary of what changed and anything material.
- Small updates do not require waiting for review.
- Maintain this progress file as work proceeds so a new session can resume if context runs out.
- Keep `agent-x` generic: no Mish-specific data, no secrets, no hardcoded personal paths in shipped source.
- `agent-x` is a placeholder/codename; keep naming easy to change.
- Primary runtime target is Kiro. Claude Code is the implementer and secondary artifact target.

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

### Task 11 — Target adapters

Commit: `7bbd00b feat: add target adapters`

Implemented assembler targets for Kiro, Claude Code, and generic output. Verified deterministic target assembly and performed initial Kiro artifact/layout validation. Kiro target output includes steering, `mcp.json`, and declared skills.

### Task 12 — Generic base capabilities

Commit: `b453ec7 feat: add generic base capabilities`

Implemented generic package capabilities:
- `context/scripts/preflight.py` for machine-readable preflight state and tool-surface output.
- `context/scripts/discover.py` for discoverability metadata.
- Declared base skills: `session-feedback`, `escalation-handoff`, and `demo-skill`.
- Moved the full rebuild spec out of the active README into `docs/spec/rebuild-spec.md` and replaced README with a concise operating README.
- Removed `.gitkeep` placeholders from directories that now contain real files so assembled targets are clean.

## Current verification status

Latest verified after Task 12:

```text
/tmp/agent-x-venv/bin/python -m pytest tests/ -q
77 passed

python3 context/scripts/validate-wiring.py --strict
WIRING VALIDATION: PASS (all capabilities) — fully wired

python3 guards/check-tool-contract.py
TOOL CONTRACT: AGREE

python3 guards/check-cli-references.py
CLI REFERENCES: AGREE

python3 context/scripts/preflight.py --with-discovery
exit 0; emits PREFLIGHT_STATE v1 and TOOL_SURFACE v1 blocks

python3 build/assemble.py --target kiro --out /tmp/agent-x-task12-kiro-final
assembled successfully; Kiro layout includes steering/00-system.md, mcp.json, and declared skills; no .gitkeep artifacts

python3 build/assemble.py --target claude-code --out /tmp/agent-x-task12-claude-final
assembled successfully

python3 build/assemble.py --target generic --out /tmp/agent-x-task12-generic-final
assembled successfully
```

System Python does not have pytest installed. Current test venv is `/tmp/agent-x-venv`.

## Material blockers / gotchas

- GitHub token lacks `workflow` scope. A previous push containing `.github/workflows/.gitkeep` was rejected. Avoid adding `.github/workflows/*` until Task 14 and/or token scope is fixed.
- Initial Kiro layout validation passed after Task 11/12, but full interactive Kiro load/runtime validation has not yet been performed.
- Generated/cache files should be removed before commits: `dist/`, `.pytest_cache/`, `tests/__pycache__/`.
- The full 3,324-line rebuild spec is preserved at `docs/spec/rebuild-spec.md`; README is now a concise operator-facing summary.

## Next task

Proceed with README Section 20 Task 13 — likely SOPs and/or next wiring layer from the preserved rebuild spec. Before starting, read the relevant Task 13 section from `docs/spec/rebuild-spec.md` and keep Kiro as the primary target.

Expected verification before the next commit:
- `/tmp/agent-x-venv/bin/python -m pytest tests/ -q`
- `python3 context/scripts/validate-wiring.py --strict`
- `python3 guards/check-tool-contract.py`
- `python3 guards/check-cli-references.py`
- `python3 context/scripts/preflight.py --with-discovery`
- assembler smoke for `kiro`, `claude-code`, and `generic`

## Suggested skills for next session

- `github-repo-management`
- `claude-code`
- `ai-product-team`
- `writing-plans`
- `subagent-driven-development`
- `handoff` if creating a temporary handoff document
