import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))

import target_paths  # noqa: E402


def test_rule_filename_joins_parts_with_hyphen():
    assert target_paths.rule_filename("guardrails/no-fabrication.md") == "guardrails-no-fabrication.md"
    assert target_paths.rule_filename("routing/00-core.md") == "routing-00-core.md"


def test_build_citation_map_covers_context_tiers_and_sops(tmp_path):
    ctx = tmp_path / "context"
    (ctx / "guardrails").mkdir(parents=True)
    (ctx / "routing").mkdir(parents=True)
    (ctx / "guardrails" / "no-fabrication.md").write_text("x", encoding="utf-8")
    (ctx / "routing" / "00-core.md").write_text("x", encoding="utf-8")
    sops = tmp_path / "sops"
    sops.mkdir()
    (sops / "wire-new-capability.sop.md").write_text("x", encoding="utf-8")

    m = target_paths.build_citation_map(ctx, sops)

    assert m["context/guardrails/no-fabrication.md"] == ".claude/rules/guardrails-no-fabrication.md"
    assert m["context/routing/00-core.md"] == ".claude/rules/routing-00-core.md"
    assert m["sops/wire-new-capability.sop.md"] == ".claude/sops/wire-new-capability.sop.md"


def test_build_citation_map_omits_tokens_with_no_file_on_disk(tmp_path):
    ctx = tmp_path / "context"
    (ctx / "guardrails").mkdir(parents=True)
    sops = tmp_path / "sops"
    sops.mkdir()

    m = target_paths.build_citation_map(ctx, sops)

    assert m == {}


def test_rewrite_citations_replaces_known_tokens_and_leaves_others(tmp_path):
    citation_map = {
        "context/guardrails/no-fabrication.md": ".claude/rules/guardrails-no-fabrication.md",
        "sops/wire-new-capability.sop.md": ".claude/sops/wire-new-capability.sop.md",
    }
    text = (
        "See `context/guardrails/no-fabrication.md` and "
        "`sops/wire-new-capability.sop.md`. Run `tool/toolkit/toolkit.py list`."
    )

    out = target_paths.rewrite_citations(text, citation_map)

    assert ".claude/rules/guardrails-no-fabrication.md" in out
    assert ".claude/sops/wire-new-capability.sop.md" in out
    assert "context/guardrails/no-fabrication.md" not in out
    assert "tool/toolkit/toolkit.py" in out  # not in the map — untouched


def test_rewrite_citations_longest_token_wins(tmp_path):
    # a shorter token that is a prefix of a longer one must not shadow it
    citation_map = {
        "context/knowledge": ".claude/rules/SHOULD-NOT-WIN",
        "context/knowledge/domain-glossary.md": ".claude/rules/knowledge-domain-glossary.md",
    }
    out = target_paths.rewrite_citations("context/knowledge/domain-glossary.md", citation_map)
    assert out == ".claude/rules/knowledge-domain-glossary.md"
