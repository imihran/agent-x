#!/usr/bin/env python3
"""Sync this fork with its upstream template.

Any agent-x-style package can be forked (agent-x-mish is one example) by
adding a remote that points at the template repo — conventionally named
`template` — then merging its history in once with
`git merge --allow-unrelated-histories`. After that one-time link, this
script does the ongoing sync: fetch the template remote, merge in whatever
is new, run the CI gate to confirm nothing broke, and report the result.

Never pushes — review the merge yourself, then push when ready.

Usage:
    python3 build/sync_template.py [--remote template] [--branch main] [--no-test]

Stdlib only.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"SYNC ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="template", help="Git remote pointing at the upstream template repo. Default: template.")
    parser.add_argument("--branch", default="main", help="Branch to sync from the remote. Default: main.")
    parser.add_argument("--no-test", action="store_true", help="Skip running build/ci.py after a successful merge.")
    args = parser.parse_args(argv)

    status = run("git", "status", "--porcelain")
    if status.stdout.strip():
        fail("working tree is dirty — commit or stash your changes before syncing")

    remotes = run("git", "remote").stdout.split()
    if args.remote not in remotes:
        fail(
            f"no remote named {args.remote!r}. Add one pointing at the upstream "
            f"template repo first: git remote add {args.remote} <template-repo-url>"
        )

    print(f"Fetching {args.remote}...")
    fetch = run("git", "fetch", args.remote)
    if fetch.returncode != 0:
        fail(f"git fetch {args.remote} failed:\n{fetch.stderr}")

    remote_ref = f"{args.remote}/{args.branch}"
    ahead = run("git", "log", f"HEAD..{remote_ref}", "--oneline")
    if not ahead.stdout.strip():
        print(f"Already up to date with {remote_ref}. Nothing to sync.")
        return 0

    new_commits = ahead.stdout.strip().splitlines()
    print(f"{len(new_commits)} new commit(s) on {remote_ref}:")
    for line in new_commits:
        print(f"  {line}")

    print(f"Merging {remote_ref}...")
    merge = run("git", "merge", "--no-ff", remote_ref, "-m", f"Sync from {remote_ref}")
    if merge.returncode != 0:
        combined = merge.stdout + merge.stderr
        if "refusing to merge unrelated histories" in combined:
            print("First-time sync detected — retrying with --allow-unrelated-histories.")
            merge = run("git", "merge", "--no-ff", remote_ref, "--allow-unrelated-histories", "-m", f"Sync from {remote_ref}")
        if merge.returncode != 0:
            print(merge.stdout)
            print(merge.stderr, file=sys.stderr)
            conflicts = run("git", "diff", "--name-only", "--diff-filter=U")
            if conflicts.stdout.strip():
                print("\nConflicts in:")
                for path in conflicts.stdout.strip().splitlines():
                    print(f"  {path}")
                print("\nResolve them, then: git add <files> && git commit")
            fail(f"merge with {remote_ref} did not complete cleanly — resolve manually")

    print("Merge complete.")

    if args.no_test:
        print("Skipping build/ci.py (--no-test). Review the merge, then `git push` when ready.")
        return 0

    print("Running build/ci.py to verify nothing broke...")
    ci = subprocess.run([sys.executable, "build/ci.py"], cwd=ROOT)
    if ci.returncode != 0:
        fail(
            "merge succeeded but build/ci.py failed — the sync brought in "
            "something that doesn't pass here. The merge is already committed "
            "locally; `git reset --hard HEAD~1` undoes it if you want to back "
            "out, or fix forward and commit before pushing."
        )

    print("Sync complete and verified. Review the changes, then: git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
