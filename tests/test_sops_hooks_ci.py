import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_package(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "dist", ".pytest_cache", "__pycache__"))
    return dest


def run_validator_at(pkg_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(pkg_root / "context" / "scripts" / "validate-wiring.py"), "--strict"],
        cwd=pkg_root,
        capture_output=True,
        text=True,
    )


def run_assemble_at(pkg_root: Path, target: str, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(pkg_root / "build" / "assemble.py"), "--target", target, "--out", str(out)],
        cwd=pkg_root,
        capture_output=True,
        text=True,
    )


def test_declared_sops_exist_and_example_is_allowlisted():
    manifest = json.loads((ROOT / "agent.manifest.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "wiring.config.json").read_text(encoding="utf-8"))

    assert manifest["sopNames"] == ["wire-new-capability", "adversarial-review"]
    for name in manifest["sopNames"]:
        assert (ROOT / "sops" / f"{name}.sop.md").is_file()
    assert config["undeclaredSopAllowlist"]["example"]


def test_undeclared_sop_not_allowlisted_fails_strict(tmp_path):
    pkg = copy_package(tmp_path)
    (pkg / "sops" / "rogue.sop.md").write_text("# Rogue\n", encoding="utf-8")

    result = run_validator_at(pkg)

    assert result.returncode == 1
    assert "WARN" in result.stdout
    assert "sops/rogue" in result.stdout
    assert "not declared in sopNames" in result.stdout


def test_hooks_are_valid_json_and_reference_wiring_sop():
    hooks = sorted((ROOT / "hooks").glob("*.hook.json"))

    # the three real hooks, plus the inert copy-me template
    assert {p.name for p in hooks} == {
        "wire-new-capability.hook.json",
        "wire-on-agent-write.hook.json",
        "wiring-audit.hook.json",
        "example.hook.json",
    }
    for path in hooks:
        hook = json.loads(path.read_text(encoding="utf-8"))
        assert hook["name"]
        assert hook["when"]["type"]
        assert hook["then"]["type"] == "askAgent"
    assert "sops/wire-new-capability.sop.md" in (ROOT / "hooks" / "wire-new-capability.hook.json").read_text(encoding="utf-8")


def test_example_hook_is_an_inert_template_excluded_from_output(tmp_path):
    pkg = copy_package(tmp_path)
    claude_out = tmp_path / "claude"
    assert run_assemble_at(pkg, "claude-code", claude_out).returncode == 0

    names = {hook["name"] for hook in json.loads((claude_out / ".claude" / "hooks.json").read_text(encoding="utf-8"))}
    assert "{{Example Hook}}" not in names
    assert names == {"Wire New Capability", "Wire Capability On Agent Write", "Capability Wiring Audit"}


def test_assembler_emits_hooks_for_claude_but_not_kiro_cli(tmp_path):
    pkg = copy_package(tmp_path)
    kiro_cli_out = tmp_path / "kiro-cli"
    claude_out = tmp_path / "claude"

    assert run_assemble_at(pkg, "kiro-cli", kiro_cli_out).returncode == 0
    assert run_assemble_at(pkg, "claude-code", claude_out).returncode == 0

    assert not (kiro_cli_out / "hooks").exists()
    hooks_json = json.loads((claude_out / ".claude" / "hooks.json").read_text(encoding="utf-8"))
    assert {hook["name"] for hook in hooks_json} >= {"Wire New Capability", "Capability Wiring Audit"}


def test_ci_entrypoint_lists_all_gate_stages():
    text = (ROOT / "build" / "ci.py").read_text(encoding="utf-8")

    for expected in [
        "context/scripts/validate-wiring.py",
        "guards/check-tool-contract.py",
        "guards/check-cli-references.py",
        "pytest",
        "build/assemble.py",
        "generic",
        "build/validate_targets.py",
        "target-aware validation",
    ]:
        assert expected in text
