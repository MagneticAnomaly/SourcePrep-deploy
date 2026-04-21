"""Tests for contextual retrieval (Phase 93 P2)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from prep.core.chunking import Chunk
from prep.core.index import CodeIndex


class TestTier1SynopsisPrefix:
    """P2 Tier 1: file synopsis prepended to chunk embedding text."""

    def test_synopsis_included_in_embedding_text(self):
        """When file_synopsis is provided, it appears in the formatted text."""
        idx = CodeIndex.__new__(CodeIndex)  # avoid __init__ side effects
        chunk = Chunk(
            chunk_id="abc123",
            content="for ch in chunks: text = self._format(ch)",
            metadata={"source_path": "src/prep/core/index.py", "section": "build"},
        )
        result = idx._format_chunk_for_embedding(
            chunk, file_hash="deadbeef",
            file_synopsis="File: src/prep/core/index.py\nPurpose: Core search index\nClasses: CodeIndex"
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


class TestTier2EpistemicContext:
    """P2 Tier 2: epistemic metadata synthesized as context prefix."""

    def _make_epistemic_file(self, tmpdir: Path, entries: list) -> Path:
        path = tmpdir / "trace_epistemic.jsonl"
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return path

    def _make_augmented_file(self, tmpdir: Path, entries: list) -> Path:
        path = tmpdir / "trace_augmented.jsonl"
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return path

    def test_epistemic_context_in_document_content(self):
        """Epistemic docs should include synthesized context prefix."""
        from prep.core.knowledge import KnowledgeIndex
        from prep.core.embedder import FakeEmbedder

        with tempfile.TemporaryDirectory() as tmpdir:
            idx_dir = Path(tmpdir)
            self._make_augmented_file(idx_dir, [
                {"node_id": "src/foo.py", "summary": "Handles requests", "role": "handler"},
            ])
            self._make_epistemic_file(idx_dir, [
                {
                    "node_id": "src/foo.py",
                    "extended_summary": "Request handler for the API gateway",
                    "domain_tags": ["api", "networking"],
                    "architecture_layer": "presentation",
                    "subsystem": "gateway",
                    "design_patterns": ["adapter", "facade"],
                },
            ])

            ki = KnowledgeIndex(index_dir=idx_dir, embedder=FakeEmbedder())
            result = ki.build()

            assert result["count"] > 0
            ep_docs = [d for d in ki._documents if d["type"] == "epistemic"]
            assert len(ep_docs) == 1
            content = ep_docs[0]["content"]
            assert "presentation" in content.lower() or "Architecture" in content
            assert "gateway" in content.lower() or "Subsystem" in content
            assert "adapter" in content.lower() or "Patterns" in content

    def test_missing_fields_graceful(self):
        """Epistemic entry with missing optional fields should still work."""
        from prep.core.knowledge import KnowledgeIndex
        from prep.core.embedder import FakeEmbedder

        with tempfile.TemporaryDirectory() as tmpdir:
            idx_dir = Path(tmpdir)
            self._make_augmented_file(idx_dir, [
                {"node_id": "src/bar.py", "summary": "Utility functions", "role": "util"},
            ])
            self._make_epistemic_file(idx_dir, [
                {
                    "node_id": "src/bar.py",
                    "extended_summary": "Collection of utility functions",
                    "domain_tags": ["utilities"],
                    "architecture_layer": "infrastructure",
                    # No subsystem, no design_patterns
                },
            ])

            ki = KnowledgeIndex(index_dir=idx_dir, embedder=FakeEmbedder())
            result = ki.build()

            ep_docs = [d for d in ki._documents if d["type"] == "epistemic"]
            assert len(ep_docs) == 1
            content = ep_docs[0]["content"]
            assert "infrastructure" in content.lower() or "Architecture" in content
            assert "None" not in content
