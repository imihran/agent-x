#!/usr/bin/env python3
"""Assemble the agent package's system prompt from its manifest.

Task 4 scope: load the manifest and resolve systemPromptIncludes in listed
order into one assembled prompt. Task 7 scope adds contextGlobs expansion for
the generic target: routing/guardrails/knowledge/conventions files are
expanded relative to context/, sorted, and appended to system-prompt.txt with
source comments — with a hard error if any pattern matches context/prompt/
(prompt partials load via systemPromptIncludes ONLY; matching them here would
load them twice). Skill/SOP copying, hooks, MCP config, and the full per-host
target layouts (claude-code, kiro) land in Task 11 (README.md Section 13.3).

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
CONTEXT = ROOT / "context"
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


def expand_context_globs(manifest: dict) -> list[Path]:
    """contextGlobs expand relative to context/, sorted by filename. A glob
    matching any context/prompt/ file is a hard error — prompt partials load
    through systemPromptIncludes ONLY (README.md 13.1); matching them here
    would load them twice."""
    files: list[Path] = []
    for pattern in manifest.get("contextGlobs", []):
        matches = sorted(CONTEXT.glob(pattern))
        for m in matches:
            if not m.is_file():
                continue
            if m.relative_to(CONTEXT).parts[0] == "prompt":
                fail(
                    f"contextGlobs must not match prompt partials: {pattern} -> "
                    f"{m.relative_to(ROOT)} (would load it twice)"
                )
            files.append(m)
    return files


def eager_block(files: list[Path]) -> str:
    """Render eager-tier files with a source comment per file, so the
    assembled prompt shows where each rule came from."""
    parts = []
    for f in files:
        rel = f.relative_to(ROOT)
        parts.append(f"<!-- {rel} -->\n{f.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts) + ("\n" if parts else "")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def target_generic(manifest: dict, out: Path) -> None:
    prompt = resolve_includes(manifest)
    eager = eager_block(expand_context_globs(manifest))
    write(out / "system-prompt.txt", prompt + "\n" + eager)


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
