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
