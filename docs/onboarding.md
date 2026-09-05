# Onboarding: How Development Works Here

Read this first if you're a new agent/session picking up work in `agent-x`
(or a personalized fork like `agent-x-mish`) — before touching code.

## 1. What this repo is

An agent capability package template: one `agent.manifest.json` declares
skills/SOPs/context, `build/assemble.py` turns that into per-host artifacts
(`claude-code`, `kiro-cli`, `generic`), and a wiring validator proves every
declared capability is actually reachable, not just present on disk. See
README's "How it works" section for the diagrammed version, and
`docs/spec/rebuild-spec.md` for the full architectural spec (the eight
design principles, the complete wiring rule set) if you're about to make a
structural change to `context/`, `skills/`, or the assembler.

## 2. Where to look for what

- **`README.md`** — quick start, architecture tree, build targets, forking a
  fork of this repo. Concise and operator-facing by design; don't bloat it.
- **`docs/spec/rebuild-spec.md`** — the full architectural spec. Read the
  relevant section before making a structural change; update the matching
  code listing if you change what it documents (see gotcha below).
- **`docs/sync-workflow.md`** — read this in full if you're working in a
  fork, or changing anything a fork depends on (`build/assemble.py`,
  `build/deploy.py`, the manifest schema).
- **`docs/progress/PROJECT_PROGRESS.md`** — the running state/history log.
  Update it after material work (repo state, what changed, what's next);
  don't treat it as instructions for *how* to work — that's this file.
- **`docs/superpowers/specs/`** and **`docs/superpowers/plans/`** — design
  and implementation records for specific larger efforts (e.g. the kiro-cli
  target migration). Read the relevant one before touching related code
  again; it usually explains *why*, not just *what*.

## 3. The core development loop

1. Before changing anything, confirm `python3 build/ci.py` is green on the
   current tree — that's your baseline.
2. Write the failing test first. This repo's own suite is TDD-disciplined
   (RED before GREEN) — `tests/test_assemble.py` and friends show the
   pattern: isolated `tmp_path` copies, real subprocess invocations, real
   file assertions, never mocks.
3. Implement the minimal fix.
4. Rerun the specific test, then the full `python3 build/ci.py` gate. Both
   must be green before you call anything done.
5. If you touched one of `build/assemble.py`'s target functions (or
   anything `docs/spec/rebuild-spec.md` documents as a code listing),
   update that listing to match. This repo has shipped real drift between
   the spec and the code before — don't add more of it.
6. Commit in small, single-concern steps; push after each. This matches
   the working convention already recorded in `docs/progress/
   PROJECT_PROGRESS.md`'s "User instructions / operating rules".
7. If the change is new tooling (not a bugfix), decide whether README needs
   a new section and whether `PROJECT_PROGRESS.md` needs a new entry.

## 4. Known gotchas (read before you rediscover them the hard way)

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

## 5. If you're working in a fork (e.g. `agent-x-mish`)

Read `docs/sync-workflow.md` in full before syncing (`python3
build/sync_template.py`) or making structural changes — it documents the
one-time bootstrap, the tool's step-by-step behavior, the recurring
`agent.manifest.json` conflict and exactly how to resolve it, and a worked
example citing real commit SHAs from an actual sync session.

## 6. Verifying you're actually done

"Tests pass" isn't the bar. This repo also has a wiring validator
(`python3 context/scripts/validate-wiring.py --strict`) that's the
authority on whether a new skill/SOP/guardrail is *reachable* — routed to,
declared, cited by path — not just sitting on disk. `python3 build/ci.py`
runs both the validator and the test suite together; that combined gate is
what "done" actually means here.
