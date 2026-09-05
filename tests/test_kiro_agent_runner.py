import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "build" / "kiro_agent.py"


def copy_package(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "dist", ".kiro", ".kiro-agents", ".pytest_cache", "__pycache__"))
    return dest


def run_runner(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
    )


def test_kiro_runner_dry_run_deploys_default_agent_to_workspace_kiro(tmp_path):
    workspace = tmp_path / "workspace"

    result = run_runner("--workspace-root", str(workspace), "--prompt", "hello", "--dry-run")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["agent"] == "agent-x"
    assert payload["profile"] == "agent-x"
    assert payload["cwd"] == str(workspace)
    assert payload["deployed_to"] == str(workspace / ".kiro")
    assert payload["command"][:5] == ["kiro", "chat", "--mode", "agent", "--profile"]
    assert payload["command"][-1] == "hello"
    assert (workspace / ".kiro" / "steering" / "00-system.md").is_file()
    assert (workspace / ".kiro" / "mcp.json").is_file()


def test_kiro_runner_can_switch_to_agent_path_with_isolated_profile(tmp_path):
    pkg = copy_package(tmp_path)
    manifest = json.loads((pkg / "agent.manifest.json").read_text(encoding="utf-8"))
    manifest["name"] = "agent-y"
    (pkg / "agent.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    workspace = tmp_path / "workspace"

    result = run_runner("--agent", str(pkg), "--workspace-root", str(workspace), "--dry-run")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["agent"] == "agent-y"
    assert payload["profile"] == "agent-y"
    assert payload["cwd"] == str(workspace)
    assert payload["deployed_to"] == str(workspace / ".kiro")
    assert (workspace / ".kiro" / "steering" / "00-system.md").is_file()


def test_kiro_runner_resolves_alias_from_local_registry(tmp_path):
    pkg = copy_package(tmp_path)
    other = copy_package(tmp_path / "other-root")
    manifest = json.loads((other / "agent.manifest.json").read_text(encoding="utf-8"))
    manifest["name"] = "aliased-agent"
    (other / "agent.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    registry = pkg / "agents" / "registry.local.json"
    registry.write_text(json.dumps({"agents": {"personal": str(other)}}, indent=2) + "\n", encoding="utf-8")
    workspace = tmp_path / "workspace"

    runner = pkg / "build" / "kiro_agent.py"
    result = subprocess.run(
        [sys.executable, str(runner), "--agent", "personal", "--workspace-root", str(workspace), "--dry-run"],
        cwd=pkg,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["agent"] == "aliased-agent"
    assert payload["agent_root"] == str(other)
    assert (workspace / ".kiro" / "steering" / "00-system.md").is_file()


def test_kiro_runner_dry_run_can_skip_deploy_when_workspace_kiro_exists(tmp_path):
    workspace = tmp_path / "workspace"
    first = run_runner("--workspace-root", str(workspace), "--dry-run")
    assert first.returncode == 0, first.stderr

    second = run_runner("--workspace-root", str(workspace), "--no-deploy", "--dry-run")

    assert second.returncode == 0, second.stderr
    payload = json.loads(second.stdout)
    assert payload["deployed_to"] == str(workspace / ".kiro")
    assert payload["deploy"] is None
