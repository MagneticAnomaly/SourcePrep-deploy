"""
Tests for the IDENTITY-line brand-drift fix on `CodebaseAtlas`
(see docs/Phase82_MCP-Dogfooding/17_Followup_2026-05-08.md).

The atlas's structural section emitted "IDENTITY: <project_root.name>" —
which on this repo is a stale codename. The user-facing product name
differs. When callers pass `project_name`, the atlas must prefer
it over the filesystem basename so the live atlas stops surfacing the
stale codename.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from prep.core.atlas.generator import CodebaseAtlas


def _stats() -> dict:
    return {
        "file_count": 1,
        "node_count": 1,
        "edge_count": 0,
        "languages": {"py": 1},
    }


def _build(atlas: CodebaseAtlas) -> str:
    return atlas._build_structural_content(_stats(), [], {}, [])


def test_identity_uses_project_name_when_provided():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp) / "CoDRAG"
        repo_root.mkdir()
        index_dir = Path(tmp) / "idx"
        index_dir.mkdir()

        atlas = CodebaseAtlas(
            index_dir, project_root=repo_root, project_name="SourcePrep",
        )
        content = _build(atlas)
        assert "IDENTITY: SourcePrep" in content
        # The stale codename must NOT survive in the IDENTITY line
        assert "IDENTITY: CoDRAG" not in content


def test_identity_falls_back_to_project_root_name_when_no_project_name():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp) / "MyProject"
        repo_root.mkdir()
        index_dir = Path(tmp) / "idx"
        index_dir.mkdir()

        atlas = CodebaseAtlas(index_dir, project_root=repo_root)
        content = _build(atlas)
        assert "IDENTITY: MyProject" in content


def test_identity_omitted_when_neither_provided():
    with tempfile.TemporaryDirectory() as tmp:
        index_dir = Path(tmp) / "idx"
        index_dir.mkdir()
        atlas = CodebaseAtlas(index_dir)
        content = _build(atlas)
        assert "IDENTITY:" not in content


def test_project_name_attr_persists():
    """Sanity: the constructor stores the param so downstream consumers
    (e.g. role projection, segmented atlas) can read it too."""
    atlas = CodebaseAtlas(Path("/tmp"), project_name="SourcePrep")
    assert atlas.project_name == "SourcePrep"
