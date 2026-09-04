import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSEMBLE = ROOT / "build" / "assemble.py"

IDENTITY_MARKER = "# Identity & Shared Behavior"
DOMAIN_MARKER = "# Domain — {{DOMAIN_NAME}}"


def run_assemble(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ASSEMBLE), *args],
        capture_output=True,
        text=True,
    )


def test_assembled_prompt_contains_both_partials_in_numeric_order_exactly_once(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--out", str(out_dir))

    assert result.returncode == 0
    prompt = (out_dir / "system-prompt.txt").read_text(encoding="utf-8")
    assert prompt.count(IDENTITY_MARKER) == 1
    assert prompt.count(DOMAIN_MARKER) == 1
    assert prompt.index(IDENTITY_MARKER) < prompt.index(DOMAIN_MARKER)
