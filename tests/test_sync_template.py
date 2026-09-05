import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "build" / "sync_template.py"


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=path, check=True)


def add_remote(fork: Path, name: str, target: Path) -> None:
    subprocess.run(["git", "remote", "add", name, str(target)], cwd=fork, check=True)


def bootstrap_merge(fork: Path, remote: str = "template", branch: str = "main") -> None:
    subprocess.run(["git", "fetch", remote], cwd=fork, check=True, capture_output=True)
    subprocess.run(
        ["git", "merge", f"{remote}/{branch}", "--allow-unrelated-histories", "-m", "bootstrap"],
        cwd=fork, check=True, capture_output=True,
    )


def make_minimal_repo(tmp_path: Path, name: str) -> Path:
    """A minimal repo containing just the sync script itself — mirrors how
    the rest of this suite invokes a script from inside a copied package;
    sync_template.py resolves its own ROOT from __file__, so it needs its
    own copy on disk."""
    repo = tmp_path / name
    init_repo(repo)
    (repo / "build").mkdir(parents=True)
    shutil.copy(SYNC_SCRIPT, repo / "build" / "sync_template.py")
    # Identical content across independently-initialized repos, so the
    # --allow-unrelated-histories bootstrap merge in tests has nothing to
    # conflict on — only later, deliberately-diverging edits should conflict.
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    commit_all(repo, "Initial commit")
    return repo


def run_sync(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "build" / "sync_template.py"), *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_sync_fails_when_working_tree_dirty(tmp_path):
    fork = make_minimal_repo(tmp_path, "fork")
    (fork / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")

    result = run_sync(fork, "--no-test")

    assert result.returncode != 0
    assert "dirty" in result.stderr.lower()


def test_sync_fails_when_remote_missing(tmp_path):
    fork = make_minimal_repo(tmp_path, "fork")

    result = run_sync(fork, "--no-test")

    assert result.returncode != 0
    assert "template" in result.stderr
    assert "git remote add" in result.stderr


def test_sync_reports_up_to_date_when_no_new_commits(tmp_path):
    template = make_minimal_repo(tmp_path, "template")
    fork = make_minimal_repo(tmp_path, "fork")
    add_remote(fork, "template", template)
    bootstrap_merge(fork)

    result = run_sync(fork, "--no-test")

    assert result.returncode == 0, result.stderr
    assert "Already up to date" in result.stdout


def test_sync_merges_new_commits_from_template(tmp_path):
    template = make_minimal_repo(tmp_path, "template")
    fork = make_minimal_repo(tmp_path, "fork")
    add_remote(fork, "template", template)
    bootstrap_merge(fork)

    (template / "NEW_FEATURE.md").write_text("new feature\n", encoding="utf-8")
    commit_all(template, "Add new feature")

    result = run_sync(fork, "--no-test")

    assert result.returncode == 0, result.stderr
    assert (fork / "NEW_FEATURE.md").is_file()
    assert "1 new commit" in result.stdout


def test_sync_reports_conflicts_without_auto_resolving(tmp_path):
    template = make_minimal_repo(tmp_path, "template")
    fork = make_minimal_repo(tmp_path, "fork")
    add_remote(fork, "template", template)
    bootstrap_merge(fork)

    (template / "README.md").write_text("# template changed\n", encoding="utf-8")
    commit_all(template, "template edits README")
    (fork / "README.md").write_text("# fork changed\n", encoding="utf-8")
    commit_all(fork, "fork edits README")

    result = run_sync(fork, "--no-test")

    assert result.returncode != 0
    assert "README.md" in (result.stdout + result.stderr)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=fork, capture_output=True, text=True)
    assert "README.md" in status.stdout  # left mid-conflict, not auto-committed


def make_repo_with_stub_ci(tmp_path: Path, name: str, ci_exit_code: int) -> Path:
    """A minimal repo with a lightweight stand-in build/ci.py, so the
    integration point (sync_template.py invokes build/ci.py and reacts to
    its exit code) is tested in isolation — invoking the REAL build/ci.py
    here would recursively re-run this whole test suite from inside the
    copy, since it runs pytest over its own tests/ directory."""
    repo = make_minimal_repo(tmp_path, name)
    label = "PASS" if ci_exit_code == 0 else "FAIL"
    (repo / "build" / "ci.py").write_text(
        f"import sys\nprint('STUB CI GATE: {label}')\nsys.exit({ci_exit_code})\n",
        encoding="utf-8",
    )
    commit_all(repo, "Add stub ci.py")
    return repo


def test_sync_runs_ci_gate_after_merge(tmp_path):
    template = make_repo_with_stub_ci(tmp_path, "template", ci_exit_code=0)
    fork = tmp_path / "fork"
    shutil.copytree(template, fork)  # shares history directly — no bootstrap needed
    (template / "NEW_FEATURE.md").write_text("new feature\n", encoding="utf-8")
    commit_all(template, "Add new feature")
    add_remote(fork, "template", template)

    result = run_sync(fork)  # no --no-test — build/ci.py should actually run

    assert result.returncode == 0, result.stdout + result.stderr
    assert (fork / "NEW_FEATURE.md").is_file()
    assert "STUB CI GATE: PASS" in result.stdout


def test_sync_fails_loudly_when_ci_gate_fails_after_merge(tmp_path):
    template = make_repo_with_stub_ci(tmp_path, "template", ci_exit_code=1)
    fork = tmp_path / "fork"
    shutil.copytree(template, fork)
    (template / "BREAKING_CHANGE.md").write_text("oops\n", encoding="utf-8")
    commit_all(template, "Add breaking change")
    add_remote(fork, "template", template)

    result = run_sync(fork)

    assert result.returncode != 0
    assert "STUB CI GATE: FAIL" in result.stdout
    assert "build/ci.py failed" in result.stderr
    # The merge itself is already committed locally, even though CI failed
    # afterward — documented behavior, so the user can `git reset --hard
    # HEAD~1` to back out or fix forward.
    log = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=fork, capture_output=True, text=True)
    assert log.stdout.strip() == "Sync from template/main"
