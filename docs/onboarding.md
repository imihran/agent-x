# Onboarding: How Development Works Here

Read this first if you're a new agent/session picking up work here — before
touching code. This file is itself a template artifact: it lives in
`agent-x` and reaches every fork via `build/sync_template.py`, so it's
written to make sense whichever repo you're actually sitting in.

## 1. Which repo am I in?

Check `agent.manifest.json`'s `"name"` field:

```bash
grep '"name"' agent.manifest.json
```

- **`"agent-x"`** → you're in the template. Go to §2a.
- **Anything else** (`"agent-x-mish"`, `"agent-x-john"`, or any other
  personalized name) → you're in a fork. Go to §2b.

Forks are created by linking a `template` git remote back to `agent-x` and
merging its history in (see `docs/sync-workflow.md`) — the mechanism is
identical no matter what the fork is named or who owns it.

### 2a. Developing the template (`agent-x`)

You're changing shared framework code that every fork inherits. Extra care
applies:

- Keep it generic — **no Mish-specific (or anyone-specific) content**: no
  personal skills, no hardcoded personal paths, no real hostnames/credentials.
  That belongs in a fork, never here.
- A behavior or schema change here (the manifest shape, `build/assemble.py`'s
  target functions, `build/deploy.py`'s mappings) is a change every fork will
  merge in later — think about whether it's likely to conflict with the kind
  of personalization a fork makes (see the `agent.manifest.json` conflict
  pattern in `docs/sync-workflow.md`) and whether that's acceptable.
- `docs/progress/FORK_NOTES.md` stays a placeholder here — never add real
  entries to it in this repo. It's the one file forks can edit without ever
  hitting a sync conflict, and that only works because the template commits
  it once and never touches it again.
- Otherwise, follow the core development loop in §3 like any other change.

### 2b. Developing a fork (`agent-x-mish`, `agent-x-john`, ...)

You're personalizing a clone. In addition to §3's core loop:

- Record *your own* fork-specific history in `docs/progress/FORK_NOTES.md`
  — not `docs/progress/PROJECT_PROGRESS.md`, which describes the template's
  work and keeps arriving from `agent-x` via sync (your edits to it would
  eventually collide with template updates to the same living sections).
  `FORK_NOTES.md` is yours alone; the template never writes to it again
  after the placeholder, so it never conflicts.
- After every `python3 build/sync_template.py`, re-check the
  manifest-name test-coupling gotcha in §4 — a sync can bring in new tests
  that hardcode the template's own name against the real manifest.
- Fork-local skills (things specific to you, not the template) live under
  `skills/` same as any other skill — wire them the normal way
  (`skillNames`, a routing row, `SKILL.md`) and they'll survive future
  syncs untouched as long as the template never creates a skill with the
  same name.
- Read `docs/sync-workflow.md` in full before your first sync if you
  haven't already — bootstrap, the tool's behavior, the recurring
  `agent.manifest.json` conflict and how to resolve it, a real worked
  example.

## 3. What this repo is

An agent capability package template: one `agent.manifest.json` declares
skills/SOPs/context, `build/assemble.py` turns that into per-host artifacts
(`claude-code`, `kiro-cli`, `generic`), and a wiring validator proves every
declared capability is actually reachable, not just present on disk. See
README's "How it works" section for the diagrammed version, and
`docs/spec/rebuild-spec.md` for the full architectural spec (the eight
design principles, the complete wiring rule set) if you're about to make a
structural change to `context/`, `skills/`, or the assembler.

## 4. Where to look for what

- **`README.md`** — quick start, architecture tree, build targets, forking.
  Concise and operator-facing by design; don't bloat it.
- **`docs/spec/rebuild-spec.md`** — the full architectural spec. Read the
  relevant section before making a structural change; update the matching
  code listing if you change what it documents (see gotcha below).
- **`docs/sync-workflow.md`** — the fork-sync mechanics: bootstrap, the
  sync tool, the manifest conflict pattern, a worked example.
- **`docs/progress/PROJECT_PROGRESS.md`** — the template's own running
  state/history log. In a fork, this describes `agent-x`'s work (arrives
  via sync), not yours — see §2b.
