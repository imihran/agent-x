# Kiro CLI Target Migration — Design

Date: 2026-09-04
Status: approved, pending implementation plan

## Problem

The repo's `kiro` assembler target (and `build/deploy.py`/`build/kiro_agent.py`,
which consume it) was built against the Kiro **GUI editor**'s steering/skills/
hooks layout. It never accounted for **kiro-cli**, a separate, independently
installed terminal tool with its own agent-activation format
(`.kiro/agents/<name>.json`, activated with `kiro-cli chat --agent <name>`).

This is a gap in the original spec, not implementation drift: `docs/spec/rebuild-spec.md`
(and the identical text at the `origin/main` commit `1f8d53c`, before this
branch's implementation work) only ever specifies the `kiro` target's
steering/`.kiro.hook` layout — `kiro-cli` is never mentioned. Confirmed via
`git show origin/main:README.md` — zero matches for "kiro-cli" or "kiro cli"
anywhere in the 3324-line original spec.

The user's actual day-to-day tool is `kiro-cli` (confirmed running in an
active terminal session during this investigation), not the GUI editor.

## Decision

Replace the `kiro` target with a `kiro-cli` target. This is a rename +
behavior change, not an additional target — the GUI editor's steering-only
layout is dropped, per explicit user decision (asked directly: "kiro-cli
only" was chosen over "both" or "kiro-cli primary, GUI secondary").

## Evidence: empirically verified kiro-cli behavior

Verified live against the installed `kiro-cli 2.20.1` (default `--agent-engine
v2`), in this repo, because the fetched official docs
(kiro.dev/docs/custom-agents/configuration-reference/) were ambiguous or
wrong on exactly these points:

1. **Steering auto-loads for every agent, unconditionally.** A custom agent
   config with `"resources": []` still correctly cited
   `guardrails-no-fabrication.md`'s content. `.kiro/steering/**/*.md` loads
   regardless of what an agent's `resources` field declares.
2. **Skills do NOT auto-load.** The same empty-`resources` agent explicitly
   said it hadn't read `SKILL.md` and would need a tool call to do so. Skill
   content only preloads if the agent config declares
   `"skill://.kiro/skills/*/SKILL.md"` in `resources`.
3. **`includeMcpJson` reads `.kiro/settings/mcp.json`**, not the top-level
   `.kiro/mcp.json` our assembler currently writes. Confirmed by running
   `kiro-cli mcp add --name __probe_test --command echo` and observing the
   file it wrote to (`.kiro/settings/mcp.json`), then removing the probe
   entry.
4. **`file://` relative paths resolve against the workspace root /
   invocation cwd**, not the agent config file's own directory (the docs
   claimed the latter). Confirmed with an unguessable marker string
   (`MARKER_TOKEN=xk7q2m9v4z`) in a throwaway resource file, referenced by a
   plain relative path, invoked from the workspace root.
5. **No hook support in the default/stable engine.** `hooks` in an agent
   config is documented only on the `--v3` experimental-engine page; absent
   from the stable configuration-reference page. `kiro-cli --help-all`
   surfaces no hook-related subcommand or concept at all.

All probe files were temporary and removed after each test; none were
committed.

## Architecture

```
agent.manifest.json  (single source, unchanged)
        │
        ▼
build/assemble.py --target kiro-cli
        │  reuses existing steering/skills/sops emission verbatim;
        │  writes mcp under settings/; adds agents/<name>.json
        ▼
dist/kiro-cli/
  ├── steering/00-system.md + one file per eager-tier file   (unchanged logic)
  ├── skills/<name>/                                          (unchanged logic)
  ├── sops/<name>.sop.md                                      (unchanged logic)
  ├── settings/mcp.json                    ← was dist/kiro/mcp.json
  └── agents/<manifest.name>.json           ← NEW
        │
        ▼
build/deploy.py  (copies dist/kiro-cli/* into <workspace-root>/.kiro/*,
                  same idempotent clean-then-copy-then-verify pattern as today)
        ▼
<workspace-root>/.kiro/{steering,skills,sops,settings/mcp.json,agents/<name>.json}
        │
        ▼
kiro-cli chat --agent <name>   (invoked by build/kiro_agent.py, cwd=workspace-root)
```

## Component changes

