# Agent X Project Progress

Last updated: 2026-09-05, after merging to `main`, adding the template-sync
workflow, and forking `agent-x-mish`.

**New agent/session picking this up: read `docs/onboarding.md` first** — it's
the "how development works here" guide (conventions, gotchas, the core dev
loop). This file is the running state/history log, not the onboarding doc.

## Current goal

Build the Agent Capability Package from the rebuild specification. This is primarily a kiro-cli agent/capability package; Claude Code support is secondary. Claude Code is being used as the implementation agent. kiro-cli layout validation has begun and should become fuller runtime/load validation as the base package matures.

## Repository state

- Local repo: `/home/mish/Documents/GitHub/agent-x`
- Remote: `https://github.com/imihran/agent-x` (private)
- Working branch: `main`. The long-lived `build/rebuild-spec-task-1` branch
  that carried Tasks 1–14a and the kiro-cli migration was merged into `main`
  and deleted (local + kept on origin at merge time; check before assuming
  it still exists remotely) once `main`'s tests passed on the merged result.
- A `dump` branch, also on origin, preserves the original 2-commit spec-dump
  state of `main` from before any rebuild work — a permanent snapshot, not
  meant to be developed on.
- A real fork exists: `agent-x-mish`
  (`/home/mish/Documents/GitHub/agent-x-mish`, own GitHub repo, private),
  linked back to this repo via a `template` git remote. See
  `docs/sync-workflow.md` for the full mechanics. `agent-x` itself must stay
  free of Mish-specific content (no personal skills, no hardcoded personal
  paths) — that belongs in `agent-x-mish` or other forks, not the template.
- Main README: `README.md`
- Preserved rebuild spec: `docs/spec/rebuild-spec.md`
- Onboarding guide: `docs/onboarding.md`
- Fork-sync guide: `docs/sync-workflow.md`
- Current latest pushed commit: `9c9d209 docs: capture the template-sync workflow in full detail`

## User instructions / operating rules

- Commit and push after every implementation step so rollback is easy.
- After every step, give a short summary of what changed and anything material.
- Small updates do not require waiting for review.
- Maintain this progress file as work proceeds so a new session can resume if context runs out.
- Keep `agent-x` generic: no Mish-specific data, no secrets, no hardcoded personal paths in shipped source.
- `agent-x` is a placeholder/codename; keep naming easy to change.
- Primary runtime target is kiro-cli. Claude Code is the implementer and secondary artifact target.

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

Full transcripts and step-by-step assessment lived at
`.superpowers/sdd/2026-09-04-kiro-cli-target-migration/task-5-report.md`
during implementation; that plan workspace was deleted after the final
whole-branch review passed clean (standard subagent-driven-development
cleanup) — the git history at the commits listed above is the durable
record now. The full design rationale is preserved at
`docs/superpowers/specs/2026-09-04-kiro-cli-target-migration-design.md` and
the task-by-task plan at
`docs/superpowers/plans/2026-09-04-kiro-cli-target-migration.md`.

### Post-migration: welcome message, README docs, and template-sync tooling

Commits (on `main`): `6b96209` feat: welcome message, README architecture
docs, and template-sync tooling; `3c43f33` fix: clean each target's output
dir before reassembling; `9c9d209` docs: capture the template-sync workflow
in full detail.

- `agent.manifest.json` gained a `version` field; `build/assemble.py`'s
  `emit_kiro_cli_agent` now composes a `welcomeMessage` (author text +
  `(v<version>)`) into the emitted kiro-cli agent config — live-verified:
  `kiro-cli chat --agent agent-x` shows "Agent X — ready to help. (v0.1.0)"
  before its first response.
- README gained a "How it works" section (assembly pipeline + routing-gate
  Mermaid diagrams, the five-context-tier table) and a worked end-to-end
  example tracing `demo-skill`'s "run the demo" through the real
  routing/skill/guardrail/toolkit flow — live-verified against `kiro-cli`,
  including the confirm-before-execute gate holding even with shell
  execution fully trusted, and annotated as such in README.
