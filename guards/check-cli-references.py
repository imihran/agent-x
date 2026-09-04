#!/usr/bin/env python3
"""Guard: every `toolkit <cmd>` reference in docs and skills must parse
against the LIVE argparse parser — derived from the parser's own choices,
never from a hand-maintained list (a hand-listed enumeration once shipped a
broken subcommand unchecked in the same change that added the guard).

Exit codes: 0 agree · 1 drift · 2 unverifiable.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "skills", ROOT / "sops", ROOT / "context", ROOT / "tool"]
SCAN_FILES = [ROOT / "README.md"]

sys.path.insert(0, str(ROOT / "tool" / "toolkit"))


def live_commands() -> set[str] | None:
    try:
        import argparse
        import toolkit  # noqa: F401  (the module under guard)
        parser = toolkit.build_parser()
        sub = next(a for a in parser._actions
                   if isinstance(a, argparse._SubParsersAction))
        return set(sub.choices)
    except Exception as exc:  # any load failure = unverifiable, not pass/fail
        print(f"UNVERIFIABLE: cannot load the toolkit parser: {exc}")
        return None


def referenced_commands() -> list[tuple[Path, str]]:
    refs: list[tuple[Path, str]] = []
    # Match only actual invocations: inline code (`toolkit list`) or a
    # script call (…/toolkit.py list). An unanchored pattern once flagged
    # prose — "the toolkit is a demo" — as a reference to subcommand `is`.
    pattern = re.compile(r"(?:`toolkit|toolkit\.py)\s+([a-z][a-z-]*)")
    files: list[Path] = list(SCAN_FILES)
    for d in SCAN_DIRS:
        if d.is_dir():
            files.extend(sorted(d.rglob("*.md")))
    for f in files:
        for m in pattern.finditer(f.read_text(encoding="utf-8")):
            refs.append((f, m.group(1)))
    return refs


def main() -> int:
    live = live_commands()
    if live is None:
        return 2
    drift = 0
    for path, cmd in referenced_commands():
        if cmd not in live:
            print(f"DRIFT: {path.relative_to(ROOT)} references "
                  f"'toolkit {cmd}' — not a live subcommand")
            drift += 1
    if drift:
        print(f"CLI REFERENCES: DRIFT — {drift} finding(s)")
        return 1
    print("CLI REFERENCES: AGREE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
