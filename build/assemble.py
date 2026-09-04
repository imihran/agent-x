#!/usr/bin/env python3
"""Assemble the agent package's system prompt from its manifest.

Task 4 scope: load the manifest and resolve systemPromptIncludes in listed
order into one assembled prompt. contextGlobs expansion, skill/SOP copying,
hooks, MCP config, and the full per-host target layouts (claude-code, kiro)
land in Task 11 (README.md Section 13.3).

Usage:
    python3 build/assemble.py [--target generic] [--out DIR]

Stdlib only. Deterministic: same inputs, byte-identical outputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "agent.manifest.json"

TARGETS = {"generic"}


def fail(msg: str) -> None:
    print(f"ASSEMBLE ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_manifest() -> dict:
    if not MANIFEST.is_file():
        fail("agent.manifest.json not found at package root")
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"agent.manifest.json is invalid JSON: {exc}")
    return {}


def resolve_includes(manifest: dict) -> str:
    """Read systemPromptIncludes in listed order and concatenate them,
    separated by blank lines. A missing include is a hard error — the
    order IS the assembled prompt order (README.md 13.1)."""
    parts: list[str] = []
    for rel in manifest.get("systemPromptIncludes", []):
        path = ROOT / rel
        if not path.is_file():
            fail(f"systemPromptIncludes entry missing on disk: {rel}")
        parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts) + "\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def target_generic(manifest: dict, out: Path) -> None:
    write(out / "system-prompt.txt", resolve_includes(manifest))


TARGET_FUNCS = {"generic": target_generic}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="generic", choices=sorted(TARGETS))
    parser.add_argument("--out", default=None, help="output dir (default dist/<target>)")
    args = parser.parse_args()

    manifest = load_manifest()
    out = Path(args.out) if args.out else ROOT / "dist" / args.target
    TARGET_FUNCS[args.target](manifest, out)
    print(f"assembled target={args.target} out={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
