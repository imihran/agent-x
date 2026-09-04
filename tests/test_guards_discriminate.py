"""Task 10 — Anti-drift guard discrimination tests (README Section 17.2/17.3).

The guards-discriminate doctrine (17.3): for every guard, prove it actually
discriminates — introduce the drift it exists to catch and assert exit 1
with a named finding; break its input and assert exit 2 (never a silent
pass). Each test also asks "what would have to break for this to fail?" —
neutralizing the guard's comparison logic must make the corresponding drift
test fail, which the mutation tests below demonstrate directly rather than
assuming.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_CONTRACT_GUARD = ROOT / "guards" / "check-tool-contract.py"
CLI_REFERENCES_GUARD = ROOT / "guards" / "check-cli-references.py"


def copy_package(tmp_path: Path) -> Path:
    """A private copy of the package so a test's edits never touch the
    real working tree."""
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git"))
    return dest


def run_guard_at(pkg_root: Path, guard_relpath: str) -> subprocess.CompletedProcess:
    guard = pkg_root / guard_relpath
    return subprocess.run(
        [sys.executable, str(guard)],
        capture_output=True,
        text=True,
    )


def edit_toolkit_readme_table(pkg_root: Path, transform) -> None:
    readme = pkg_root / "tool" / "toolkit" / "README.md"
    lines = readme.read_text(encoding="utf-8").splitlines()
    readme.write_text("\n".join(transform(lines)) + "\n", encoding="utf-8")


# ── check-tool-contract.py — agreement baseline ──────────────────────────

def test_tool_contract_agrees_on_unmodified_package(tmp_path):
    pkg = copy_package(tmp_path)
    result = run_guard_at(pkg, "guards/check-tool-contract.py")
    assert result.returncode == 0
    assert "TOOL CONTRACT: AGREE" in result.stdout


# ── check-tool-contract.py — drift (exit 1, named finding) ──────────────

def test_tool_contract_phantom_command_is_drift(tmp_path):
    pkg = copy_package(tmp_path)
    edit_toolkit_readme_table(
        pkg, lambda lines: lines + ["| ghost-cmd | no |"]
    )

    result = run_guard_at(pkg, "guards/check-tool-contract.py")

    assert result.returncode == 1
    assert "PHANTOM" in result.stdout
    assert "ghost-cmd" in result.stdout
    assert "TOOL CONTRACT: DRIFT" in result.stdout


def test_tool_contract_missing_command_is_drift(tmp_path):
    pkg = copy_package(tmp_path)
    edit_toolkit_readme_table(
        pkg, lambda lines: [l for l in lines if not l.strip().startswith("| authcheck")]
    )

    result = run_guard_at(pkg, "guards/check-tool-contract.py")

    assert result.returncode == 1
    assert "MISSING" in result.stdout
    assert "authcheck" in result.stdout
    assert "TOOL CONTRACT: DRIFT" in result.stdout


def test_tool_contract_underspecified_write_flag_is_drift(tmp_path):
    pkg = copy_package(tmp_path)
    edit_toolkit_readme_table(
        pkg,
        lambda lines: [
            "| create | no |" if l.strip() == "| create | yes |" else l
            for l in lines
        ],
    )

    result = run_guard_at(pkg, "guards/check-tool-contract.py")

    assert result.returncode == 1
    assert "UNDERSPECIFIED" in result.stdout
    assert "create" in result.stdout
    assert "TOOL CONTRACT: DRIFT" in result.stdout


# ── check-tool-contract.py — unverifiable (exit 2, never 0 or 1) ────────

def test_tool_contract_missing_toolkit_script_is_unverifiable(tmp_path):
    pkg = copy_package(tmp_path)
    (pkg / "tool" / "toolkit" / "toolkit.py").unlink()

    result = run_guard_at(pkg, "guards/check-tool-contract.py")

    assert result.returncode == 2
    assert "UNVERIFIABLE" in result.stdout


def test_tool_contract_missing_readme_is_unverifiable(tmp_path):
    pkg = copy_package(tmp_path)
    (pkg / "tool" / "toolkit" / "README.md").unlink()

    result = run_guard_at(pkg, "guards/check-tool-contract.py")

    assert result.returncode == 2
    assert "UNVERIFIABLE" in result.stdout


def test_tool_contract_corrupt_discover_output_is_unverifiable(tmp_path):
    """Breaking the live side's output shape (not just its presence) must
    also fall through to exit 2, never a false AGREE/DRIFT."""
    pkg = copy_package(tmp_path)
    toolkit_py = pkg / "tool" / "toolkit" / "toolkit.py"
    text = toolkit_py.read_text(encoding="utf-8")
    # Make `discover` print non-JSON instead of the surface inventory.
    broken = text.replace(
        'def cmd_discover(_: argparse.Namespace) -> int:',
        'def cmd_discover(_: argparse.Namespace) -> int:\n'
        '    print("not json")\n'
        '    return 0\n'
        'def _unused_original_cmd_discover(_: argparse.Namespace) -> int:',
        1,
    )
    assert broken != text, "expected to patch cmd_discover"
    toolkit_py.write_text(broken, encoding="utf-8")

    result = run_guard_at(pkg, "guards/check-tool-contract.py")

    assert result.returncode == 2
    assert "UNVERIFIABLE" in result.stdout


# ── check-tool-contract.py — mutation proves the comparison is load-bearing

def test_tool_contract_neutralized_comparison_hides_phantom_drift(tmp_path):
    """Prove the drift test above is not vacuous: if the guard's own
    drift-detection is neutralized (comparison replaced with an
    unconditional agree), the SAME phantom-drift fixture that exit-1s
    against the real guard must exit 0 against the neutralized one —
    demonstrating the real guard's exit 1 actually comes from the
    comparison, not from something else."""
    pkg = copy_package(tmp_path)
    edit_toolkit_readme_table(
        pkg, lambda lines: lines + ["| ghost-cmd | no |"]
    )

    guard_path = pkg / "guards" / "check-tool-contract.py"
    text = guard_path.read_text(encoding="utf-8")
    neutralized = text.replace(
        "    if drift:\n"
        '        print(f"TOOL CONTRACT: DRIFT — {drift} finding(s)")\n'
        "        return 1\n",
        "    if False:\n"
        '        print(f"TOOL CONTRACT: DRIFT — {drift} finding(s)")\n'
        "        return 1\n",
        1,
    )
    assert neutralized != text, "expected to patch the drift branch"
    guard_path.write_text(neutralized, encoding="utf-8")

    result = run_guard_at(pkg, "guards/check-tool-contract.py")

    assert result.returncode == 0
    assert "TOOL CONTRACT: AGREE" in result.stdout


# ── check-cli-references.py — agreement baseline ─────────────────────────

def test_cli_references_agrees_on_unmodified_package(tmp_path):
    pkg = copy_package(tmp_path)
    result = run_guard_at(pkg, "guards/check-cli-references.py")
    assert result.returncode == 0
    assert "CLI REFERENCES: AGREE" in result.stdout


# ── check-cli-references.py — drift (exit 1, named finding) ─────────────

def test_cli_references_dead_command_reference_is_drift(tmp_path):
    pkg = copy_package(tmp_path)
    skill_md = pkg / "skills" / "example-skill" / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8") + "\n\nSee `toolkit ghost-cmd` for details.\n",
        encoding="utf-8",
    )

    result = run_guard_at(pkg, "guards/check-cli-references.py")

    assert result.returncode == 1
    assert "DRIFT" in result.stdout
    assert "ghost-cmd" in result.stdout
    assert "SKILL.md" in result.stdout
    assert "CLI REFERENCES: DRIFT" in result.stdout


def test_cli_references_ignores_unanchored_prose(tmp_path):
    """`toolkit is a demo` must not be mistaken for a reference to a
    subcommand named `is` — the pattern requires a backtick or `.py`
    anchor, exactly the false positive the guard's docstring calls out."""
    pkg = copy_package(tmp_path)
    skill_md = pkg / "skills" / "example-skill" / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8") + "\n\nthe toolkit is a demo tool.\n",
        encoding="utf-8",
    )

    result = run_guard_at(pkg, "guards/check-cli-references.py")

    assert result.returncode == 0
    assert "CLI REFERENCES: AGREE" in result.stdout


