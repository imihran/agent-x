import filecmp
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "build" / "deploy.py"


def copy_package(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "dist", ".kiro", ".kiro-agents", ".pytest_cache", "__pycache__"))
    return dest


def run_deploy(pkg: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(pkg / "build" / "deploy.py"), *args],
        cwd=pkg,
        capture_output=True,
        text=True,
    )


def same_tree(left: Path, right: Path) -> bool:
    cmp = filecmp.dircmp(left, right)
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return False
    return all(same_tree(left / name, right / name) for name in cmp.common_dirs)


def test_deploy_writes_workspace_kiro_matching_assembled_output(tmp_path):
    pkg = copy_package(tmp_path)

    result = run_deploy(pkg, "--json")

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    deployed = pkg / ".kiro"
    assembled = pkg / "dist" / "kiro-cli"
    assert summary["deployed_to"] == str(deployed)
    assert (deployed / "steering" / "00-system.md").is_file()
    assert (deployed / "skills" / "demo-skill" / "SKILL.md").is_file()
    assert (deployed / "settings" / "mcp.json").is_file()
    assert (deployed / "agents" / "agent-x.json").is_file()
    assert not (deployed / "hooks").exists()
    assert same_tree(assembled, deployed)


def test_deploy_is_idempotent(tmp_path):
    pkg = copy_package(tmp_path)

    first = run_deploy(pkg, "--json")
    second = run_deploy(pkg, "--json")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(first.stdout)["files_written"] == json.loads(second.stdout)["files_written"]
    assert same_tree(pkg / "dist" / "kiro-cli", pkg / ".kiro")


def test_deploy_can_target_different_workspace_root(tmp_path):
    pkg = copy_package(tmp_path)
    workspace = tmp_path / "workspace"

    result = run_deploy(pkg, "--workspace-root", str(workspace), "--json")

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["deployed_to"] == str(workspace / ".kiro")
    assert (workspace / ".kiro" / "steering" / "00-system.md").is_file()


def test_registry_example_documents_alias_shape():
    data = json.loads((ROOT / "agents" / "registry.local.json.example").read_text(encoding="utf-8"))

    assert "agents" in data
    assert "agent-x" in data["agents"]
