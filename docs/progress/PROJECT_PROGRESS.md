# Agent X Project Progress

Last updated: after the kiro-cli target migration live verification (Task 5, 2026-09-04).

## Current goal

Build the Agent Capability Package from the rebuild specification. This is primarily a Kiro agent/capability package; Claude Code support is secondary. Claude Code is being used as the implementation agent. Kiro layout validation has begun and should become fuller runtime/load validation as the base package matures.

## Repository state

- Local repo: `/home/mish/Documents/GitHub/agent-x`
- Remote: `https://github.com/imihran/agent-x`
- Working branch: `build/rebuild-spec-task-1`
- Main README: `README.md`
- Preserved rebuild spec: `docs/spec/rebuild-spec.md`
- Current latest pushed commit: `3364b46 feat: add Kiro agent launcher`
- The kiro-cli target migration (see below) is committed locally on top of that but not yet pushed to `origin/build/rebuild-spec-task-1`.

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

### Task 13a — Optional readonly investigator subagent

Commit: `5e09a75 feat: add readonly investigator subagent`

Implemented the first half of Task 13:
- `agents/readonly-investigator.agent.json`
- `context/prompts/readonly-investigator.md`
- manifest `subagentNames` declaration
- validator/tests proving the investigator is read-only by tool scope and only permits toolkit read verbs (`list|get|search|discover|authcheck`).

### Task 13b — Optional unattended templates

Commit: `24be0cc feat: add unattended operation templates`

Implemented the second half of Task 13:
- `unattended/README.md`
- `unattended/jobs.template.json`
- `unattended/policy.template.json`
- validator/tests proving every packaged job ships with `enabled: false` and the policy template ships empty lists with empty-means-CLEAR semantics.

### Task 14a — SOPs, hooks, and local CI gate

Commit: `11eb8f9 feat: add SOPs hooks and CI gate`

Implemented most of Task 14:
- `sops/wire-new-capability.sop.md`
- `sops/adversarial-review.sop.md`
- `sops/example.sop.md` as an undeclared allowlisted template
- manifest `sopNames` declaration for the first two SOPs
- `wiring.config.json` undeclared SOP allowlist for `example`
- `hooks/wire-new-capability.hook.json`
- `hooks/wire-on-agent-write.hook.json`
- `hooks/wiring-audit.hook.json`
- `build/ci.py` as the canonical cross-platform CI gate
- tests proving SOP declaration/allowlist behavior, hook emission in Kiro/Claude targets, and CI stage coverage.

Not yet implemented: `.github/workflows/validate.yml`, because current `gh auth status` shows token scopes `gist`, `read:org`, and `repo`, but not `workflow`; GitHub rejects pushes that add workflow files without that scope.

### Kiro launcher/switcher

Commit: `3364b46 feat: add Kiro agent launcher`

Added `build/kiro_agent.py`, a repeatable Kiro launcher that:
- assembles a selected agent package into `.kiro-agents/<agent-name>/` by default
- launches `kiro chat --mode agent` from that assembled artifact directory
- assigns each agent its own Kiro profile by default
- supports swapping agents via `--agent /path/to/agent` or aliases in local-only `agents/registry.local.json`
- supports `--dry-run` so the exact command/path/profile can be inspected without launching Kiro

Added `tests/test_kiro_agent_runner.py` and README usage notes. `.kiro-agents/` and `agents/registry.local.json` are gitignored.

### Kiro-cli target migration — assembler, deploy, launcher, docs, and live verification (Tasks 1–5)

Commits: `23c4aa8` docs: add kiro-cli target migration design, `38c07f4` docs: add
kiro-cli target migration implementation plan, `97d28f9` feat: replace kiro
assembler target with kiro-cli, `5a7b309` fix: guard missing manifest name
before building kiro-cli agent path, `f73c5ff` feat: deploy the kiro-cli
layout instead of the GUI kiro layout, `3165cab` feat: launch kiro-cli chat
--agent instead of the GUI's kiro chat --profile, `8bb18eb` docs: amend
canonical spec and README for the kiro-cli target, `871766e` docs: fix
emit_kiro_cli_agent listing to match the guarded implementation.