# ── check-cli-references.py — unverifiable (exit 2, never 0 or 1) ───────

def test_cli_references_missing_toolkit_module_is_unverifiable(tmp_path):
    pkg = copy_package(tmp_path)
    (pkg / "tool" / "toolkit" / "toolkit.py").unlink()

    result = run_guard_at(pkg, "guards/check-cli-references.py")

    assert result.returncode == 2
    assert "UNVERIFIABLE" in result.stdout


def test_cli_references_broken_parser_is_unverifiable(tmp_path):
    """Breaking build_parser() itself (not just deleting the file) must
    also fall through to exit 2."""
    pkg = copy_package(tmp_path)
    toolkit_py = pkg / "tool" / "toolkit" / "toolkit.py"
    text = toolkit_py.read_text(encoding="utf-8")
    broken = text.replace(
        "def build_parser() -> argparse.ArgumentParser:",
        "def build_parser() -> argparse.ArgumentParser:\n"
        "    raise RuntimeError('parser construction broken')",
        1,
    )
    assert broken != text, "expected to patch build_parser"
    toolkit_py.write_text(broken, encoding="utf-8")

    result = run_guard_at(pkg, "guards/check-cli-references.py")

    assert result.returncode == 2
    assert "UNVERIFIABLE" in result.stdout


# ── check-cli-references.py — mutation proves the comparison is load-bearing

def test_cli_references_neutralized_comparison_hides_dead_reference(tmp_path):
    """Same discrimination proof as the tool-contract guard: neutralize the
    drift branch and show the SAME dead-reference fixture that exit-1s
    against the real guard exits 0 against the neutralized one."""
    pkg = copy_package(tmp_path)
    skill_md = pkg / "skills" / "example-skill" / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8") + "\n\nSee `toolkit ghost-cmd` for details.\n",
        encoding="utf-8",
    )

    guard_path = pkg / "guards" / "check-cli-references.py"
    text = guard_path.read_text(encoding="utf-8")
    neutralized = text.replace(
        "    if drift:\n"
        '        print(f"CLI REFERENCES: DRIFT — {drift} finding(s)")\n'
        "        return 1\n",
        "    if False:\n"
        '        print(f"CLI REFERENCES: DRIFT — {drift} finding(s)")\n'
        "        return 1\n",
        1,
    )
    assert neutralized != text, "expected to patch the drift branch"
    guard_path.write_text(neutralized, encoding="utf-8")

    result = run_guard_at(pkg, "guards/check-cli-references.py")

    assert result.returncode == 0
    assert "CLI REFERENCES: AGREE" in result.stdout


# ── sanity: pattern regex used by the drift-detection helper is present ──

def test_cli_references_pattern_anchors_on_backtick_or_pydotpy():
    """Guards against a future edit accidentally loosening the anchor and
    reintroducing the `toolkit is` false positive the docstring warns about."""
    text = CLI_REFERENCES_GUARD.read_text(encoding="utf-8")
    pattern_match = re.search(r're\.compile\((.+?)\)', text)
    assert pattern_match, "expected a compiled regex literal in the guard"
    assert "`toolkit" in pattern_match.group(1)
    assert "toolkit\\.py" in pattern_match.group(1)
