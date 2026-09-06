# Native Target Split — Kiro Primary, Claude Code Secondary Native

**Date:** 2026-09-06
**Status:** design approved, plan pending
**Scope:** target assembly, deploy, target-aware validation, tests, docs. No
change to `context/`, `skills/`, `sops/`, or `agents/*.agent.json` source
modules.

## Problem

`build/assemble.py`'s `target_claude_code` emits a Kiro-shaped hybrid, not a
Claude Code native layout:

- `CLAUDE.md` is one flat blob — the assembled system prompt with every eager
  context tier (`routing/`, `guardrails/`, `knowledge/`, `conventions/`)
  appended inline.
- SOPs land at `dist/claude-code/sops/` (repo root, not under `.claude/`).
- Hooks land at `dist/claude-code/hooks.json` (repo root).
- There is **no** `.claude/agents/` file, so `claude --agent agent-x` has
  nothing to discover.
- There is **no** `.claude/settings.json`.
- There is **no** `.claude/rules/` modular context.
- Declared subagents (`agents/readonly-investigator.agent.json`,
  `manifest.subagentNames`) are emitted to **neither** target.
- Skill and SOP bodies cite `context/…` and `sops/…` by repo-relative path;
  those paths do not exist in either emitted target.

`context/scripts/validate-wiring.py` validates the **source tree only**. It
never inspects emitted output, so "a manifest-declared capability was not
emitted into a target" is currently undetectable.

Kiro (`kiro-cli`) remains the primary, fully working target. This change makes
Claude Code a first-class *native* secondary target and adds output-path
validation for both, without degrading Kiro.

## Goals

1. Claude Code output is a native Claude Code project layout.
2. `claude --agent <name>` discovers a generated agent file.
3. `.claude/settings.json` can declare the agent as default, gated by a
   configurable manifest field.
4. Eager context becomes modular `.claude/rules/*.md`, imported by a thin
   `CLAUDE.md`.
5. Declared subagents are emitted to **both** targets.
6. Validation is target-aware and asserts real output paths, failing if a
   declared capability is missing from a target.
7. Skill/SOP citations in the Claude output resolve to emitted paths.
8. Kiro output for existing files stays byte-identical (determinism, no
   degradation).
9. A fork (`agent-x-mish`) can sync this, deploy both targets, and launch each
   with its own name.

## Non-goals

- Translating hooks into Claude Code's native `.claude/settings.json` `hooks`
  schema (matcher/event objects). The neutral aggregated list is relocated to
  `.claude/hooks.json` but not schema-translated. Follow-up.
- Emitting `tool/toolkit/` into any target (pre-existing gap; `demo-skill`
  cites it and it works in dev only because the workspace root is the repo).
- A `settings.local.json` emitter. Not generated; documented as a
  user/local-only artifact.
- Any rewrite of `context/`, `skills/`, `sops/` source content.

## Design

### 1. Manifest field (source stays target-neutral)

Add one optional block to `agent.manifest.json`:

```json
"claudeSettings": { "defaultAgent": false }
```

- `defaultAgent: true` → the Claude emitter writes `{"agent": "<name>"}` into
  `.claude/settings.json`.
- `defaultAgent: false` (or `claudeSettings` absent) → `.claude/settings.json`
  is still emitted, as `{}` (or with any future non-agent settings), with no
  `agent` key.

This is the only manifest change. It is additive; a fork resolving the
recurring `agent.manifest.json` sync conflict keeps its own `name` /
`welcomeMessage` / identity and takes this block.

No change to `wiring.config.json`.

### 2. `build/target_paths.py` (new)

Owns the single citation-rewrite map used by the Claude emitter. Pure
functions, stdlib only, unit-tested in isolation.