The machine actually installed on this box is `kiro-cli` (a terminal tool,
v2.20.1) — a different product from the Kiro GUI editor the original `kiro`
target was built for. This migration retargeted the whole chain to the real
binary:

- `build/assemble.py`: `target_kiro_cli` + `emit_kiro_cli_agent` replace the
  old GUI-oriented `target_kiro`. Output layout is
  `dist/kiro-cli/{steering,skills,sops,settings/mcp.json,agents/<name>.json}`
  — no `hooks/`, since kiro-cli's default engine has no hook runtime. The
  emitted agent JSON declares `resources: ["file://.kiro/steering/**/*.md",
  "skill://.kiro/skills/*/SKILL.md"]` and `includeMcpJson: true`.
- `build/deploy.py`: deploys `dist/kiro-cli`'s tree into `<repo>/.kiro/`
  (previously deployed the GUI `kiro` layout).
- `build/kiro_agent.py`: launches `kiro-cli chat --agent <name>` (previously
  `kiro chat --mode agent --profile <name>`).
- `docs/spec/rebuild-spec.md` + `README.md`: component-mapping table and code
  listings updated to match; the spec now carries a "Verified kiro-cli
  agent-activation behavior" note recording four empirically-tested facts
  (steering auto-loads for every agent regardless of `resources`; skills do
  **not** auto-load and need an explicit `skill://` entry; `includeMcpJson`
  reads `.kiro/settings/mcp.json`, not a top-level `.kiro/mcp.json`; a
  relative `file://` resource resolves against the workspace root/cwd, not
  the agent config's own directory).

Task 5 (this entry) is the live, end-to-end check of all of the above against
the real installed `kiro-cli` binary — not just unit tests against isolated
`tmp_path` copies. Verification commands and results:

1. `python3 build/ci.py` → `CI GATE: PASS — all stages green`, all 7 stages
   including the new `assembler smoke: kiro-cli` stage; 105 tests passed.
2. `rm -rf .kiro dist && python3 build/deploy.py` → `deployed agent-x to
   <repo>/.kiro`, `files_written: 21`. `ls .kiro` → `agents settings skills
   sops steering` (no `hooks`, as expected). `.kiro/agents/agent-x.json`
   matches Task 1's declared shape (`resources`, `includeMcpJson: true`,
   `tools: ["*"]`).
3. `kiro-cli agent list` → lists `agent-x` as `Workspace`, alongside built-in
   `kiro_default`, `kiro_help`, `kiro_planner`. Confirmed.
4. Identity/guardrail probe (`kiro-cli chat --agent agent-x --no-interactive
   --trust-tools= "...name one specific guardrail...cite its filename..."`)
   → *"I'm Agent X, ... one guardrail I operate under is no-fabrication
   (`guardrails-no-fabrication.md`), which requires me to verify facts before
   stating them rather than guessing."* `guardrails-no-fabrication.md` is a
   real file deployed at `.kiro/steering/guardrails-no-fabrication.md`
   (source: `context/guardrails/no-fabrication.md`). Genuine, not
   plausible-sounding filler — confirmed.
