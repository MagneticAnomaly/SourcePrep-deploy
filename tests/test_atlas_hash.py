"""Tests for atlas content hash embedding and extraction."""
import hashlib

from prep.core.rules_generator import _build_managed_content
from prep.mcp.server import MCPServer


def test_managed_content_includes_atlas_hash():
    """The managed content block should include a hash of the atlas content."""
    atlas = "IDENTITY: Test project\nSTACK: Python"
    content = _build_managed_content(
        project_name="test",
        atlas_content=atlas,
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    expected_hash = hashlib.sha256(atlas.strip().encode()).hexdigest()[:12]
    assert f"codrag-atlas-hash:{expected_hash}" in content


def test_managed_content_no_hash_when_no_atlas():
    """No hash comment when atlas is empty."""
    content = _build_managed_content(
        project_name="test",
        atlas_content="",
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    assert "codrag-atlas-hash" not in content


def test_extract_atlas_hash_from_rules_content():
    """The MCP server should extract the atlas hash from rules file content."""
    atlas = "IDENTITY: Test\nSTACK: Python"
    expected_hash = hashlib.sha256(atlas.strip().encode()).hexdigest()[:12]
    rules_content = f"<!-- codrag-atlas-hash:{expected_hash} -->\n## Codebase Atlas\n{atlas}"
    extracted = MCPServer._extract_atlas_hash(rules_content)
    assert extracted == expected_hash


def test_extract_atlas_hash_missing():
    """Returns None when no hash comment is present."""
    extracted = MCPServer._extract_atlas_hash("## Just some content")
    assert extracted is None


def test_managed_content_includes_permission_hint():
    """The managed content should include auto-approve configuration hint."""
    content = _build_managed_content(
        project_name="test",
        atlas_content="",
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    assert "mcp__codrag" in content


def test_managed_content_mentions_resources():
    """Generated content should inform agents about available MCP resources."""
    content = _build_managed_content(
        project_name="test",
        atlas_content="IDENTITY: Test",
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    assert "MCP Resources" in content
    assert "@" in content  # mentions @ browsing


def test_managed_content_mentions_prompts():
    """Generated content should inform agents about available MCP prompts."""
    content = _build_managed_content(
        project_name="test",
        atlas_content="IDENTITY: Test",
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    assert "codrag-onboard" in content
    assert "MCP Prompts" in content


def test_get_rules_atlas_hash_returns_cached_hash():
    """_get_rules_atlas_hash should return hash after _project_has_rules_file populates cache."""
    server = MCPServer.__new__(MCPServer)
    # Manually set up the hash cache as _project_has_rules_file would
    server._rules_atlas_hash_cache = {"proj-1": "abcdef123456"}
    assert server._get_rules_atlas_hash("proj-1") == "abcdef123456"
    assert server._get_rules_atlas_hash("proj-unknown") is None


def test_get_rules_atlas_hash_returns_none_without_cache():
    """_get_rules_atlas_hash returns None when cache doesn't exist."""
    server = MCPServer.__new__(MCPServer)
    assert server._get_rules_atlas_hash("proj-1") is None
