# Agent X

Agent capability package template. Built on the modular capability framework: every capability is explicitly wired, and a validator proves the wiring. A file on disk does nothing until it is wired in.

Agent X is a codename. Keep user-facing names configurable until the final name is chosen.

To run the agent: `agent-x` — assemble the primary Kiro target with:

    python3 build/assemble.py --target kiro

The full rebuild specification is preserved at:

    docs/spec/rebuild-spec.md

## Architecture

    agent-x/
    ├── agent.manifest.json
    ├── wiring.config.json
    ├── build/
    │   └── assemble.py
    ├── context/
    │   ├── prompt/
    │   │   ├── 00-identity.md
    │   │   └── 10-domain-template.md
    │   ├── routing/
    │   │   ├── 00-core.md
    │   │   └── 10-domain-template.md
    │   ├── guardrails/
    │   │   ├── no-fabrication.md
    │   │   ├── evidence-gate.md
    │   │   ├── confirm-before-execute.md
    │   │   ├── verify-before-assert.md
    │   │   ├── tool-surface-discipline.md
    │   │   ├── self-report-honesty.md
    │   │   └── scope-boundaries.md
    │   ├── knowledge/
    │   │   ├── known-silent-failures.md
    │   │   └── domain-glossary.md
    │   ├── conventions/
    │   │   └── authoring-conventions.md
    │   ├── prompts/
    │   └── scripts/
    │       ├── validate-wiring.py
    │       ├── preflight.py
    │       └── discover.py
    ├── skills/ (4)
    │   ├── session-feedback/
    │   ├── escalation-handoff/
    │   ├── demo-skill/
    │   └── example-skill/
    ├── sops/
    ├── agents/
    ├── unattended/
    ├── tool/
    │   └── toolkit/
    │       ├── toolkit.py
    │       └── README.md
    ├── hooks/
    ├── guards/
    │   ├── check-tool-contract.py
    │   └── check-cli-references.py
    ├── tests/
    └── docs/
        ├── progress/PROJECT_PROGRESS.md
        └── spec/rebuild-spec.md

## Declared skills (3)

| Skill | What it does |
|---|---|
| `session-feedback` | Honest session retrospective with root-cause tags |
| `escalation-handoff` | Structured handoff when the agent hits a wall |
| `demo-skill` | Wiring-loop demonstration — replace with your first real skill |

One more directory, `example-skill/`, is an intentionally undeclared template. It is counted in the `skills/ (4)` directory count above but never activated.

## Guardrails

no-fabrication · evidence-gate · confirm-before-execute · verify-before-assert · tool-surface-discipline · self-report-honesty · scope-boundaries

## Validation

Run the source-tree validation gate:

    python3 context/scripts/validate-wiring.py --strict
    python3 guards/check-tool-contract.py
    python3 guards/check-cli-references.py
    python3 -m pytest tests/ -q

On hosts that fire no hook events, running the validator directly is the primary enforcement path. Run it before every commit that touches `skills/`, `context/`, `sops/`, `agent.manifest.json`, or `wiring.config.json`.

## Build targets

Primary target: Kiro

    python3 build/assemble.py --target kiro

Secondary target: Claude Code

    python3 build/assemble.py --target claude-code

Portable fallback target:

    python3 build/assemble.py --target generic

## Wiring a new capability

Follow the rebuild spec's capability wiring procedure in `docs/spec/rebuild-spec.md`. The validator is the authority for whether the capability is actually wired.
