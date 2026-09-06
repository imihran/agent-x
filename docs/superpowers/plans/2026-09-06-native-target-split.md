# Native Target Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude Code a native secondary build target (thin `CLAUDE.md` + `@`-imported `.claude/rules/`, `.claude/agents/` for `claude --agent`, `.claude/settings.json`, `.claude/skills/` with rewritten citations), add symmetric subagent emission for both targets, and add target-aware output validation — without changing Kiro output for existing files.

**Architecture:** `build/assemble.py` keeps one manifest-driven pipeline with per-target emit functions. A new `build/target_paths.py` owns the `context/… → .claude/rules/…` and `sops/… → .claude/sops/…` citation-rewrite map. `target_claude_code` is rewritten to the native layout; `target_kiro_cli` gains a subagent loop that leaves its existing output byte-identical. A new `build/validate_targets.py` assembles each target into a temp dir and asserts real paths, replacing the three bare assembler smokes in `build/ci.py`. `build/deploy.py` gains `--target {kiro-cli,claude-code}` with a *surgical* Claude mode that never wipes `.claude/`.

**Tech Stack:** Python 3.12, stdlib only. pytest (real `tmp_path` copies, real subprocess invocations, real file assertions, no mocks). Deterministic builds — same inputs, byte-identical outputs, no timestamps.

**Spec:** `docs/superpowers/specs/2026-09-06-native-target-split-design.md`

## Global Constraints

- **Stdlib only.** No new dependencies in any build script.
- **Deterministic output.** Same inputs → byte-identical outputs. Sort every directory walk (`sorted(root.rglob(...))`), sort every emitted list, never embed a timestamp.
- **Kiro output for existing files stays byte-identical.** `emit_kiro_cli_agent` and every current `dist/kiro-cli/` path are untouched; only new `agents/<subagent>.json` files may appear. The existing `tests/test_assemble.py` kiro-cli assertions must keep passing unmodified.
- **No source-module rewrites.** `context/`, `skills/`, `sops/`, `agents/*.agent.json` content is not edited. The only source change is the additive `claudeSettings` block in `agent.manifest.json`.
- **TDD, RED first.** Every behavior change: update/write the test, run it, watch it fail for the right reason, implement minimally, watch it pass.
- **Commit per task.** Small, single-concern commits. End every commit message with:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC
  ```
- **Spec code listings.** `docs/spec/rebuild-spec.md` §13.3 embeds `build/assemble.py` and §... embeds `build/ci.py`. If you change those files' behavior, update the embedded listing in Task 10 — the repo has shipped spec/code drift before.
- **Branch:** `reorg-test` (already created).
- **Full gate:** `python3 build/ci.py` must be green before any task is called done.

---

### Task 1: `build/target_paths.py` — citation-rewrite map

**Files:**
- Create: `build/target_paths.py`
- Test: `tests/test_target_paths.py`

**Interfaces:**
- Consumes: nothing (leaf module, stdlib only).
- Produces:
  - `rule_filename(context_relpath: str) -> str` — `"guardrails/no-fabrication.md"` → `"guardrails-no-fabrication.md"`.
  - `build_citation_map(context_dir: Path, sops_dir: Path) -> dict[str, str]` — maps each on-disk citation token to its emitted `.claude/` path.
  - `rewrite_citations(text: str, citation_map: dict[str, str]) -> str` — replaces every known token, longest-first.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_target_paths.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))

import target_paths  # noqa: E402


def test_rule_filename_joins_parts_with_hyphen():
    assert target_paths.rule_filename("guardrails/no-fabrication.md") == "guardrails-no-fabrication.md"
    assert target_paths.rule_filename("routing/00-core.md") == "routing-00-core.md"


def test_build_citation_map_covers_context_tiers_and_sops(tmp_path):
    ctx = tmp_path / "context"
    (ctx / "guardrails").mkdir(parents=True)
    (ctx / "routing").mkdir(parents=True)
    (ctx / "guardrails" / "no-fabrication.md").write_text("x", encoding="utf-8")
    (ctx / "routing" / "00-core.md").write_text("x", encoding="utf-8")
    sops = tmp_path / "sops"
    sops.mkdir()
    (sops / "wire-new-capability.sop.md").write_text("x", encoding="utf-8")

    m = target_paths.build_citation_map(ctx, sops)

    assert m["context/guardrails/no-fabrication.md"] == ".claude/rules/guardrails-no-fabrication.md"
    assert m["context/routing/00-core.md"] == ".claude/rules/routing-00-core.md"
    assert m["sops/wire-new-capability.sop.md"] == ".claude/sops/wire-new-capability.sop.md"


def test_build_citation_map_omits_tokens_with_no_file_on_disk(tmp_path):
    ctx = tmp_path / "context"
    (ctx / "guardrails").mkdir(parents=True)
    sops = tmp_path / "sops"
    sops.mkdir()

    m = target_paths.build_citation_map(ctx, sops)

    assert m == {}


def test_rewrite_citations_replaces_known_tokens_and_leaves_others(tmp_path):
    citation_map = {
        "context/guardrails/no-fabrication.md": ".claude/rules/guardrails-no-fabrication.md",
        "sops/wire-new-capability.sop.md": ".claude/sops/wire-new-capability.sop.md",
    }
    text = (
        "See `context/guardrails/no-fabrication.md` and "
        "`sops/wire-new-capability.sop.md`. Run `tool/toolkit/toolkit.py list`."
    )

    out = target_paths.rewrite_citations(text, citation_map)

    assert ".claude/rules/guardrails-no-fabrication.md" in out
    assert ".claude/sops/wire-new-capability.sop.md" in out
    assert "context/guardrails/no-fabrication.md" not in out
    assert "tool/toolkit/toolkit.py" in out  # not in the map — untouched


def test_rewrite_citations_longest_token_wins(tmp_path):
    # a shorter token that is a prefix of a longer one must not shadow it
    citation_map = {
        "context/knowledge": ".claude/rules/SHOULD-NOT-WIN",
        "context/knowledge/domain-glossary.md": ".claude/rules/knowledge-domain-glossary.md",
    }
    out = target_paths.rewrite_citations("context/knowledge/domain-glossary.md", citation_map)
    assert out == ".claude/rules/knowledge-domain-glossary.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_target_paths.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'target_paths'`.

- [ ] **Step 3: Write minimal implementation**

