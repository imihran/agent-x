#!/usr/bin/env python3
"""Run the full validation gate: both validator families, tests, and an assembler smoke across all targets.

This is the single CI entry point. Any vendor CI binding should call exactly this script. Exits non-zero on the first failing stage.

Guard exit code 2 (UNVERIFIABLE) fails the gate like drift does — a guard that cannot load what it compares must not be treated as passing.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STAGES: list[tuple[str, list[str]]] = [
    ("wiring validator (family 1)",
     [sys.executable, "context/scripts/validate-wiring.py", "--strict"]),
    ("anti-drift guard: tool contract (family 2)",
     [sys.executable, "guards/check-tool-contract.py"]),
    ("anti-drift guard: cli references (family 2)",
     [sys.executable, "guards/check-cli-references.py"]),
    ("tests",
     [sys.executable, "-m", "pytest", "tests/", "-q"]),
    ("assembler smoke: claude-code",
     [sys.executable, "build/assemble.py", "--target", "claude-code"]),
    ("assembler smoke: kiro",
     [sys.executable, "build/assemble.py", "--target", "kiro"]),
    ("assembler smoke: generic",
     [sys.executable, "build/assemble.py", "--target", "generic"]),
]


def main() -> int:
    for name, cmd in STAGES:
        print(f"── {name} ──")
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            print(f"CI GATE: FAIL at stage '{name}' (exit {result.returncode})")
            return 1
    print("CI GATE: PASS — all stages green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
