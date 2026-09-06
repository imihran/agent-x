#!/usr/bin/env python3
"""Assemble the agent package into per-host artifacts.

Usage:
    python3 build/assemble.py --target claude-code|kiro-cli|generic [--out DIR]

Reads agent.manifest.json, resolves systemPromptIncludes in listed order,
expands contextGlobs (erroring if any glob matches a prompt/ partial),
copies declared skills and declared SOPs (skills and hooks cite SOPs by
path), and emits the target's artifact layout under dist/<target>/.

Stdlib only. Deterministic: same inputs, byte-identical outputs.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import target_paths  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "context"
SKILLS = ROOT / "skills"
SOPS = ROOT / "sops"
HOOKS = ROOT / "hooks"
AGENTS = ROOT / "agents"

TARGETS = ("claude-code", "kiro-cli", "generic")

WRITE_VERBS = {"write", "edit", "delete", "create", "update", "patch"}


def fail(msg: str) -> None:
    print(f"ASSEMBLE ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_manifest() -> dict:
    path = ROOT / "agent.manifest.json"
    if not path.is_file():
        fail("agent.manifest.json not found at package root")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"agent.manifest.json is invalid JSON: {exc}")
    return {}


def resolve_includes(manifest: dict) -> str:
    """Read systemPromptIncludes in listed order and concatenate them,
    separated by blank lines. A missing include is a hard error — the
    order IS the assembled prompt order (README.md 13.1)."""
    parts: list[str] = []
    for rel in manifest.get("systemPromptIncludes", []):
        path = ROOT / rel
        if not path.is_file():
            fail(f"systemPromptIncludes entry missing on disk: {rel}")
        parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts) + "\n"


def expand_context_globs(manifest: dict) -> list[Path]:
    """contextGlobs expand relative to context/, sorted by filename. A glob
    matching any context/prompt/ file is a hard error — prompt partials load
    through systemPromptIncludes ONLY (README.md 13.1); matching them here
    would load them twice."""
    files: list[Path] = []
    for pattern in manifest.get("contextGlobs", []):
        matches = sorted(CONTEXT.glob(pattern))
        for m in matches:
            if not m.is_file():
                continue
            if m.relative_to(CONTEXT).parts[0] == "prompt":
                fail(
                    f"contextGlobs must not match prompt partials: {pattern} -> "
                    f"{m.relative_to(ROOT)} (would load it twice)"
                )
            files.append(m)
    return files


def eager_block(files: list[Path]) -> str:
    """Render eager-tier files with a source comment per file, so the
    assembled prompt shows where each rule came from."""
    parts = []
    for f in files:
        rel = f.relative_to(ROOT)
        parts.append(f"<!-- {rel} -->\n{f.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts) + ("\n" if parts else "")


def emit_claude_rules(manifest: dict, out: Path) -> list[str]:
    """Write each eager-tier context file as its own .claude/rules/ file,
    keeping the `<!-- context/<path> -->` provenance comment. Returns the
    emitted filenames, sorted — that IS the CLAUDE.md import order."""
    names: list[str] = []
    for f in expand_context_globs(manifest):
        rel = f.relative_to(CONTEXT).as_posix()
        fname = target_paths.rule_filename(rel)
        body = f"<!-- context/{rel} -->\n{f.read_text(encoding='utf-8').strip()}\n"
        write(out / ".claude" / "rules" / fname, body)
        names.append(fname)
    return sorted(names)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def rewrite_tree_citations(root: Path, citation_map: dict[str, str]) -> None:
    """Rewrite every markdown file under `root` in place, mapping source
    citation tokens to their emitted .claude/ locations. Sorted walk;
    writes only when the text actually changes (determinism + no churn)."""
    for md in sorted(root.rglob("*.md")):
        original = md.read_text(encoding="utf-8")
        rewritten = target_paths.rewrite_citations(original, citation_map)
        if rewritten != original:
            md.write_text(rewritten, encoding="utf-8")


def declared_skill_dirs(manifest: dict) -> list[Path]:
    dirs: list[Path] = []
    for name in manifest.get("skillNames", []):
        d = SKILLS / name
        if not d.is_dir():
            fail(f"skillNames entry has no directory: skills/{name}/")
        dirs.append(d)
    return dirs


def declared_sop_files(manifest: dict) -> list[Path]:
    files: list[Path] = []
    for name in manifest.get("sopNames", []):
        p = SOPS / f"{name}.sop.md"
        if not p.is_file():
            fail(f"sopNames entry has no file: sops/{name}.sop.md")
        files.append(p)
    return files


def copy_sops(manifest: dict, out: Path) -> None:
    """Copy declared SOPs into the target. Skills and hooks cite SOPs by
    the relative path sops/<name>.sop.md — a target without them would
    ship broken citations."""
    for p in declared_sop_files(manifest):
        write(out / "sops" / p.name, p.read_text(encoding="utf-8"))


def emit_mcp(manifest: dict, path: Path) -> None:
    write(path, json.dumps({"mcpServers": manifest.get("mcpServers", {})},
                            indent=2, sort_keys=True) + "\n")


def emit_kiro_cli_agent(manifest: dict, agents_dir: Path) -> None:
    """kiro-cli's agent-activation format — distinct from the Kiro GUI
    editor's steering-file convention. Verified live against kiro-cli 2.20.1
    (2026-09-04): steering (`.kiro/steering/**/*.md`) auto-loads for every
    agent regardless of `resources`, but it's still declared explicitly here
    so this doesn't depend on an unstated default that could change across
    versions. Skills load progressively: with
    `skill://.kiro/skills/*/SKILL.md` declared, description-level metadata is
    visible at session start, while the full SKILL.md body was not observed
    in context without a tool-based read — matching kiro-cli's documented
    "metadata loads at startup, full content loads on demand." A deploy
    without the entry was not tested, so what it contributes beyond that is
    unconfirmed; it stays declared. Routing to skills is unaffected either
    way."""
    name = manifest.get("name")
    if not name:
        fail("agent.manifest.json has no name — required for the kiro-cli agent config filename")
    welcome = manifest.get("welcomeMessage") or name
    version = manifest.get("version")
    if version:
        welcome = f"{welcome} (v{version})"
    config = {
        "name": name,
        "description": manifest.get("description", ""),
        "prompt": None,
        "mcpServers": {},
        "tools": manifest.get("tools") or ["*"],
        "allowedTools": manifest.get("allowedTools", []),
        "resources": [
            "file://.kiro/steering/**/*.md",
            "skill://.kiro/skills/*/SKILL.md",
        ],
        "includeMcpJson": True,
        "model": None,
        "welcomeMessage": welcome,
    }
    write(agents_dir / f"{name}.json", json.dumps(config, indent=2, sort_keys=True) + "\n")


def hook_files() -> list[Path]:
    """Real hook files only — an empty hooks/ directory produces no
    hooks.json output, and hooks/example.hook.json is an inert copy-me
    template (like skills/example-skill/ and sops/example.sop.md) that must
    never reach a target's output."""
    if not HOOKS.is_dir():
        return []
    return sorted(p for p in HOOKS.glob("*.hook.json") if p.name != "example.hook.json")


