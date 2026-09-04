#!/usr/bin/env python3
"""Guard: the toolkit README's surface table must agree with the live surface.

Compares `toolkit discover` output (generated truth) against the hand-written
markdown table in tool/toolkit/README.md.

Exit codes: 0 agree · 1 drift · 2 unverifiable.
A guard that cannot load what it compares must not report agreement or
drift — a silent pass turns a guard into decoration.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT = ROOT / "tool" / "toolkit" / "toolkit.py"
README = ROOT / "tool" / "toolkit" / "README.md"


def live_surface() -> dict[str, bool] | None:
    """{command: is_write} from the generated truth, or None if unverifiable."""
    try:
        out = subprocess.run(
            [sys.executable, str(TOOLKIT), "discover"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"UNVERIFIABLE: cannot run toolkit discover: {exc}")
        return None
    if out.returncode != 0:
        print(f"UNVERIFIABLE: toolkit discover exited {out.returncode}")
        return None
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        print(f"UNVERIFIABLE: discover output not JSON: {exc}")
        return None
    try:
        return {row["command"]: bool(row["write"]) for row in data["surface"]}
    except (KeyError, TypeError) as exc:
        # Valid JSON with the wrong shape is still an unloadable side —
        # crashing here would turn the mandated exit-2 into a traceback.
        print(f"UNVERIFIABLE: discover output missing expected fields: {exc}")
        return None


def documented_surface() -> dict[str, bool] | None:
    if not README.is_file():
        print(f"UNVERIFIABLE: {README} not found")
        return None
    docs: dict[str, bool] = {}
    for line in README.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*([a-z-]+)\s*\|\s*(yes|no)\s*\|$", line.strip())
        if m and m.group(1) not in ("command",):
            docs[m.group(1)] = m.group(2) == "yes"
    if not docs:
        print("UNVERIFIABLE: no surface table found in the README")
        return None
    return docs


def main() -> int:
    live = live_surface()
    docs = documented_surface()
    if live is None or docs is None:
        return 2

    drift = 0
    for cmd in sorted(set(docs) - set(live)):
        print(f"PHANTOM: README documents '{cmd}' but it is not on the surface")
        drift += 1
    for cmd in sorted(set(live) - set(docs)):
        print(f"MISSING: surface has '{cmd}' but the README does not document it")
        drift += 1
    for cmd in sorted(set(live) & set(docs)):
        if live[cmd] != docs[cmd]:
            print(f"UNDERSPECIFIED: '{cmd}' write={live[cmd]} on the surface, "
                  f"write={docs[cmd]} in the README")
            drift += 1

    if drift:
        print(f"TOOL CONTRACT: DRIFT — {drift} finding(s)")
        return 1
    print("TOOL CONTRACT: AGREE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