5. Skill-content probe (same command shape, asking for the demo skill's
   activation phrase per its own SKILL.md) → the model named "run the demo"
   but explicitly said it had **not** read the full SKILL.md, only a one-line
   description. Follow-up probes (asking for workflow/SOP details that exist
   only in SKILL.md's body, not in any steering file) got explicit refusals
   in both `--no-interactive` and interactive mode ("I don't have the
   content... only its one-line description... I won't guess" — the
   no-fabrication guardrail correctly firing). The phrases the model *can*
   state ("run the demo", "try the demo skill") are independently present in
   the always-loaded steering routing table
   (`routing-10-domain-template.md`), so this probe does not cleanly prove
   the `skill://` resources entry preloads full SKILL.md body content the
   way `assemble.py`'s code comment implies — see the Task 5 report for full
   transcripts. Not a functional break (the skill is still correctly
   discoverable and routable), but a nuance in the "preload" claim worth
   flagging.
6. `kiro-cli mcp list` → lists `agent-x` under `workspace` with `(empty)`
   servers, no error. `.kiro/settings/mcp.json` is `{"mcpServers": {}}`,
   valid JSON, resolved cleanly via `includeMcpJson: true`.

Full transcripts and step-by-step assessment: see
`.superpowers/sdd/2026-09-04-kiro-cli-target-migration/task-5-report.md`.

## Current verification status

Latest verified live against the installed `kiro-cli` 2.20.1 (Task 5, kiro-cli
target migration — this is a real binary run, not just tests against
`tmp_path` copies):

```text
python3 build/ci.py
WIRING VALIDATION: PASS (all capabilities) — fully wired
TOOL CONTRACT: AGREE
CLI REFERENCES: AGREE
105 passed in 3.92s
assembled target=claude-code out=<repo>/dist/claude-code
assembled target=kiro-cli out=<repo>/dist/kiro-cli
assembled target=generic out=<repo>/dist/generic
CI GATE: PASS — all stages green

rm -rf .kiro dist && python3 build/deploy.py
deployed agent-x to <repo>/.kiro
source: <repo>/dist/kiro-cli
files_written: 21

ls .kiro
agents  settings  skills  sops  steering

kiro-cli agent list
  agent-x       Workspace
  kiro_default  (Built-in)   Default agent
  kiro_help     (Built-in)   Help agent ...
  kiro_planner  (Built-in)   Specialized planning agent ...

kiro-cli chat --agent agent-x --no-interactive --trust-tools= "..."
identity/guardrail probe: correctly names "Agent X" and cites the real
`guardrails-no-fabrication.md`.
skill-content probe: names a real activation phrase, but see the migration
entry above / task-5 report — the probe doesn't cleanly isolate whether the
skill:// resources entry or the always-loaded routing steering is the source.

kiro-cli mcp list
workspace: agent-x (empty) — no error; resolves against
.kiro/settings/mcp.json ({"mcpServers": {}}).
```

System Python does not have pytest installed. Current test venv is `/tmp/agent-x-venv` for local ad-hoc pytest runs, but `python3 build/ci.py` with the system `python3` (used above) also runs the full suite (105 tests) directly — no venv activation needed for the CI gate itself.

## Material blockers / gotchas

- GitHub token lacks `workflow` scope. Do not commit `.github/workflows/*` until auth is refreshed with workflow scope, or the push will be rejected. Re-checked 2026-09-04 via `gh auth status`: token scopes are still `gist`, `read:org`, `repo` — no `workflow`.
- Initial Kiro layout validation passed after Task 11/12 against the GUI-oriented `kiro` target. That target was retargeted to the real installed `kiro-cli` tool (see "Kiro-cli target migration" above), and full live/interactive verification against the actual `kiro-cli` 2.20.1 binary has now been performed (Task 5) — deploy, `agent list`, steering/guardrail loading, skill discoverability, and `mcp list` all confirmed working, with one nuance noted about skill body preloading (see above).
- Generated/cache files should be removed before commits: `dist/`, `.pytest_cache/`, `tests/__pycache__/`.
- The full 3,324-line rebuild spec is preserved at `docs/spec/rebuild-spec.md`; README is now a concise operator-facing summary.

## Next task

The kiro-cli target migration (assembler → deploy → launcher → docs → live
verification) is now done and live-verified against the real installed
`kiro-cli` 2.20.1 binary — see "Kiro-cli target migration" above.

The only outstanding item carried over from before this migration is still
Task 14b, and it is still blocked the same way:

Finish Task 14b when GitHub auth has `workflow` scope:
- Add `.github/workflows/validate.yml` as the vendor binding around `python3 build/ci.py`.
- Verify the workflow file locally with syntax/read checks and rerun `python3 build/ci.py`.
- Commit and push only after `gh auth status` includes `workflow`.

Re-checked 2026-09-04: `gh auth status` still reports scopes `gist`,
`read:org`, `repo` only — no `workflow` — so this remains blocked on an auth
refresh, not code.

Also outstanding: the kiro-cli migration commits (see above) are committed
locally but not yet pushed to `origin/build/rebuild-spec-task-1` — push when
ready.

If workflow scope is not available yet, proceed to the next non-workflow task from Section 20 after reading its exact scope from `docs/spec/rebuild-spec.md`.

## Suggested skills for next session

- `github-repo-management`
- `claude-code`
- `ai-product-team`
- `writing-plans`
- `subagent-driven-development`
- `handoff` if creating a temporary handoff document