def emit_claude_agent_file(manifest: dict, prompt: str, out: Path) -> None:
    """The generated Claude Code project agent. Claude discovers agents by
    scanning .claude/agents/*.md and matching frontmatter `name`;
    `claude --agent <name>` resolves here."""
    name = manifest.get("name")
    if not name:
        fail("agent.manifest.json has no name — required for the claude-code agent file")
    desc = manifest.get("description") or f"{name} — assembled by build/assemble.py"
    frontmatter = f"---\nname: {name}\ndescription: {json.dumps(desc)}\n---\n\n"
    write(out / ".claude" / "agents" / f"{name}.md", frontmatter + prompt)


def subagent_agent_files(manifest: dict) -> list[Path]:
    files: list[Path] = []
    for name in manifest.get("subagentNames", []):
        p = AGENTS / f"{name}.agent.json"
        if not p.is_file():
            fail(f"subagentNames entry has no file: agents/{name}.agent.json")
        files.append(p)
    return files


def _subagent_body(spec: dict, name: str) -> str:
    parts: list[str] = []
    for rel in spec.get("systemPromptIncludes", []):
        path = ROOT / rel
        if not path.is_file():
            fail(f"subagent {name}: systemPromptIncludes missing on disk: {rel}")
        parts.append(path.read_text(encoding="utf-8").strip())
    for pattern in spec.get("contextGlobs", []):
        for m in sorted(CONTEXT.glob(pattern)):
            if m.is_file():
                rel = m.relative_to(ROOT).as_posix()
                parts.append(f"<!-- {rel} -->\n{m.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)


def emit_claude_subagent(spec: dict, out: Path) -> None:
    """Translate agents/<name>.agent.json into a Claude Code subagent file.
    Read-only guarantee rests on `tools:` — write verbs are dropped.
    shellAllowedCommands has no Claude subagent-file equivalent (mapping gap)."""
    name = spec["name"]
    tools = [t for t in spec.get("tools", []) if str(t).lower() not in WRITE_VERBS]
    allowed = spec.get("allowedTools")
    if allowed:
        narrowed = [t for t in tools if t in allowed]
        tools = narrowed or list(allowed)
    fm = ["---", f"name: {name}", f"description: {json.dumps(spec.get('description', ''))}"]
    if tools:
        fm.append(f"tools: {', '.join(tools)}")
    fm.append("---")
    write(out / ".claude" / "agents" / f"{name}.md",
          "\n".join(fm) + "\n\n" + _subagent_body(spec, name) + "\n")


def emit_claude_settings(manifest: dict, out: Path) -> None:
    """.claude/settings.json — always emitted. Declares the default agent
    only when the manifest opts in (claudeSettings.defaultAgent), so a bare
    `claude` picks up Agent X; otherwise `claude --agent <name>` is explicit."""
    settings: dict = {}
    if manifest.get("claudeSettings", {}).get("defaultAgent"):
        settings["agent"] = manifest["name"]
    write(out / ".claude" / "settings.json",
          json.dumps(settings, indent=2, sort_keys=True) + "\n")


def target_claude_code(manifest: dict, out: Path) -> None:
    prompt = resolve_includes(manifest)
    rule_names = emit_claude_rules(manifest, out)
    imports = "".join(f"@.claude/rules/{n}\n" for n in rule_names)
    write(
        out / "CLAUDE.md",
        prompt
        + "\n---\n\n"
        + "<!-- Always-on project context (loaded via imports). -->\n"
        + imports,
    )
    emit_claude_agent_file(manifest, prompt, out)
    emit_claude_settings(manifest, out)
    for p in subagent_agent_files(manifest):
        emit_claude_subagent(json.loads(p.read_text(encoding="utf-8")), out)
    citation_map = target_paths.build_citation_map(CONTEXT, SOPS)

    for d in declared_skill_dirs(manifest):
        dst = out / ".claude" / "skills" / d.name
        copy_tree(d, dst)
        rewrite_tree_citations(dst, citation_map)

    for p in declared_sop_files(manifest):
        body = target_paths.rewrite_citations(p.read_text(encoding="utf-8"), citation_map)
        write(out / ".claude" / "sops" / p.name, body)

    emit_mcp(manifest, out / ".mcp.json")

    hooks = hook_files()
    if hooks:
        aggregated = [json.loads(p.read_text(encoding="utf-8")) for p in hooks]
        write(out / ".claude" / "hooks.json", json.dumps(aggregated, indent=2) + "\n")


def target_kiro_cli(manifest: dict, out: Path) -> None:
    write(out / "steering" / "00-system.md", resolve_includes(manifest))
    for f in expand_context_globs(manifest):
        rel = f.relative_to(CONTEXT)
        write(out / "steering" / "-".join(rel.parts), f.read_text(encoding="utf-8"))
    for d in declared_skill_dirs(manifest):
        copy_tree(d, out / "skills" / d.name)
    copy_sops(manifest, out)
    emit_mcp(manifest, out / "settings" / "mcp.json")
    emit_kiro_cli_agent(manifest, out / "agents")


def target_generic(manifest: dict, out: Path) -> None:
    prompt = resolve_includes(manifest)
    eager = eager_block(expand_context_globs(manifest))
    write(out / "system-prompt.txt", prompt + "\n" + eager)
    emit_mcp(manifest, out / "mcp.json")
    lines = ["# Skills Catalog", ""]
    for d in declared_skill_dirs(manifest):
        text = (d / "SKILL.md").read_text(encoding="utf-8")
        desc = ""
        if text.startswith("---"):
            end = text.find("\n---", 3)
            for line in text[3:end].splitlines():
                if line.strip().startswith("description:"):
                    desc = line.partition(":")[2].strip()
        lines.append(f"- **{d.name}** — {desc}")
        copy_tree(d, out / "skills" / d.name)
    copy_sops(manifest, out)
    write(out / "skills-catalog.md", "\n".join(lines) + "\n")


TARGET_FUNCS = {
    "claude-code": target_claude_code,
    "kiro-cli": target_kiro_cli,
    "generic": target_generic,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="generic", choices=sorted(TARGETS))
    parser.add_argument("--out", default=None, help="output dir (default dist/<target>)")
    args = parser.parse_args()

    manifest = load_manifest()
    out = Path(args.out) if args.out else ROOT / "dist" / args.target
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    TARGET_FUNCS[args.target](manifest, out)
    print(f"assembled target={args.target} out={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
