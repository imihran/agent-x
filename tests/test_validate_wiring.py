import json
import shutil
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


def copy_package(tmp_path: Path) -> Path:
    """A private copy of the package so a test's manifest/README edits
    never touch the real working tree."""
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git"))
    return dest


def run_validator_at(pkg_root: Path, *args: str) -> subprocess.CompletedProcess:
    validator = pkg_root / "context" / "scripts" / "validate-wiring.py"
    return subprocess.run(
        [sys.executable, str(validator), *args],
        capture_output=True,
        text=True,
    )


def set_manifest(pkg_root: Path, **fields) -> None:
    manifest_path = pkg_root / "agent.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(fields)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_declared_skill_missing_on_disk_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, skillNames=["ghost-skill"])

    result = run_validator_at(pkg)

    assert "ERROR skillNames:ghost-skill" in result.stdout
    assert "does not exist" in result.stdout


def test_declared_sop_missing_on_disk_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, sopNames=["ghost-sop"])

    result = run_validator_at(pkg)

    assert "ERROR sopNames:ghost-sop" in result.stdout
    assert "does not exist" in result.stdout


def test_readme_advertised_agent_without_manifest_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    (pkg / "README.md").write_text(
        "run the agent: `ghost-agent`\n", encoding="utf-8"
    )

    result = run_validator_at(pkg)

    assert "ERROR README:ghost-agent" in result.stdout