```
CLAUDE_CITATION_MAP maps a repo-relative citation token to its emitted
Claude location:

  context/routing/<f>.md      -> .claude/rules/routing-<f>.md
  context/guardrails/<f>.md   -> .claude/rules/guardrails-<f>.md
  context/knowledge/<f>.md    -> .claude/rules/knowledge-<f>.md
  context/conventions/<f>.md  -> .claude/rules/conventions-<f>.md
  sops/<n>.sop.md             -> .claude/sops/<n>.sop.md

Anything else (notably tool/…) is left unchanged.

rewrite_citations(text: str) -> str
    Exact-string replacement over the known token set derived from the
    files actually present on disk. No free-form regex over prose.

rule_filename(context_relpath: str) -> str
    "guardrails/no-fabrication.md" -> "guardrails-no-fabrication.md"
    (the "-".join(parts) convention already used by target_kiro_cli).
```

The rewrite set is built from the real files under `context/{routing,
guardrails,knowledge,conventions}` and `sops/*.sop.md` at assemble time, so a
token is only rewritten when its target file genuinely exists.

### 3. `target_claude_code` rewrite (`build/assemble.py`)

Output tree under `dist/claude-code/`:

```
CLAUDE.md
.mcp.json
.claude/
  settings.json
  hooks.json                       (only if real hook files exist)
  rules/<tier>-<file>.md           (one per eager context file)
  skills/<skill>/…                 (SKILL.md + bundled files, citations rewritten)
  agents/agent-x.md                (primary agent)
  agents/<subagent>.md             (one per subagentNames)
  sops/<name>.sop.md               (citations rewritten)
```

**CLAUDE.md** — thin:

```
<resolve_includes(manifest)>            # identity + domain partials, unchanged helper

---

<!-- Always-on project context (loaded via imports). -->
@.claude/rules/conventions-authoring-conventions.md
@.claude/rules/guardrails-confirm-before-execute.md
@.claude/rules/guardrails-evidence-gate.md
…                                       # one @-import per emitted rule file, sorted
@.claude/rules/routing-00-core.md
@.claude/rules/routing-10-domain-template.md
```

Import lines are sorted by emitted filename for determinism. The rule files
themselves carry the same `<!-- context/<path> -->` source comment that
`eager_block` writes today, so provenance is preserved; they are not wrapped
in `eager_block`'s single concatenation.

**`.claude/rules/<tier>-<file>.md`** — one file per member of
`expand_context_globs(manifest)`, named via `target_paths.rule_filename`,
content = the source file's text with a leading `<!-- context/<relpath> -->`
comment.

**`.claude/skills/<skill>/`** — `copy_tree` as today, then post-process:
every `*.md` in the copied tree is passed through
`target_paths.rewrite_citations`. Bundled non-md files (`scripts/`,
`references/`, `assets/`, `templates/`) are copied unchanged by `copy_tree`
— no new logic needed, but a test locks it in (`escalation-handoff/
templates/handoff.md`).

**`.claude/sops/<name>.sop.md`** — replaces the current root `sops/`
emission for this target. Content passed through `rewrite_citations`.

**`.claude/agents/agent-x.md`** — new:

```markdown
---
name: <manifest.name>
description: <manifest.description or "<name> — assembled by build/assemble.py">
---

<resolve_includes(manifest)>
```

Claude Code discovers project agents by scanning `.claude/agents/*.md` and
reading frontmatter `name`; `claude --agent <name>` resolves to the file
whose frontmatter `name` matches. Filename mirrors `name` for humans. No
`tools:` / `model:` keys emitted (the manifest has no field for them at the
agent level today; adding one is out of scope).

**`.claude/agents/<subagent>.md`** — for each `manifest.subagentNames`
entry, translate `agents/<name>.agent.json`:

