#!/usr/bin/env python3
"""Validate that every capability in this package is completely wired up.

A skill or guardrail file on disk does nothing on its own. Each one has to be
attached at several points before an agent will load and route to it. This
script asserts those attachments exist, so a half-wired capability fails
loudly instead of sitting inert.

Task 1 scope: manifest/config loading, the exit-2 structural floor
(no skills/ directory), and check #17 (missing routing/00-core.md).
Task 2 scope adds the declared-but-missing checks: skills #7, SOPs #11,
and README-advertised agents #14. Task 3 scope adds the skill contract
checks #1-#5 (every skills/<dir>/ has a valid, declared SKILL.md).
Task 4 scope adds checks #15-16 (every systemPromptIncludes entry exists
on disk and is sorted by numeric prefix; every on-disk context/prompt/*.md
partial is included). Task 5 scope adds check #6: every declared skill must
be routed or registered always-on and invoked from a prompt partial. Task 6
scope adds checks #8-10: every guardrail on disk must be in the identity
partial's always-in-effect list (#8, ERROR), cited from some partial, routing
file, or skill (#9, WARN), and listed in README.md (#10, WARN). Task 12 scope
adds check #13: the README's `skills/ (N)` count must match the number of
directories on disk under skills/. Later rebuild tasks add the remaining
checks described in README.md Section 17.1.

Severities:
  ERROR  behavioral wiring — the capability will not load or will never be
         routed to. Exits non-zero.
  WARN   documentation drift — behavior is fine, docs are stale. Exits zero
         unless --strict is passed.

Usage:
    python3 context/scripts/validate-wiring.py [--strict] [--skill NAME]

Stdlib only. Run from anywhere; paths resolve relative to this file.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SKILLS_DIR = ROOT / "skills"
GUARDRAILS_DIR = ROOT / "context" / "guardrails"
ROUTING_DIR = ROOT / "context" / "routing"
PROMPT_DIR = ROOT / "context" / "prompt"
IDENTITY_PARTIAL = PROMPT_DIR / "00-identity.md"
SOPS_DIR = ROOT / "sops"
AGENTS_DIR = ROOT / "agents"
MANIFEST = ROOT / "agent.manifest.json"
WIRING_CONFIG = ROOT / "wiring.config.json"
README = ROOT / "README.md"

findings: list[tuple[str, str, str]] = []  # (severity, subject, message)


def error(subject: str, message: str) -> None:
    findings.append(("ERROR", subject, message))


def warn(subject: str, message: str) -> None:
    findings.append(("WARN", subject, message))


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        error(str(path.relative_to(ROOT)), f"unreadable: {exc}")
        return ""


def load_json(path: Path) -> dict | None:
    """None = missing or invalid (caller decides severity). A valid empty
    document `{}` is returned as-is — it is a real document, not an error;
    conflating the two once misreported an empty manifest as unreadable."""
    if not path.is_file():
        return None
    try:
        return json.loads(read(path))
    except json.JSONDecodeError as exc:
        error(path.name, f"invalid JSON: {exc}")
        return None


_readme_memo: list[str | None] = []


def readme_text_or_none() -> str | None:
    """README-dependent checks are documentation-axis (WARN tier). A
    missing README is reported ONCE as drift — the rebuild sequence
    legitimately runs the validator before the README task — and each
    dependent check is skipped, not fired vacuously against empty text."""
    if not _readme_memo:
        if README.is_file():
            _readme_memo.append(read(README))
        else:
            warn("README.md", "missing — README documentation checks skipped")
            _readme_memo.append(None)
    return _readme_memo[0]


def parse_frontmatter(text: str) -> dict[str, str]:
    """Minimal YAML frontmatter reader — flat `key: value` pairs only."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def concat(paths: list[Path]) -> str:
    return "\n".join(read(p) for p in paths)


def mentions(text: str, name: str) -> bool:
    """Whole-token mention: `name` must not be embedded in a longer
    hyphenated identifier. Bare substring matching would let a skill named
    `demo` count as routed merely because `demo-skill` appears."""
    return re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text) is not None


