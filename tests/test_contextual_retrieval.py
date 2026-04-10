"""Tests for contextual retrieval (Phase 93 P2)."""

from __future__ import annotations

from codrag.core.chunking import Chunk
from codrag.core.index import CodeIndex


class TestTier1SynopsisPrefix:
    """P2 Tier 1: file synopsis prepended to chunk embedding text."""

    def test_synopsis_included_in_embedding_text(self):
        """When file_synopsis is provided, it appears in the formatted text."""
        idx = CodeIndex.__new__(CodeIndex)  # avoid __init__ side effects
        chunk = Chunk(
            chunk_id="abc123",
            content="for ch in chunks: text = self._format(ch)",
            metadata={"source_path": "src/codrag/core/index.py", "section": "build"},
        )
        result = idx._format_chunk_for_embedding(
            chunk, file_hash="deadbeef",
            file_synopsis="File: src/codrag/core/index.py\nPurpose: Core search index\nClasses: CodeIndex"
        )
        assert "File context:" in result
        assert "Core search index" in result
        assert "for ch in chunks" in result

    def test_no_synopsis_unchanged(self):
        """Without file_synopsis, output is identical to previous behavior."""
        idx = CodeIndex.__new__(CodeIndex)
        chunk = Chunk(
            chunk_id="abc123",
            content="some code here",
            metadata={"source_path": "foo.py", "section": ""},
        )
        result_without = idx._format_chunk_for_embedding(chunk, file_hash="deadbeef")
        result_empty = idx._format_chunk_for_embedding(chunk, file_hash="deadbeef", file_synopsis="")
        assert result_without == result_empty
        assert "File context:" not in result_without

    def test_meta_synopsis_chunk_excluded(self):
        """META_SYNOPSIS chunks should NOT get the synopsis prefix (circular)."""
        idx = CodeIndex.__new__(CodeIndex)
        chunk = Chunk(
            chunk_id="abc123",
            content="File: index.py\nPurpose: search",
            metadata={"source_path": "index.py", "section": "META_SYNOPSIS"},
        )
        result = idx._format_chunk_for_embedding(
            chunk, file_hash="deadbeef",
            file_synopsis="File: index.py\nPurpose: search"
        )
        assert "File context:" not in result
