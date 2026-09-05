#!/usr/bin/env python3
"""Session-start preflight. Emits one fact per check; writes NOTHING.

Fact format:  key | SEVERITY | detail     (SEVERITY: OK|INFO|WARN|ERROR)
A missing capability blocks only that capability — never the session.
Always exits 0: preflight reports; it never blocks the session.

--with-discovery: after the fact block, run discovery (context/scripts/
discover.py) — sequential by construction, avoiding the race where discovery
runs while preflight is still probing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def fact(key: str, severity: str, detail: str) -> None:
    print(f"{key} | {severity} | {detail}")


def clean_env() -> dict[str, str]:
    """Minimal environment for the clean probe. On some platforms the
    interpreter needs a system root to start at all, so retain only that —
    everything else (PYTHONPATH above all) is stripped, because a capability
    importable solely via an inherited variable is not provisioned."""
    keep = {}
    for k in ("SystemRoot", "SYSTEMROOT", "windir"):
        if k in os.environ:
            keep[k] = os.environ[k]
    return keep


def main() -> int:
    print("=== PREFLIGHT_STATE v1 ===")

    # 1. Interpreter — we are running, so report the version against the floor
    vi = sys.version_info
    if (vi.major, vi.minor) >= (3, 10):
        fact("python", "OK", f"python {vi.major}.{vi.minor}")
    else:
        fact("python", "WARN",
             f"python {vi.major}.{vi.minor} found; 3.10+ required for tooling")

    # 2. Toolkit store — demo tool layer
    store = Path(os.environ.get("TOOLKIT_STORE", "")) if os.environ.get(
        "TOOLKIT_STORE") else Path.home() / ".agent-toolkit" / "store.json"
    if store.is_file():
        fact("toolkit_store", "OK", f"store present at {store}")
    else:
        fact("toolkit_store", "INFO",
             f"no store at {store} — toolkit will create it on first write")

    # 3. Ambient vs clean double probe — import the REAL toolkit module.
    #    Works-only-ambient is an inherited accident, not provisioning.
    #    (Probing only stdlib imports here would be a check that cannot
    #    fail — the exact defect class 9.2 names.)
    toolkit_dir = Path(__file__).resolve().parents[2] / "tool" / "toolkit"
    if not (toolkit_dir / "toolkit.py").is_file():
        fact("toolkit_import", "ERROR",
             f"toolkit module missing at {toolkit_dir} — tool layer unavailable")
    else:
        probe = [sys.executable, "-c",
                 f"import sys; sys.path.insert(0, {str(toolkit_dir)!r}); "
                 "import toolkit"]
        ambient_ok = subprocess.run(probe, capture_output=True).returncode == 0
        clean_ok = subprocess.run(probe, capture_output=True,
                                  env=clean_env()).returncode == 0
        if ambient_ok and clean_ok:
            fact("toolkit_import", "OK",
                 "toolkit imports in ambient AND clean env")
        elif ambient_ok:
            fact("toolkit_import", "WARN",
                 "SPLIT: toolkit imports in this shell but FAILS in a clean "
                 "env — scheduled runs will break")
        else:
            fact("toolkit_import", "ERROR",
                 "toolkit import fails even in ambient env — run "
                 "`python3 tool/toolkit/toolkit.py authcheck` for detail")

    # 4. Optional integrations — absent tool reads "not evaluated", never "failed"
    if shutil.which("git"):
        fact("git", "OK", "git available")
    else:
        fact("git", "INFO",
             "git not evaluated (not found) — version-control features off")

    print("=== END PREFLIGHT_STATE ===")

    if "--with-discovery" in sys.argv:
        # Flush before spawning: stdout is block-buffered when piped/captured
        # (as in tests), so without this the discovery child's own flush-at-
        # exit can land before our buffered fact block — output order would
        # contradict the documented "fact block, then discovery" sequence.
        sys.stdout.flush()
        discover = Path(__file__).resolve().parent / "discover.py"
        subprocess.run([sys.executable, str(discover)])

    return 0  # preflight reports; it never blocks the session


if __name__ == "__main__":
    sys.exit(main())