### `build/assemble.py`
- `TARGETS = ("claude-code", "kiro-cli", "generic")`
- `target_kiro_cli(manifest, out)` replaces `target_kiro`:
  - Steering emission: unchanged (`resolve_includes` + `expand_context_globs`
    → `out/steering/00-system.md` + one file per eager-tier file)
  - Skills: unchanged (`declared_skill_dirs` → `out/skills/<name>/`)
  - SOPs: unchanged (`copy_sops` → `out/sops/<name>.sop.md`)
  - MCP: `emit_mcp(manifest, out / "settings" / "mcp.json")` (path changed
    from `out / "mcp.json"`)
  - New: write `out/agents/<manifest["name"]>.json`:
    ```json
    {
      "name": "<manifest.name>",
      "description": "<manifest.description>",
      "prompt": null,
      "mcpServers": {},
      "tools": <manifest.tools if non-empty else ["*"]>,
      "allowedTools": <manifest.allowedTools>,
      "resources": [
        "file://.kiro/steering/**/*.md",
        "skill://.kiro/skills/*/SKILL.md"
      ],
      "includeMcpJson": true,
      "model": null
    }
    ```
    `tools` defaults to `["*"]` when the manifest's list is empty — an empty
    manifest.tools today means "not yet restricted," not "zero tools usable";
    mapping it literally would ship an agent that can do nothing.
    Steering is listed in `resources` explicitly even though it auto-loads
    (finding #1) — self-documenting, and doesn't depend on an unstated
    default that could change across kiro-cli versions.
  - No hook emission — no consumer in the target engine (finding #5). Same
    precedent as today's `generic` target ("omitted — no hook runtime
    assumed").
- `hook_files()` helper stays (still used by `target_claude_code`).

### `build/deploy.py`
- `MAPPINGS = ("steering", "skills", "sops", "settings/mcp.json", "agents")`
  (was `("steering", "skills", "hooks", "sops", "mcp.json")`)
- `assemble()` invokes `--target kiro-cli` (was `kiro`)
- `copy_path` needs no change — it already `mkdir(parents=True)`s the
  destination's parent, so a nested mapping entry like `"settings/mcp.json"`
  copies correctly.
- `assert_same_tree` needs no change — it's a generic recursive dircmp.

### `build/kiro_agent.py`
Real rework, not a rename — the CLI surface it targets is different:
- Deploy step (call `deploy.py`, then read its JSON summary) is unchanged.
- Launch command changes from the GUI's window-launch shape
  (`kiro chat --mode agent --profile <name>`) to kiro-cli's terminal-chat
  shape (`kiro-cli chat --agent <name> [prompt]`).
- Flags that only made sense for the GUI (`--mode`, `--reuse-window`,
  `--new-window`, `--user-data-dir`, `--add-file`) are dropped.
- New passthrough flags matching kiro-cli's real surface: `--no-interactive`,
  `--trust-all-tools` (default off — P5/P8 confirm-before-side-effects stays
  the default; a caller opts in explicitly), `--model`, `--effort`.
- `--dry-run` output shape (JSON with `command`/`shell_command`/`deploy`)
  stays the same idea, values reflect the new command.

### Tests
- `tests/test_assemble.py`: every `"--target", "kiro"` → `"--target",
  "kiro-cli"`; mcp assertion path → `settings/mcp.json`; the two
  hook-specific kiro tests
  (`test_kiro_target_omits_hooks_dir_when_no_hooks`,
  `test_kiro_target_writes_kiro_hook_file_when_hooks_exist`) are replaced
  with agent-config tests (file exists, `resources`/`tools`/`allowedTools`
  populated correctly, `tools` defaults to `["*"]` when manifest's is empty).
- `tests/test_sops_hooks_ci.py`: `test_assemblers_emit_hooks_for_kiro_and_claude`
  scoped to claude-code only (kiro-cli emits no hooks).
- `tests/test_deploy.py`: path assertions updated
  (`.kiro/settings/mcp.json`, `.kiro/agents/agent-x.json`); hook assertion
  removed.
- `tests/test_kiro_agent_runner.py`: rewritten expected subprocess command
  construction; GUI-only flag tests removed, kiro-cli flag tests added.
- `build/ci.py`: smoke-test label/command updated to `kiro-cli`.

### `docs/spec/rebuild-spec.md` (canonical spec — the actual fix for "the miss")
- Target concept table: `kiro` column → `kiro-cli` column, describing the
  agent-config + resources mechanism, `settings/mcp.json`, no hooks.
- `target_kiro` code listing → `target_kiro_cli`.
- `TARGET_FUNCS` registry listing updated.
- Hooks section prose: replace "`kiro` target renames each file to
  `<name>.kiro.hook`" with the kiro-cli non-support note (finding #5),
  matching the existing `generic`-target precedent already in that
  paragraph.
- CLI usage line: `--target claude-code|kiro|generic` →
  `--target claude-code|kiro-cli|generic`.
- New subsection recording the five empirically-verified behaviors above,
  so this isn't relearned the hard way again.

### `README.md`
Quick start's step 3 changes from "Open the repo folder in Kiro" to
`kiro-cli chat --agent agent-x`. CLI-reference lines mentioning `kiro chat
--profile` updated to `kiro-cli chat --agent`.

### `docs/progress/PROJECT_PROGRESS.md`
Append a new dated section after implementation (existing convention —
append-only log, not rewritten), noting the target rename and why.

## Error handling

No new error-handling design needed — `deploy.py`'s existing `fail()` /
`assert_same_tree()` pattern (hard-fail on any mismatch between assembled
and deployed trees) already covers the new `agents/` and `settings/`
mappings without modification, since it walks whatever `MAPPINGS` lists.

## Testing strategy

Existing test shape (assemble in an isolated tmp copy of the repo, run
target, assert files/content) is reused as-is. New assertions target the
new `agents/<name>.json` file's exact shape and the moved `mcp.json`
location. `build/ci.py` (93→now 101 tests, +new ones) must stay green.

## Explicitly out of scope

- **`subagentNames` never being assembled into any target's output.**
  Real, pre-existing gap (validated by `validate-wiring.py` but not emitted
  anywhere), unrelated to the kiro-cli/GUI distinction — affects all three
  targets equally. Not addressed here.
- **kiro-cli's `--v3` experimental engine's inline `hooks` object.** Only
  documented on the v3 page; our target assumes the default v2 engine.
  Revisit if/when v3 becomes the installed default.
- **Root directory restructuring** (`context/`, `skills/`, `sops/` etc. into
  one consolidated folder). Raised and explicitly declined in favor of the
  current flat layout, which matches the original spec's Section 3 package
  layout.
