#!/usr/bin/env python3
"""Validate that every capability in this package is completely wired up.

A skill or guardrail file on disk does nothing on its own. Each one has to be
attached at several points before an agent will load and route to it. This
script asserts those attachments exist, so a half-wired capability fails
loudly instead of sitting inert.

Task 1 scope only: manifest/config loading, the exit-2 structural floor
(no skills/ directory), and check #17 (missing routing/00-core.md). Later
rebuild tasks add the remaining checks described in README.md Section 17.1.

Severities:
  ERROR  behavioral wiring — the capability will not load or will never be
         routed to. Exits non-zero.
  WARN   documentation drift — behavior is fine, docs are stale. Exits zero
         unless --strict is passed.

Usage:
    python3 context/scripts/validate-wiring.py [--strict] [--skill NAME]

Stdlib only. Run from anywhere; paths resolve relative to this file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SKILLS_DIR = ROOT / "skills"
ROUTING_DIR = ROOT / "context" / "routing"
MANIFEST = ROOT / "agent.manifest.json"
WIRING_CONFIG = ROOT / "wiring.config.json"

findings: list[tuple[str, str, str]] = []  # (severity, subject, message)


def error(subject: str, message: str) -> None:
    findings.append(("ERROR", subject, message))


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        error(str(path.relative_to(ROOT)), f"unreadable: {exc}")
        return ""


def load_json(path: Path) -> dict | None:
    """None = missing or invalid (caller decides severity). A valid empty
    document `{}` is returned as-is — it is a real document, not an error;
    conflating the two once misreported an empty manifest as unreadable."""
    if not path.is_file():
        return None
    try:
        return json.loads(read(path))
    except json.JSONDecodeError as exc:
        error(path.name, f"invalid JSON: {exc}")
        return None


def check_routing_core(only: str | None) -> None:
    """Check #17: routing/00-core.md is the sole dispatch authority."""
    if only:
        return
    if not (ROUTING_DIR / "00-core.md").is_file():
        error("routing/00-core.md",
              "missing — the routing core gate is the sole dispatch "
              "authority; without it nothing routes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    parser.add_argument("--skill", metavar="NAME", help="check one skill only")
    args = parser.parse_args()

    if not SKILLS_DIR.is_dir():
        print(f"FAIL — no skills/ directory under {ROOT}", file=sys.stderr)
        return 2
    if args.skill and not (SKILLS_DIR / args.skill).is_dir():
        print(f"FAIL — skills/{args.skill}/ does not exist", file=sys.stderr)
        return 2

    manifest = load_json(MANIFEST)
    if manifest is None:
        error("agent.manifest.json", "missing or unreadable — nothing can be wired")
        manifest = {}
    load_json(WIRING_CONFIG)  # validated for well-formedness only in Task 1

    check_routing_core(args.skill)

    errors = [f for f in findings if f[0] == "ERROR"]
    warnings = [f for f in findings if f[0] == "WARN"]
    for severity, subject, message in errors + warnings:
        print(f"{severity:5} {subject}: {message}")

    scope = f"skill {args.skill}" if args.skill else "all capabilities"
    if errors:
        print(f"\nWIRING VALIDATION: FAIL ({scope}) — "
              f"{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    if warnings and args.strict:
        print(f"\nWIRING VALIDATION: FAIL ({scope}) — "
              f"{len(warnings)} warning(s), --strict")
        return 1
    if warnings:
        print(f"\nWIRING VALIDATION: PASS ({scope}) — "
              f"{len(warnings)} warning(s), no errors")
        return 0
    print(f"WIRING VALIDATION: PASS ({scope}) — fully wired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
