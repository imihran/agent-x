import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "build" / "validate_targets.py"

sys.path.insert(0, str(ROOT / "build"))
import validate_targets  # noqa: E402

MANIFEST = json.loads((ROOT / "agent.manifest.json").read_text(encoding="utf-8"))


def run_validate_at(pkg_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(pkg_root / "build" / "validate_targets.py")],
        cwd=pkg_root, capture_output=True, text=True,
    )


def copy_package(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(
        ".git", "dist", ".kiro", ".pytest_cache", "__pycache__"))
    return dest


# --------------------------------------------------------------------------
# End-to-end: the real package must validate clean, and the <assembly>
# backstop must fire when a declared capability is missing from the SOURCE.
# --------------------------------------------------------------------------

def test_real_package_validates_clean_for_both_targets(tmp_path):
    pkg = copy_package(tmp_path)
    result = run_validate_at(pkg)
    assert result.returncode == 0, result.stdout + result.stderr


def test_validation_fails_when_a_declared_skill_dir_is_missing(tmp_path):
    pkg = copy_package(tmp_path)
    shutil.rmtree(pkg / "skills" / "demo-skill")
    result = run_validate_at(pkg)
    assert result.returncode == 1
    assert "demo-skill" in result.stdout


def test_validation_fails_when_a_declared_subagent_is_missing(tmp_path):
    pkg = copy_package(tmp_path)
    (pkg / "agents" / "readonly-investigator.agent.json").unlink()
    result = run_validate_at(pkg)
    assert result.returncode == 1
    assert "readonly-investigator" in result.stdout


# --------------------------------------------------------------------------
# Per-path backstop: drive check_claude / check_kiro against a MUTATED
# assembled OUTPUT (capability assembles fine but lands wrong / is missing).
# `validate_targets.failures` is a module global — clear it per test.
# --------------------------------------------------------------------------

def _assemble(target: str, tmp_path: Path) -> Path:
    out = tmp_path / target
    validate_targets.failures.clear()
    validate_targets.assemble(target, out)
    assert not validate_targets.failures, validate_targets.failures
    return out


def test_check_claude_flags_wrong_agent_frontmatter_name(tmp_path):
    out = _assemble("claude-code", tmp_path)
    agent_md = out / ".claude" / "agents" / f"{MANIFEST['name']}.md"
    text = agent_md.read_text(encoding="utf-8")
    agent_md.write_text(
        text.replace(f"name: {MANIFEST['name']}", "name: wrong-name", 1),
        encoding="utf-8")

    validate_targets.failures.clear()
    validate_targets.check_claude(MANIFEST, out)

    hits = [f for f in validate_targets.failures if "claude-code agent" in f]
    assert hits, validate_targets.failures
    assert any("discovery" in f for f in hits)


def test_check_claude_flags_missing_emitted_rule_file(tmp_path):
    out = _assemble("claude-code", tmp_path)
    rules = sorted((out / ".claude" / "rules").glob("*.md"))
    assert rules
    victim = rules[0]  # e.g. conventions-authoring-conventions.md
    victim.unlink()

    validate_targets.failures.clear()
    validate_targets.check_claude(MANIFEST, out)

    assert any(victim.name in f and "claude-code" in f
               for f in validate_targets.failures), validate_targets.failures


def test_check_kiro_flags_missing_emitted_subagent(tmp_path):
    out = _assemble("kiro-cli", tmp_path)
    (out / "agents" / "readonly-investigator.json").unlink()

    validate_targets.failures.clear()
    validate_targets.check_kiro(MANIFEST, out)

    assert any("readonly-investigator" in f and "kiro-cli" in f
               for f in validate_targets.failures), validate_targets.failures


def test_check_kiro_flags_missing_emitted_steering_file(tmp_path):
    out = _assemble("kiro-cli", tmp_path)
    steering = sorted((out / "steering").glob("*-*.md"))
    assert steering
    victim = steering[0]
    victim.unlink()

    validate_targets.failures.clear()
    validate_targets.check_kiro(MANIFEST, out)

    assert any(victim.name in f and "kiro-cli" in f
               for f in validate_targets.failures), validate_targets.failures


def test_check_claude_flags_default_agent_setting_disagreement(tmp_path):
    out = _assemble("claude-code", tmp_path)
    # opt in to the default agent, but the emitted settings.json does not
    # carry the matching "agent" key -> the coherence check must fire.
    (out / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    manifest = dict(MANIFEST, claudeSettings={"defaultAgent": True})

    validate_targets.failures.clear()
    validate_targets.check_claude(manifest, out)

    assert any("settings" in f and "defaultAgent" in f
               for f in validate_targets.failures), validate_targets.failures


def test_check_claude_flags_residual_source_citation_in_emitted_file(tmp_path):
    out = _assemble("claude-code", tmp_path)
    # reintroduce a bare source citation token into an emitted rule file
    victim = out / ".claude" / "rules" / "guardrails-no-fabrication.md"
    text = victim.read_text(encoding="utf-8")
    victim.write_text(
        text + "\nSee context/guardrails/evidence-gate.md for the gate.\n",
        encoding="utf-8")

    validate_targets.failures.clear()
    validate_targets.check_claude(MANIFEST, out)

    assert any("residual-citation" in f and "evidence-gate" in f
               for f in validate_targets.failures), validate_targets.failures


def test_check_claude_clean_output_has_no_residual_citation_finding(tmp_path):
    out = _assemble("claude-code", tmp_path)
    validate_targets.failures.clear()
    validate_targets.check_claude(MANIFEST, out)
    assert not any("residual-citation" in f for f in validate_targets.failures), \
        validate_targets.failures


def test_check_claude_passes_when_default_agent_opt_in_is_honored(tmp_path):
    out = _assemble("claude-code", tmp_path)
    (out / ".claude" / "settings.json").write_text(
        json.dumps({"agent": MANIFEST["name"]}), encoding="utf-8")
    manifest = dict(MANIFEST, claudeSettings={"defaultAgent": True})

    validate_targets.failures.clear()
    validate_targets.check_claude(manifest, out)

    assert not any("settings" in f for f in validate_targets.failures), \
        validate_targets.failures
