#!/usr/bin/env python3
"""Emit the toolkit surface inventory into session context.

Prints exact errors instead of swallowing them; ALWAYS exits 0 because it
runs inside a combined agentSpawn hook and must not abort the chain.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLKIT = ROOT / "tool" / "toolkit" / "toolkit.py"


def main() -> int:
    print("=== TOOL_SURFACE v1 ===")
    try:
        out = subprocess.run([sys.executable, str(TOOLKIT), "discover"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            print(out.stdout.rstrip())
        else:
            print("discover-error | toolkit discover failed:")
            print((out.stdout + out.stderr).rstrip())
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"discover-error | could not run toolkit discover: {exc}")
    print("=== END TOOL_SURFACE ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
