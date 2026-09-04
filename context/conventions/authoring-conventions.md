# Authoring Conventions

Team conventions for composing and presenting work products. These are quality
practices, not safety rules — mandatory safety rules live in
`context/guardrails/`.

## Cite your sources

When you compose an artifact by adapting existing material, include a header
comment listing which sources informed each part, so users can trace the logic
and update it when sources change.

## Prefer recently updated sources

When multiple existing artifacts could serve as a starting point, prefer the
most recently maintained one — it is most likely to reflect current reality.

## Strip non-applicable boilerplate

When adapting a template or prior artifact, evaluate every structural element
against the new purpose. Scheduling metadata, environment-specific headers, and
sampling limits from the source usually do not apply — flag them rather than
silently copying them.

## Flag stale parameters

Hardcoded dates, identifiers, and unresolved placeholders inherited from a
source artifact silently produce wrong results. Flag them before use.

## Present results cleanly

Present tabular results as formatted tables (first N rows) with any relevant
timing or provenance info.
