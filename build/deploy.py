#!/usr/bin/env python3
"""Deploy a selected agent package into a kiro-cli workspace root.

kiro-cli loads agent configuration from `.kiro/` in the workspace root. The
source package stays editable at repo root; this script assembles the
selected agent's kiro-cli target and then copies the generated layout into
`<workspace-root>/.kiro/`.

Stdlib only. Idempotent: repeated runs produce the same `.kiro/` tree.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPINGS = ("steering", "skills", "sops", "settings/mcp.json", "agents")
CLAUDE_MAPPINGS = (
    "CLAUDE.md",
    ".mcp.json",
    ".claude/rules",
    ".claude/skills",
    ".claude/sops",
    ".claude/agents",
    ".claude/settings.json",
    ".claude/hooks.json",
)


def fail(message: str) -> None:
    print(f"DEPLOY ERROR: {message}", file=sys.stderr)
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


def agent_name(agent_root: Path) -> str:
    manifest = load_json(agent_root / "agent.manifest.json")
    name = manifest.get("name")
    if not name:
        fail(f"agent manifest has no name: {agent_root / 'agent.manifest.json'}")
    return str(name)


def assemble(agent_root: Path, out: Path, target: str = "kiro-cli") -> None:
    assembler = agent_root / "build" / "assemble.py"
    if not assembler.is_file():
        fail(f"agent has no build/assemble.py: {agent_root}")
    result = subprocess.run(
        [sys.executable, str(assembler), "--target", target, "--out", str(out)],
        cwd=agent_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        fail(f"assembly failed for {agent_root} (exit {result.returncode})")


def copy_path(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    if dst.exists():
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    if src.is_dir():
        shutil.copytree(src, dst)
        return sum(1 for p in dst.rglob("*") if p.is_file())
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return 1


def assert_same_tree(src: Path, dst: Path) -> None:
    comparison = filecmp.dircmp(src, dst)
    problems = comparison.left_only + comparison.right_only + comparison.diff_files + comparison.funny_files
    if problems:
        fail(f"deployed tree does not match assembled output: {problems}")
    for name in comparison.common_dirs:
        assert_same_tree(src / name, dst / name)


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
        if src.is_dir():
            assert_same_tree(src, dst)

    return {
        "target": "claude-code",
        "agent": agent_name(agent_root),
        "agent_root": str(agent_root),
        "assembled_from": str(source_out),
        "deployed_to": str(workspace_root),
        "files_written": written,
    }


def deploy(agent_root: Path, workspace_root: Path, clean: bool = True,
           target: str = "kiro-cli") -> dict:
    if target == "claude-code":
        workspace_root.mkdir(parents=True, exist_ok=True)
        return deploy_claude(agent_root, workspace_root)

    source_out = agent_root / "dist" / "kiro-cli"
    kiro_dir = workspace_root / ".kiro"

    assemble(agent_root, source_out)

    if clean and kiro_dir.exists():
        shutil.rmtree(kiro_dir)
    kiro_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for name in MAPPINGS:
        written += copy_path(source_out / name, kiro_dir / name)

    assert_same_tree(source_out, kiro_dir)
    return {
        "target": "kiro-cli",
        "agent": agent_name(agent_root),
        "agent_root": str(agent_root),
        "assembled_from": str(source_out),
        "deployed_to": str(kiro_dir),
        "files_written": written,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=str(ROOT), help="Agent source path or alias from agents/registry.local.json.")
    parser.add_argument("--workspace-root", default=str(ROOT), help="Workspace root where kiro-cli should load `.kiro/`.")
    parser.add_argument("--no-clean", action="store_true", help="Do not remove existing .kiro before copying.")
    parser.add_argument("--target", default="kiro-cli", choices=("kiro-cli", "claude-code"),
                        help="Which assembled layout to deploy.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON summary.")
    args = parser.parse_args(argv)

    agent_root = resolve_agent(args.agent)
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    summary = deploy(agent_root, workspace_root, clean=not args.no_clean, target=args.target)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"deployed {summary['agent']} ({summary['target']}) to {summary['deployed_to']}")
        print(f"source: {summary['assembled_from']}")
        print(f"files_written: {summary['files_written']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
