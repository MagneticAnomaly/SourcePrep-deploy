"""Tests for atlas content hash embedding and extraction."""
import hashlib

from codrag.core.rules_generator import _build_managed_content
from codrag.mcp.server import MCPServer


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
