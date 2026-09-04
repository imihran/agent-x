"""Task 8 — wiring-loop acceptance test.

Simulates an author creating a brand-new skill with ZERO wiring and fixing
one attachment point at a time. After each fix the validator's error
message must change (never the same failure surviving a fix, never a
premature PASS) until the final step reaches PASS. This is the demoable
proof that the validator can walk an author through wiring a capability
end to end, error by error (README Section 20, Task 8).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_package(tmp_path: Path) -> Path:
    """A private copy of the package so a test's manifest/skill/routing
    edits never touch the real working tree."""
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


def set_wiring_config(pkg_root: Path, **fields) -> None:
    config_path = pkg_root / "wiring.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.update(fields)
    config_path.write_text(json.dumps(config), encoding="utf-8")


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


def test_wiring_loop_walks_author_through_each_attachment_point_via_routing(tmp_path):
    """Zero-wiring skill -> SKILL.md missing -> bad frontmatter -> undeclared
    -> unrouted -> PASS, wiring the routing-row attachment point last."""
    pkg = copy_package(tmp_path)
    skill_dir = pkg / "skills" / "loop-skill"
    skill_dir.mkdir()

    # Stage 0: zero wiring — the directory exists but has no SKILL.md at all.
    result = run_validator_at(pkg, "--skill", "loop-skill")
    assert result.returncode == 1
    assert "ERROR skills/loop-skill" in result.stdout
    assert "no SKILL.md" in result.stdout
    previous_message = "no SKILL.md"

    # Stage 1: fix #1 — add SKILL.md, but its frontmatter is incomplete.
    (skill_dir / "SKILL.md").write_text(
        "---\nname: loop-skill\ntype: skill\nversion: 1.0\n---\n\n# loop-skill\n",
        encoding="utf-8",
    )
    result = run_validator_at(pkg, "--skill", "loop-skill")
    assert result.returncode == 1
    assert previous_message not in result.stdout
    assert "missing name and/or description" in result.stdout
    previous_message = "missing name and/or description"

    # Stage 2: fix #2 — complete the frontmatter, but the skill is not
    # declared in the manifest yet.
    (skill_dir / "SKILL.md").write_text(
        skill_md(
            "loop-skill",
            "A skill wired one attachment point at a time by the acceptance test.",
        ),
        encoding="utf-8",
    )
    result = run_validator_at(pkg, "--skill", "loop-skill")
    assert result.returncode == 1
    assert previous_message not in result.stdout
    assert "not declared in manifest skillNames" in result.stdout
    previous_message = "not declared in manifest skillNames"

    # Stage 3: fix #3 — declare it in the manifest, but no routing row
    # mentions it and it is not registered always-on.
    set_manifest(pkg, skillNames=["loop-skill"])
    result = run_validator_at(pkg, "--skill", "loop-skill")
    assert result.returncode == 1
    assert previous_message not in result.stdout
    assert "nothing will ever route to it" in result.stdout
    previous_message = "nothing will ever route to it"

    # Stage 4: fix #4 — add a routing row. Every prior failure message is
    # gone and the validator reaches PASS.
    (pkg / "context" / "routing" / "10-domain-template.md").write_text(
        '| User signal / intent | Activate skill |\n'
        '|---|---|\n'
        '| "wire the loop" | `loop-skill` |\n',
        encoding="utf-8",
    )
    result = run_validator_at(pkg, "--skill", "loop-skill")
    assert previous_message not in result.stdout
    assert "ERROR" not in result.stdout
    assert "WIRING VALIDATION: PASS" in result.stdout
    assert result.returncode == 0


def test_wiring_loop_reaches_pass_via_always_on_prompt_invocation(tmp_path):
    """Same starting point, but the final attachment point is registering
    the skill always-on and invoking it from a prompt partial instead of
    adding a routing row — the validator's other accepted path for check #6."""
    pkg = copy_package(tmp_path)
    skill_dir = pkg / "skills" / "always-on-loop-skill"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        skill_md(
            "always-on-loop-skill",
            "An always-on skill wired one attachment point at a time by the acceptance test.",
        ),
        encoding="utf-8",
    )

    # Stage 0: declared nowhere yet.
    result = run_validator_at(pkg, "--skill", "always-on-loop-skill")
    assert result.returncode == 1
    assert "not declared in manifest skillNames" in result.stdout
    previous_message = "not declared in manifest skillNames"

    # Stage 1: fix #1 — declare in the manifest and register always-on, but
    # no prompt partial invokes it yet.
    set_manifest(pkg, skillNames=["always-on-loop-skill"])
    set_wiring_config(pkg, alwaysOnSkills=["always-on-loop-skill"])
    result = run_validator_at(pkg, "--skill", "always-on-loop-skill")
    assert result.returncode == 1
    assert previous_message not in result.stdout
    assert "always-on skill but no prompt partial invokes it" in result.stdout
    previous_message = "always-on skill but no prompt partial invokes it"

    # Stage 2: fix #2 — a prompt partial invokes it by name. PASS.
    (pkg / "context" / "prompt" / "20-loop-startup.md").write_text(
        "# Startup\n\nInvoke always-on-loop-skill.\n", encoding="utf-8"
    )
    result = run_validator_at(pkg, "--skill", "always-on-loop-skill")
    assert previous_message not in result.stdout
    assert "ERROR" not in result.stdout
    assert "WIRING VALIDATION: PASS" in result.stdout
    assert result.returncode == 0
