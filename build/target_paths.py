#!/usr/bin/env python3
"""Path mapping for the claude-code target.

The source tree cites context files and SOPs by repo-relative path
(`context/guardrails/x.md`, `sops/y.sop.md`). The claude-code target emits
those under `.claude/`, so copied skill and SOP bodies need their citations
rewritten to the emitted locations. This module owns that map.

Stdlib only. Pure functions.
"""
from __future__ import annotations

from pathlib import Path

# context tiers that become .claude/rules/ files (prompt/ is never a rule —
# it loads via systemPromptIncludes into CLAUDE.md's prompt half)
_RULE_TIERS = ("routing", "guardrails", "knowledge", "conventions")


def rule_filename(context_relpath: str) -> str:
    """context-relative path -> .claude/rules/ filename.

    "guardrails/no-fabrication.md" -> "guardrails-no-fabrication.md".
    Mirrors target_kiro_cli's "-".join(parts) steering-file convention.
    """
    return "-".join(Path(context_relpath).parts)


def build_citation_map(context_dir: Path, sops_dir: Path) -> dict[str, str]:
    """Every rewritable citation token -> its emitted .claude/ path.

    Built from files actually on disk, so a token is only rewritten when its
    destination genuinely exists in the target.
    """
    mapping: dict[str, str] = {}
    for tier in _RULE_TIERS:
        tier_dir = context_dir / tier
        if not tier_dir.is_dir():
            continue
        for f in sorted(tier_dir.glob("*.md")):
            rel = f.relative_to(context_dir).as_posix()
            mapping[f"context/{rel}"] = f".claude/rules/{rule_filename(rel)}"
    if sops_dir.is_dir():
        for f in sorted(sops_dir.glob("*.sop.md")):
            mapping[f"sops/{f.name}"] = f".claude/sops/{f.name}"
    return mapping


def rewrite_citations(text: str, citation_map: dict[str, str]) -> str:
    """Replace each known citation token with its emitted path.

    Longest tokens first, so a token that is a prefix of a longer one never
    shadows it.
    """
    for token in sorted(citation_map, key=len, reverse=True):
        text = text.replace(token, citation_map[token])
    return text
