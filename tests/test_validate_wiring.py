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


def skill_md(name: str, description: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "type: skill\n"
        f"description: {description}\n"
        "version: 1.0\n"
        "---\n\n"
        f"# {name}\n"
    )


def write_skill(pkg_root: Path, skill_name: str, content: str) -> None:
    skill_dir = pkg_root / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


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


def test_skill_missing_skill_md_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    (pkg / "skills" / "no-contract").mkdir()
    set_manifest(pkg, skillNames=["no-contract"])

    result = run_validator_at(pkg, "--skill", "no-contract")

    assert "ERROR skills/no-contract" in result.stdout
    assert "no SKILL.md" in result.stdout
    assert result.returncode == 1


def test_skill_frontmatter_name_mismatch_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    write_skill(
        pkg, "mismatched-skill",
        skill_md("wrong-name",
                  "A skill whose frontmatter name does not match its own directory name."),
    )
    set_manifest(pkg, skillNames=["mismatched-skill"])

    result = run_validator_at(pkg, "--skill", "mismatched-skill")

    assert "ERROR skills/mismatched-skill" in result.stdout
    assert "!= directory" in result.stdout
    assert result.returncode == 1


def test_skill_missing_description_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    content = "---\nname: no-desc\ntype: skill\nversion: 1.0\n---\n\n# No Desc\n"
    write_skill(pkg, "no-desc", content)
    set_manifest(pkg, skillNames=["no-desc"])

    result = run_validator_at(pkg, "--skill", "no-desc")

    assert "ERROR skills/no-desc" in result.stdout
    assert "missing name and/or description" in result.stdout
    assert result.returncode == 1


def test_skill_short_description_warns(tmp_path):
    pkg = copy_package(tmp_path)
    write_skill(pkg, "short-desc", skill_md("short-desc", "Too short."))
    set_manifest(pkg, skillNames=["short-desc"])

    result = run_validator_at(pkg, "--skill", "short-desc")

    assert "WARN" in result.stdout
    assert "skills/short-desc" in result.stdout
    assert "too thin to route" in result.stdout
    assert result.returncode == 0


def test_skill_undeclared_and_not_allowlisted_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    write_skill(
        pkg, "rogue-skill",
        skill_md("rogue-skill",
                  "A skill that exists on disk but is never declared in the manifest."),
    )

    result = run_validator_at(pkg, "--skill", "rogue-skill")

    assert "ERROR skills/rogue-skill" in result.stdout
    assert "not declared in manifest skillNames" in result.stdout
    assert result.returncode == 1


def write_prompt_partial(pkg_root: Path, filename: str, content: str) -> None:
    prompt_dir = pkg_root / "context" / "prompt"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / filename).write_text(content, encoding="utf-8")


def test_missing_prompt_include_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, systemPromptIncludes=[
        "context/prompt/00-identity.md",
        "context/prompt/99-ghost.md",
    ])

    result = run_validator_at(pkg)

    assert "ERROR systemPromptIncludes:context/prompt/99-ghost.md" in result.stdout
    assert "missing on disk" in result.stdout
    assert result.returncode == 1


def test_unsorted_prompt_includes_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, systemPromptIncludes=[
        "context/prompt/10-domain-template.md",
        "context/prompt/00-identity.md",
    ])

    result = run_validator_at(pkg)

    assert "ERROR systemPromptIncludes:" in result.stdout
    assert "not sorted by numeric prefix" in result.stdout
    assert result.returncode == 1


def test_unincluded_prompt_partial_is_error(tmp_path):
    pkg = copy_package(tmp_path)
    write_prompt_partial(pkg, "20-extra.md", "# Extra\n\nAn unincluded partial.\n")

    result = run_validator_at(pkg)

    assert "ERROR prompt/20-extra.md" in result.stdout
    assert "not in systemPromptIncludes" in result.stdout
    assert result.returncode == 1


def test_example_skill_passes_via_allowlist(tmp_path):
    pkg = copy_package(tmp_path)

    result = run_validator_at(pkg, "--skill", "example-skill")

    assert "skills/example-skill" not in result.stdout
    assert "WIRING VALIDATION: PASS" in result.stdout
    assert result.returncode == 0
