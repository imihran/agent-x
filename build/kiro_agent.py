#!/usr/bin/env python3
"""Assemble and launch a selected agent package with the Kiro CLI.

This wrapper makes Kiro testing repeatable and switchable: each source agent is
assembled into its own Kiro artifact directory and launched with its own Kiro
profile, so testing another agent is just changing --agent.
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
DEFAULT_WORKSPACE = ROOT / ".kiro-agents"


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

    fail(
        f"agent {value!r} is neither a directory nor an alias in "
        "agents/registry.local.json"
    )
    raise SystemExit(1)


def manifest_name(agent_root: Path) -> str:
    manifest = load_json(agent_root / "agent.manifest.json")
    name = manifest.get("name")
    if not name:
        fail(f"agent manifest has no name: {agent_root / 'agent.manifest.json'}")
    return str(name)


def assemble(agent_root: Path, out: Path) -> None:
    assembler = agent_root / "build" / "assemble.py"
    if not assembler.is_file():
        fail(f"agent has no build/assemble.py: {agent_root}")
    result = subprocess.run(
        [sys.executable, str(assembler), "--target", "kiro", "--out", str(out)],
        cwd=agent_root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stderr, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        fail(f"assembly failed for {agent_root} (exit {result.returncode})")


def command_for(args: argparse.Namespace, agent_root: Path, out: Path, profile: str) -> list[str]:
    cmd = ["kiro", "chat", "--mode", args.mode, "--profile", profile]
    if args.new_window:
        cmd.append("--new-window")
    elif args.reuse_window:
        cmd.append("--reuse-window")
    if args.user_data_dir:
        cmd.extend(["--user-data-dir", str(Path(args.user_data_dir).expanduser())])
    for add_file in args.add_file:
        cmd.extend(["--add-file", add_file])
    if args.prompt:
        cmd.append(args.prompt)
    return cmd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        default=str(ROOT),
        help="Agent package path, or alias from agents/registry.local.json. Default: this repo.",
    )
    parser.add_argument(
        "--workspace",
        default=str(DEFAULT_WORKSPACE),
        help="Where assembled Kiro artifacts live. Default: .kiro-agents/",
    )
    parser.add_argument("--profile", default=None, help="Kiro profile name. Default: agent name.")
    parser.add_argument("--mode", default="agent", help="Kiro chat mode. Default: agent.")
    parser.add_argument("--prompt", default=None, help="Prompt to pass to `kiro chat`.")
    parser.add_argument("--add-file", action="append", default=[], help="Extra file context for Kiro chat.")
    parser.add_argument("--user-data-dir", default=None, help="Optional isolated Kiro user-data dir.")
    parser.add_argument("--reuse-window", action="store_true", help="Reuse last Kiro window.")
    parser.add_argument("--new-window", action="store_true", help="Open a new Kiro window.")
    parser.add_argument("--no-assemble", action="store_true", help="Use existing assembled artifact.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved launch JSON without running Kiro.")
    args = parser.parse_args(argv)

    if args.new_window and args.reuse_window:
        fail("choose only one of --new-window or --reuse-window")

    agent_root = resolve_agent(args.agent)
    name = manifest_name(agent_root)
    workspace = Path(args.workspace).expanduser().resolve()
    out = workspace / name
    profile = args.profile or name

    if not args.no_assemble:
        assemble(agent_root, out)

    cmd = command_for(args, agent_root, out, profile)
    payload = {
        "agent": name,
        "agent_root": str(agent_root),
        "artifact_dir": str(out),
        "profile": profile,
        "cwd": str(out),
        "command": cmd,
        "shell_command": "cd " + shlex.quote(str(out)) + " && " + " ".join(shlex.quote(x) for x in cmd),
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    env = os.environ.copy()
    result = subprocess.run(cmd, cwd=out, env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