- **Real bug found and fixed**: `build/assemble.py` never cleaned
  `dist/<target>/` between runs, so renaming an agent (or anything else
  changing an output filename) left orphaned files behind that
  `build/deploy.py` then faithfully copied into `.kiro/` too. Found live
  while personalizing `agent-x-mish`'s manifest name — `kiro-cli agent
  list` showed a phantom `agent-x` entry that didn't match the current
  manifest. Fixed test-first (`test_reassembling_into_same_out_dir_removes_
  stale_files_from_prior_run`, confirmed RED then GREEN); `main()` now
  `rmtree`s the target's own output dir before writing, same pattern
  `build/deploy.py` already used for `.kiro/`.
- `build/sync_template.py` added: lets a fork pull updates from this repo
  via a `template` git remote (fetch, `--no-ff` merge so every sync leaves
  a visible commit, conflicts reported not auto-resolved, `build/ci.py` run
  automatically after a clean merge, never pushes). Full mechanics,
  including the recurring `agent.manifest.json` conflict pattern and a
  worked example with real commit SHAs, documented in
  `docs/sync-workflow.md`.

### Forked `agent-x-mish` and proved the sync loop end to end

Not commits on `agent-x`'s own history (this repo stayed the template), but
material state worth recording here since it's this repo's first real fork:

- `agent-x-mish` (`/home/mish/Documents/GitHub/agent-x-mish`) was created —
  an empty repo populated by merging this repo's full history in with
  `--allow-unrelated-histories`, then personalizing `agent.manifest.json`'s
  `name` to `agent-x-mish` (which required fixing several tests that
  hardcoded `agent-x` against the real manifest — see `docs/sync-workflow.md`).
- Proved the fork-sync loop for real: added a fork-local skill
  (`mish-notes`) in `agent-x-mish`, made the stale-`dist/`-files fix above
  in `agent-x` as a genuine "minor template update," then ran `python3
  build/sync_template.py` in `agent-x-mish` — clean merge (no conflict,
  since the update touched files the fork never had), `build/ci.py` ran
  automatically and passed. Both the fork-local skill and the template fix
  coexisted correctly afterward.
- Also ported a real personal skill from an unrelated tool (a Hermes Agent
  skill at `~/.hermes/skills/devops/mish-hermes-host-topology/SKILL.md`)
  into `agent-x-mish` as `mish-host-topology` — reshaped into this
  template's `SKILL.md`/routing/manifest wiring format, live-verified to
  activate correctly and answer using the real ported knowledge.

## Current verification status

Latest verified 2026-09-05 on `main`, against the real installed `kiro-cli`
2.20.1 binary (not just tests against `tmp_path` copies):

```text
python3 build/ci.py
WIRING VALIDATION: PASS (all capabilities) — fully wired
TOOL CONTRACT: AGREE
CLI REFERENCES: AGREE
115 passed in ~5s
assembled target=claude-code out=<repo>/dist/claude-code
assembled target=kiro-cli out=<repo>/dist/kiro-cli
assembled target=generic out=<repo>/dist/generic
CI GATE: PASS — all stages green

kiro-cli chat --agent agent-x --no-interactive --trust-tools= "..."
welcome message: "Agent X — ready to help. (v0.1.0)" displays before the
first response — confirmed live.
identity/guardrail probe: correctly names "Agent X" and cites the real
`guardrails-no-fabrication.md`.
demo-skill full loop probe: "run the demo" correctly activates the gate
(reads SKILL.md before any other tool call), runs the read path, proposes
the gated write with an exact pre-execution summary citing its own source
("demo-skill § Workflow step 2–3"), holds for confirmation even with shell
execution fully trusted, then on confirmation executes and reports the
toolkit's real `"verified": "read-back"` result — full loop genuinely
confirmed end to end, not just the activation step.
```

`agent-x-mish` (the fork) independently confirms the same shape:
`python3 build/ci.py` green there too (115 passed), `mish-notes` and
`mish-host-topology` (fork-local skills) both live-verified to activate
correctly via real `kiro-cli` sessions.

System Python does not have pytest installed as a separate package; running
`python3 build/ci.py` or `python3 -m pytest tests/` with the system
`python3` works directly (confirmed repeatedly this session) — no venv
needed for the CI gate itself.

## Material blockers / gotchas

- **GitHub token still lacks `workflow` scope** (Task 14b remains blocked —
  see below). Re-checked 2026-09-05 via `gh auth status`: token scopes are
  `gist`, `read:org`, `repo` — no `workflow`. Do not commit
  `.github/workflows/*` until this is refreshed, or the push will be
  rejected.
- `build/assemble.py` used to leave stale files in `dist/<target>/` across
  runs with different manifest settings — fixed (`3c43f33`). See
  `docs/onboarding.md`'s "Known gotchas" for the symptom
  (`rm -rf dist .kiro` if you ever see a phantom agent).
- Generated/cache files should be removed before commits: `dist/`,
  `.pytest_cache/`, `tests/__pycache__/`, `.kiro/` (all gitignored).
- The full 3,324-line rebuild spec is preserved at
  `docs/spec/rebuild-spec.md`; README is a concise operator-facing summary;
  `docs/onboarding.md` is the "how to work here" guide for a new
  agent/session.

## Next task

No active development task right now — the kiro-cli migration, the
welcome-message/README/sync-tooling additions, and the `agent-x-mish` fork
are all done, live-verified, committed, and pushed.

The only outstanding item, carried over unchanged from before all of the
above, is still Task 14b:

Finish Task 14b when GitHub auth has `workflow` scope:
- Add `.github/workflows/validate.yml` as the vendor binding around `python3 build/ci.py`.
- Verify the workflow file locally with syntax/read checks and rerun `python3 build/ci.py`.
- Commit and push only after `gh auth status` includes `workflow`.

Re-checked 2026-09-05: `gh auth status` still reports scopes `gist`,
`read:org`, `repo` only — no `workflow` — so this remains blocked on an auth
refresh, not code.

If workflow scope is not available yet, proceed to the next non-workflow
task from Section 20 after reading its exact scope from
`docs/spec/rebuild-spec.md` — or, if picking this up as a new
agent/session, read `docs/onboarding.md` first regardless.

## Suggested skills for next session

- `github-repo-management`
- `claude-code`
- `ai-product-team`
- `writing-plans`
- `subagent-driven-development`
- `handoff` if creating a temporary handoff document
