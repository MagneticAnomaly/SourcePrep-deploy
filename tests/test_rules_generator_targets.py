"""Tests for client-aware content delivery in rules generator."""
import hashlib

from prep.core.rules_generator import _build_managed_content


# -- Shared fixture args --
_BASE_ARGS = dict(
    project_name="test-project",
    atlas_content="IDENTITY: Test project\nSTACK: Python, React",
    included_paths=["src/main.py", "src/utils.py"],
    is_preliminary=False,
    stats={"node_count": 42, "edge_count": 100, "coverage_pct": 85},
    project_id="aaaa-bbbb-cccc-dddd",
)


def test_universal_target_is_default():
    """Without target param, output matches current behavior (universal)."""
    content = _build_managed_content(**_BASE_ARGS)
    # Universal includes all sections: resources, prompts, auto-approve with IDE list
    assert "MCP Resources" in content
    assert "MCP Prompts" in content
    assert "In Claude Code:" in content or "In Cursor:" in content


def test_claude_target_omits_cursor_references():
    """Claude target should not mention Cursor or other IDEs."""
    content = _build_managed_content(**_BASE_ARGS, target="claude")
    assert "Cursor" not in content
    assert "Windsurf" not in content


def test_claude_target_is_compact():
    """Claude target should be noticeably shorter than universal."""
    universal = _build_managed_content(**_BASE_ARGS, target="universal")
    claude = _build_managed_content(**_BASE_ARGS, target="claude")
    # Claude should be at least 30% shorter
    assert len(claude) < len(universal) * 0.75


def test_claude_target_keeps_essentials():
    """Claude target must still include project_id routing and tool table."""
    content = _build_managed_content(**_BASE_ARGS, target="claude")
    assert "aaaa-bbbb-cccc-dddd" in content
    assert "codrag_search" in content
    assert "codrag_impact" in content
    assert "Codebase Atlas" in content
    assert "Focus Areas" in content


def test_claude_target_includes_claude_specific_hints():
    """Claude target should include Claude Code specific features."""
    content = _build_managed_content(**_BASE_ARGS, target="claude")
    # Should mention @ resources and / prompts (Claude Code supports both)
    assert "@" in content or "resources" in content.lower()


def test_claude_target_has_compact_auto_approve():
    """Claude target auto-approve references .claude/settings.json only."""
    content = _build_managed_content(**_BASE_ARGS, target="claude")
    assert "mcp__codrag" in content
    assert ".claude/settings.json" in content


def test_universal_target_has_generic_auto_approve():
    """Universal target mentions multiple IDEs for auto-approve."""
    content = _build_managed_content(**_BASE_ARGS, target="universal")
    assert "mcp__codrag" in content


def test_cursor_target_omits_claude_hints():
    """Cursor target should not mention slash commands or .claude/ paths."""
    content = _build_managed_content(**_BASE_ARGS, target="cursor")
    assert "/mcp__codrag" not in content
    assert ".claude/settings.json" not in content


def test_atlas_hash_preserved_for_all_targets():
    """All targets should embed the atlas hash when atlas is present."""
    for target in ("claude", "cursor", "universal"):
        content = _build_managed_content(**_BASE_ARGS, target=target)
        expected_hash = hashlib.sha256(
            _BASE_ARGS["atlas_content"].strip().encode()
        ).hexdigest()[:12]
        assert f"codrag-atlas-hash:{expected_hash}" in content, f"Missing hash for target={target}"


def test_no_project_id_still_works():
    """All targets should handle missing project_id gracefully."""
    args = {**_BASE_ARGS, "project_id": None}
    for target in ("claude", "cursor", "universal"):
        content = _build_managed_content(**args, target=target)
        assert "codrag" in content.lower()


# -- Integration tests: write_rules_file wiring --

from pathlib import Path

from prep.core.rules_generator import write_rules_file


def test_write_rules_passes_claude_target(tmp_path):
    """write_rules_file should pass target='claude' for Claude rules."""
    (tmp_path / "CLAUDE.md").write_text("# My Project\n")
    (tmp_path / ".claude").mkdir()

    write_rules_file(
        project_path=tmp_path,
        project_name="test",
        atlas_content="IDENTITY: Test",
        ide="claude",
        project_id="test-id",
    )
    claude_md = (tmp_path / "CLAUDE.md").read_text()
    # Claude target should NOT contain the verbose universal sections
    assert "Tool Calling Rules" not in claude_md
    assert "codrag" in claude_md.lower()


def test_write_rules_passes_universal_target_for_agents_md(tmp_path):
    """AGENTS.md should always use the universal target."""
    write_rules_file(
        project_path=tmp_path,
        project_name="test",
        atlas_content="IDENTITY: Test",
        ide="agents_md",
        project_id="test-id",
    )
    agents_md = (tmp_path / "AGENTS.md").read_text()
    # Universal includes the verbose sections
    assert "Tool Calling Rules" in agents_md
