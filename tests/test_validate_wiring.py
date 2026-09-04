import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "context" / "scripts" / "validate-wiring.py"


def run_validator(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        capture_output=True,
        text=True,
    )


def test_empty_package_fails_on_missing_routing_core():
    result = run_validator()
    assert result.returncode == 1
    assert "routing/00-core.md" in result.stdout
    assert "WIRING VALIDATION: FAIL" in result.stdout