| `.agent.json` field | Claude subagent `.md` |
|---|---|
| `name` | frontmatter `name` |
| `description` | frontmatter `description` |
| `tools` + `allowedTools` | frontmatter `tools:` — the intersection that is not write-capable; for `readonly-investigator` that is `read` |
| `systemPromptIncludes` | resolved (same helper) and inlined as the body |
| `contextGlobs` | expanded and appended to the body under a `<!-- context -->` section, OR emitted as extra rule imports — **decision: inline into the body**, to keep a subagent file self-contained |
| `shellAllowedCommands` | **no equivalent** — dropped, recorded as mapping gap #1 |
| `mcpServers` | frontmatter only if non-empty (empty today) |

**`.claude/settings.json`** — `{"agent": "<name>"}` iff
`manifest.claudeSettings.defaultAgent` is `true`, else `{}`. Always emitted.
`json.dumps(..., indent=2, sort_keys=True) + "\n"`.

**`.claude/hooks.json`** — the exact aggregated list
`target_claude_code` builds today, moved from `dist/claude-code/hooks.json`
to `dist/claude-code/.claude/hooks.json`. Same content, same
"real hook files only" rule (`hook_files()` unchanged). Omitted when there
are no real hook files.

**`.mcp.json`** — unchanged (`emit_mcp(manifest, out / ".mcp.json")`).

### 4. `target_kiro_cli` — symmetric subagent emission

Add to `target_kiro_cli`: for each `manifest.subagentNames` entry, load
`agents/<name>.agent.json` and write `dist/kiro-cli/agents/<name>.json`.

- A declared subagent with no `.agent.json` on disk is a hard error (same
  posture as a declared skill/SOP missing).
- Emitted pass-through: the `.agent.json` content, plus the `resources`
  wiring the primary agent gets (`file://.kiro/steering/**/*.md`,
  `skill://.kiro/skills/*/SKILL.md`) if the source omits it, and
  `includeMcpJson: true`. Keep it minimal — match what `emit_kiro_cli_agent`
  produces for the primary so the two are consistent.
- The primary `emit_kiro_cli_agent` is **unchanged** → `agent-x.json` output
  stays byte-identical. Only new `<subagent>.json` files appear.

`build/deploy.py` `MAPPINGS` already contains `"agents"` (whole directory),
so deploy picks up the new files with no change.

### 5. `build/deploy.py` — `--target` flag

Add `--target {kiro-cli,claude-code}`, default `kiro-cli` (preserves current
behavior and every current invocation).

**`--target kiro-cli`** — unchanged. `rmtree(.kiro/)` then copy `MAPPINGS`
(`.kiro/` is 100% generated; clean-slate is safe).

**`--target claude-code`** — **surgical**, because `.claude/` in a real
workspace holds human-authored files (`settings.local.json`, `commands/`,
possibly a hand-written `CLAUDE.md`):

```
CLAUDE_MAPPINGS = (
    "CLAUDE.md",            # root file — overwritten
    ".mcp.json",            # root file — overwritten
    ".claude/rules",        # dir — replaced wholesale (fully generated)
    ".claude/skills",       # dir — replaced wholesale
    ".claude/agents",       # dir — replaced wholesale
    ".claude/settings.json",# file — overwritten
    ".claude/hooks.json",   # file — overwritten (or removed if not generated)
)
```

Only these paths are removed and rewritten. Anything else under `.claude/`
(`settings.local.json`, `commands/`, `mcp.json` variants a user added by
hand) is left untouched. `assert_same_tree` is applied per generated
subpath, not against the whole `.claude/` directory.

`--json` summary gains a `"target"` field.

Docs note: in a **fork**, personalize via the manifest and `context/`, never
by hand-editing the generated `CLAUDE.md` — a `--target claude-code` deploy
overwrites it.

### 6. `build/validate_targets.py` (new) + `build/ci.py`

New module. For each target, assemble into a `tempfile.TemporaryDirectory`
and assert the real output paths. Stdlib only. Exit non-zero on any failure.

**Kiro assertions:**

