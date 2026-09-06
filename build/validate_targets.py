#!/usr/bin/env python3
"""Assemble each target and assert its real output layout.

Fails if a manifest-declared capability (skill, SOP, subagent, eager context
file) is not emitted where its target expects it. This is the output-side
counterpart to context/scripts/validate-wiring.py (which checks the source
tree only).

Stdlib only.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "context"
SOPS = ROOT / "sops"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import target_paths  # noqa: E402

failures: list[str] = []


def fail(target: str, capability: str, detail: str) -> None:
    failures.append(f"VALIDATE FAIL {target} {capability}: {detail}")


def assemble(target: str, out: Path) -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "build" / "assemble.py"),
         "--target", target, "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        fail(target, "<assembly>", (r.stderr or r.stdout).strip())


def eager_context_files() -> list[str]:
    manifest = json.loads((ROOT / "agent.manifest.json").read_text(encoding="utf-8"))
    files: list[str] = []
    for pattern in manifest.get("contextGlobs", []):
        for m in sorted(CONTEXT.glob(pattern)):
            if m.is_file():
                files.append(m.relative_to(CONTEXT).as_posix())
    return files


def check_kiro(manifest: dict, out: Path) -> None:
    t = "kiro-cli"
    if not (out / "steering" / "00-system.md").is_file():
        fail(t, "system-prompt", "steering/00-system.md missing")
    for rel in eager_context_files():
        fn = target_paths.rule_filename(rel)
        if not (out / "steering" / fn).is_file():
            fail(t, f"context/{rel}", f"steering/{fn} missing")
    for name in manifest.get("skillNames", []):
        if not (out / "skills" / name / "SKILL.md").is_file():
            fail(t, f"skill/{name}", f"skills/{name}/SKILL.md missing")
    for name in manifest.get("sopNames", []):
        if not (out / "sops" / f"{name}.sop.md").is_file():
            fail(t, f"sop/{name}", f"sops/{name}.sop.md missing")
    if not (out / "settings" / "mcp.json").is_file():
        fail(t, "mcp", "settings/mcp.json missing")
    prim = out / "agents" / f"{manifest['name']}.json"
    if not prim.is_file():
        fail(t, "agent", f"agents/{manifest['name']}.json missing")
    for name in manifest.get("subagentNames", []):
        if not (out / "agents" / f"{name}.json").is_file():
            fail(t, f"subagent/{name}", f"agents/{name}.json missing")


def check_claude(manifest: dict, out: Path) -> None:
    t = "claude-code"
    claude_md = out / "CLAUDE.md"
    if not claude_md.is_file():
        fail(t, "system-prompt", "CLAUDE.md missing")
        return
    text = claude_md.read_text(encoding="utf-8")
    for rel in eager_context_files():
        fn = target_paths.rule_filename(rel)
        if not (out / ".claude" / "rules" / fn).is_file():
            fail(t, f"context/{rel}", f".claude/rules/{fn} missing")
        if f"@.claude/rules/{fn}" not in text:
            fail(t, f"context/{rel}", f"CLAUDE.md has no @-import for {fn}")
    for name in manifest.get("skillNames", []):
        if not (out / ".claude" / "skills" / name / "SKILL.md").is_file():
            fail(t, f"skill/{name}", f".claude/skills/{name}/SKILL.md missing")
    for name in manifest.get("sopNames", []):
        if not (out / ".claude" / "sops" / f"{name}.sop.md").is_file():
            fail(t, f"sop/{name}", f".claude/sops/{name}.sop.md missing")
    agent_md = out / ".claude" / "agents" / f"{manifest['name']}.md"
    if not agent_md.is_file():
        fail(t, "agent", f".claude/agents/{manifest['name']}.md missing")
    elif f"\nname: {manifest['name']}\n" not in agent_md.read_text(encoding="utf-8"):
        fail(t, "agent", "frontmatter name does not match manifest name "
                         "(claude --agent discovery would miss it)")
    for name in manifest.get("subagentNames", []):
        sub = out / ".claude" / "agents" / f"{name}.md"
        if not sub.is_file():
            fail(t, f"subagent/{name}", f".claude/agents/{name}.md missing")
            continue
        tools_line = next((l for l in sub.read_text(encoding="utf-8").splitlines()
                           if l.startswith("tools:")), "")
        if any(v in tools_line for v in ("write", "edit", "delete", "create", "update", "patch")):
            fail(t, f"subagent/{name}", f"tools line has a write verb: {tools_line!r}")
    if not (out / ".mcp.json").is_file():
        fail(t, "mcp", ".mcp.json missing")
    settings_path = out / ".claude" / "settings.json"
    if not settings_path.is_file():
        fail(t, "settings", ".claude/settings.json missing")
    else:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        want_default = bool(manifest.get("claudeSettings", {}).get("defaultAgent"))
        has_agent = settings.get("agent") == manifest["name"]
        if want_default and not has_agent:
            fail(t, "settings", "claudeSettings.defaultAgent is true but "
                                ".claude/settings.json lacks the matching agent key")
        if not want_default and "agent" in settings:
            fail(t, "settings", "claudeSettings.defaultAgent is false but "
                                ".claude/settings.json declares an agent")

    # Residual-citation backstop (spec §6): no emitted Claude markdown file may
    # still carry a source citation token that has a mapping entry — those must
    # have been rewritten to their .claude/ location. The `<!-- context/… -->`
    # provenance comment lines are deliberately literal (§13.6) and exempt.
    citation_map = target_paths.build_citation_map(CONTEXT, SOPS)
    comment_line = re.compile(r"^\s*<!--.*-->\s*$")
    md_files = [out / "CLAUDE.md"] + sorted((out / ".claude").rglob("*.md"))
    for md in md_files:
        if not md.is_file():
            continue
        body = "\n".join(l for l in md.read_text(encoding="utf-8").splitlines()
                         if not comment_line.match(l))
        for token, dest in citation_map.items():
            # a rewritten `.claude/…` path ends with the bare token — strip the
            # emitted paths before checking so that tail is not a false hit.
            if token in body.replace(dest, ""):
                fail(t, "residual-citation",
                     f"{md.relative_to(out)} still contains unrewritten "
                     f"source citation {token!r} (should be {dest!r})")


def main(argv: list[str] | None = None) -> int:
    failures.clear()
    manifest = json.loads((ROOT / "agent.manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        assemble("kiro-cli", base / "kiro-cli")
        assemble("claude-code", base / "claude-code")
        if not failures:
            check_kiro(manifest, base / "kiro-cli")
            check_claude(manifest, base / "claude-code")
    for line in failures:
        print(line)
    if failures:
        print(f"\nTARGET VALIDATION: FAIL — {len(failures)} finding(s)")
        return 1
    print("TARGET VALIDATION: PASS — both targets emit every declared capability")
    return 0


if __name__ == "__main__":
    sys.exit(main())
