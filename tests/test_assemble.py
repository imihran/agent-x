import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSEMBLE = ROOT / "build" / "assemble.py"

IDENTITY_MARKER = "# Identity & Shared Behavior"
DOMAIN_MARKER = "# Domain — {{DOMAIN_NAME}}"
ROUTING_MARKER = "# Routing — Core Gate, Precedence & Escalation"
GUARDRAIL_MARKER = "# No Fabrication — Never Invent, Confirm the Ambiguous"
KNOWLEDGE_MARKER = "# Known Silent Failures"
CONVENTION_MARKER = "# Authoring Conventions"


def run_assemble(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ASSEMBLE), *args],
        capture_output=True,
        text=True,
    )


def copy_package(tmp_path: Path) -> Path:
    """A private copy of the package so a test's manifest edits never touch
    the real working tree."""
    dest = tmp_path / "pkg"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git"))
    return dest


def run_assemble_at(pkg_root: Path, *args: str) -> subprocess.CompletedProcess:
    assemble = pkg_root / "build" / "assemble.py"
    return subprocess.run(
        [sys.executable, str(assemble), *args],
        capture_output=True,
        text=True,
    )


def set_manifest(pkg_root: Path, **fields) -> None:
    manifest_path = pkg_root / "agent.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(fields)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_assembled_prompt_contains_both_partials_in_numeric_order_exactly_once(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--out", str(out_dir))

    assert result.returncode == 0
    prompt = (out_dir / "system-prompt.txt").read_text(encoding="utf-8")
    assert prompt.count(IDENTITY_MARKER) == 1
    assert prompt.count(DOMAIN_MARKER) == 1
    assert prompt.index(IDENTITY_MARKER) < prompt.index(DOMAIN_MARKER)


def test_assembled_prompt_includes_eager_tier_content_with_source_comments(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--out", str(out_dir))

    assert result.returncode == 0
    prompt = (out_dir / "system-prompt.txt").read_text(encoding="utf-8")
    assert ROUTING_MARKER in prompt
    assert GUARDRAIL_MARKER in prompt
    assert KNOWLEDGE_MARKER in prompt
    assert CONVENTION_MARKER in prompt
    assert "<!-- context/routing/00-core.md -->" in prompt
    assert "<!-- context/guardrails/no-fabrication.md -->" in prompt
    assert "<!-- context/knowledge/known-silent-failures.md -->" in prompt
    assert "<!-- context/conventions/authoring-conventions.md -->" in prompt


def test_prompt_partials_appear_exactly_once_alongside_eager_tiers(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--out", str(out_dir))

    assert result.returncode == 0
    prompt = (out_dir / "system-prompt.txt").read_text(encoding="utf-8")
    assert prompt.count(IDENTITY_MARKER) == 1
    assert prompt.count(DOMAIN_MARKER) == 1
    assert prompt.count(ROUTING_MARKER) == 1
    assert prompt.count(GUARDRAIL_MARKER) == 1


def test_context_globs_matching_prompt_partial_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, contextGlobs=["prompt/*"])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--out", str(out_dir))

    assert result.returncode != 0
    assert "prompt" in result.stderr
    assert not (out_dir / "system-prompt.txt").exists()


def declare_skill(pkg_root: Path, name: str) -> None:
    set_manifest(pkg_root, skillNames=[name])


def declare_sop(pkg_root: Path, name: str, body: str = "# Example SOP\n\nDo the thing.\n") -> None:
    sop_path = pkg_root / "sops" / f"{name}.sop.md"
    sop_path.write_text(body, encoding="utf-8")
    manifest_path = pkg_root / "agent.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sopNames"] = manifest.get("sopNames", []) + [name]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def declare_hook(pkg_root: Path, name: str, obj: dict) -> None:
    hook_path = pkg_root / "hooks" / f"{name}.hook.json"
    hook_path.write_text(json.dumps(obj), encoding="utf-8")


def assert_trees_byte_identical(a: Path, b: Path) -> None:
    a_files = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    b_files = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert a_files == b_files, f"file sets differ: {a_files} vs {b_files}"
    for rel in a_files:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"content differs: {rel}"


