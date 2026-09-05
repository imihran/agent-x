# Agent X

Agent capability package template. Built on the modular capability framework: every capability is explicitly wired, and a validator proves the wiring. A file on disk does nothing until it is wired in.

Agent X is a codename. Keep user-facing names configurable until the final name is chosen.

## Quick start

1. Clone the repo.
2. Deploy the Kiro runtime files into the workspace root:

       python3 build/deploy.py

3. Open the repo folder in Kiro, or ask it from the CLI:

       python3 build/kiro_agent.py --agent . --prompt "What agent are you?"

The full rebuild specification is preserved at:

    docs/spec/rebuild-spec.md

## Architecture

    agent-x/
    ├── agent.manifest.json
    ├── wiring.config.json
    ├── build/
    │   ├── assemble.py
    │   ├── ci.py
    │   ├── deploy.py
    │   └── kiro_agent.py
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
    │   │   └── readonly-investigator.md
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
    │   ├── wire-new-capability.sop.md
    │   ├── adversarial-review.sop.md
    │   └── example.sop.md
    ├── agents/
    │   ├── readonly-investigator.agent.json
    │   └── registry.local.json.example
    ├── unattended/
    │   ├── README.md
    │   ├── jobs.template.json
    │   └── policy.template.json
    ├── tool/
    │   └── toolkit/
    │       ├── toolkit.py
    │       └── README.md
    ├── hooks/
    │   ├── wire-new-capability.hook.json
    │   ├── wire-on-agent-write.hook.json
    │   └── wiring-audit.hook.json
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

Or run the canonical local CI gate:

    python3 build/ci.py

On hosts that fire no hook events, running the validator directly is the primary enforcement path. Run it before every commit that touches `skills/`, `context/`, `sops/`, `agent.manifest.json`, or `wiring.config.json`.

## Build targets

Primary target: Kiro

    python3 build/assemble.py --target kiro

To make Kiro actually load Agent X in this workspace, deploy generated files into `.kiro/`:

    python3 build/deploy.py

For repeatable Kiro CLI testing and agent switching, use the launcher:

    python3 build/kiro_agent.py --agent . --prompt "Run the demo skill" --dry-run
    python3 build/kiro_agent.py --agent . --prompt "Run the demo skill"

To switch agents, pass another agent package path or an alias from `agents/registry.local.json`:

    cp agents/registry.local.json.example agents/registry.local.json
    python3 build/kiro_agent.py --agent /path/to/other-agent --prompt "Smoke test"

The launcher deploys the selected agent into `<workspace-root>/.kiro/` and launches Kiro from that workspace root, because Kiro loads agent config from the workspace `.kiro/` directory.

Secondary target: Claude Code

    python3 build/assemble.py --target claude-code

Portable fallback target:

    python3 build/assemble.py --target generic

## Wiring a new capability

Follow the rebuild spec's capability wiring procedure in `docs/spec/rebuild-spec.md`. The validator is the authority for whether the capability is actually wired.
