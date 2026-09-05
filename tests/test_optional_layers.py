import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "context" / "scripts" / "validate-wiring.py"


def copy_package(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git"))
    return dest


def run_validator_at(pkg_root: Path) -> subprocess.CompletedProcess:
    validator = pkg_root / "context" / "scripts" / "validate-wiring.py"
    return subprocess.run([sys.executable, str(validator), "--strict"], capture_output=True, text=True)


def load_manifest(pkg_root: Path) -> dict:
    return json.loads((pkg_root / "agent.manifest.json").read_text(encoding="utf-8"))


def write_manifest(pkg_root: Path, manifest: dict) -> None:
    (pkg_root / "agent.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def load_investigator(pkg_root: Path) -> dict:
    return json.loads((pkg_root / "agents" / "readonly-investigator.agent.json").read_text(encoding="utf-8"))


def test_readonly_investigator_is_declared_and_prompt_exists():
    manifest = load_manifest(ROOT)
    subagent = load_investigator(ROOT)

    assert "readonly-investigator" in manifest["subagentNames"]
    assert subagent["name"] == "readonly-investigator"
    for include in subagent["systemPromptIncludes"]:
        assert (ROOT / include).is_file()


def test_readonly_investigator_has_no_write_tools():
    subagent = load_investigator(ROOT)

    assert subagent["allowedTools"] == ["read"]
    assert not ({"write", "edit", "delete", "create", "update", "patch"} & {tool.lower() for tool in subagent["tools"]})


def test_readonly_investigator_shell_allowlist_is_read_verbs_only():
    subagent = load_investigator(ROOT)
    patterns = subagent["shellAllowedCommands"]

    assert patterns
    for pattern in patterns:
        assert "(list|get|search|discover|authcheck)" in pattern
        assert not re.search(r"\b(create|update|delete)\b", pattern)


def test_declared_subagent_missing_manifest_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    (pkg / "agents" / "readonly-investigator.agent.json").unlink()

    result = run_validator_at(pkg)

    assert result.returncode == 1
    assert "ERROR subagentNames:readonly-investigator" in result.stdout


def test_readonly_investigator_write_tool_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    path = pkg / "agents" / "readonly-investigator.agent.json"
    subagent = json.loads(path.read_text(encoding="utf-8"))
    subagent["allowedTools"] = ["read", "write"]
    path.write_text(json.dumps(subagent, indent=2) + "\n", encoding="utf-8")

    result = run_validator_at(pkg)

    assert result.returncode == 1
    assert "allowedTools must contain only read" in result.stdout


def test_readonly_investigator_write_shell_verb_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    path = pkg / "agents" / "readonly-investigator.agent.json"
    subagent = json.loads(path.read_text(encoding="utf-8"))
    subagent["shellAllowedCommands"] = [r"^python3 tool/toolkit/toolkit\.py (list|create)( .*)?$"]
    path.write_text(json.dumps(subagent, indent=2) + "\n", encoding="utf-8")

    result = run_validator_at(pkg)

    assert result.returncode == 1
    assert "shellAllowedCommands" in result.stdout