- `steering/00-system.md` exists and contains the identity marker.
- one `steering/<rule_filename>` per file in `expand_context_globs`.
- `skills/<name>/SKILL.md` for every `manifest.skillNames`.
- `settings/mcp.json` exists and parses.
- `agents/<manifest.name>.json` exists, `name` matches.
- `agents/<sub>.json` for every `manifest.subagentNames`, `name` matches.
- no `hooks/` directory (Kiro omits hooks by choice).

**Claude assertions:**

- `CLAUDE.md` exists, contains the identity marker, and contains an
  `@.claude/rules/<f>` import line for **every** emitted rule file.
- `CLAUDE.md` does **not** inline guardrail bodies (assert a known
  guardrail heading appears only in its rule file, not in `CLAUDE.md`).
- `.claude/rules/<rule_filename>` for every eager context file.
- `.claude/skills/<name>/SKILL.md` for every `manifest.skillNames`.
- copied skill `*.md` contain no residual `context/` or `sops/` citation
  token that has a mapping entry (they were rewritten).
- `.claude/agents/<manifest.name>.md` exists with frontmatter
  `name: <manifest.name>` — the `claude --agent` discovery contract.
- `.claude/agents/<sub>.md` for every `manifest.subagentNames`, frontmatter
  `name` matches, and `tools:` contains no write-capable verb.
- `.mcp.json` exists and parses.
- `.claude/settings.json` exists and parses; has an `agent` key **iff**
  `manifest.claudeSettings.defaultAgent` is true, and its value is
  `manifest.name`.

**Cross-cutting (item 7 core requirement):** a single routine that, given a
manifest and an assembled target dir, asserts every declared capability —
each `skillNames` entry, each `sopNames` entry, each `subagentNames` entry,
each eager context file — is present at that target's expected path. Missing
→ FAIL with a message naming the capability and the expected path.

**`build/ci.py`:** replace the three bare `assembler smoke: <target>`
stages with one `target-aware validation` stage that runs
`build/validate_targets.py`. (It assembles all targets internally, so smoke
coverage is retained and strengthened.) `test_validate_targets.py` is picked
up by the existing `pytest` stage.

### 7. `.gitignore`

Current: `dist/`, `.kiro/`, `.kiro-agents/`, `agents/registry.local.json`,
`local/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`.

Add the Claude artifacts a `--workspace-root .` deploy generates into the
repo tree — narrow entries, not all of `.claude/`:

```
/CLAUDE.md
/.mcp.json
/.claude/rules/
/.claude/skills/
/.claude/agents/
/.claude/hooks.json
/.claude/settings.json
```

Verified 2026-09-06: nothing under `.claude/` is tracked in `agent-x`
(`git ls-files .claude/` is empty; only a runtime `scheduled_tasks.lock`
exists on disk, already excluded via `.git/info/exclude`), and there is no
root `CLAUDE.md` or `.mcp.json`. So all seven entries above are safe to add
and there is no committed hand-authored `.claude/settings.json` to protect.
The surgical deploy behavior (§5) still matters for **forks and external
workspaces**, where `.claude/` routinely holds human-authored files.

### 8. Tests

**`tests/test_assemble.py` — rewrite the `--- claude-code target ---`
section.** Remove assertions encoding the old layout:

- `test_claude_code_target_writes_claude_md_with_prompt_and_eager_tiers` —
  the eager tiers are no longer inline. Replace with: `CLAUDE.md` has the
  prompt markers and `@.claude/rules/` import lines; a known guardrail body
  is **not** in `CLAUDE.md`.
- `test_claude_code_target_copies_declared_sops` — path moves to
  `.claude/sops/<name>.sop.md`.
- `test_claude_code_target_omits_hooks_json_when_no_hooks` /
  `test_claude_code_target_writes_hooks_json_when_hooks_exist` — path moves
  to `.claude/hooks.json`.
- keep `test_claude_code_target_writes_mcp_json`,
  `…_copies_declared_skill_dir` (path already `.claude/skills/…`),
  `…_missing_declared_skill_is_hard_error`,
  `…_is_deterministic_across_two_runs`.

Add:

