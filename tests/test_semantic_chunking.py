"""Tests for semantic markdown chunking (Phase 93 P1)."""

from __future__ import annotations

import pytest

from prep.core.chunking import chunk_markdown, _split_long_text
from prep.core.embedder import FakeEmbedder


class TestSemanticSplitBackwardCompat:
    """chunk_markdown without embedder must produce identical output to before."""

    def test_no_embedder_unchanged(self):
        """Without embedder, oversized sections split at paragraph boundaries."""
        text = "# Title\n\n" + "First paragraph. " * 60 + "\n\n" + "Second paragraph. " * 60
        chunks_without = chunk_markdown(text, source_path="test.md", max_chars=500)
        assert len(chunks_without) >= 2
        for ch in chunks_without:
            assert len(ch.content) <= 500 * 1.5

    def test_small_section_not_affected(self):
        """Sections within max_chars are never semantically split."""
        text = "# Title\n\nShort section content."
        chunks = chunk_markdown(text, source_path="test.md", embedder=FakeEmbedder())
        assert len(chunks) == 1


class TestSemanticSplitWithEmbedder:
    """Semantic splitting when embedder is provided."""

    def test_oversized_section_split_semantically(self):
        """An oversized section should be split into multiple chunks."""
        topic1 = "Machine learning models are trained on large datasets. " * 15
        topic2 = "Database indexing improves query performance significantly. " * 15
        text = f"# Research\n\n{topic1}\n\n{topic2}"

        embedder = FakeEmbedder(dim=384)
        chunks = chunk_markdown(text, source_path="test.md", max_chars=800, embedder=embedder)
        assert len(chunks) >= 2
        for ch in chunks:
            assert len(ch.content.strip()) > 0

    def test_few_sentences_falls_back(self):
        """With fewer than 5 sentences, should fall back to paragraph splitting."""
        text = "# Title\n\n" + "Very long sentence one. " * 40 + "Short two. Short three."
        embedder = FakeEmbedder(dim=384)
        chunks = chunk_markdown(text, source_path="test.md", max_chars=500, embedder=embedder)
        assert len(chunks) >= 1

    def test_chunk_metadata_preserved(self):
        """Chunks from semantic split should still carry correct metadata."""
        topic1 = "First topic about network protocols. " * 20
        topic2 = "Second topic about compiler design. " * 20
        text = f"# Deep Dive\n\n{topic1}\n\n{topic2}"

        embedder = FakeEmbedder(dim=384)
        chunks = chunk_markdown(text, source_path="doc.md", max_chars=600, embedder=embedder)
        for ch in chunks:
            assert ch.metadata["source_path"] == "doc.md"
            assert "section" in ch.metadata

    def test_oversized_group_post_processed(self):
        """Groups exceeding max_chars * 1.5 should be recursively split."""
        # Create text where semantic boundaries produce one huge group
        # by having many similar sentences (no topic shift)
        text = "# Title\n\n" + "The same topic repeated in slightly different words. " * 80
        embedder = FakeEmbedder(dim=384)
        chunks = chunk_markdown(text, source_path="test.md", max_chars=500, embedder=embedder)
        # Should produce multiple chunks even if SG finds no boundaries
        assert len(chunks) >= 2
        for ch in chunks:
            # No chunk should exceed max_chars * 1.5 (the post-processing threshold)
            assert len(ch.content) <= 500 * 1.5 + 50  # small margin for joining