def check_skill_contract(manifest: dict, cfg: dict, only: str | None) -> None:
    """Checks #1-5: every skills/<dir>/ has a SKILL.md; its frontmatter
    has name + description; name is byte-identical to the directory name;
    a short description warns; and the skill is declared in the manifest's
    skillNames unless it is an intentionally undeclared template listed in
    wiring.config.json's undeclaredSkillAllowlist. Check #6 (routing
    mention) needs the routing tier and lands in Task 5."""
    declared = set(manifest.get("skillNames", []))
    undeclared_ok = set(cfg.get("undeclaredSkillAllowlist", {}))
    on_disk = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir()) \
        if SKILLS_DIR.is_dir() else []

    for skill in on_disk:
        if only and skill != only:
            continue
        subject = f"skills/{skill}"

        if skill in undeclared_ok:
            if not (SKILLS_DIR / skill / "SKILL.md").is_file():
                warn(subject, "allowlisted template has no SKILL.md")
            continue

        skill_md = SKILLS_DIR / skill / "SKILL.md"
        if not skill_md.is_file():
            error(subject, "no SKILL.md — the directory will never load")
            continue

        fm = parse_frontmatter(read(skill_md))
        if not fm or not fm.get("name") or not fm.get("description"):
            error(subject, "SKILL.md frontmatter missing name and/or description")
        else:
            if fm.get("name") != skill:
                error(subject,
                      f"frontmatter name {fm.get('name')!r} != directory "
                      f"name {skill!r} — activation looks up by name")
            desc = fm.get("description", "")
            if len(desc) < 40:
                warn(subject, f"description is only {len(desc)} chars; "
                              "too thin to route on reliably")

        if skill not in declared:
            error(subject, "not declared in manifest skillNames — "
                           "it can never be activated")


def check_declared_skills(manifest: dict, only: str | None) -> None:
    """Check #7: a skill declared in manifest skillNames must exist on
    disk — a typo or a deleted directory otherwise points at nothing."""
    declared = set(manifest.get("skillNames", []))
    on_disk = {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()} \
        if SKILLS_DIR.is_dir() else set()
    for skill in sorted(declared):
        if only and skill != only:
            continue
        if skill not in on_disk:
            error(f"skillNames:{skill}",
                  f"declared in the manifest but skills/{skill}/ does not exist")


def check_skill_routing(manifest: dict, cfg: dict, only: str | None) -> None:
    """Check #6: a declared skill must be reachable. It is reachable when
    mentioned in context/routing/*.md, or when registered in alwaysOnSkills
    and invoked by a prompt partial. Allowlisted template skills are inert and
    intentionally skipped."""
    declared = set(manifest.get("skillNames", []))
    always_on = set(cfg.get("alwaysOnSkills", []))
    undeclared_ok = set(cfg.get("undeclaredSkillAllowlist", {}))
    routing_text = concat(sorted(ROUTING_DIR.glob("*.md")))
    prompt_text = concat(sorted(PROMPT_DIR.glob("*.md")))

    for skill in sorted(declared - undeclared_ok):
        if only and skill != only:
            continue
        if skill in always_on:
            if not mentions(prompt_text, skill):
                error(f"skills/{skill}",
                      "always-on skill but no prompt partial invokes it — "
                      "it will never activate")
        elif not mentions(routing_text, skill):
            error(f"skills/{skill}",
                  "no mention in context/routing/*.md — nothing will ever route to it")


def check_guardrails(cfg: dict, only: str | None) -> None:
    """Checks #8-10: every guardrail on disk must be declared in the
    identity partial's always-in-effect list (#8, ERROR — that list is the
    single mandatory declaration); cited from some partial, routing file, or
    skill (#9, WARN — it loads via glob regardless, but nothing points at it
    from the point of use); and listed in README.md (#10, WARN —
    documentation drift). guardrailReferenceAllowlist entries in
    wiring.config.json skip all three checks for that guardrail."""
    if only:
        return
    if not GUARDRAILS_DIR.is_dir():
        error("context/guardrails",
              "directory missing — every always-in-effect guardrail is "
              "gone; a vacuous pass here would hide that")
        return
    identity_text = read(IDENTITY_PARTIAL)
    citing_text = concat(
        sorted(PROMPT_DIR.glob("*.md"))
        + sorted(ROUTING_DIR.glob("*.md"))
        + sorted(SKILLS_DIR.glob("*/SKILL.md")))
    readme_text = readme_text_or_none()
    exempt = set(cfg.get("guardrailReferenceAllowlist", {}))

    for path in sorted(GUARDRAILS_DIR.glob("*.md")):
        stem = path.stem
        subject = f"guardrails/{stem}"
        if stem in exempt:
            continue
        if not mentions(identity_text, stem):
            error(subject, "not in the always-in-effect list in "
                           "context/prompt/00-identity.md — the single "
                           "mandatory declaration is missing")
        if not mentions(citing_text, stem):
            warn(subject, "not cited by any partial, routing file, or skill — "
                          "loaded but never pointed at from the point of use")
        if readme_text is not None and not mentions(readme_text, stem):
            warn(subject, "not listed in README.md")


def check_declared_sops(manifest: dict, only: str | None) -> None:
    """Check #11: a SOP declared in manifest sopNames must exist on disk."""
    if only:
        return
    declared = set(manifest.get("sopNames", []))
    on_disk = {p.name.removesuffix(".sop.md") for p in SOPS_DIR.glob("*.sop.md")} \
        if SOPS_DIR.is_dir() else set()
    for sop in sorted(declared - on_disk):
        error(f"sopNames:{sop}",
              f"declared in the manifest but sops/{sop}.sop.md does not exist")


