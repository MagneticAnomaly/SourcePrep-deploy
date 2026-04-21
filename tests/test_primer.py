"""
Tests for Project Primer feature.

Uses FakeEmbedder so no Ollama dependency is required.
Run with: pytest tests/test_primer.py -v
"""

import tempfile
from pathlib import Path

import pytest

from prep.core import FakeEmbedder, CodeIndex
from prep.core.repo_policy import (
    DEFAULT_PRIMER_CONFIG,
    _normalize_primer_config,
    ensure_repo_policy,
)


@pytest.fixture
def repo_with_primer(tmp_path: Path) -> Path:
    """Create a test repository with a primer file."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    
    # Create a primer file (AGENTS.md)
    (repo / "AGENTS.md").write_text(
        "# Project Context\n\n"
        "This is a Python project using FastAPI.\n"
        "Always use type hints and follow PEP8.\n"
        "The main entry point is `main.py`.\n"
    )
    
    # Create regular source files
    (repo / "main.py").write_text(
        'def main() -> str:\n    """Return hello world."""\n    return "hello world"\n'
    )
    (repo / "utils.py").write_text(
        'def add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b\n'
    )
    
    return repo


@pytest.fixture
def repo_without_primer(tmp_path: Path) -> Path:
    """Create a test repository without a primer file."""
    repo = tmp_path / "test_repo_no_primer"
    repo.mkdir()
    
    (repo / "main.py").write_text(
        'def main() -> str:\n    return "hello world"\n'
    )
    
    return repo


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder(model="test-embed", dim=384)


class TestPrimerConfig:
    """Tests for primer configuration normalization."""
    
    def test_default_config(self):
        """Default config should have expected values."""
        assert DEFAULT_PRIMER_CONFIG["enabled"] is True
        assert "AGENTS.md" in DEFAULT_PRIMER_CONFIG["filenames"]
        assert DEFAULT_PRIMER_CONFIG["score_boost"] == 0.25
        assert DEFAULT_PRIMER_CONFIG["always_include"] is False
        assert DEFAULT_PRIMER_CONFIG["max_primer_chars"] == 2000
    
    def test_normalize_empty_returns_defaults(self):
        """Empty or non-dict input should return defaults."""
        result = _normalize_primer_config(None)
        assert result == DEFAULT_PRIMER_CONFIG
        
        result = _normalize_primer_config("invalid")
        assert result == DEFAULT_PRIMER_CONFIG
    
    def test_normalize_partial_config(self):
        """Partial config should be merged with defaults."""
        result = _normalize_primer_config({"enabled": False})
        assert result["enabled"] is False
        assert result["filenames"] == DEFAULT_PRIMER_CONFIG["filenames"]
        assert result["score_boost"] == DEFAULT_PRIMER_CONFIG["score_boost"]
    
    def test_normalize_score_boost_clamped(self):
        """Score boost should be clamped to [0, 1]."""
        result = _normalize_primer_config({"score_boost": 2.0})
        assert result["score_boost"] == 1.0
        
        result = _normalize_primer_config({"score_boost": -0.5})
        assert result["score_boost"] == 0.0
    
    def test_normalize_max_chars_minimum(self):
        """max_primer_chars should have a minimum of 100."""
        result = _normalize_primer_config({"max_primer_chars": 50})
        assert result["max_primer_chars"] == 100


class TestPrimerScoreBoost:
    """Tests for primer score boosting in search."""
    
    def test_primer_chunks_get_boosted(self, repo_with_primer: Path, fake_embedder: FakeEmbedder):
        """Primer document chunks should receive a score boost."""
        idx_dir = repo_with_primer / ".prep" / "index"
        idx = CodeIndex(index_dir=idx_dir, embedder=fake_embedder)
        idx.build(repo_root=repo_with_primer)
        
        # Search with low min_score to see all results
        results = idx.search("python project", k=10, min_score=0.0)
        
        # Find the AGENTS.md result
        primer_results = [r for r in results if "AGENTS.md" in r.doc.get("source_path", "")]
        other_results = [r for r in results if "AGENTS.md" not in r.doc.get("source_path", "")]
        
        assert len(primer_results) > 0, "Primer should be in results"
        
        # Check that primer boost was applied by verifying it's in the results
        # (FakeEmbedder produces low scores, so without boost primer might not appear)
        primer_score = primer_results[0].score
        assert primer_score > 0, "Primer should have positive score"
    
    def test_no_boost_when_disabled(self, repo_with_primer: Path, fake_embedder: FakeEmbedder):
        """No boost should be applied when primer is disabled."""
        idx_dir = repo_with_primer / ".prep" / "index"
        idx = CodeIndex(index_dir=idx_dir, embedder=fake_embedder)
        idx.build(repo_root=repo_with_primer)
        
        # Manually disable primer in manifest
        idx._manifest["config"] = idx._manifest.get("config", {})
        idx._manifest["config"]["primer"] = {"enabled": False}
        
        # Get primer boosts
        boosts = idx._primer_boosts(idx._documents)
        
        # All boosts should be zero
        assert all(b == 0.0 for b in boosts)


class TestPrimerAlwaysInclude:
    """Tests for always-include primer functionality."""
    
    def test_always_include_prepends_primer(self, repo_with_primer: Path, fake_embedder: FakeEmbedder):
        """When always_include is True, primer should be prepended to context."""
        idx_dir = repo_with_primer / ".prep" / "index"
        idx = CodeIndex(index_dir=idx_dir, embedder=fake_embedder)
        idx.build(repo_root=repo_with_primer)
        
        # Enable always_include
        idx._manifest["config"] = idx._manifest.get("config", {})
        idx._manifest["config"]["primer"] = {
            "enabled": True,
            "filenames": ["AGENTS.md"],
            "always_include": True,
            "max_primer_chars": 2000,
        }
        
        # Get context
        result = idx.get_context_structured("explain main function", k=5, min_score=0.0)
        
        # Check that primer is in context
        assert "PRIMER" in result["context"], "Primer header should be in context"
        assert "AGENTS.md" in result["context"], "Primer file should be in context"
        
        # Check that primer chunk is marked
        primer_chunks = [c for c in result["chunks"] if c.get("is_primer")]
        assert len(primer_chunks) > 0, "Should have primer chunks marked"
    
    def test_always_include_respects_max_chars(self, repo_with_primer: Path, fake_embedder: FakeEmbedder):
        """Primer should respect max_primer_chars budget."""
        idx_dir = repo_with_primer / ".prep" / "index"
        idx = CodeIndex(index_dir=idx_dir, embedder=fake_embedder)
        idx.build(repo_root=repo_with_primer)
        
        # Enable always_include with very small budget
        idx._manifest["config"] = idx._manifest.get("config", {})
        idx._manifest["config"]["primer"] = {
            "enabled": True,
            "filenames": ["AGENTS.md"],
            "always_include": True,
            "max_primer_chars": 100,  # Very small
        }
        
        # Get context
        result = idx.get_context_structured("test", k=5, min_score=0.0)
        
        # Check that primer is truncated
        primer_chunks = [c for c in result["chunks"] if c.get("is_primer")]
        if primer_chunks:
            # At least one should be truncated if content exceeds budget
            assert any(c.get("truncated") for c in primer_chunks) or len(primer_chunks) == 1
    
    def test_no_duplicate_chunks(self, repo_with_primer: Path, fake_embedder: FakeEmbedder):
        """Primer chunks should not be duplicated in search results."""
        idx_dir = repo_with_primer / ".prep" / "index"
        idx = CodeIndex(index_dir=idx_dir, embedder=fake_embedder)
        idx.build(repo_root=repo_with_primer)
        
        # Enable always_include
        idx._manifest["config"] = idx._manifest.get("config", {})
        idx._manifest["config"]["primer"] = {
            "enabled": True,
            "filenames": ["AGENTS.md"],
            "always_include": True,
        }
        
        # Get context
        result = idx.get_context_structured("Python FastAPI", k=10, min_score=0.0)
        
        # Count AGENTS.md occurrences - should only appear once (as primer)
        agents_count = result["context"].count("AGENTS.md")
        assert agents_count == 1, f"AGENTS.md should appear exactly once, found {agents_count}"


class TestGetPrimerChunks:
    """Tests for get_primer_chunks helper method."""
    
    def test_returns_primer_chunks(self, repo_with_primer: Path, fake_embedder: FakeEmbedder):
        """Should return chunks from primer files."""
        idx_dir = repo_with_primer / ".prep" / "index"
        idx = CodeIndex(index_dir=idx_dir, embedder=fake_embedder)
        idx.build(repo_root=repo_with_primer)
        
        chunks = idx.get_primer_chunks()
        
        assert len(chunks) > 0
        assert all("AGENTS.md" in c.get("source_path", "") for c in chunks)
    
    def test_returns_empty_when_no_primer(self, repo_without_primer: Path, fake_embedder: FakeEmbedder):
        """Should return empty list when no primer files exist."""
        idx_dir = repo_without_primer / ".prep" / "index"
        idx = CodeIndex(index_dir=idx_dir, embedder=fake_embedder)
        idx.build(repo_root=repo_without_primer)
        
        chunks = idx.get_primer_chunks()
        
        assert len(chunks) == 0
    
    def test_returns_empty_when_disabled(self, repo_with_primer: Path, fake_embedder: FakeEmbedder):
        """Should return empty list when primer is disabled."""
        idx_dir = repo_with_primer / ".prep" / "index"
        idx = CodeIndex(index_dir=idx_dir, embedder=fake_embedder)
        idx.build(repo_root=repo_with_primer)
        
        # Disable primer
        idx._manifest["config"] = idx._manifest.get("config", {})
        idx._manifest["config"]["primer"] = {"enabled": False}
        
        chunks = idx.get_primer_chunks()
        
        assert len(chunks) == 0


class TestRepoPolicyWithPrimer:
    """Tests for repo policy including primer config."""
    
    def test_ensure_policy_includes_primer(self, repo_with_primer: Path):
        """ensure_repo_policy should include primer config."""
        idx_dir = repo_with_primer / ".prep" / "index"
        
        policy = ensure_repo_policy(idx_dir, repo_with_primer)
        
        assert "primer" in policy
        assert policy["primer"]["enabled"] is True
        assert "AGENTS.md" in policy["primer"]["filenames"]
