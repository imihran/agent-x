import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSEMBLE = ROOT / "build" / "assemble.py"

IDENTITY_MARKER = "# Identity & Shared Behavior"
DOMAIN_MARKER = "# Domain — {{DOMAIN_NAME}}"
ROUTING_MARKER = "# Routing — Core Gate, Precedence & Escalation"
GUARDRAIL_MARKER = "# No Fabrication — Never Invent, Confirm the Ambiguous"
KNOWLEDGE_MARKER = "# Known Silent Failures"
CONVENTION_MARKER = "# Authoring Conventions"


def run_assemble(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ASSEMBLE), *args],
        capture_output=True,
        text=True,
    )


def copy_package(tmp_path: Path) -> Path:
    """A private copy of the package so a test's manifest edits never touch
    the real working tree."""
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git"))
    return dest


def run_assemble_at(pkg_root: Path, *args: str) -> subprocess.CompletedProcess:
    assemble = pkg_root / "build" / "assemble.py"
    return subprocess.run(
        [sys.executable, str(assemble), *args],
        capture_output=True,
        text=True,
    )


def set_manifest(pkg_root: Path, **fields) -> None:
    manifest_path = pkg_root / "agent.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(fields)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_assembled_prompt_contains_both_partials_in_numeric_order_exactly_once(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--out", str(out_dir))

    assert result.returncode == 0
    prompt = (out_dir / "system-prompt.txt").read_text(encoding="utf-8")
    assert prompt.count(IDENTITY_MARKER) == 1
    assert prompt.count(DOMAIN_MARKER) == 1
    assert prompt.index(IDENTITY_MARKER) < prompt.index(DOMAIN_MARKER)


def test_assembled_prompt_includes_eager_tier_content_with_source_comments(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--out", str(out_dir))

    assert result.returncode == 0
    prompt = (out_dir / "system-prompt.txt").read_text(encoding="utf-8")
    assert ROUTING_MARKER in prompt
    assert GUARDRAIL_MARKER in prompt
    assert KNOWLEDGE_MARKER in prompt
    assert CONVENTION_MARKER in prompt
    assert "<!-- context/routing/00-core.md -->" in prompt
    assert "<!-- context/guardrails/no-fabrication.md -->" in prompt
    assert "<!-- context/knowledge/known-silent-failures.md -->" in prompt
    assert "<!-- context/conventions/authoring-conventions.md -->" in prompt


def test_prompt_partials_appear_exactly_once_alongside_eager_tiers(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--out", str(out_dir))

    assert result.returncode == 0
    prompt = (out_dir / "system-prompt.txt").read_text(encoding="utf-8")
    assert prompt.count(IDENTITY_MARKER) == 1
    assert prompt.count(DOMAIN_MARKER) == 1
    assert prompt.count(ROUTING_MARKER) == 1
    assert prompt.count(GUARDRAIL_MARKER) == 1


def test_context_globs_matching_prompt_partial_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, contextGlobs=["prompt/*"])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--out", str(out_dir))

    assert result.returncode != 0
    assert "prompt" in result.stderr
    assert not (out_dir / "system-prompt.txt").exists()
