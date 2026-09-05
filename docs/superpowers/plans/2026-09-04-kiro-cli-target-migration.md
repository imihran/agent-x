# Kiro CLI Target Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `kiro` assembler target (built for the Kiro GUI editor) with a `kiro-cli` target (built for the separate `kiro-cli` terminal tool the user actually runs), so `python3 build/deploy.py` followed by `kiro-cli chat --agent agent-x` actually activates this package's identity, guardrails, routing, and skills.

**Architecture:** `build/assemble.py` gains `target_kiro_cli`, reusing the existing steering/skills/sops emission verbatim, writing MCP config to `settings/mcp.json` (not `mcp.json`), and emitting a new `agents/<name>.json` kiro-cli agent-activation file. `build/deploy.py` copies the new layout into `<workspace-root>/.kiro/`. `build/kiro_agent.py` launches `kiro-cli chat --agent <name>` instead of the GUI's `kiro chat --profile <name>`. No hooks are emitted for this target (kiro-cli's stable engine has no hook runtime).

**Tech Stack:** Python 3, stdlib only (`argparse`, `json`, `shutil`, `subprocess`, `pathlib`) — no new dependencies. `pytest` for tests. `kiro-cli` (installed locally, v2.20.1) for live verification.

**Spec:** `docs/superpowers/specs/2026-09-04-kiro-cli-target-migration-design.md` (this plan implements it) and `docs/spec/rebuild-spec.md` (the project's canonical spec, amended by Task 4 below).

## Global Constraints

- Python 3 standard library only — no third-party dependencies in `build/assemble.py`, `build/deploy.py`, or `build/kiro_agent.py`.
- Assembler output must stay deterministic: same inputs → byte-identical outputs across two runs.
- `build/deploy.py` must stay idempotent — running it twice leaves the same `.kiro/` tree.
- Do not modify skill/SOP/hook source content under `context/`, `skills/`, `sops/`, `hooks/` — only `build/assemble.py`'s target function and its emitted paths change.
- `python3 build/ci.py` must exit 0 (`CI GATE: PASS`) after every task in this plan — run it at the end of each task, not just at the end of the plan.
- Every empirically-verified kiro-cli behavior cited below was tested live against the installed `kiro-cli 2.20.1` (default `--agent-engine v2`) in this repo on 2026-09-04; do not second-guess it against the (looser/partly-inaccurate) hosted docs.

---

### Task 1: `build/assemble.py` — replace `kiro` target with `kiro-cli`

**Files:**
- Modify: `build/assemble.py:28` (`TARGETS` tuple), `build/assemble.py:156-168` (`target_kiro` → `target_kiro_cli`), `build/assemble.py:190-194` (`TARGET_FUNCS` dict)
- Modify: `tests/test_assemble.py:220-317` (the `# --- kiro target ---` section)
- Modify: `build/ci.py:27-28` (smoke-test stage label/command)
- Modify: `tests/test_sops_hooks_ci.py:72-82,85-98` (hooks-emission test, CI-stage-list test)

**Interfaces:**
- Produces: `TARGET_FUNCS["kiro-cli"]` → a function assembling `out/steering/**`, `out/skills/<name>/`, `out/sops/<name>.sop.md`, `out/settings/mcp.json`, `out/agents/<manifest.name>.json`. `out/agents/<manifest.name>.json` has shape `{"name", "description", "prompt": null, "mcpServers": {}, "tools", "allowedTools", "resources": [two fixed strings], "includeMcpJson": true, "model": null}`.
- Consumes: nothing new — reuses `resolve_includes`, `expand_context_globs`, `declared_skill_dirs`, `copy_sops`, `emit_mcp`, `write` exactly as they exist today.

- [ ] **Step 1: Update `tests/test_assemble.py`'s kiro-target section to target `kiro-cli`**

Replace the `# --- kiro target ---` section (current lines 220–317) with:

```python
# --- kiro-cli target ---


def test_kiro_cli_target_writes_00_system_steering_with_prompt_includes(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    system = (out_dir / "steering" / "00-system.md").read_text(encoding="utf-8")
    assert IDENTITY_MARKER in system
    assert DOMAIN_MARKER in system
    assert ROUTING_MARKER not in system  # eager tiers are separate steering files


def test_kiro_cli_target_writes_one_steering_file_per_eager_tier_file(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    routing = (out_dir / "steering" / "routing-00-core.md").read_text(encoding="utf-8")
    assert ROUTING_MARKER in routing
    guardrail = (out_dir / "steering" / "guardrails-no-fabrication.md").read_text(encoding="utf-8")
    assert GUARDRAIL_MARKER in guardrail


def test_kiro_cli_target_writes_mcp_json_under_settings(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, mcpServers={"example": {"command": "echo"}})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    mcp = json.loads((out_dir / "settings" / "mcp.json").read_text(encoding="utf-8"))
    assert mcp == {"mcpServers": {"example": {"command": "echo"}}}
    assert not (out_dir / "mcp.json").exists()


def test_kiro_cli_target_copies_declared_skill_dir(tmp_path):
    pkg = copy_package(tmp_path)
    declare_skill(pkg, "example-skill")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    copied = out_dir / "skills" / "example-skill" / "SKILL.md"
    original = pkg / "skills" / "example-skill" / "SKILL.md"
    assert copied.read_text(encoding="utf-8") == original.read_text(encoding="utf-8")


def test_kiro_cli_target_copies_declared_sops(tmp_path):
    pkg = copy_package(tmp_path)
    declare_sop(pkg, "example-sop")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    copied = out_dir / "sops" / "example-sop.sop.md"
    assert copied.read_text(encoding="utf-8") == "# Example SOP\n\nDo the thing.\n"


def test_kiro_cli_target_context_globs_matching_prompt_partial_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, contextGlobs=["prompt/*"])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode != 0
    assert "prompt" in result.stderr
    assert not (out_dir / "steering" / "routing-00-core.md").exists()


def test_kiro_cli_target_never_emits_hooks(tmp_path):
    pkg = copy_package(tmp_path)
    declare_hook(pkg, "example", {"event": "SessionStart", "command": "true"})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    assert not (out_dir / "hooks").exists()


def test_kiro_cli_target_writes_agent_config_with_resources_and_mcp_flag(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    config = json.loads((out_dir / "agents" / "agent-x.json").read_text(encoding="utf-8"))
    assert config["name"] == "agent-x"
    assert config["prompt"] is None
    assert config["resources"] == [
        "file://.kiro/steering/**/*.md",
        "skill://.kiro/skills/*/SKILL.md",
    ]
    assert config["includeMcpJson"] is True
    assert config["mcpServers"] == {}


def test_kiro_cli_target_agent_config_tools_defaults_to_wildcard_when_manifest_empty(tmp_path):
    out_dir = tmp_path / "out"

    # The real agent.manifest.json ships "tools": [] today — assert the
    # fallback, not an override, so this breaks loudly if that ever changes.
    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    config = json.loads((out_dir / "agents" / "agent-x.json").read_text(encoding="utf-8"))
    assert config["tools"] == ["*"]


def test_kiro_cli_target_agent_config_tools_passes_through_when_manifest_declares_some(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, tools=["read", "write"], allowedTools=["read"])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    config = json.loads((out_dir / "agents" / "agent-x.json").read_text(encoding="utf-8"))
    assert config["tools"] == ["read", "write"]
    assert config["allowedTools"] == ["read"]
```

Also update the two determinism tests further down: change
`test_kiro_target_is_deterministic_across_two_runs` (current lines 417–430)
to `test_kiro_cli_target_is_deterministic_across_two_runs`, with both
`run_assemble_at(pkg, "--target", "kiro", ...)` calls changed to
`"--target", "kiro-cli"`.

- [ ] **Step 2: Run the new/changed tests to confirm they fail against current code**

Run: `python3 -m pytest tests/test_assemble.py -k kiro_cli -v`
Expected: FAIL — `argparse` rejects `--target kiro-cli` (not yet a valid choice), or `out_dir / "agents"` doesn't exist.

- [ ] **Step 3: Update `build/assemble.py`**

Change the `TARGETS` tuple:

```python
TARGETS = ("claude-code", "kiro-cli", "generic")
```

Add a new helper function right after `emit_mcp` (which stays unchanged — it's still used by `claude-code` and `generic`):

```python
def emit_kiro_cli_agent(manifest: dict, path: Path) -> None:
    """kiro-cli's agent-activation format — distinct from the Kiro GUI
    editor's steering-file convention. Verified live against kiro-cli 2.20.1
    (2026-09-04): steering (`.kiro/steering/**/*.md`) auto-loads for every
    agent regardless of `resources`, but it's still declared explicitly here
    so this doesn't depend on an unstated default that could change across
    versions. Skills do NOT auto-load — `skill://.kiro/skills/*/SKILL.md`
    must be declared for skill content to preload."""
    name = manifest.get("name")
    if not name:
        fail("agent.manifest.json has no name — required for the kiro-cli agent config filename")
    config = {
        "name": name,
        "description": manifest.get("description", ""),
        "prompt": None,
        "mcpServers": {},
        "tools": manifest.get("tools") or ["*"],
        "allowedTools": manifest.get("allowedTools", []),
        "resources": [
            "file://.kiro/steering/**/*.md",
            "skill://.kiro/skills/*/SKILL.md",
        ],
        "includeMcpJson": True,
        "model": None,
    }
    write(path, json.dumps(config, indent=2, sort_keys=True) + "\n")
```

Replace `target_kiro` with `target_kiro_cli`:

```python
def target_kiro_cli(manifest: dict, out: Path) -> None:
    write(out / "steering" / "00-system.md", resolve_includes(manifest))
    for f in expand_context_globs(manifest):
        rel = f.relative_to(CONTEXT)
        write(out / "steering" / "-".join(rel.parts), f.read_text(encoding="utf-8"))
    for d in declared_skill_dirs(manifest):
        copy_tree(d, out / "skills" / d.name)
    copy_sops(manifest, out)
    emit_mcp(manifest, out / "settings" / "mcp.json")
    emit_kiro_cli_agent(manifest, out / "agents" / f"{manifest['name']}.json")
```

Update `TARGET_FUNCS`:

```python
TARGET_FUNCS = {
    "claude-code": target_claude_code,
    "kiro-cli": target_kiro_cli,
    "generic": target_generic,
}
```

Update the module docstring's usage line (near the top of the file):
`python3 build/assemble.py --target claude-code|kiro|generic [--out DIR]` →
`python3 build/assemble.py --target claude-code|kiro-cli|generic [--out DIR]`

Leave `hook_files()` in place — `target_claude_code` still uses it.

- [ ] **Step 4: Update `tests/test_sops_hooks_ci.py`**

Replace `test_assemblers_emit_hooks_for_kiro_and_claude` (current lines 72–82) with:

```python
def test_assembler_emits_hooks_for_claude_but_not_kiro_cli(tmp_path):
    pkg = copy_package(tmp_path)
    kiro_cli_out = tmp_path / "kiro-cli"
    claude_out = tmp_path / "claude"

    assert run_assemble_at(pkg, "kiro-cli", kiro_cli_out).returncode == 0
    assert run_assemble_at(pkg, "claude-code", claude_out).returncode == 0

    assert not (kiro_cli_out / "hooks").exists()
    hooks_json = json.loads((claude_out / "hooks.json").read_text(encoding="utf-8"))
    assert {hook["name"] for hook in hooks_json} >= {"Wire New Capability", "Capability Wiring Audit"}
```

In `test_ci_entrypoint_lists_all_gate_stages` (current lines 85–98), change
the expected string `"kiro"` to `"kiro-cli"`.

- [ ] **Step 5: Update `build/ci.py`'s smoke-test stage**

Change:

```python
    ("assembler smoke: kiro",
     [sys.executable, "build/assemble.py", "--target", "kiro"]),
```

to:

```python
    ("assembler smoke: kiro-cli",
     [sys.executable, "build/assemble.py", "--target", "kiro-cli"]),
```

- [ ] **Step 6: Run the full assemble/CI test files to confirm they pass**

Run: `python3 -m pytest tests/test_assemble.py tests/test_sops_hooks_ci.py -v`
Expected: all PASS.

Run: `python3 build/assemble.py --target kiro-cli` (manual smoke, matches
`build/ci.py`'s new stage)
Expected: `assembled target=kiro-cli out=dist/kiro-cli`; then
`cat dist/kiro-cli/agents/agent-x.json` shows the shape from Step 3.

- [ ] **Step 7: Commit**

```bash
git add build/assemble.py build/ci.py tests/test_assemble.py tests/test_sops_hooks_ci.py
git commit -m "$(cat <<'EOF'
feat: replace kiro assembler target with kiro-cli

The kiro target was built for the Kiro GUI editor's steering/hooks layout
and never accounted for kiro-cli, the separate terminal tool actually in
use. kiro-cli has its own agent-activation format (.kiro/agents/<name>.json)
and no hook runtime in its default engine — this target reuses the existing
steering/skills/sops emission, moves mcp.json under settings/ (where
kiro-cli's includeMcpJson actually reads it, verified live), and adds the
agent-config file. See docs/superpowers/specs/2026-09-04-kiro-cli-target-migration-design.md.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UFfLiurXYysVzDXHDQaXLW
EOF
)"
```

---

### Task 2: `build/deploy.py` — deploy the new `kiro-cli` layout

**Files:**
- Modify: `build/deploy.py` (`MAPPINGS` tuple, `assemble()`'s `--target` arg)
- Modify: `tests/test_deploy.py`

**Interfaces:**
- Consumes: `TARGET_FUNCS["kiro-cli"]` from Task 1 (via `assemble.py --target kiro-cli --out <dist_dir>`).
- Produces: `<workspace_root>/.kiro/{steering,skills,sops,settings/mcp.json,agents/<name>.json}` — Task 3's launcher and Task 6's live verification both read this tree.

- [ ] **Step 1: Update `tests/test_deploy.py`**

In `test_deploy_writes_workspace_kiro_matching_assembled_output`, change:

```python
    assert (deployed / "steering" / "00-system.md").is_file()
    assert (deployed / "skills" / "demo-skill" / "SKILL.md").is_file()
    assert (deployed / "hooks" / "wire-new-capability.kiro.hook").is_file()
    assert (deployed / "mcp.json").is_file()
```

to:

```python
    assert (deployed / "steering" / "00-system.md").is_file()
    assert (deployed / "skills" / "demo-skill" / "SKILL.md").is_file()
    assert (deployed / "settings" / "mcp.json").is_file()
    assert (deployed / "agents" / "agent-x.json").is_file()
    assert not (deployed / "hooks").exists()
```

`test_deploy_is_idempotent` and `test_deploy_can_target_different_workspace_root` need no assertion changes — they only check `steering/00-system.md` and rely on `same_tree()`, which is target-agnostic.

- [ ] **Step 2: Run to confirm the updated assertion fails**

Run: `python3 -m pytest tests/test_deploy.py -v`
Expected: FAIL on the new `settings/mcp.json` / `agents/agent-x.json` assertions (current `deploy.py` still calls `--target kiro` and uses the old flat `MAPPINGS`).

- [ ] **Step 3: Update `build/deploy.py`**

Change:

```python
MAPPINGS = ("steering", "skills", "hooks", "sops", "mcp.json")
```

to:

```python
MAPPINGS = ("steering", "skills", "sops", "settings/mcp.json", "agents")
```

In `assemble()`, change:

```python
        [sys.executable, str(assembler), "--target", "kiro", "--out", str(out)],
```

to:

```python
        [sys.executable, str(assembler), "--target", "kiro-cli", "--out", str(out)],
```

No other changes needed — `copy_path` already creates parent directories
(`dst.parent.mkdir(parents=True, exist_ok=True)`), so the nested
`"settings/mcp.json"` mapping entry copies correctly, and `assert_same_tree`
is a generic recursive comparison unaffected by the mapping names.

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python3 -m pytest tests/test_deploy.py -v`
Expected: all PASS.

- [ ] **Step 5: Manual smoke test**

Run:
```bash
rm -rf .kiro  # safe — gitignored, regenerated below
python3 build/deploy.py
ls .kiro
```
Expected output includes: `agents  settings  skills  sops  steering` (no
`hooks`, no top-level `mcp.json`).

Run: `cat .kiro/settings/mcp.json` — expect `{"mcpServers": {}}`.
Run: `cat .kiro/agents/agent-x.json` — expect the shape from Task 1 Step 3.

- [ ] **Step 6: Commit**

```bash
git add build/deploy.py tests/test_deploy.py
git commit -m "$(cat <<'EOF'
feat: deploy the kiro-cli layout instead of the GUI kiro layout

Matches the assembler's new kiro-cli target: copies settings/mcp.json and
agents/ instead of the flat mcp.json and hooks/ the old kiro target wrote.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UFfLiurXYysVzDXHDQaXLW
EOF
)"
```

---

### Task 3: `build/kiro_agent.py` — launch `kiro-cli chat --agent`, not `kiro chat --profile`

**Files:**
- Modify: `build/kiro_agent.py`
- Modify: `tests/test_kiro_agent_runner.py`

**Interfaces:**
- Consumes: `deploy_agent()`'s existing JSON summary shape (`{"agent", "agent_root", "assembled_from", "deployed_to", "files_written"}`) from Task 2 — unchanged.
- Produces: a `command: list[str]` in the `--dry-run` JSON payload of the shape `["kiro-cli", "chat", "--agent", <profile>, ...optional flags..., <prompt>]` — used by whoever actually launches kiro-cli (README examples, the user directly) and by Task 6's live verification.

- [ ] **Step 1: Update `tests/test_kiro_agent_runner.py`**

Change `test_kiro_runner_dry_run_deploys_default_agent_to_workspace_kiro`:

```python
def test_kiro_runner_dry_run_deploys_default_agent_to_workspace_kiro(tmp_path):
    workspace = tmp_path / "workspace"

    result = run_runner("--workspace-root", str(workspace), "--prompt", "hello", "--dry-run")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["agent"] == "agent-x"
    assert payload["profile"] == "agent-x"
    assert payload["cwd"] == str(workspace)
    assert payload["deployed_to"] == str(workspace / ".kiro")
    assert payload["command"] == ["kiro-cli", "chat", "--agent", "agent-x", "hello"]
    assert (workspace / ".kiro" / "steering" / "00-system.md").is_file()
    assert (workspace / ".kiro" / "settings" / "mcp.json").is_file()
    assert (workspace / ".kiro" / "agents" / "agent-x.json").is_file()
```

Add a new test for the passthrough flags:

```python
def test_kiro_runner_passes_through_no_interactive_and_trust_all_tools(tmp_path):
    workspace = tmp_path / "workspace"

    result = run_runner(
        "--workspace-root", str(workspace), "--prompt", "hi",
        "--no-interactive", "--trust-all-tools", "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["command"] == [
        "kiro-cli", "chat", "--agent", "agent-x",
        "--no-interactive", "--trust-all-tools", "hi",
    ]
```

`test_kiro_runner_can_switch_to_agent_path_with_isolated_profile`,
`test_kiro_runner_resolves_alias_from_local_registry`, and
`test_kiro_runner_dry_run_can_skip_deploy_when_workspace_kiro_exists` need no
changes — none of them assert on `payload["command"]`.

- [ ] **Step 2: Run to confirm the updated test fails**

Run: `python3 -m pytest tests/test_kiro_agent_runner.py -v`
Expected: FAIL on the `payload["command"]` assertion (current code still
builds the `kiro chat --mode agent --profile` shape) and on the new
passthrough test (current code has no `--no-interactive`/`--trust-all-tools`
flags at all).

- [ ] **Step 3: Rewrite `build/kiro_agent.py`**

Replace the whole file:

```python
#!/usr/bin/env python3
"""Deploy and launch a selected agent package with kiro-cli.

kiro-cli (the terminal chat tool) is a separate program from the Kiro GUI
editor — it activates agents via `.kiro/agents/<name>.json` in the workspace
root, not the GUI's steering/profile mechanism. This wrapper deploys the
selected source agent into the workspace root, then starts
`kiro-cli chat --agent <name>` from that same workspace. Switching agents is
changing `--agent`.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "build" / "deploy.py"


def fail(message: str) -> None:
    print(f"KIRO AGENT ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing required file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")
    return {}


def resolve_agent(value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_dir():
        return candidate.resolve()

    registry = ROOT / "agents" / "registry.local.json"
    if registry.is_file():
        data = load_json(registry)
        target = data.get("agents", {}).get(value)
        if target:
            return Path(target).expanduser().resolve()

    fail(f"agent {value!r} is neither a directory nor an alias in agents/registry.local.json")
    raise SystemExit(1)


def manifest_name(agent_root: Path) -> str:
    manifest = load_json(agent_root / "agent.manifest.json")
    name = manifest.get("name")
    if not name:
        fail(f"agent manifest has no name: {agent_root / 'agent.manifest.json'}")
    return str(name)


def deploy_agent(agent_root: Path, workspace_root: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(DEPLOY), "--agent", str(agent_root), "--workspace-root", str(workspace_root), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        fail(f"deploy failed for {agent_root} (exit {result.returncode})")
    return json.loads(result.stdout)


def command_for(args: argparse.Namespace, profile: str) -> list[str]:
    cmd = ["kiro-cli", "chat", "--agent", profile]
    if args.no_interactive:
        cmd.append("--no-interactive")
    if args.trust_all_tools:
        cmd.append("--trust-all-tools")
    if args.model:
        cmd.extend(["--model", args.model])
    if args.effort:
        cmd.extend(["--effort", args.effort])
    if args.prompt:
        cmd.append(args.prompt)
    return cmd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=str(ROOT), help="Agent package path, or alias from agents/registry.local.json. Default: this repo.")
    parser.add_argument("--workspace-root", default=str(ROOT), help="Workspace root where kiro-cli should load .kiro/. Default: this repo.")
    parser.add_argument("--profile", default=None, help="kiro-cli agent name to activate (passed as kiro-cli chat's --agent). Default: agent name.")
    parser.add_argument("--prompt", default=None, help="Prompt to pass to `kiro-cli chat`.")
    parser.add_argument("--no-interactive", action="store_true", help="Run kiro-cli chat without expecting further user input.")
    parser.add_argument("--trust-all-tools", action="store_true", help="Allow kiro-cli to use any tool without confirmation prompts.")
    parser.add_argument("--model", default=None, help="Model to pass to kiro-cli chat.")
    parser.add_argument("--effort", default=None, help="Effort level to pass to kiro-cli chat (low, medium, high, xhigh, max).")
    parser.add_argument("--no-deploy", action="store_true", help="Use existing workspace-root/.kiro without redeploying.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved launch JSON without running kiro-cli.")
    args = parser.parse_args(argv)

    agent_root = resolve_agent(args.agent)
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    name = manifest_name(agent_root)
    profile = args.profile or name

    deployed = None
    if not args.no_deploy:
        deployed = deploy_agent(agent_root, workspace_root)

    cmd = command_for(args, profile)
    payload = {
        "agent": name,
        "agent_root": str(agent_root),
        "workspace_root": str(workspace_root),
        "deployed_to": str(workspace_root / ".kiro"),
        "profile": profile,
        "cwd": str(workspace_root),
        "command": cmd,
        "shell_command": "cd " + shlex.quote(str(workspace_root)) + " && " + " ".join(shlex.quote(x) for x in cmd),
        "deploy": deployed,
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    env = os.environ.copy()
    result = subprocess.run(cmd, cwd=workspace_root, env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `python3 -m pytest tests/test_kiro_agent_runner.py -v`
Expected: all PASS (6 tests: the 4 existing ones plus the rewritten command
assertion plus the new passthrough test).

- [ ] **Step 5: Manual dry-run smoke test**

Run: `python3 build/kiro_agent.py --agent . --prompt "What agent are you?" --dry-run`
Expected: JSON payload with
`"command": ["kiro-cli", "chat", "--agent", "agent-x", "What agent are you?"]`
and `"shell_command": "cd ... && kiro-cli chat --agent agent-x 'What agent are you?'"`.

- [ ] **Step 6: Commit**

```bash
git add build/kiro_agent.py tests/test_kiro_agent_runner.py
git commit -m "$(cat <<'EOF'
feat: launch kiro-cli chat --agent instead of the GUI's kiro chat --profile

The launcher's whole CLI surface (--mode, --reuse-window, --new-window,
--user-data-dir, --add-file) targeted the Kiro GUI editor's window-launch
flags, which kiro-cli doesn't have. Rebuilt around kiro-cli chat's actual
flags (--agent, --no-interactive, --trust-all-tools, --model, --effort);
the deploy-then-launch flow and registry-alias resolution are unchanged.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UFfLiurXYysVzDXHDQaXLW
EOF
)"
```

---

### Task 4: Amend the canonical spec and README

**Files:**
- Modify: `docs/spec/rebuild-spec.md` (lines 1677-1695, 1830-1888, 2052, 3188-3189, 3311)
- Modify: `README.md` (lines 7-16, 119-139)

**Interfaces:**
- Consumes: nothing (documentation only — no code interface).
- Produces: nothing consumed by later tasks, but Task 6's final progress-log entry references this task as done.

- [ ] **Step 1: Update the target concept table in `docs/spec/rebuild-spec.md` (section 13.2)**

Replace the table (current lines 1679–1685):

```markdown
| Concept | `claude-code` target | `kiro` target | `generic` target |
|---|---|---|---|
| System prompt | `dist/claude-code/CLAUDE.md` (assembled prompt + eager tiers appended) | `dist/kiro/steering/00-system.md` (always-included steering) + one steering file per eager tier file | `dist/generic/system-prompt.txt` (everything concatenated) |
| Skills | `dist/claude-code/.claude/skills/<name>/` | `dist/kiro/skills/<name>/` | `dist/generic/skills-catalog.md` (frontmatter index for prompt injection) + copied dirs |
| SOPs | `dist/claude-code/sops/<name>.sop.md` (copied — skills and hooks cite these paths) | `dist/kiro/sops/<name>.sop.md` | `dist/generic/sops/<name>.sop.md` |
| MCP servers | `dist/claude-code/.mcp.json` | `dist/kiro/mcp.json` | `dist/generic/mcp.json` |
| Hooks | `dist/claude-code/hooks.json` (aggregated list, neutral schema — no trigger rewriting) | `dist/kiro/hooks/<name>.kiro.hook` | omitted (no hook runtime assumed) |
| Wiring proof | the validator runs on the SOURCE tree — identical for all targets | same | same |
```

with:

```markdown
| Concept | `claude-code` target | `kiro-cli` target | `generic` target |
|---|---|---|---|
| System prompt | `dist/claude-code/CLAUDE.md` (assembled prompt + eager tiers appended) | `dist/kiro-cli/steering/00-system.md` (always-included steering) + one steering file per eager tier file | `dist/generic/system-prompt.txt` (everything concatenated) |
| Skills | `dist/claude-code/.claude/skills/<name>/` | `dist/kiro-cli/skills/<name>/` | `dist/generic/skills-catalog.md` (frontmatter index for prompt injection) + copied dirs |
| SOPs | `dist/claude-code/sops/<name>.sop.md` (copied — skills and hooks cite these paths) | `dist/kiro-cli/sops/<name>.sop.md` | `dist/generic/sops/<name>.sop.md` |
| MCP servers | `dist/claude-code/.mcp.json` | `dist/kiro-cli/settings/mcp.json` | `dist/generic/mcp.json` |
| Agent activation | n/a (host loads `CLAUDE.md` directly) | `dist/kiro-cli/agents/<name>.json` — `resources` field points at the steering/skills paths above; kiro-cli's own `--agent <name>` flag activates it | n/a |
| Hooks | `dist/claude-code/hooks.json` (aggregated list, neutral schema — no trigger rewriting) | omitted — kiro-cli's default engine has no hook runtime | omitted (no hook runtime assumed) |
| Wiring proof | the validator runs on the SOURCE tree — identical for all targets | same | same |

**Verified kiro-cli agent-activation behavior** (tested live against kiro-cli
2.20.1, default `--agent-engine v2`, 2026-09-04 — the hosted docs are
ambiguous or wrong on these points, so this repo's own empirical test is the
source of truth):
- `.kiro/steering/**/*.md` loads for every agent in the workspace
  unconditionally, regardless of what that agent's `resources` field
  declares. `resources` still lists it explicitly, since relying on an
  unstated default is fragile across kiro-cli versions.
- `.kiro/skills/*/SKILL.md` does **not** auto-load — it requires an explicit
  `"skill://.kiro/skills/*/SKILL.md"` entry in `resources`.
- `includeMcpJson: true` reads `.kiro/settings/mcp.json` — not a top-level
  `.kiro/mcp.json`.
- A relative `file://` resource path resolves against the workspace root
  (the invocation `cwd`), not the agent config file's own directory.
```

- [ ] **Step 2: Update the CLI usage line in section 13.3**

Change (current line 1695):
```
    python3 build/assemble.py --target claude-code|kiro|generic [--out DIR]
```
to:
```
    python3 build/assemble.py --target claude-code|kiro-cli|generic [--out DIR]
```

- [ ] **Step 3: Update the `target_kiro` code listing in section 13.3**

Replace (current lines 1830–1842):

```python
def target_kiro(manifest: dict, out: Path) -> None:
    write(out / "steering" / "00-system.md", resolve_includes(manifest))
    for f in expand_globs(manifest):
        rel = f.relative_to(CONTEXT)
        write(out / "steering" / "-".join(rel.parts), f.read_text(encoding="utf-8"))
    for d in declared_skill_dirs(manifest):
        copy_tree(d, out / "skills" / d.name)
    copy_sops(manifest, out)
    emit_mcp(manifest, out / "mcp.json")
    if HOOKS.is_dir():
        for p in sorted(HOOKS.glob("*.hook.json")):
            write(out / "hooks" / (p.stem.replace(".hook", "") + ".kiro.hook"),
                  p.read_text(encoding="utf-8"))
```

with:

```python
def emit_kiro_cli_agent(manifest: dict, path: Path) -> None:
    """kiro-cli's agent-activation format. Steering auto-loads regardless of
    `resources` (declared here anyway, for clarity); skills do not — see the
    verified-behavior note in 13.2."""
    config = {
        "name": manifest["name"],
        "description": manifest.get("description", ""),
        "prompt": None,
        "mcpServers": {},
        "tools": manifest.get("tools") or ["*"],
        "allowedTools": manifest.get("allowedTools", []),
        "resources": [
            "file://.kiro/steering/**/*.md",
            "skill://.kiro/skills/*/SKILL.md",
        ],
        "includeMcpJson": True,
        "model": None,
    }
    write(path, json.dumps(config, indent=2, sort_keys=True) + "\n")


def target_kiro_cli(manifest: dict, out: Path) -> None:
    write(out / "steering" / "00-system.md", resolve_includes(manifest))
    for f in expand_globs(manifest):
        rel = f.relative_to(CONTEXT)
        write(out / "steering" / "-".join(rel.parts), f.read_text(encoding="utf-8"))
    for d in declared_skill_dirs(manifest):
        copy_tree(d, out / "skills" / d.name)
    copy_sops(manifest, out)
    emit_mcp(manifest, out / "settings" / "mcp.json")
    emit_kiro_cli_agent(manifest, out / "agents" / f"{manifest['name']}.json")
```

And update the `TARGETS` dict a few lines below (current line 1867):
```python
TARGETS = {
    "claude-code": target_claude_code,
    "kiro": target_kiro,
    "generic": target_generic,
}
```
to:
```python
TARGETS = {
    "claude-code": target_claude_code,
    "kiro-cli": target_kiro_cli,
    "generic": target_generic,
}
```

- [ ] **Step 4: Update the hooks-section prose in section 13.5**

Change (current line 2052):
```markdown
Host-neutral shape, re-emitted **without translation**: the `kiro` target renames each file to `<name>.kiro.hook`, the `claude-code` target aggregates all hooks into one `hooks.json` list. Neither rewrites triggers — the neutral field names ARE the contract. A host whose runtime expects different trigger names gets its mapping added in that host's target function in `build/assemble.py`; the extension point is deliberate, and claiming translation the assembler does not perform would violate self-report honesty.
```
to:
```markdown
Host-neutral shape, re-emitted **without translation**: the `claude-code` target aggregates all hooks into one `hooks.json` list. The `kiro-cli` target omits hooks entirely — kiro-cli's default engine has no hook runtime to receive them (verified: no hook-related concept anywhere in its CLI surface). Neither rewrites triggers where they are emitted — the neutral field names ARE the contract. A host whose runtime expects different trigger names gets its mapping added in that host's target function in `build/assemble.py`; the extension point is deliberate, and claiming translation the assembler does not perform would violate self-report honesty.
```

- [ ] **Step 5: Update the CI-stages listing in the `build/ci.py` code block (section 17.4 area)**

Change (current lines 3188–3189):
```python
    ("assembler smoke: kiro",
     [sys.executable, "build/assemble.py", "--target", "kiro"]),
```
to:
```python
    ("assembler smoke: kiro-cli",
     [sys.executable, "build/assemble.py", "--target", "kiro-cli"]),
```

- [ ] **Step 6: Update Task 11's demo line in section 20**

Change (current line 3311):
```markdown
*Demo:* `python3 build/assemble.py --target claude-code|kiro|generic` each produce the documented artifact layout; outputs are byte-identical across two runs.
```
to:
```markdown
*Demo:* `python3 build/assemble.py --target claude-code|kiro-cli|generic` each produce the documented artifact layout; outputs are byte-identical across two runs.
```

- [ ] **Step 7: Update `README.md`**

Change the Quick start section (current lines 7–16):
```markdown
## Quick start

1. Clone the repo.
2. Deploy the Kiro runtime files into the workspace root:

       python3 build/deploy.py

3. Open the repo folder in Kiro, or ask it from the CLI:

       python3 build/kiro_agent.py --agent . --prompt "What agent are you?"
```
to:
```markdown
## Quick start

1. Clone the repo.
2. Deploy the kiro-cli runtime files into the workspace root:

       python3 build/deploy.py

3. Activate the agent:

       kiro-cli chat --agent agent-x
       # or, via the launcher (deploys first, then launches):
       python3 build/kiro_agent.py --agent . --prompt "What agent are you?"
```

Change the "Build targets" section (current lines 119–139):
```markdown
Primary target: Kiro

    python3 build/assemble.py --target kiro

To make Kiro actually load Agent X in this workspace, deploy generated files into `.kiro/`:

    python3 build/deploy.py

For repeatable Kiro CLI testing and agent switching, use the launcher:

    python3 build/kiro_agent.py --agent . --prompt "Run the demo skill" --dry-run
    python3 build/kiro_agent.py --agent . --prompt "Run the demo skill"

To switch agents, pass another agent package path or an alias from `agents/registry.local.json`:

    cp agents/registry.local.json.example agents/registry.local.json
    python3 build/kiro_agent.py --agent /path/to/other-agent --prompt "Smoke test"

The launcher deploys the selected agent into `<workspace-root>/.kiro/` and launches Kiro from that workspace root, because Kiro loads agent config from the workspace `.kiro/` directory.
```
to:
```markdown
Primary target: kiro-cli

    python3 build/assemble.py --target kiro-cli

To make kiro-cli actually load Agent X in this workspace, deploy generated files into `.kiro/`:

    python3 build/deploy.py
    kiro-cli chat --agent agent-x

For repeatable kiro-cli testing and agent switching, use the launcher:

    python3 build/kiro_agent.py --agent . --prompt "Run the demo skill" --dry-run
    python3 build/kiro_agent.py --agent . --prompt "Run the demo skill"

To switch agents, pass another agent package path or an alias from `agents/registry.local.json`:

    cp agents/registry.local.json.example agents/registry.local.json
    python3 build/kiro_agent.py --agent /path/to/other-agent --prompt "Smoke test"

The launcher deploys the selected agent into `<workspace-root>/.kiro/` and launches `kiro-cli chat --agent <name>` from that workspace root, because kiro-cli loads agent config from the workspace `.kiro/agents/` directory.
```

- [ ] **Step 8: Verify no other "kiro" (GUI) references remain stale**

Run: `grep -n '"kiro"\|--target kiro\b\|kiro chat --profile\|dist/kiro\b' README.md docs/spec/rebuild-spec.md`
Expected: no matches (the pattern `\bkiro\b` deliberately excludes `kiro-cli`
substring matches — if this greps clean, every remaining `kiro` mention in
these two files is either `kiro-cli` or unrelated prose).

- [ ] **Step 9: Commit**

```bash
git add docs/spec/rebuild-spec.md README.md
git commit -m "$(cat <<'EOF'
docs: amend canonical spec and README for the kiro-cli target

The rebuild spec's kiro target section (and README's usage instructions)
described the GUI editor's layout this repo no longer assembles. Updates
the target table, target_kiro_cli code listing, hooks-section prose, CI
stage list, and Task 11 demo line to match, plus records the empirically-
verified kiro-cli agent-activation behavior so it isn't relearned later.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UFfLiurXYysVzDXHDQaXLW
EOF
)"
```

---

### Task 5: Live verification — deploy, activate, and confirm routing/skills/identity

**Files:**
- Modify: `docs/progress/PROJECT_PROGRESS.md` (append a new dated section — existing convention, do not rewrite prior entries)
- No other files change in this task — it's verification, not new code.

**Interfaces:**
- Consumes: everything from Tasks 1–4 — this is the end-to-end check that they compose correctly against the real, installed `kiro-cli` binary (not just unit tests against isolated `tmp_path` copies).

- [ ] **Step 1: Full CI gate**

Run: `python3 build/ci.py`
Expected: `CI GATE: PASS — all stages green` (all 7 stages, including the new
`assembler smoke: kiro-cli` stage).

- [ ] **Step 2: Fresh deploy against the real workspace**

Run:
```bash
rm -rf .kiro dist
python3 build/deploy.py
```
Expected: `deployed agent-x to <repo>/.kiro`, `files_written: <N>`. Then:
```bash
ls .kiro
cat .kiro/agents/agent-x.json
```
Expected: `agents  settings  skills  sops  steering` (no `hooks`); the agent
config matches Task 1's shape.

- [ ] **Step 3: Confirm kiro-cli discovers the agent**

Run: `kiro-cli agent list`
Expected: the listing includes `agent-x    Workspace` alongside the
built-ins (`kiro_default`, `kiro_help`, `kiro_planner`).

- [ ] **Step 4: Confirm identity and guardrail routing (steering)**

Run:
```bash
timeout 60 kiro-cli chat --agent agent-x --no-interactive --trust-tools= \
  "In one sentence: what agent are you, and name one specific guardrail or SOP you were given (cite its filename)."
```
Expected: response identifies as the Agent X / agent-x persona and cites a
real guardrail filename (e.g. `guardrails-no-fabrication.md`) — proving
`.kiro/steering/**/*.md` loaded via the new `kiro-cli` target's deployed
output.

- [ ] **Step 5: Confirm skill content is reachable (resources declaration)**

Run:
```bash
timeout 60 kiro-cli chat --agent agent-x --no-interactive --trust-tools= \
  "Without using any tool: what exact user phrase activates the demo skill, per that skill's own SKILL.md?"
```
Expected: response quotes a phrase matching `skills/demo-skill/SKILL.md`'s
"When to activate" section (e.g. "run the demo" / "try the demo skill"),
confirming the `"skill://.kiro/skills/*/SKILL.md"` resources entry works
against the real deployed tree (not just the isolated probe from the design
phase).

- [ ] **Step 6: Confirm MCP config location took effect**

Run: `kiro-cli mcp list`
Expected: no error about a missing/malformed config (the agent's
`includeMcpJson: true` should resolve cleanly against
`.kiro/settings/mcp.json`, which exists and is valid JSON even though it's
`{"mcpServers": {}}` today).

- [ ] **Step 7: Append the progress note**

Read `docs/progress/PROJECT_PROGRESS.md`'s existing structure first (task
sections, "Current verification status", "Next task"), then append a new
section following the same format as the existing `### Task 14a` entry —
include: what changed (kiro target → kiro-cli target, across assemble.py /
deploy.py / kiro_agent.py), the verification commands from Steps 1–6 above
and their results, and update "Next task" to point at whatever remains
(Task 14b's CI-workflow-file / `workflow` auth scope, unless that's been
resolved separately).

- [ ] **Step 8: Commit**

```bash
git add docs/progress/PROJECT_PROGRESS.md
git commit -m "$(cat <<'EOF'
docs: record kiro-cli target migration verification

Full CI gate green; live-verified against the installed kiro-cli 2.20.1:
agent-x discoverable via `kiro-cli agent list`, identity/guardrail content
loads from steering, skill content loads via the resources declaration, and
MCP config resolves from the new settings/mcp.json location.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UFfLiurXYysVzDXHDQaXLW
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** every component listed in the design doc's "Component
  changes" section has a task: `assemble.py` (Task 1), `deploy.py` (Task 2),
  `kiro_agent.py` (Task 3), `docs/spec/rebuild-spec.md` + `README.md` (Task
  4), live verification + `PROJECT_PROGRESS.md` (Task 5). Test files
  (`test_assemble.py`, `test_deploy.py`, `test_kiro_agent_runner.py`,
  `test_sops_hooks_ci.py`) and `build/ci.py` are folded into the task whose
  code they test, per the task-right-sizing rule.
- **Placeholder scan:** no TBD/TODO; every step shows literal code, not a
  description of code.
- **Type/name consistency:** `target_kiro_cli`, `emit_kiro_cli_agent`,
  `MAPPINGS`, `command_for(args, profile)` are spelled identically across
  Tasks 1–3 and their doc mirror in Task 4.
- **Out of scope** (carried over from the design doc, not tasks here):
  `subagentNames` never being assembled into any target; kiro-cli's `--v3`
  experimental engine's inline `hooks`; root directory restructuring.