```python
# build/target_paths.py
#!/usr/bin/env python3
"""Path mapping for the claude-code target.

The source tree cites context files and SOPs by repo-relative path
(`context/guardrails/x.md`, `sops/y.sop.md`). The claude-code target emits
those under `.claude/`, so copied skill and SOP bodies need their citations
rewritten to the emitted locations. This module owns that map.

Stdlib only. Pure functions.
"""
from __future__ import annotations

from pathlib import Path

# context tiers that become .claude/rules/ files (prompt/ is never a rule —
# it loads via systemPromptIncludes into CLAUDE.md's prompt half)
_RULE_TIERS = ("routing", "guardrails", "knowledge", "conventions")


def rule_filename(context_relpath: str) -> str:
    """context-relative path -> .claude/rules/ filename.

    "guardrails/no-fabrication.md" -> "guardrails-no-fabrication.md".
    Mirrors target_kiro_cli's "-".join(parts) steering-file convention.
    """
    return "-".join(Path(context_relpath).parts)


def build_citation_map(context_dir: Path, sops_dir: Path) -> dict[str, str]:
    """Every rewritable citation token -> its emitted .claude/ path.

    Built from files actually on disk, so a token is only rewritten when its
    destination genuinely exists in the target.
    """
    mapping: dict[str, str] = {}
    for tier in _RULE_TIERS:
        tier_dir = context_dir / tier
        if not tier_dir.is_dir():
            continue
        for f in sorted(tier_dir.glob("*.md")):
            rel = f.relative_to(context_dir).as_posix()
            mapping[f"context/{rel}"] = f".claude/rules/{rule_filename(rel)}"
    if sops_dir.is_dir():
        for f in sorted(sops_dir.glob("*.sop.md")):
            mapping[f"sops/{f.name}"] = f".claude/sops/{f.name}"
    return mapping


def rewrite_citations(text: str, citation_map: dict[str, str]) -> str:
    """Replace each known citation token with its emitted path.

    Longest tokens first, so a token that is a prefix of a longer one never
    shadows it.
    """
    for token in sorted(citation_map, key=len, reverse=True):
        text = text.replace(token, citation_map[token])
    return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_target_paths.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add build/target_paths.py tests/test_target_paths.py
git commit -m "feat: add build/target_paths.py citation-rewrite map for the claude-code target

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

### Task 2: Claude target — thin `CLAUDE.md` + `.claude/rules/`

**Files:**
- Modify: `build/assemble.py` — add `AGENTS` constant, `emit_claude_rules`, rewrite the first half of `target_claude_code`.
- Test: `tests/test_assemble.py` — update `test_claude_code_target_writes_claude_md_with_prompt_and_eager_tiers`; add rules tests.

**Interfaces:**
- Consumes: `target_paths.rule_filename` (Task 1); existing `resolve_includes`, `expand_context_globs`, `write`, `CONTEXT`.
- Produces: `emit_claude_rules(manifest: dict, out: Path) -> list[str]` — writes `.claude/rules/<tier>-<file>.md` per eager context file, returns the emitted filenames sorted. `CLAUDE.md` = prompt + `\n---\n\n` + `<!-- Always-on project context (loaded via imports). -->\n` + one `@.claude/rules/<name>\n` per returned filename.

- [ ] **Step 1: Update the existing test to the new expectation (RED)**

In `tests/test_assemble.py`, replace `test_claude_code_target_writes_claude_md_with_prompt_and_eager_tiers` with:

```python
def test_claude_code_target_writes_thin_claude_md_with_prompt_and_rule_imports(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    claude_md = (out_dir / "CLAUDE.md").read_text(encoding="utf-8")
    # prompt half still present
    assert IDENTITY_MARKER in claude_md
    assert DOMAIN_MARKER in claude_md
    assert claude_md.index(IDENTITY_MARKER) < claude_md.index(DOMAIN_MARKER)
    # eager tiers are NO LONGER inlined — they are imported
    assert ROUTING_MARKER not in claude_md
    assert GUARDRAIL_MARKER not in claude_md
    assert "@.claude/rules/routing-00-core.md" in claude_md
    assert "@.claude/rules/guardrails-no-fabrication.md" in claude_md


def test_claude_code_target_emits_one_rule_file_per_eager_context_file(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    routing = (out_dir / ".claude" / "rules" / "routing-00-core.md").read_text(encoding="utf-8")
    assert ROUTING_MARKER in routing
    assert "<!-- context/routing/00-core.md -->" in routing
    guardrail = (out_dir / ".claude" / "rules" / "guardrails-no-fabrication.md").read_text(encoding="utf-8")
    assert GUARDRAIL_MARKER in guardrail


def test_claude_code_target_claude_md_import_list_is_sorted_and_complete(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    claude_md = (out_dir / "CLAUDE.md").read_text(encoding="utf-8")
    imports = [line[len("@.claude/rules/"):] for line in claude_md.splitlines()
               if line.startswith("@.claude/rules/")]
    rule_files = sorted(p.name for p in (out_dir / ".claude" / "rules").glob("*.md"))
    assert imports == rule_files
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assemble.py -q -k claude_code`
Expected: the three tests above FAIL — `CLAUDE.md` still contains the inlined eager block; `.claude/rules/` does not exist.

- [ ] **Step 3: Implement in `build/assemble.py`**

Add near the other path constants (after `HOOKS = ROOT / "hooks"`):

```python
AGENTS = ROOT / "agents"
```

Add the script dir to `sys.path` so `target_paths` imports when run as `python3 build/assemble.py` (place immediately after the existing imports):

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
import target_paths  # noqa: E402
```

Add the helper (near `eager_block`):

```python
def emit_claude_rules(manifest: dict, out: Path) -> list[str]:
    """Write each eager-tier context file as its own .claude/rules/ file,
    keeping the `<!-- context/<path> -->` provenance comment. Returns the
    emitted filenames, sorted — that IS the CLAUDE.md import order."""
    names: list[str] = []
    for f in expand_context_globs(manifest):
        rel = f.relative_to(CONTEXT).as_posix()
        fname = target_paths.rule_filename(rel)
        body = f"<!-- context/{rel} -->\n{f.read_text(encoding='utf-8').strip()}\n"
        write(out / ".claude" / "rules" / fname, body)
        names.append(fname)
    return sorted(names)
```

Rewrite the top of `target_claude_code` (leave the skills/sops/mcp/hooks lines for Task 3):

```python
def target_claude_code(manifest: dict, out: Path) -> None:
    prompt = resolve_includes(manifest)
    rule_names = emit_claude_rules(manifest, out)
    imports = "".join(f"@.claude/rules/{n}\n" for n in rule_names)
    write(
        out / "CLAUDE.md",
        prompt
        + "\n---\n\n"
        + "<!-- Always-on project context (loaded via imports). -->\n"
        + imports,
    )
    for d in declared_skill_dirs(manifest):
        copy_tree(d, out / ".claude" / "skills" / d.name)
    copy_sops(manifest, out)
    emit_mcp(manifest, out / ".mcp.json")
    hooks = hook_files()
    if hooks:
        aggregated = [json.loads(p.read_text(encoding="utf-8")) for p in hooks]
        write(out / "hooks.json", json.dumps(aggregated, indent=2) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assemble.py -q -k claude_code`
Expected: PASS. `test_claude_code_target_is_deterministic_across_two_runs` still passes.

- [ ] **Step 5: Commit**

```bash
git add build/assemble.py tests/test_assemble.py
git commit -m "feat: claude-code target emits thin CLAUDE.md + @-imported .claude/rules/

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

### Task 3: Claude target — `.claude/sops/`, `.claude/hooks.json`, citation rewriting

**Files:**
- Modify: `build/assemble.py` — add `rewrite_tree_citations`, finish `target_claude_code` (sops → `.claude/sops/`, hooks → `.claude/hooks.json`, rewrite skill + sop citations).
- Test: `tests/test_assemble.py` — update `test_claude_code_target_copies_declared_sops`, `test_claude_code_target_omits_hooks_json_when_no_hooks`, `test_claude_code_target_writes_hooks_json_when_hooks_exist`; add citation + bundled-file tests.

**Interfaces:**
- Consumes: `target_paths.build_citation_map`, `target_paths.rewrite_citations` (Task 1); existing `declared_skill_dirs`, `declared_sop_files`, `copy_tree`, `write`, `hook_files`, `SOPS`, `CONTEXT`.
- Produces: `rewrite_tree_citations(root: Path, citation_map: dict[str, str]) -> None` — rewrites every `*.md` under `root` in place (sorted walk, only writes if changed).

- [ ] **Step 1: Update existing tests + add new ones (RED)**

In `tests/test_assemble.py`:

Replace `test_claude_code_target_copies_declared_sops` body's path assertion:
```python
    copied = out_dir / ".claude" / "sops" / "example-sop.sop.md"
    assert copied.read_text(encoding="utf-8") == "# Example SOP\n\nDo the thing.\n"
    assert not (out_dir / "sops").exists()
```

Replace `test_claude_code_target_omits_hooks_json_when_no_hooks` final assertion:
```python
    assert not (out_dir / ".claude" / "hooks.json").exists()
    assert not (out_dir / "hooks.json").exists()
```

Replace `test_claude_code_target_writes_hooks_json_when_hooks_exist` read path:
```python
    hooks = json.loads((out_dir / ".claude" / "hooks.json").read_text(encoding="utf-8"))
```

Add:
```python
def test_claude_code_target_rewrites_skill_citations_to_emitted_paths(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    skill_md = (out_dir / ".claude" / "skills" / "demo-skill" / "SKILL.md").read_text(encoding="utf-8")
    # demo-skill/SKILL.md cites context/guardrails/... and sops/wire-new-capability.sop.md
    assert ".claude/rules/guardrails-confirm-before-execute.md" in skill_md
    assert ".claude/sops/wire-new-capability.sop.md" in skill_md
    assert "context/guardrails/confirm-before-execute.md" not in skill_md
    assert "sops/wire-new-capability.sop.md" not in skill_md.replace(".claude/sops/wire-new-capability.sop.md", "")
    # a non-mapped path is left alone
    assert "tool/toolkit/toolkit.py" in skill_md


def test_claude_code_target_copies_bundled_skill_files(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    bundled = out_dir / ".claude" / "skills" / "escalation-handoff" / "templates" / "handoff.md"
    assert bundled.is_file()


def test_claude_code_target_rewrites_sop_citations(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    sop = (out_dir / ".claude" / "sops" / "wire-new-capability.sop.md").read_text(encoding="utf-8")
    # the wire-new-capability SOP cites context/ paths; assert none survive un-rewritten
    for line in sop.splitlines():
        assert "context/guardrails/" not in line or ".claude/rules/guardrails-" in line
```

> Note: verify the exact citation strings in `skills/demo-skill/SKILL.md` and `sops/wire-new-capability.sop.md` before finalizing the asserted tokens — grep them first: `grep -n "context/\|sops/" skills/demo-skill/SKILL.md sops/wire-new-capability.sop.md`. Adjust the asserted paths to real citations present in those files.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assemble.py -q -k claude_code`
Expected: updated + new tests FAIL — sops still at `out/sops/`, hooks at `out/hooks.json`, citations not rewritten.

- [ ] **Step 3: Implement in `build/assemble.py`**

Add helper (near `copy_tree`):

```python
def rewrite_tree_citations(root: Path, citation_map: dict[str, str]) -> None:
    """Rewrite every markdown file under `root` in place, mapping source
    citation tokens to their emitted .claude/ locations. Sorted walk;
    writes only when the text actually changes (determinism + no churn)."""
    for md in sorted(root.rglob("*.md")):
        original = md.read_text(encoding="utf-8")
        rewritten = target_paths.rewrite_citations(original, citation_map)
        if rewritten != original:
            md.write_text(rewritten, encoding="utf-8")
```

Replace the skills/sops/hooks tail of `target_claude_code`:

```python
    citation_map = target_paths.build_citation_map(CONTEXT, SOPS)

    for d in declared_skill_dirs(manifest):
        dst = out / ".claude" / "skills" / d.name
        copy_tree(d, dst)
        rewrite_tree_citations(dst, citation_map)

    for p in declared_sop_files(manifest):
        body = target_paths.rewrite_citations(p.read_text(encoding="utf-8"), citation_map)
        write(out / ".claude" / "sops" / p.name, body)

    emit_mcp(manifest, out / ".mcp.json")

    hooks = hook_files()
    if hooks:
        aggregated = [json.loads(p.read_text(encoding="utf-8")) for p in hooks]
        write(out / ".claude" / "hooks.json", json.dumps(aggregated, indent=2) + "\n")
```

(Delete the now-unused `copy_sops(manifest, out)` call from `target_claude_code` only — `copy_sops` is still used by `target_kiro_cli` and `target_generic`, keep the function.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assemble.py -q`
Expected: PASS (whole file — kiro-cli and generic sections unaffected). Determinism tests green.

- [ ] **Step 5: Commit**

```bash
git add build/assemble.py tests/test_assemble.py
git commit -m "feat: claude-code target moves sops/hooks under .claude and rewrites citations

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

### Task 4: Claude target — `.claude/agents/<name>.md` primary agent

**Files:**
- Modify: `build/assemble.py` — add `emit_claude_agent_file`, call it from `target_claude_code`.
- Test: `tests/test_assemble.py` — add primary-agent tests.

**Interfaces:**
- Consumes: `resolve_includes` (existing); the assembled `prompt` string already built in `target_claude_code`.
- Produces: `emit_claude_agent_file(manifest: dict, prompt: str, out: Path) -> None` — writes `.claude/agents/<manifest.name>.md` with frontmatter `name: <name>` + `description: <json-quoted>` and body = `prompt`. Hard error if `manifest.name` is missing.

- [ ] **Step 1: Write the failing tests**

```python
def test_claude_code_target_emits_primary_agent_file_discoverable_by_name(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    agent = (out_dir / ".claude" / "agents" / "agent-x.md").read_text(encoding="utf-8")
    assert agent.startswith("---\n")
    assert "\nname: agent-x\n" in agent
    assert "description:" in agent
    # body carries the assembled system prompt
    assert IDENTITY_MARKER in agent
    assert DOMAIN_MARKER in agent


def test_claude_code_target_primary_agent_filename_follows_manifest_name(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, name="agent-x-mish")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    assert (out_dir / ".claude" / "agents" / "agent-x-mish.md").is_file()
    assert not (out_dir / ".claude" / "agents" / "agent-x.md").exists()
    agent = (out_dir / ".claude" / "agents" / "agent-x-mish.md").read_text(encoding="utf-8")
    assert "\nname: agent-x-mish\n" in agent


def test_claude_code_target_missing_name_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    manifest_path = pkg / "agent.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["name"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode != 0
    assert "name" in result.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assemble.py -q -k "primary_agent or missing_name"`
Expected: FAIL — no `.claude/agents/` output.

- [ ] **Step 3: Implement in `build/assemble.py`**

```python
def emit_claude_agent_file(manifest: dict, prompt: str, out: Path) -> None:
    """The generated Claude Code project agent. Claude discovers agents by
    scanning .claude/agents/*.md and matching frontmatter `name`;
    `claude --agent <name>` resolves here."""
    name = manifest.get("name")
    if not name:
        fail("agent.manifest.json has no name — required for the claude-code agent file")
    desc = manifest.get("description") or f"{name} — assembled by build/assemble.py"
    frontmatter = f"---\nname: {name}\ndescription: {json.dumps(desc)}\n---\n\n"
    write(out / ".claude" / "agents" / f"{name}.md", frontmatter + prompt)
```

Call it in `target_claude_code`, right after the `CLAUDE.md` write:

```python
    emit_claude_agent_file(manifest, prompt, out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assemble.py -q`
Expected: PASS (full file).

- [ ] **Step 5: Commit**

```bash
git add build/assemble.py tests/test_assemble.py
git commit -m "feat: claude-code target emits .claude/agents/<name>.md for claude --agent

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

### Task 5: `claudeSettings` manifest field + `.claude/settings.json`

**Files:**
- Modify: `agent.manifest.json` — add `"claudeSettings": { "defaultAgent": false }`.
- Modify: `build/assemble.py` — add `emit_claude_settings`, call from `target_claude_code`.
- Test: `tests/test_assemble.py` — add settings tests.

**Interfaces:**
- Consumes: `manifest.get("claudeSettings", {}).get("defaultAgent")`, `manifest["name"]`.
- Produces: `emit_claude_settings(manifest: dict, out: Path) -> None` — always writes `.claude/settings.json`; contents `{"agent": "<name>"}` iff `defaultAgent` is truthy, else `{}`. `json.dumps(..., indent=2, sort_keys=True) + "\n"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_claude_code_target_settings_json_is_empty_by_default(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    settings = json.loads((out_dir / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings == {}


def test_claude_code_target_settings_json_sets_default_agent_when_manifest_opts_in(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, claudeSettings={"defaultAgent": True})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    settings = json.loads((out_dir / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings == {"agent": "agent-x"}


def test_claude_code_target_default_agent_uses_renamed_manifest_name(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, name="agent-x-mish", claudeSettings={"defaultAgent": True})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    settings = json.loads((out_dir / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings == {"agent": "agent-x-mish"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assemble.py -q -k settings_json`
Expected: FAIL — `.claude/settings.json` not written.

- [ ] **Step 3: Implement**

In `agent.manifest.json`, add after `"hooks": {}` (keep valid JSON, trailing comma rules):

```json
  "claudeSettings": {
    "defaultAgent": false
  },
```

In `build/assemble.py`:

```python
def emit_claude_settings(manifest: dict, out: Path) -> None:
    """.claude/settings.json — always emitted. Declares the default agent
    only when the manifest opts in (claudeSettings.defaultAgent), so a bare
    `claude` picks up Agent X; otherwise `claude --agent <name>` is explicit."""
    settings: dict = {}
    if manifest.get("claudeSettings", {}).get("defaultAgent"):
        settings["agent"] = manifest["name"]
    write(out / ".claude" / "settings.json",
          json.dumps(settings, indent=2, sort_keys=True) + "\n")
```

Call in `target_claude_code`, after `emit_claude_agent_file`:

```python
    emit_claude_settings(manifest, out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assemble.py -q`
Expected: PASS. Also run `python3 context/scripts/validate-wiring.py --strict` — the new manifest key must not trip the source validator (it does not inspect unknown keys; confirm green).

- [ ] **Step 5: Commit**

```bash
git add agent.manifest.json build/assemble.py tests/test_assemble.py
git commit -m "feat: emit .claude/settings.json with configurable default-agent

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

### Task 6: Claude target — `.claude/agents/<subagent>.md`

**Files:**
- Modify: `build/assemble.py` — add `WRITE_VERBS`, `subagent_agent_files`, `emit_claude_subagent`; call from `target_claude_code`.
- Test: `tests/test_assemble.py` — add subagent tests.

**Interfaces:**
- Consumes: `manifest.get("subagentNames", [])`; `agents/<name>.agent.json` on disk; `ROOT`, `CONTEXT`, `AGENTS`.
- Produces:
  - `WRITE_VERBS: set[str]` — `{"write", "edit", "delete", "create", "update", "patch"}`.
  - `subagent_agent_files(manifest: dict) -> list[Path]` — resolves each `subagentNames` entry to `agents/<name>.agent.json`; hard error if missing.
  - `emit_claude_subagent(spec: dict, out: Path) -> None` — writes `.claude/agents/<spec["name"]>.md`: frontmatter `name`, `description` (json-quoted), and `tools:` (comma-joined, write verbs excluded, narrowed to `allowedTools` when present); body = resolved `systemPromptIncludes` + inlined `contextGlobs` expansions, each with a `<!-- <relpath> -->` comment.

- [ ] **Step 1: Write the failing tests**

```python
def test_claude_code_target_emits_declared_subagent_as_markdown(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    sub = (out_dir / ".claude" / "agents" / "readonly-investigator.md").read_text(encoding="utf-8")
    assert "\nname: readonly-investigator\n" in sub
    assert "description:" in sub
    # body carries the subagent's own system prompt
    assert "readonly-investigator" in sub.lower()


def test_claude_code_target_subagent_tools_exclude_write_verbs(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    sub = (out_dir / ".claude" / "agents" / "readonly-investigator.md").read_text(encoding="utf-8")
    tools_line = next(line for line in sub.splitlines() if line.startswith("tools:"))
    for verb in ("write", "edit", "delete", "create", "update", "patch"):
        assert verb not in tools_line
    assert "read" in tools_line


def test_claude_code_target_missing_subagent_agent_json_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, subagentNames=["nonexistent-subagent"])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode != 0
    assert "nonexistent-subagent" in result.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assemble.py -q -k subagent`
Expected: FAIL — no subagent markdown emitted.

- [ ] **Step 3: Implement in `build/assemble.py`**

```python
WRITE_VERBS = {"write", "edit", "delete", "create", "update", "patch"}


def subagent_agent_files(manifest: dict) -> list[Path]:
    files: list[Path] = []
    for name in manifest.get("subagentNames", []):
        p = AGENTS / f"{name}.agent.json"
        if not p.is_file():
            fail(f"subagentNames entry has no file: agents/{name}.agent.json")
        files.append(p)
    return files


def _subagent_body(spec: dict, name: str) -> str:
    parts: list[str] = []
    for rel in spec.get("systemPromptIncludes", []):
        path = ROOT / rel
        if not path.is_file():
            fail(f"subagent {name}: systemPromptIncludes missing on disk: {rel}")
        parts.append(path.read_text(encoding="utf-8").strip())
    for pattern in spec.get("contextGlobs", []):
        for m in sorted(CONTEXT.glob(pattern)):
            if m.is_file():
                rel = m.relative_to(ROOT).as_posix()
                parts.append(f"<!-- {rel} -->\n{m.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)


def emit_claude_subagent(spec: dict, out: Path) -> None:
    """Translate agents/<name>.agent.json into a Claude Code subagent file.
    Read-only guarantee rests on `tools:` — write verbs are dropped.
    shellAllowedCommands has no Claude subagent-file equivalent (mapping gap)."""
    name = spec["name"]
    tools = [t for t in spec.get("tools", []) if str(t).lower() not in WRITE_VERBS]
    allowed = spec.get("allowedTools")
    if allowed:
        narrowed = [t for t in tools if t in allowed]
        tools = narrowed or list(allowed)
    fm = ["---", f"name: {name}", f"description: {json.dumps(spec.get('description', ''))}"]
    if tools:
        fm.append(f"tools: {', '.join(tools)}")
    fm.append("---")
    write(out / ".claude" / "agents" / f"{name}.md",
          "\n".join(fm) + "\n\n" + _subagent_body(spec, name) + "\n")
```

Call in `target_claude_code`, after `emit_claude_agent_file`:

```python
    for p in subagent_agent_files(manifest):
        emit_claude_subagent(json.loads(p.read_text(encoding="utf-8")), out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assemble.py -q`
Expected: PASS (full file), determinism tests green.

- [ ] **Step 5: Commit**

```bash
git add build/assemble.py tests/test_assemble.py
git commit -m "feat: claude-code target emits declared subagents as .claude/agents/<name>.md

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

### Task 7: Kiro target — `.kiro/agents/<subagent>.json`

**Files:**
- Modify: `build/assemble.py` — add `emit_kiro_subagents`, call from `target_kiro_cli`.
- Test: `tests/test_assemble.py` (kiro-cli section) + `tests/test_deploy.py`.

**Interfaces:**
- Consumes: `subagent_agent_files` (Task 6); `manifest`.
- Produces: `emit_kiro_subagents(manifest: dict, agents_dir: Path) -> None` — for each declared subagent writes `<agents_dir>/<name>.json`, a clean kiro-cli agent config built from the source spec (`name`, `description`, `tools` or `["*"]`, `allowedTools`, the standard `resources` + `includeMcpJson: true`, and `shellAllowedCommands` preserved when present). `emit_kiro_cli_agent` (the primary) is NOT modified.

- [ ] **Step 1: Write the failing tests**

In `tests/test_assemble.py` kiro-cli section:

```python
def test_kiro_cli_target_emits_declared_subagent_config(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    sub = json.loads((out_dir / "agents" / "readonly-investigator.json").read_text(encoding="utf-8"))
    assert sub["name"] == "readonly-investigator"
    assert sub["includeMcpJson"] is True
    assert sub["allowedTools"] == ["read"]
    assert sub["shellAllowedCommands"]  # preserved from the source spec


def test_kiro_cli_target_primary_agent_config_unchanged_by_subagent_emission(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    config = json.loads((out_dir / "agents" / "agent-x.json").read_text(encoding="utf-8"))
    assert config["name"] == "agent-x"
    assert config["resources"] == [
        "file://.kiro/steering/**/*.md",
        "skill://.kiro/skills/*/SKILL.md",
    ]


def test_kiro_cli_target_missing_subagent_agent_json_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, subagentNames=["nonexistent-subagent"])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode != 0
    assert "nonexistent-subagent" in result.stderr
```

In `tests/test_deploy.py`, add to `test_deploy_writes_workspace_kiro_matching_assembled_output` after the existing `agents/agent-x.json` assertion:

```python
    assert (deployed / "agents" / "readonly-investigator.json").is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_assemble.py tests/test_deploy.py -q -k "subagent or matching_assembled"`
Expected: FAIL — no `agents/readonly-investigator.json` emitted.

- [ ] **Step 3: Implement in `build/assemble.py`**

```python
def emit_kiro_subagents(manifest: dict, agents_dir: Path) -> None:
    """Declared subagents as kiro-cli agent configs, alongside the primary.
    Built clean from the source spec (not raw pass-through) so the emitted
    file is a valid kiro-cli agent config, mirroring emit_kiro_cli_agent."""
    for p in subagent_agent_files(manifest):
        spec = json.loads(p.read_text(encoding="utf-8"))
        config = {
            "name": spec["name"],
            "description": spec.get("description", ""),
            "prompt": None,
            "mcpServers": {},
            "tools": spec.get("tools") or ["*"],
            "allowedTools": spec.get("allowedTools", []),
            "resources": [
                "file://.kiro/steering/**/*.md",
                "skill://.kiro/skills/*/SKILL.md",
            ],
            "includeMcpJson": True,
            "model": None,
            "welcomeMessage": spec["name"],
        }
        if spec.get("shellAllowedCommands"):
            config["shellAllowedCommands"] = spec["shellAllowedCommands"]
        write(agents_dir / f"{spec['name']}.json",
              json.dumps(config, indent=2, sort_keys=True) + "\n")
```

Call in `target_kiro_cli`, right after `emit_kiro_cli_agent(manifest, out / "agents")`:

```python
    emit_kiro_subagents(manifest, out / "agents")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_assemble.py tests/test_deploy.py -q`
Expected: PASS — all existing kiro-cli assertions still green (primary unchanged), deploy idempotency + `same_tree` still hold.

- [ ] **Step 5: Commit**

```bash
git add build/assemble.py tests/test_assemble.py tests/test_deploy.py
git commit -m "feat: kiro-cli target emits declared subagents alongside the primary agent

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

### Task 8: `build/validate_targets.py` + `build/ci.py`

**Files:**
- Create: `build/validate_targets.py`
- Modify: `build/ci.py` — replace the three `assembler smoke: <target>` stages with one `target-aware validation` stage.
- Test: `tests/test_validate_targets.py`

**Interfaces:**
- Consumes: `build/assemble.py` via subprocess (matches `ci.py` style); `agent.manifest.json`.
- Produces: `main(argv: list[str] | None = None) -> int` — assembles `kiro-cli` and `claude-code` into temp dirs and asserts every declared capability lands at its target's expected path. Exit `0` all good, `1` any failure (each failure printed as `VALIDATE FAIL <target> <capability>: <detail>`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_validate_targets.py
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "build" / "validate_targets.py"


def run_validate_at(pkg_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(pkg_root / "build" / "validate_targets.py")],
        cwd=pkg_root, capture_output=True, text=True,
    )


def copy_package(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(
        ".git", "dist", ".kiro", ".pytest_cache", "__pycache__"))
    return dest


def test_real_package_validates_clean_for_both_targets(tmp_path):
    pkg = copy_package(tmp_path)
    result = run_validate_at(pkg)
    assert result.returncode == 0, result.stdout + result.stderr


def test_validation_fails_when_a_declared_skill_dir_is_missing(tmp_path):
    pkg = copy_package(tmp_path)
    shutil.rmtree(pkg / "skills" / "demo-skill")
    result = run_validate_at(pkg)
    assert result.returncode == 1
    assert "demo-skill" in result.stdout


def test_validation_fails_when_a_declared_subagent_is_missing(tmp_path):
    pkg = copy_package(tmp_path)
    (pkg / "agents" / "readonly-investigator.agent.json").unlink()
    result = run_validate_at(pkg)
    assert result.returncode == 1
    assert "readonly-investigator" in result.stdout


def test_validation_checks_claude_agent_discovery_contract(tmp_path):
    pkg = copy_package(tmp_path)
    result = run_validate_at(pkg)
    # positive: the clean run confirms .claude/agents/agent-x.md exists with
    # name: agent-x — assert the check name is exercised by inspecting -v output
    assert result.returncode == 0


def test_validation_fails_when_default_agent_flag_and_settings_disagree(tmp_path):
    pkg = copy_package(tmp_path)
    manifest_path = pkg / "agent.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claudeSettings"] = {"defaultAgent": True}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    # with the flag on, settings.json MUST carry "agent": "agent-x"; the real
    # emitter does this, so this is a positive check that the validator asserts it
    result = run_validate_at(pkg)
    assert result.returncode == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_validate_targets.py -q`
Expected: FAIL — `build/validate_targets.py` does not exist.

- [ ] **Step 3: Implement `build/validate_targets.py`**

```python
#!/usr/bin/env python3
"""Assemble each target and assert its real output layout.

Fails if a manifest-declared capability (skill, SOP, subagent, eager context
file) is not emitted where its target expects it. This is the output-side
counterpart to context/scripts/validate-wiring.py (which checks the source
tree only).

Stdlib only.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "context"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import target_paths  # noqa: E402

failures: list[str] = []


def fail(target: str, capability: str, detail: str) -> None:
    failures.append(f"VALIDATE FAIL {target} {capability}: {detail}")


def assemble(target: str, out: Path) -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "build" / "assemble.py"),
         "--target", target, "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        fail(target, "<assembly>", (r.stderr or r.stdout).strip())


def eager_context_files() -> list[str]:
    manifest = json.loads((ROOT / "agent.manifest.json").read_text(encoding="utf-8"))
    files: list[str] = []
    for pattern in manifest.get("contextGlobs", []):
        for m in sorted(CONTEXT.glob(pattern)):
            if m.is_file():
                files.append(m.relative_to(CONTEXT).as_posix())
    return files


def check_kiro(manifest: dict, out: Path) -> None:
    t = "kiro-cli"
    if not (out / "steering" / "00-system.md").is_file():
        fail(t, "system-prompt", "steering/00-system.md missing")
    for rel in eager_context_files():
        fn = target_paths.rule_filename(rel)
        if not (out / "steering" / fn).is_file():
            fail(t, f"context/{rel}", f"steering/{fn} missing")
    for name in manifest.get("skillNames", []):
        if not (out / "skills" / name / "SKILL.md").is_file():
            fail(t, f"skill/{name}", f"skills/{name}/SKILL.md missing")
    for name in manifest.get("sopNames", []):
        if not (out / "sops" / f"{name}.sop.md").is_file():
            fail(t, f"sop/{name}", f"sops/{name}.sop.md missing")
    if not (out / "settings" / "mcp.json").is_file():
        fail(t, "mcp", "settings/mcp.json missing")
    prim = out / "agents" / f"{manifest['name']}.json"
    if not prim.is_file():
        fail(t, "agent", f"agents/{manifest['name']}.json missing")
    for name in manifest.get("subagentNames", []):
        if not (out / "agents" / f"{name}.json").is_file():
            fail(t, f"subagent/{name}", f"agents/{name}.json missing")


def check_claude(manifest: dict, out: Path) -> None:
    t = "claude-code"
    claude_md = out / "CLAUDE.md"
    if not claude_md.is_file():
        fail(t, "system-prompt", "CLAUDE.md missing")
        return
    text = claude_md.read_text(encoding="utf-8")
    for rel in eager_context_files():
        fn = target_paths.rule_filename(rel)
        if not (out / ".claude" / "rules" / fn).is_file():
            fail(t, f"context/{rel}", f".claude/rules/{fn} missing")
        if f"@.claude/rules/{fn}" not in text:
            fail(t, f"context/{rel}", f"CLAUDE.md has no @-import for {fn}")
    for name in manifest.get("skillNames", []):
        if not (out / ".claude" / "skills" / name / "SKILL.md").is_file():
            fail(t, f"skill/{name}", f".claude/skills/{name}/SKILL.md missing")
    for name in manifest.get("sopNames", []):
        if not (out / ".claude" / "sops" / f"{name}.sop.md").is_file():
            fail(t, f"sop/{name}", f".claude/sops/{name}.sop.md missing")
    agent_md = out / ".claude" / "agents" / f"{manifest['name']}.md"
    if not agent_md.is_file():
        fail(t, "agent", f".claude/agents/{manifest['name']}.md missing")
    elif f"\nname: {manifest['name']}\n" not in agent_md.read_text(encoding="utf-8"):
        fail(t, "agent", "frontmatter name does not match manifest name "
                         "(claude --agent discovery would miss it)")
    for name in manifest.get("subagentNames", []):
        sub = out / ".claude" / "agents" / f"{name}.md"
        if not sub.is_file():
            fail(t, f"subagent/{name}", f".claude/agents/{name}.md missing")
            continue
        tools_line = next((l for l in sub.read_text(encoding="utf-8").splitlines()
                           if l.startswith("tools:")), "")
        if any(v in tools_line for v in ("write", "edit", "delete", "create", "update", "patch")):
            fail(t, f"subagent/{name}", f"tools line has a write verb: {tools_line!r}")
    if not (out / ".mcp.json").is_file():
        fail(t, "mcp", ".mcp.json missing")
    settings_path = out / ".claude" / "settings.json"
    if not settings_path.is_file():
        fail(t, "settings", ".claude/settings.json missing")
    else:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        want_default = bool(manifest.get("claudeSettings", {}).get("defaultAgent"))
        has_agent = settings.get("agent") == manifest["name"]
        if want_default and not has_agent:
            fail(t, "settings", "claudeSettings.defaultAgent is true but "
                                ".claude/settings.json lacks the matching agent key")
        if not want_default and "agent" in settings:
            fail(t, "settings", "claudeSettings.defaultAgent is false but "
                                ".claude/settings.json declares an agent")


def main(argv: list[str] | None = None) -> int:
    manifest = json.loads((ROOT / "agent.manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        assemble("kiro-cli", base / "kiro-cli")
        assemble("claude-code", base / "claude-code")
        if not failures:
            check_kiro(manifest, base / "kiro-cli")
            check_claude(manifest, base / "claude-code")
    for line in failures:
        print(line)
    if failures:
        print(f"\nTARGET VALIDATION: FAIL — {len(failures)} finding(s)")
        return 1
    print("TARGET VALIDATION: PASS — both targets emit every declared capability")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_validate_targets.py -q && python3 build/validate_targets.py`
Expected: PASS (all tests); direct run prints `TARGET VALIDATION: PASS`.

- [ ] **Step 5: Wire into `build/ci.py`**

Replace the three tuples `("assembler smoke: claude-code", ...)`, `("assembler smoke: kiro-cli", ...)`, `("assembler smoke: generic", ...)` in `STAGES` with:

```python
    ("assembler smoke: generic",
     [sys.executable, "build/assemble.py", "--target", "generic"]),
    ("target-aware validation",
     [sys.executable, "build/validate_targets.py"]),
```

(Keep the `generic` smoke — `validate_targets.py` covers only kiro-cli and claude-code.)

Run: `python3 build/ci.py`
Expected: `CI GATE: PASS — all stages green`.

- [ ] **Step 6: Commit**

```bash
git add build/validate_targets.py build/ci.py tests/test_validate_targets.py
git commit -m "feat: target-aware output validation; wire into build/ci.py

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

### Task 9: `build/deploy.py --target` + `.gitignore`

**Files:**
- Modify: `build/deploy.py` — add `--target {kiro-cli,claude-code}`, a `deploy_claude` path, `CLAUDE_MAPPINGS`.
- Modify: `.gitignore` — add the generated Claude artifacts.
- Test: `tests/test_deploy.py` — add claude-target + surgical-preservation tests.

**Interfaces:**
- Consumes: `assemble` (existing helper — parametrize its `--target`), `copy_path`, `assert_same_tree`.
- Produces:
  - `MAPPINGS` unchanged for kiro-cli.
  - `CLAUDE_MAPPINGS = ("CLAUDE.md", ".mcp.json", ".claude/rules", ".claude/skills", ".claude/agents", ".claude/settings.json", ".claude/hooks.json")` — each removed and rewritten; nothing else under `.claude/` is touched.
  - `deploy(agent_root, workspace_root, *, target="kiro-cli", clean=True) -> dict` — summary gains `"target"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_deploy_claude_target_writes_native_layout(tmp_path):
    pkg = copy_package(tmp_path)
    workspace = tmp_path / "ws"

    result = run_deploy(pkg, "--target", "claude-code", "--workspace-root", str(workspace), "--json")

    assert result.returncode == 0, result.stderr
    assert (workspace / "CLAUDE.md").is_file()
    assert (workspace / ".mcp.json").is_file()
    assert (workspace / ".claude" / "rules" / "routing-00-core.md").is_file()
    assert (workspace / ".claude" / "skills" / "demo-skill" / "SKILL.md").is_file()
    assert (workspace / ".claude" / "agents" / "agent-x.md").is_file()
    assert (workspace / ".claude" / "settings.json").is_file()
    assert json.loads(result.stdout)["target"] == "claude-code"


def test_deploy_claude_target_is_surgical_and_preserves_human_files(tmp_path):
    pkg = copy_package(tmp_path)
    workspace = tmp_path / "ws"
    (workspace / ".claude" / "commands").mkdir(parents=True)
    (workspace / ".claude" / "commands" / "mine.md").write_text("keep me", encoding="utf-8")
    (workspace / ".claude" / "settings.local.json").write_text('{"local": true}', encoding="utf-8")

    result = run_deploy(pkg, "--target", "claude-code", "--workspace-root", str(workspace), "--json")

    assert result.returncode == 0, result.stderr
    assert (workspace / ".claude" / "commands" / "mine.md").read_text(encoding="utf-8") == "keep me"
    assert (workspace / ".claude" / "settings.local.json").read_text(encoding="utf-8") == '{"local": true}'


def test_deploy_default_target_is_still_kiro_cli(tmp_path):
    pkg = copy_package(tmp_path)
    result = run_deploy(pkg, "--json")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["target"] == "kiro-cli"
    assert (pkg / ".kiro" / "steering" / "00-system.md").is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_deploy.py -q -k "claude or default_target"`
Expected: FAIL — `--target` unknown argument.

- [ ] **Step 3: Implement in `build/deploy.py`**

Add near `MAPPINGS`:

```python
CLAUDE_MAPPINGS = (
    "CLAUDE.md",
    ".mcp.json",
    ".claude/rules",
    ".claude/skills",
    ".claude/agents",
    ".claude/settings.json",
    ".claude/hooks.json",
)
```

Parametrize `assemble` (change the hard-coded `"kiro-cli"`):

```python
def assemble(agent_root: Path, out: Path, target: str = "kiro-cli") -> None:
    ...
        [sys.executable, str(assembler), "--target", target, "--out", str(out)],
    ...
```

Add a Claude deploy path and branch `deploy`:

```python
def deploy_claude(agent_root: Path, workspace_root: Path) -> dict:
    source_out = agent_root / "dist" / "claude-code"
    assemble(agent_root, source_out, target="claude-code")
    written = 0
    for name in CLAUDE_MAPPINGS:
        src = source_out / name
        dst = workspace_root / name
        # surgical: only remove the paths we own; never rmtree .claude/ itself
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        written += copy_path(src, dst)
        if src.exists():
            assert_same_tree(src, dst) if src.is_dir() else None
    return {
        "target": "claude-code",
        "agent": agent_name(agent_root),
        "agent_root": str(agent_root),
        "assembled_from": str(source_out),
        "deployed_to": str(workspace_root),
        "files_written": written,
    }
```

In `deploy(...)`, add a `target` kwarg and short-circuit:

```python
def deploy(agent_root: Path, workspace_root: Path, clean: bool = True,
           target: str = "kiro-cli") -> dict:
    if target == "claude-code":
        workspace_root.mkdir(parents=True, exist_ok=True)
        return deploy_claude(agent_root, workspace_root)
    ...  # existing kiro-cli body unchanged, but add "target": "kiro-cli" to its summary dict
```

Add the CLI flag in `main`:

```python
    parser.add_argument("--target", default="kiro-cli",
                        choices=("kiro-cli", "claude-code"),
                        help="Which assembled layout to deploy.")
    ...
    summary = deploy(agent_root, workspace_root, clean=not args.no_clean, target=args.target)
```

Update the non-JSON print branch to mention `summary['target']`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_deploy.py -q`
Expected: PASS — including the existing kiro-cli deploy tests (now also asserting `target` where added).

- [ ] **Step 5: Update `.gitignore`**

Append:

```
/CLAUDE.md
/.mcp.json
/.claude/rules/
/.claude/skills/
/.claude/agents/
/.claude/hooks.json
/.claude/settings.json
```

Run: `python3 build/deploy.py --target claude-code && git status --porcelain`
Expected: no new tracked/untracked-and-unignored files from the deploy (the generated paths are ignored). Then `rm -rf .claude/rules .claude/skills .claude/agents .claude/hooks.json .claude/settings.json CLAUDE.md .mcp.json dist` to clean the tree.

- [ ] **Step 6: Commit**

```bash
git add build/deploy.py .gitignore tests/test_deploy.py
git commit -m "feat: deploy.py --target claude-code (surgical .claude/ deploy); gitignore generated Claude artifacts

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

### Task 10: Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/spec/rebuild-spec.md`
- Modify: `docs/onboarding.md`
- Modify: `docs/sync-workflow.md`
- Modify: `docs/progress/PROJECT_PROGRESS.md`

No test cycle — this task's gate is `python3 build/ci.py` staying green (the CLI-reference and skill-count guards read `README.md`) and `python3 guards/check-cli-references.py` clean.

- [ ] **Step 1: `README.md`**

- In "Build targets": keep "Primary target: kiro-cli". Rename "Secondary target: Claude Code" content to describe the native layout and add the deploy + launch pair:
  ```
  python3 build/deploy.py --target claude-code
  claude --agent agent-x
  ```
- Add this table under the Claude Code subsection:

  | Concept | kiro-cli | Claude Code |
  |---|---|---|
  | System prompt | `.kiro/steering/00-system.md` | `CLAUDE.md` (thin — prompt + `@`-imports) |
  | Eager context | `.kiro/steering/<tier>-*.md` | `.claude/rules/<tier>-*.md` (imported by `CLAUDE.md`) |
  | Skills | `.kiro/skills/<name>/` | `.claude/skills/<name>/` |
  | SOPs | `.kiro/sops/` | `.claude/sops/` |
  | Agent | `.kiro/agents/<name>.json` | `.claude/agents/<name>.md` |
  | Subagents | `.kiro/agents/<sub>.json` | `.claude/agents/<sub>.md` |
  | MCP | `.kiro/settings/mcp.json` | `.mcp.json` |
  | Hooks / settings | agent-config `hooks` block (not emitted) | `.claude/settings.json`, `.claude/hooks.json` (neutral list) |
  | Default agent | `--agent` flag | `--agent` flag, or `.claude/settings.json` `{"agent": …}` |

- In the "Architecture" tree: add `build/target_paths.py` and `build/validate_targets.py` under `build/`.
- In the "How it works" mermaid `flowchart LR`: add an edge `A -->|"--target claude-code"| D1` already exists; add `D1 --> DPC["build/deploy.py --target claude-code"] --> CC[".claude/ + CLAUDE.md"] --> CL["claude --agent agent-x"]`.
- In "Validation": add `python3 build/validate_targets.py` to the listed gate commands.

- [ ] **Step 2: `docs/spec/rebuild-spec.md`**

- §13.2 "Target bindings" table: rewrite the `claude-code` column to the native layout (rows: System prompt → `CLAUDE.md` thin + `@`-imports; Eager context → `.claude/rules/<tier>-*.md`; Skills → `.claude/skills/<name>/` (citations rewritten); SOPs → `.claude/sops/<name>.sop.md`; MCP → `.mcp.json`; Agent activation → `.claude/agents/<name>.md`, discovered by frontmatter `name`, `claude --agent <name>`; Subagents → `.claude/agents/<sub>.md`; Hooks → `.claude/hooks.json` neutral list, not schema-translated; Settings → `.claude/settings.json`). Add a `subagentNames` row to the kiro-cli column: `.kiro/agents/<sub>.json`.
- §13.3 embedded `build/assemble.py` listing: replace with the post-Task-7 file content verbatim (`cat build/assemble.py`).
- Embedded `build/ci.py` listing: replace `STAGES` with the post-Task-8 version.
- Add **§13.6 Claude Code native layout**: the `.claude/` tree; that Claude Code has no `.claude/rules/` auto-load — files load only via `CLAUDE.md` `@`-imports; the `build/target_paths.py` citation-rewrite map; the `claude --agent <name>` discovery contract (frontmatter `name` match).
- Add **§13.7 Mapping gaps**: the four gaps from the spec's "Mapping gaps" section verbatim.
- Note `build/target_paths.py` and `build/validate_targets.py` as new build modules wherever build scripts are enumerated.

- [ ] **Step 3: `docs/onboarding.md`**

- §4 file map: add `build/target_paths.py` (citation map) and `build/validate_targets.py` (output-side validation) with one-line roles.
- §6 gotchas: add "The `claude-code` deploy is *surgical* — it replaces only the `.claude/` subpaths it generates, never `rmtree`s `.claude/`. Personalize a fork via the manifest/`context/`, not by hand-editing the generated `CLAUDE.md`."
- §6 gotchas: extend the "manifest-name test coupling" bullet to also name `tests/test_assemble.py` (the `.claude/agents/agent-x.md` / `name: agent-x` assertions) and `tests/test_validate_targets.py`.
- §7 "Verifying you're actually done": add `python3 build/validate_targets.py` alongside the wiring validator.

- [ ] **Step 4: `docs/sync-workflow.md`**

- In the `agent.manifest.json` conflict section's worked example: add `claudeSettings` to the list of additive template fields a fork "takes as-is while keeping its own `name`".

- [ ] **Step 5: `docs/progress/PROJECT_PROGRESS.md`**

- Add a dated entry (`2026-09-06`): the native target split — what changed (thin `CLAUDE.md` + `.claude/rules/`, `.claude/agents/` for `claude --agent`, `.claude/settings.json`, subagent emission for both targets, `build/target_paths.py`, `build/validate_targets.py`, `deploy.py --target`), why (Claude was a Kiro-shaped hybrid), what verified it (`python3 build/ci.py` green, `python3 build/validate_targets.py` green).
- Update "Next task" / "Suggested skills" as appropriate.

- [ ] **Step 6: Verify + commit**

```bash
python3 build/ci.py
python3 guards/check-cli-references.py
git add README.md docs/
git commit -m "docs: describe the Kiro-primary / Claude-native target split

$(printf 'Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017EE3VQaageQmSaa3pA8eDC')"
```

---

## Final verification (after Task 10)

- [ ] `python3 build/ci.py` → `CI GATE: PASS — all stages green`
- [ ] `python3 build/validate_targets.py` → `TARGET VALIDATION: PASS`
- [ ] `python3 build/assemble.py --target claude-code && python3 build/assemble.py --target claude-code` → assemble twice into `dist/claude-code`, confirm byte-identical (`diff -r` two `--out` dirs).
- [ ] `python3 build/deploy.py --target claude-code --workspace-root /tmp/ax-claude-smoke` then confirm `/tmp/ax-claude-smoke/.claude/agents/agent-x.md` has `name: agent-x` and `CLAUDE.md` imports every `.claude/rules/*.md`.
- [ ] `python3 build/deploy.py` (kiro-cli) still produces the same `.kiro/` as before plus `agents/readonly-investigator.json`.
- [ ] `git status` clean (no generated artifacts staged).
- [ ] Clean up smoke dirs: `rm -rf dist .kiro CLAUDE.md .mcp.json .claude/rules .claude/skills .claude/agents .claude/hooks.json .claude/settings.json /tmp/ax-claude-smoke`

## Self-Review

**Spec coverage:**
- Goal 1 (native layout) → Tasks 2–6. Goal 2 (`claude --agent`) → Task 4 + validator check Task 8. Goal 3 (configurable default agent) → Task 5. Goal 4 (modular rules) → Task 2. Goal 5 (subagents both targets) → Tasks 6, 7. Goal 6 (target-aware validation) → Task 8. Goal 7 (citation resolution) → Tasks 1, 3. Goal 8 (Kiro byte-identical) → Task 7 constraint + `test_kiro_cli_target_primary_agent_config_unchanged`. Goal 9 (fork port) → docs Task 10 + spec "Rollout" section.
- Spec §1 manifest field → Task 5. §2 `target_paths.py` → Task 1. §3 `target_claude_code` → Tasks 2–6. §4 Kiro subagents → Task 7. §5 `deploy.py` → Task 9. §6 `validate_targets.py` + `ci.py` → Task 8. §7 `.gitignore` → Task 9. §8 tests → folded into each task. §9 docs → Task 10. Mapping gaps → Task 10 §13.7 + reported on completion.

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". Two explicit "verify the real citation strings / grep first" notes in Task 3 are deliberate — the asserted tokens depend on current file content and must be checked, not guessed.

**Type consistency:** `rule_filename`, `build_citation_map`, `rewrite_citations` signatures identical across Tasks 1, 2, 3, 8. `emit_claude_rules` returns `list[str]` (sorted filenames) consumed as the import list in Task 2. `subagent_agent_files` defined Task 6, reused Task 7. `WRITE_VERBS` defined Task 6, referenced by string-literal checks in Tasks 8. `CLAUDE_MAPPINGS` Task 9 only. `deploy(..., target=...)` kwarg added Task 9, default preserves current callers.

**Open item carried to implementation:** Task 6 leans on inlining `contextGlobs` into the subagent body; confirm against real Claude subagent consumption during the task (does not block the task — the fallback is extra `@`-imports, same data).