# --- claude-code target ---


def test_claude_code_target_writes_thin_claude_md_with_prompt_and_rule_imports(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    claude_md = (out_dir / "CLAUDE.md").read_text(encoding="utf-8")
    # prompt half still present
    assert IDENTITY_MARKER in claude_md
    assert DOMAIN_MARKER in claude_md
    assert claude_md.index(IDENTITY_MARKER) < claude_md.index(DOMAIN_MARKER)
    # eager tiers are NO LONGER inlined — they are imported
    assert ROUTING_MARKER not in claude_md
    assert GUARDRAIL_MARKER not in claude_md
    assert "@.claude/rules/routing-00-core.md" in claude_md
    assert "@.claude/rules/guardrails-no-fabrication.md" in claude_md


def test_claude_code_target_emits_one_rule_file_per_eager_context_file(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    routing = (out_dir / ".claude" / "rules" / "routing-00-core.md").read_text(encoding="utf-8")
    assert ROUTING_MARKER in routing
    assert "<!-- context/routing/00-core.md -->" in routing
    guardrail = (out_dir / ".claude" / "rules" / "guardrails-no-fabrication.md").read_text(encoding="utf-8")
    assert GUARDRAIL_MARKER in guardrail


def test_claude_code_target_claude_md_import_list_is_sorted_and_complete(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    claude_md = (out_dir / "CLAUDE.md").read_text(encoding="utf-8")
    imports = [line[len("@.claude/rules/"):] for line in claude_md.splitlines()
               if line.startswith("@.claude/rules/")]
    rule_files = sorted(p.name for p in (out_dir / ".claude" / "rules").glob("*.md"))
    assert imports == rule_files


def test_claude_code_target_writes_mcp_json(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, mcpServers={"example": {"command": "echo"}})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    mcp = json.loads((out_dir / ".mcp.json").read_text(encoding="utf-8"))
    assert mcp == {"mcpServers": {"example": {"command": "echo"}}}


def test_claude_code_target_copies_declared_skill_dir(tmp_path):
    pkg = copy_package(tmp_path)
    declare_skill(pkg, "example-skill")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    copied = (out_dir / ".claude" / "skills" / "example-skill" / "SKILL.md").read_text(encoding="utf-8")
    original = (pkg / "skills" / "example-skill" / "SKILL.md").read_text(encoding="utf-8")
    # the copy is verbatim except that source citations are rewritten to the
    # target's emitted .claude/ locations
    assert "# Example Skill Template" in copied
    assert ".claude/sops/wire-new-capability.sop.md" in copied
    assert "sops/wire-new-capability.sop.md" in original
    assert "sops/wire-new-capability.sop.md" not in copied.replace(".claude/sops/wire-new-capability.sop.md", "")


def test_claude_code_target_copies_declared_sops(tmp_path):
    pkg = copy_package(tmp_path)
    declare_sop(pkg, "example-sop")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    copied = out_dir / ".claude" / "sops" / "example-sop.sop.md"
    assert copied.read_text(encoding="utf-8") == "# Example SOP\n\nDo the thing.\n"
    assert not (out_dir / "sops").exists()


def test_claude_code_target_omits_hooks_json_when_no_hooks(tmp_path):
    pkg = copy_package(tmp_path)
    for hook in (pkg / "hooks").glob("*.hook.json"):
        hook.unlink()
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    assert not (out_dir / ".claude" / "hooks.json").exists()
    assert not (out_dir / "hooks.json").exists()


def test_claude_code_target_writes_hooks_json_when_hooks_exist(tmp_path):
    pkg = copy_package(tmp_path)
    # not "example" — hooks/example.hook.json is the reserved inert template,
    # excluded from output like skills/example-skill and sops/example.sop.md
    declare_hook(pkg, "demo", {"event": "SessionStart", "command": "true"})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    hooks = json.loads((out_dir / ".claude" / "hooks.json").read_text(encoding="utf-8"))
    assert {json.dumps(hook, sort_keys=True) for hook in hooks} >= {
        json.dumps({"event": "SessionStart", "command": "true"}, sort_keys=True)
    }


def test_claude_code_target_rewrites_skill_citations_to_emitted_paths(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    skill_md = (out_dir / ".claude" / "skills" / "demo-skill" / "SKILL.md").read_text(encoding="utf-8")
    # demo-skill/SKILL.md cites context/guardrails/... and sops/wire-new-capability.sop.md
    assert ".claude/rules/guardrails-confirm-before-execute.md" in skill_md
    assert ".claude/sops/wire-new-capability.sop.md" in skill_md
    assert "context/guardrails/confirm-before-execute.md" not in skill_md
    assert "sops/wire-new-capability.sop.md" not in skill_md.replace(".claude/sops/wire-new-capability.sop.md", "")
    # a non-mapped path is left alone
    assert "tool/toolkit/toolkit.py" in skill_md


def test_claude_code_target_copies_bundled_skill_files(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    bundled = out_dir / ".claude" / "skills" / "escalation-handoff" / "templates" / "handoff.md"
    assert bundled.is_file()


def test_claude_code_target_rewrites_sop_citations(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    sop = (out_dir / ".claude" / "sops" / "wire-new-capability.sop.md").read_text(encoding="utf-8")
    # wire-new-capability.sop.md cites sops/adversarial-review.sop.md — a real
    # on-disk SOP, in the citation map — so it must be rewritten under .claude/.
    assert ".claude/sops/adversarial-review.sop.md" in sop
    # the bare token only survives as the tail of the rewritten path
    assert "sops/adversarial-review.sop.md" not in sop.replace(".claude/sops/adversarial-review.sop.md", "")
    # a non-mapped context/ path is left untouched verbatim
    assert "context/scripts/validate-wiring.py" in sop


def test_claude_code_target_missing_declared_skill_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    declare_skill(pkg, "nonexistent-skill")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode != 0
    assert "nonexistent-skill" in result.stderr


def test_claude_code_target_emits_primary_agent_file_discoverable_by_name(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    agent = (out_dir / ".claude" / "agents" / "agent-x.md").read_text(encoding="utf-8")
    assert agent.startswith("---\n")
    assert "\nname: agent-x\n" in agent
    assert "description:" in agent
    # body carries the assembled system prompt
    assert IDENTITY_MARKER in agent
    assert DOMAIN_MARKER in agent


def test_claude_code_target_primary_agent_filename_follows_manifest_name(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, name="agent-x-mish")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    assert (out_dir / ".claude" / "agents" / "agent-x-mish.md").is_file()
    assert not (out_dir / ".claude" / "agents" / "agent-x.md").exists()
    agent = (out_dir / ".claude" / "agents" / "agent-x-mish.md").read_text(encoding="utf-8")
    assert "\nname: agent-x-mish\n" in agent


def test_claude_code_target_missing_name_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    manifest_path = pkg / "agent.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["name"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode != 0
    assert "name" in result.stderr


def test_claude_code_target_settings_json_is_empty_by_default(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    settings = json.loads((out_dir / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings == {}


def test_claude_code_target_settings_json_sets_default_agent_when_manifest_opts_in(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, claudeSettings={"defaultAgent": True})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    settings = json.loads((out_dir / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings == {"agent": "agent-x"}


def test_claude_code_target_default_agent_uses_renamed_manifest_name(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, name="agent-x-mish", claudeSettings={"defaultAgent": True})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    settings = json.loads((out_dir / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings == {"agent": "agent-x-mish"}


# --- kiro-cli target ---


def test_kiro_cli_target_writes_00_system_steering_with_prompt_includes(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    system = (out_dir / "steering" / "00-system.md").read_text(encoding="utf-8")
    assert IDENTITY_MARKER in system
    assert DOMAIN_MARKER in system
    assert ROUTING_MARKER not in system  # eager tiers are separate steering files


def test_kiro_cli_target_writes_one_steering_file_per_eager_tier_file(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    routing = (out_dir / "steering" / "routing-00-core.md").read_text(encoding="utf-8")
    assert ROUTING_MARKER in routing
    guardrail = (out_dir / "steering" / "guardrails-no-fabrication.md").read_text(encoding="utf-8")
    assert GUARDRAIL_MARKER in guardrail


def test_kiro_cli_target_writes_mcp_json_under_settings(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, mcpServers={"example": {"command": "echo"}})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    mcp = json.loads((out_dir / "settings" / "mcp.json").read_text(encoding="utf-8"))
    assert mcp == {"mcpServers": {"example": {"command": "echo"}}}
    assert not (out_dir / "mcp.json").exists()


def test_kiro_cli_target_copies_declared_skill_dir(tmp_path):
    pkg = copy_package(tmp_path)
    declare_skill(pkg, "example-skill")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    copied = out_dir / "skills" / "example-skill" / "SKILL.md"
    original = pkg / "skills" / "example-skill" / "SKILL.md"
    assert copied.read_text(encoding="utf-8") == original.read_text(encoding="utf-8")


def test_kiro_cli_target_copies_declared_sops(tmp_path):
    pkg = copy_package(tmp_path)
    declare_sop(pkg, "example-sop")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    copied = out_dir / "sops" / "example-sop.sop.md"
    assert copied.read_text(encoding="utf-8") == "# Example SOP\n\nDo the thing.\n"


def test_kiro_cli_target_context_globs_matching_prompt_partial_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, contextGlobs=["prompt/*"])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode != 0
    assert "prompt" in result.stderr
    assert not (out_dir / "steering" / "routing-00-core.md").exists()


def test_kiro_cli_target_never_emits_hooks(tmp_path):
    pkg = copy_package(tmp_path)
    declare_hook(pkg, "demo", {"event": "SessionStart", "command": "true"})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    assert not (out_dir / "hooks").exists()


def test_kiro_cli_target_writes_agent_config_with_resources_and_mcp_flag(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    config = json.loads((out_dir / "agents" / "agent-x.json").read_text(encoding="utf-8"))
    assert config["name"] == "agent-x"
    assert config["prompt"] is None
    assert config["resources"] == [
        "file://.kiro/steering/**/*.md",
        "skill://.kiro/skills/*/SKILL.md",
    ]
    assert config["includeMcpJson"] is True
    assert config["mcpServers"] == {}


def test_kiro_cli_target_agent_config_welcome_message_includes_version(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, welcomeMessage="Agent X — ready to help.", version="0.1.0")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    config = json.loads((out_dir / "agents" / "agent-x.json").read_text(encoding="utf-8"))
    assert config["welcomeMessage"] == "Agent X — ready to help. (v0.1.0)"


def test_kiro_cli_target_agent_config_welcome_message_falls_back_to_name_without_text_or_version(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, welcomeMessage="", version=None)
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    config = json.loads((out_dir / "agents" / "agent-x.json").read_text(encoding="utf-8"))
    assert config["welcomeMessage"] == "agent-x"


def test_kiro_cli_target_agent_config_tools_defaults_to_wildcard_when_manifest_empty(tmp_path):
    out_dir = tmp_path / "out"

    # The real agent.manifest.json ships "tools": [] today — assert the
    # fallback, not an override, so this breaks loudly if that ever changes.
    result = run_assemble("--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    config = json.loads((out_dir / "agents" / "agent-x.json").read_text(encoding="utf-8"))
    assert config["tools"] == ["*"]


def test_kiro_cli_target_agent_config_tools_passes_through_when_manifest_declares_some(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, tools=["read", "write"], allowedTools=["read"])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode == 0
    config = json.loads((out_dir / "agents" / "agent-x.json").read_text(encoding="utf-8"))
    assert config["tools"] == ["read", "write"]
    assert config["allowedTools"] == ["read"]


def test_kiro_cli_target_agent_config_missing_name_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    manifest_path = pkg / "agent.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["name"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))

    assert result.returncode != 0
    assert "name" in result.stderr


# --- generic target additions ---


def test_generic_target_writes_mcp_json(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, mcpServers={"example": {"command": "echo"}})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "generic", "--out", str(out_dir))

    assert result.returncode == 0
    mcp = json.loads((out_dir / "mcp.json").read_text(encoding="utf-8"))
    assert mcp == {"mcpServers": {"example": {"command": "echo"}}}


def test_generic_target_writes_skills_catalog_with_description_and_copies_dir(tmp_path):
    pkg = copy_package(tmp_path)
    declare_skill(pkg, "example-skill")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "generic", "--out", str(out_dir))

    assert result.returncode == 0
    catalog = (out_dir / "skills-catalog.md").read_text(encoding="utf-8")
    assert "**example-skill**" in catalog
    assert "Example skill template" in catalog
    copied = out_dir / "skills" / "example-skill" / "SKILL.md"
    original = pkg / "skills" / "example-skill" / "SKILL.md"
    assert copied.read_text(encoding="utf-8") == original.read_text(encoding="utf-8")


def test_generic_target_skills_catalog_is_header_only_when_no_skills_declared(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, skillNames=[])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "generic", "--out", str(out_dir))

    assert result.returncode == 0
    catalog = (out_dir / "skills-catalog.md").read_text(encoding="utf-8")
    assert catalog == "# Skills Catalog\n\n"


def test_generic_target_skills_catalog_includes_declared_package_skills(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "generic", "--out", str(out_dir))

    assert result.returncode == 0
    catalog = (out_dir / "skills-catalog.md").read_text(encoding="utf-8")
    assert "**session-feedback**" in catalog
    assert "**escalation-handoff**" in catalog
    assert "**demo-skill**" in catalog


def test_generic_target_copies_declared_sops(tmp_path):
    pkg = copy_package(tmp_path)
    declare_sop(pkg, "example-sop")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "generic", "--out", str(out_dir))

    assert result.returncode == 0
    copied = out_dir / "sops" / "example-sop.sop.md"
    assert copied.read_text(encoding="utf-8") == "# Example SOP\n\nDo the thing.\n"


def test_generic_target_missing_declared_sop_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    set_manifest(pkg, sopNames=["nonexistent-sop"])
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "generic", "--out", str(out_dir))

    assert result.returncode != 0
    assert "nonexistent-sop" in result.stderr


# --- determinism, all targets ---


def test_claude_code_target_is_deterministic_across_two_runs(tmp_path):
    pkg = copy_package(tmp_path)
    declare_skill(pkg, "example-skill")
    declare_sop(pkg, "example-sop")
    declare_hook(pkg, "demo", {"event": "SessionStart", "command": "true"})
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"

    result_a = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_a))
    result_b = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_b))

    assert result_a.returncode == 0
    assert result_b.returncode == 0
    assert_trees_byte_identical(out_a, out_b)


def test_kiro_cli_target_is_deterministic_across_two_runs(tmp_path):
    pkg = copy_package(tmp_path)
    declare_skill(pkg, "example-skill")
    declare_sop(pkg, "example-sop")
    declare_hook(pkg, "demo", {"event": "SessionStart", "command": "true"})
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"

    result_a = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_a))
    result_b = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_b))

    assert result_a.returncode == 0
    assert result_b.returncode == 0
    assert_trees_byte_identical(out_a, out_b)


def test_reassembling_into_same_out_dir_removes_stale_files_from_prior_run(tmp_path):
    pkg = copy_package(tmp_path)
    out_dir = tmp_path / "out"

    original_name = json.loads((pkg / "agent.manifest.json").read_text(encoding="utf-8"))["name"]
    result_a = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))
    assert result_a.returncode == 0
    stale_agent_file = out_dir / "agents" / f"{original_name}.json"
    assert stale_agent_file.is_file()

    set_manifest(pkg, name="renamed-agent")
    result_b = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_dir))
    assert result_b.returncode == 0

    assert not stale_agent_file.exists(), "stale per-name file from the prior run must not survive"
    assert (out_dir / "agents" / "renamed-agent.json").is_file()


def test_generic_target_is_deterministic_across_two_runs(tmp_path):
    pkg = copy_package(tmp_path)
    declare_skill(pkg, "example-skill")
    declare_sop(pkg, "example-sop")
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"

    result_a = run_assemble_at(pkg, "--target", "generic", "--out", str(out_a))
    result_b = run_assemble_at(pkg, "--target", "generic", "--out", str(out_b))

    assert result_a.returncode == 0
    assert result_b.returncode == 0
    assert_trees_byte_identical(out_a, out_b)
