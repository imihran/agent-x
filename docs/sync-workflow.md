# Template Sync Workflow

How a fork of this template (e.g. `agent-x-mish`) stays connected to it and
pulls in future updates. This is an operational guide — read it before
touching `build/sync_template.py` or helping someone set up a new fork.

---

## Concepts

- **Template** — the upstream repo (`agent-x`). Owns shared framework code
  (`build/`, `context/`, the wiring validator, guardrails) and evolves
  independently of any fork.
- **Fork** — a clone that personalizes the template: its own
  `agent.manifest.json` `name`, its own skills, its own identity/domain
  prompt content. `agent-x-mish` is the running example throughout this doc.
- **The `template` remote** — the *only* thing that connects a fork back to
  its template. It's a plain git remote, conventionally named `template`,
  pointing at the template repo's URL. Nothing else links them — no
  submodule, no package manager, no CI dependency.
- Fork-local content (a personalized manifest field, a fork-only skill) and
  template updates (a bug fix, a new guardrail) are expected to coexist.
  Sometimes they touch the same line and conflict — that's normal git
  behavior, not a tooling failure, and this doc shows exactly what that
  looks like and how to resolve it.

---

## One-time setup: linking a new fork to its template

Do this once, right after creating the fork (cloning the template repo under
a new name/remote, or starting from an empty repo and merging the template
in — either way, the fork needs its own git history *before* this step).

```bash
cd <fork-root>
git remote add template <template-repo-url>
git fetch template
git merge template/main --allow-unrelated-histories -m "Import <template-name> as starting point"
```

`--allow-unrelated-histories` is required exactly once, here — it's the only
merge where the fork's history and the template's history have no common
ancestor. Every sync after this point is a normal merge (`build/sync_template.py`
retries with the flag automatically if it ever detects this situation, but
that should only fire on a truly fresh fork that skipped this step).

After the merge, personalize what needs personalizing — at minimum,
`agent.manifest.json`'s `"name"` field, since the template's own tests
assert the *real* repo's manifest name in a few places (see "Known
conflict: agent.manifest.json" below for exactly which ones, and why).

**Worked example** (this repo, `agent-x-mish`, 2026-09-04):

```bash
git remote add template https://github.com/imihran/agent-x.git
git fetch template
git merge template/main --allow-unrelated-histories -m "Import agent-x template as starting point for agent-x-mish"
```

Then renamed `agent.manifest.json`'s `"name"` from `"agent-x"` to
`"agent-x-mish"`, which broke 5 tests that hardcoded `"agent-x"` against the
real manifest (not test fixtures) — fixed by updating those literal strings
to `"agent-x-mish"` in `tests/test_assemble.py`, `tests/test_deploy.py`, and
`tests/test_kiro_agent_runner.py`. `python3 build/ci.py` must be green
before committing the personalization.

---

## Ongoing sync: `build/sync_template.py`

Once linked, pull future template updates any time with:

```bash
python3 build/sync_template.py
```

What it does, in order:

1. **Refuses on a dirty working tree.** Commit or stash first — the script
   never touches uncommitted work.
2. **Refuses if the `template` remote doesn't exist**, with the exact
   command to add it.
3. **`git fetch template`.**
4. **Reports and exits 0 if there's nothing new** (`git log HEAD..template/main`
   is empty) — safe to run speculatively any time.
5. **Merges with `--no-ff`** — always creates a real merge commit
   (`Sync from template/main`), even when a fast-forward would be possible,
   so every sync leaves a visible point in history. Falls back to
   `--allow-unrelated-histories` automatically if it detects that error
   (only relevant if step "One-time setup" above was skipped).
6. **On conflict: stops, lists the conflicted files, does not auto-resolve.**
   Resolve manually (see below), then `git add <files> && git commit` to
   finish the merge the script started.
7. **On a clean merge: runs `python3 build/ci.py`.** If CI fails, the merge
   is still sitting there as a local commit — either
   `git reset --hard HEAD~1` to back out, or fix forward and commit.
8. **Never pushes.** Review the result, then `git push` yourself.

Flags: `--remote <name>` (default `template`), `--branch <name>` (default
`main`), `--no-test` (skip step 7, e.g. if `build/ci.py` doesn't exist yet in
a very early fork).

---

## Recording your own fork's history without ever conflicting

`docs/progress/PROJECT_PROGRESS.md` is the *template's* running log — it
keeps arriving via sync and describes `agent-x`'s own work, not your fork's.
If a fork edits it to record fork-specific history, that edit will
eventually collide with a template update to the same living sections
(same failure mode as `agent.manifest.json`, just harder to predict).

Use `docs/progress/FORK_NOTES.md` instead. The template commits it once as
a placeholder and never touches it again — specifically so a fork can write
whatever it wants there without ever hitting a sync conflict. See
`docs/onboarding.md` §2b for what belongs in it.

---

## Known conflict: `agent.manifest.json`

The single most likely conflict, because both sides legitimately touch the
same small block at the top of the file:

- The fork personalizes `"name"`.
- The template adds fields (it added `"version"`, and later the
  `"claudeSettings": { "defaultAgent": false }` block for the native
  Claude Code target) or changes `"description"`/`"welcomeMessage"` defaults.