def check_readme_agents(manifest: dict, only: str | None) -> None:
    """Check #14: every agent name the README advertises must have a
    manifest on disk — either this package's own manifest or a subagent
    under agents/*.agent.json."""
    if only:
        return
    readme_text = readme_text_or_none()
    if readme_text is None:
        return
    known = {manifest.get("name", "")}
    if AGENTS_DIR.is_dir():
        for p in AGENTS_DIR.glob("*.agent.json"):
            known.add((load_json(p) or {}).get("name", p.stem))
    for m in re.finditer(r"run the agent[: ]+`([a-z0-9-]+)`", readme_text):
        name = m.group(1)
        if name not in known:
            error(f"README:{name}",
                  "README advertises an agent with no manifest on disk")


def check_readme_skill_count(only: str | None) -> None:
    """Check #13: README's skills/ (N) count must match directories on disk."""
    if only:
        return
    readme_text = readme_text_or_none()
    if readme_text is None:
        return
    match = re.search(r"skills/\s*\((\d+)\)", readme_text)
    if not match:
        warn("README.md", "no skills/(N) count found")
        return
    stated = int(match.group(1))
    actual = len([p for p in SKILLS_DIR.iterdir() if p.is_dir()]) if SKILLS_DIR.is_dir() else 0
    if stated != actual:
        warn("README.md", f"says skills/ ({stated}); found {actual} on disk")


def check_prompt_includes(manifest: dict, only: str | None) -> None:
    """Checks #15-16: every systemPromptIncludes entry must exist on disk
    and the list must be sorted by numeric filename prefix (#15) — the
    order IS the assembled prompt order; and every on-disk
    context/prompt/*.md partial must appear in that list (#16) — partials
    are in no glob, so an unincluded one never loads."""
    if only:
        return
    includes = manifest.get("systemPromptIncludes", [])
    for rel in includes:
        if not (ROOT / rel).is_file():
            error(f"systemPromptIncludes:{rel}",
                  "listed in the manifest but missing on disk — "
                  "assembly will hard-error")
    prefixes = [int(m.group(1)) for rel in includes
                if (m := re.match(r"(\d+)", Path(rel).name))]
    if prefixes != sorted(prefixes):
        error("systemPromptIncludes",
              "not sorted by numeric prefix — assembled prompt order "
              "would not match the documented order")
    included = {Path(rel).name for rel in includes}
    if PROMPT_DIR.is_dir():
        for p in sorted(PROMPT_DIR.glob("*.md")):
            if p.name not in included:
                error(f"prompt/{p.name}",
                      "partial on disk but not in systemPromptIncludes — "
                      "partials are in no glob, so it will never load")


def check_routing_core(only: str | None) -> None:
    """Check #17: routing/00-core.md is the sole dispatch authority."""
    if only:
        return
    if not (ROUTING_DIR / "00-core.md").is_file():
        error("routing/00-core.md",
              "missing — the routing core gate is the sole dispatch "
              "authority; without it nothing routes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    parser.add_argument("--skill", metavar="NAME", help="check one skill only")
    args = parser.parse_args()

    if not SKILLS_DIR.is_dir():
        print(f"FAIL — no skills/ directory under {ROOT}", file=sys.stderr)
        return 2
    if args.skill and not (SKILLS_DIR / args.skill).is_dir():
        print(f"FAIL — skills/{args.skill}/ does not exist", file=sys.stderr)
        return 2

    manifest = load_json(MANIFEST)
    if manifest is None:
        error("agent.manifest.json", "missing or unreadable — nothing can be wired")
        manifest = {}
    cfg = load_json(WIRING_CONFIG) or {}

    check_skill_contract(manifest, cfg, args.skill)
    check_declared_skills(manifest, args.skill)
    check_skill_routing(manifest, cfg, args.skill)
    check_guardrails(cfg, args.skill)
    check_declared_sops(manifest, args.skill)
    check_readme_agents(manifest, args.skill)
    check_readme_skill_count(args.skill)
    check_prompt_includes(manifest, args.skill)
    check_routing_core(args.skill)

    errors = [f for f in findings if f[0] == "ERROR"]
    warnings = [f for f in findings if f[0] == "WARN"]
    for severity, subject, message in errors + warnings:
        print(f"{severity:5} {subject}: {message}")

    scope = f"skill {args.skill}" if args.skill else "all capabilities"
    if errors:
        print(f"\nWIRING VALIDATION: FAIL ({scope}) — "
              f"{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    if warnings and args.strict:
        print(f"\nWIRING VALIDATION: FAIL ({scope}) — "
              f"{len(warnings)} warning(s), --strict")
        return 1
    if warnings:
        print(f"\nWIRING VALIDATION: PASS ({scope}) — "
              f"{len(warnings)} warning(s), no errors")
        return 0
    print(f"WIRING VALIDATION: PASS ({scope}) — fully wired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