- `.claude/rules/<tier>-<file>.md` emitted per eager context file, with the
  source-path comment.
- `CLAUDE.md` import list is sorted and complete.
- `.claude/agents/<name>.md` exists with `name: <name>` frontmatter (drives
  `claude --agent` discovery) — use `copy_package` + `set_manifest` to also
  test a renamed manifest so the fork case is covered name-agnostically.
- `.claude/agents/<subagent>.md` emitted; `tools:` excludes write verbs;
  body contains the subagent prompt text.
- skill `*.md` citations rewritten: `.claude/rules/guardrails-…` present,
  bare `context/guardrails/…` absent.
- bundled skill file copied: `escalation-handoff/templates/handoff.md`
  present under `.claude/skills/escalation-handoff/templates/`.
- `.claude/settings.json` emitted as `{}` by default; as
  `{"agent": "<name>"}` when `claudeSettings.defaultAgent` is true —
  parametrized via `set_manifest`.

**`tests/test_assemble.py` — kiro-cli section.** Add:

- `agents/<subagent>.json` emitted for a `subagentNames` entry; `name`
  matches; missing `.agent.json` for a declared subagent is a hard error.
- `agents/agent-x.json` output is unchanged (byte-compare against a
  pre-recorded expectation or assert the specific fields the existing tests
  already check — determinism guard).

**`tests/test_validate_targets.py` (new).**

- Kiro layout of the real package validates clean.
- Claude layout of the real package validates clean.
- deleting a declared skill dir from a package copy → Kiro validation
  FAILS naming the skill; Claude validation FAILS naming the skill.
- removing a `subagentNames` target `.agent.json` → both FAIL.
- `claudeSettings.defaultAgent` true but `settings.json` lacking the
  `agent` key (simulated by a patched emitter, or asserted positively) →
  FAIL. (Primarily: assert the positive — key present ⇔ flag true.)

**`tests/test_deploy.py`.** Add:

- `--target claude-code` writes `CLAUDE.md`, `.mcp.json`, `.claude/rules/`,
  `.claude/skills/`, `.claude/agents/<name>.md`, `.claude/settings.json`
  into the workspace root, matching the assembled output.
- surgical guarantee: a pre-existing `.claude/settings.local.json` and
  `.claude/commands/foo.md` in the workspace **survive** a
  `--target claude-code` deploy.
- `--target kiro-cli` (explicit) behaves exactly as the current default.
- Kiro deploy now also lands `agents/<subagent>.json`.

All new tests follow the suite's conventions: isolated `tmp_path` copies,
real subprocess invocations, real file assertions, no mocks.

### 9. Docs

**`README.md`:**

- "Build targets" section: reframe as **Primary target: kiro-cli** /
  **Secondary native target: Claude Code** (drop "Portable fallback" framing
  change for `generic` — leave `generic` as-is).
- Show both deploy + launch paths:
  ```
  python3 build/deploy.py                        # kiro-cli
  kiro-cli chat --agent agent-x

  python3 build/deploy.py --target claude-code   # Claude Code
  claude --agent agent-x
  ```
- Add a per-target "where each target expects what" table:

  | | kiro-cli | Claude Code |
  |---|---|---|
  | System prompt | `.kiro/steering/00-system.md` | `CLAUDE.md` (thin) |
  | Eager context | `.kiro/steering/<tier>-*.md` | `.claude/rules/<tier>-*.md` (imported by `CLAUDE.md`) |
  | Skills | `.kiro/skills/<name>/` | `.claude/skills/<name>/` |
  | SOPs | `.kiro/sops/` | `.claude/sops/` |
  | Agent | `.kiro/agents/<name>.json` | `.claude/agents/<name>.md` |
  | Subagents | `.kiro/agents/<sub>.json` | `.claude/agents/<sub>.md` |
  | MCP | `.kiro/settings/mcp.json` | `.mcp.json` |
  | Hooks/settings | agent-config `hooks` block (not emitted) | `.claude/settings.json`, `.claude/hooks.json` (neutral list) |
  | Default agent | `--agent` flag | `--agent` flag, or `.claude/settings.json` `{"agent": …}` |

