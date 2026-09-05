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


def test_claude_code_target_writes_claude_md_with_prompt_and_eager_tiers(tmp_path):
    out_dir = tmp_path / "out"

    result = run_assemble("--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    claude_md = (out_dir / "CLAUDE.md").read_text(encoding="utf-8")
    assert IDENTITY_MARKER in claude_md
    assert DOMAIN_MARKER in claude_md
    assert ROUTING_MARKER in claude_md
    assert claude_md.index(IDENTITY_MARKER) < claude_md.index(ROUTING_MARKER)


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
    copied = out_dir / ".claude" / "skills" / "example-skill" / "SKILL.md"
    original = pkg / "skills" / "example-skill" / "SKILL.md"
    assert copied.read_text(encoding="utf-8") == original.read_text(encoding="utf-8")


def test_claude_code_target_copies_declared_sops(tmp_path):
    pkg = copy_package(tmp_path)
    declare_sop(pkg, "example-sop")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    copied = out_dir / "sops" / "example-sop.sop.md"
    assert copied.read_text(encoding="utf-8") == "# Example SOP\n\nDo the thing.\n"


def test_claude_code_target_omits_hooks_json_when_no_hooks(tmp_path):
    pkg = copy_package(tmp_path)
    for hook in (pkg / "hooks").glob("*.hook.json"):
        hook.unlink()
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    assert not (out_dir / "hooks.json").exists()


def test_claude_code_target_writes_hooks_json_when_hooks_exist(tmp_path):
    pkg = copy_package(tmp_path)
    declare_hook(pkg, "example", {"event": "SessionStart", "command": "true"})
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode == 0
    hooks = json.loads((out_dir / "hooks.json").read_text(encoding="utf-8"))
    assert {json.dumps(hook, sort_keys=True) for hook in hooks} >= {
        json.dumps({"event": "SessionStart", "command": "true"}, sort_keys=True)
    }


def test_claude_code_target_missing_declared_skill_is_hard_error(tmp_path):
    pkg = copy_package(tmp_path)
    declare_skill(pkg, "nonexistent-skill")
    out_dir = tmp_path / "out"

    result = run_assemble_at(pkg, "--target", "claude-code", "--out", str(out_dir))

    assert result.returncode != 0
    assert "nonexistent-skill" in result.stderr


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
    declare_hook(pkg, "example", {"event": "SessionStart", "command": "true"})
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
    declare_hook(pkg, "example", {"event": "SessionStart", "command": "true"})
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
    declare_hook(pkg, "example", {"event": "SessionStart", "command": "true"})
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"

    result_a = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_a))
    result_b = run_assemble_at(pkg, "--target", "kiro-cli", "--out", str(out_b))

    assert result_a.returncode == 0
    assert result_b.returncode == 0
    assert_trees_byte_identical(out_a, out_b)


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