**Resolution:** always keep the fork's `"name"` (and its own
`"welcomeMessage"` / identity), take everything else — `"version"`,
`"claudeSettings"`, any other new additive block — from whichever side
actually changed it. Concretely, a conflict looks like:

```json
{
  "schemaVersion": "1",
<<<<<<< HEAD
  "name": "agent-x-mish",
=======
  "name": "agent-x",
  "version": "0.1.0",
>>>>>>> template/main
  "description": "",
```

Resolve by hand-editing to keep both intents:

```json
{
  "schemaVersion": "1",
  "name": "agent-x-mish",
  "version": "0.1.0",
  "description": "",
```

Then:

```bash
git add agent.manifest.json
git commit --no-edit
python3 build/ci.py
```

If CI fails after resolving, check for the same class of issue described
next.

## Known follow-up: hardcoded manifest-name assertions in tests

A handful of tests assert against the **real, current repo's own manifest**
(not an isolated fixture) — they check things like
`out_dir / "agents" / "agent-x.json"` or `payload["agent"] == "agent-x"`.
These are legitimate in the template repo (where the name really is
`agent-x`), but a personalized fork will see them fail after any merge that
touches those test files, because the literal string still says `agent-x`
instead of the fork's own name.

**Fix:** find and update the literal name string in the affected test(s) to
match the fork's manifest name, then rerun `python3 build/ci.py`. This is
expected maintenance for a personalized fork, not a bug — grep for the
fork's *old* incorrect assumption, e.g.:

```bash
grep -rn '"agent-x"' tests/
```

and judge each hit: a hardcoded check against the real repo's own output
needs updating; a check inside a test that explicitly sets its own fixture
manifest (`set_manifest(pkg, name="something-else")`) does not.

---

## Worked example: this session's full test (2026-09-05)

Real commits, both repos, showing the fork-local-addition-plus-template-update
scenario end to end.

**1. Caught `agent-x-mish` up to a `agent-x` baseline it didn't have yet**
(manual merge — the fork didn't have `sync_template.py` yet at this point):

```
agent-x-mish: 3ccc833 Sync from template/main   (hit the manifest conflict above, resolved by hand)
agent-x-mish: 0392448 fix: personalize welcome-message tests brought in by the template sync
```

**2. Added fork-local content** — `agent-x-mish` only:

```
agent-x-mish: eaae165 feat: add mish-notes, a fork-local personal skill
```

A properly-wired skill (`skills/mish-notes/SKILL.md`, a `skillNames` entry,
a routing row in `context/routing/10-domain-template.md`), live-verified to
activate correctly via the real installed `kiro-cli` before being committed.

**3. Added a template-side update** — `agent-x` only, unrelated file:

```
agent-x: 3c43f33 fix: clean each target's output dir before reassembling
```

A real bug fix in `build/assemble.py` (it never cleaned `dist/<target>/`
between runs, so renaming an agent left stale per-name files behind that
`build/deploy.py` then faithfully copied into `.kiro/` too — this is
*literally* the bug that caused a phantom `agent-x` entry to show up in
`agent-x-mish`'s own `kiro-cli agent list` earlier in the same session).
Written test-first: a failing test reproduced the exact scenario (assemble
twice into the same `--out` dir, once as `agent-x`, once renamed — assert
the stale file is gone), confirmed RED, then GREEN after the fix.

**4. Ran the actual sync** — `agent-x-mish`, using the real script this time:

```bash
python3 build/sync_template.py
```

Result: **clean merge, no conflict** (this update touched `build/assemble.py`
and its tests — files `agent-x-mish` had never modified), `build/ci.py` ran
automatically and passed, script printed "Sync complete and verified" and
stopped short of pushing:

```
agent-x-mish: 3ca20ad Sync from template/main
```

**Verified after sync:** `skills/mish-notes/` untouched, the assemble.py fix
present (`grep -n "if out.exists" build/assemble.py`), manifest `"name"`
still `"agent-x-mish"` — fork-local content and the template update coexist
correctly in the same tree. Then `git push`.

This demonstrates both paths the tool needs to handle: a manual bootstrap
merge that legitimately conflicts (step 1, because both sides touch
`agent.manifest.json`'s top block), and an automated ongoing sync that
merges cleanly with zero manual intervention (step 4, because the update
happened to land in files the fork never touched). Expect the real ratio
over time to skew toward step 4's shape — conflicts are the exception,
triggered specifically by both sides editing the same lines.

---

## Troubleshooting

- **A stale/phantom agent shows up in `kiro-cli agent list`** that doesn't
  match the current manifest name: almost certainly leftover files in
  `dist/` from before `build/assemble.py`'s output-dir cleaning fix
  (commit `3c43f33`, template and any fork that has synced past it).
  `rm -rf dist .kiro && python3 build/deploy.py` clears it.
- **`build/ci.py` fails right after a sync** with test failures naming a
  literal `agent-x` string: see "Known follow-up" above.
- **Merge conflict outside `agent.manifest.json`**: same manual-resolve
  procedure — edit to keep both intents, `git add`, `git commit --no-edit`,
  rerun `python3 build/ci.py` before pushing.