- "Architecture" tree: add the new `build/` modules.
- Update the mermaid `flowchart LR` to show `--target claude-code` → deploy
  → `.claude/` → `claude --agent`.

**`docs/spec/rebuild-spec.md` §13:**

- Rewrite the §13.2 "Target bindings" table to the native Claude layout.
- Update the embedded `build/assemble.py` listing (§13.3) to match the
  rewritten `target_claude_code` and the `target_kiro_cli` subagent loop.
- Update the embedded `build/ci.py` listing to the new validation stage.
- New subsection: "§13.6 Claude Code native layout" — the `.claude/` tree,
  the `@`-import mechanism (Claude Code has no `.claude/rules/` auto-load;
  files load only via `CLAUDE.md` imports), the citation-rewrite map, the
  `claude --agent` discovery contract.
- New subsection: "§13.7 Mapping gaps" — the four gaps below.
- Note `build/target_paths.py` and `build/validate_targets.py` as the two
  new build modules.

**`docs/onboarding.md`:** §4 file map — add the two new build modules and
`build/validate_targets.py`'s role in "verifying you're done". §6 gotchas —
note the Claude deploy is surgical about `.claude/` and the new
manifest-name coupling in `tests/test_assemble.py` / `test_validate_targets.py`.

**`docs/sync-workflow.md`:** the `agent.manifest.json` conflict section
already covers additive fields; add `claudeSettings` to the worked example's
"take the new field, keep your name" note.

**`docs/progress/PROJECT_PROGRESS.md`:** dated entry — what changed, why,
what verified it.

## Mapping gaps (to report on completion)

1. **`shellAllowedCommands`** — the `readonly-investigator` subagent's shell
   allowlist has no representation in a Claude `.claude/agents/*.md` file.
   Claude's read-only guarantee for that subagent rests entirely on `tools:`
   excluding write verbs. Kiro keeps the full allowlist. A user who needs a
   shell-command allowlist under Claude must add it via `.claude/settings.json`
   `permissions` by hand.
2. **Hooks schema** — Claude Code's native hooks are matcher/event objects in
   `.claude/settings.json`. The repo's `hooks/*.hook.json` are Kiro-flavored.
   This change relocates the neutral aggregated list to `.claude/hooks.json`
   but does not translate it — it will not auto-run under Claude Code.
   Follow-up: a real translator, or a decision to author Claude hooks
   separately.
3. **`tool/toolkit/`** — cited by `demo-skill`, emitted into no target. Works
   in dev only because the workspace root is the repo. Not addressed here.
4. **`welcomeMessage`** — a `kiro-cli` agent-config field with no
   `.claude/agents/*.md` equivalent. Dropped for the Claude target.

## Rollout / fork port

1. Land in `agent-x` on branch `reorg-test`, green `python3 build/ci.py`,
   merge.
2. In `agent-x-mish`: `python3 build/sync_template.py`.
3. Resolve the `agent.manifest.json` conflict — keep fork `name` /
   `welcomeMessage` / identity, take `claudeSettings`.
4. Re-run the manifest-name test-coupling grep-and-fix
   (`docs/sync-workflow.md` "Known follow-up") for the new hard-coded
   `agent-x` assertions in `test_assemble.py` / `test_validate_targets.py`.
5. `python3 build/ci.py` green in the fork.
6. `python3 build/deploy.py && kiro-cli chat --agent agent-x-mish`
7. `python3 build/deploy.py --target claude-code && claude --agent agent-x-mish`

## Open items for the plan

- Decide whether the Claude subagent body inlines `contextGlobs` expansion or
  emits extra rule imports (§3 leans inline; confirm during implementation
  against how a real Claude subagent file consumes context).