- **`docs/progress/FORK_NOTES.md`** — a fork's own running log of its own
  history. Placeholder in the template; see §2a/§2b.
- **`docs/superpowers/specs/`** and **`docs/superpowers/plans/`** — design
  and implementation records for specific larger efforts (e.g. the kiro-cli
  target migration). Read the relevant one before touching related code
  again; it usually explains *why*, not just *what*.

## 5. The core development loop

1. Before changing anything, confirm `python3 build/ci.py` is green on the
   current tree — that's your baseline.
2. If the change adds or ports a skill, decide its shape first — what it
   costs in the eager tiers vs. what stays lazy — per
   `sops/wire-new-capability.sop.md` step 2 and `docs/spec/rebuild-spec.md`
   §8.7.
3. Write the failing test first. This repo's own suite is TDD-disciplined
   (RED before GREEN) — `tests/test_assemble.py` and friends show the
   pattern: isolated `tmp_path` copies, real subprocess invocations, real
   file assertions, never mocks.
4. Implement the minimal fix.
5. Rerun the specific test, then the full `python3 build/ci.py` gate. Both
   must be green before you call anything done.
6. If you touched one of `build/assemble.py`'s target functions (or
   anything `docs/spec/rebuild-spec.md` documents as a code listing),
   update that listing to match. This repo has shipped real drift between
   the spec and the code before — don't add more of it.
7. Commit in small, single-concern steps; push after each. This matches
   the working convention already recorded in
   `docs/progress/PROJECT_PROGRESS.md`'s "User instructions / operating
   rules".
8. If the change is new tooling (not a bugfix), decide whether README needs
   a new section and whether your progress log (`PROJECT_PROGRESS.md` in
   the template, `FORK_NOTES.md` in a fork) needs a new entry.

## 6. Known gotchas (read before you rediscover them the hard way)

- **Manifest-name test coupling.** Several tests assert the real repo's own
  `agent.manifest.json` name literally (e.g. `agents/agent-x.json`,
  `payload["agent"] == "agent-x"`). A personalized fork must update these
  to its own name after every sync that touches those test files — see
  `docs/sync-workflow.md`'s "Known follow-up" section for the exact
  grep-and-fix procedure.
- **`build/assemble.py` used to leave stale files in `dist/<target>/`
  across runs** (fixed — it now `rmtree`s its own output dir first, same
  as `build/deploy.py` already did for `.kiro/`). If you ever see a
  phantom file, or an agent that shouldn't exist in `kiro-cli agent list`,
  `rm -rf dist .kiro` and rebuild before assuming something is actually
  wired wrong.
- **Two different "Kiro" products exist**: the Kiro GUI editor and
  `kiro-cli`, a separate terminal tool. This repo targets `kiro-cli` only.
  See `docs/superpowers/specs/2026-09-04-kiro-cli-target-migration-design.md`
  for the full story of how that distinction was originally missed, and
  what was empirically verified about `kiro-cli`'s actual behavior (some of
  it contradicts its own hosted docs).
- **`docs/spec/rebuild-spec.md`'s embedded code listings can drift from the
  real code.** Some drift is pre-existing and explicitly out of scope (see
  the design doc above); new drift you personally introduce should be
  fixed, not left for the next session.

## 7. Verifying you're actually done

"Tests pass" isn't the bar. This repo also has a wiring validator
(`python3 context/scripts/validate-wiring.py --strict`) that's the
authority on whether a new skill/SOP/guardrail is *reachable* — routed to,
declared, cited by path — not just sitting on disk. `python3 build/ci.py`
runs both the validator and the test suite together; that combined gate is
what "done" actually means here.
