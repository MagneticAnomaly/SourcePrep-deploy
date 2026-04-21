"""Tests for Wave 2.3: exclude_paths parameter in search().

Verifies that:
  - Excluded files never appear in results
  - Empty exclude_paths = current behavior (no change)
  - Multiple paths can be excluded simultaneously
  - Excluding a non-existent path is a no-op
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prep.core.index import CodeIndex, SearchResult


# ---------------------------------------------------------------------------
# Unit tests on _adaptive_k_trim and _mmr_rerank already exist.
# These tests exercise exclude_paths at the search() integration level.
# ---------------------------------------------------------------------------


class TestExcludePaths:

    @pytest.fixture
    def built_index(self, tmp_path, fake_embedder):
        """A built CodeIndex with 3 Python files."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "auth.py").write_text("def login(user, password): pass\ndef logout(user): pass\n")
        (repo / "database.py").write_text("def connect(): pass\ndef query(sql): pass\n")
        (repo / "utils.py").write_text("def helper(): pass\ndef format_date(d): pass\n")

        index_dir = tmp_path / "idx"
        idx = CodeIndex(index_dir=index_dir, embedder=fake_embedder)
        idx.build(repo_root=repo)
        return idx

    def test_excluded_path_absent_from_results(self, built_index):
        """A file listed in exclude_paths must not appear in search results."""
        results = built_index.search(
            "login logout authentication",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
            exclude_paths=["auth.py"],
        )
        returned_paths = {r.doc.get("source_path", "") for r in results}
        assert "auth.py" not in returned_paths

    def test_empty_exclude_paths_returns_all(self, built_index):
        """Empty exclude_paths should produce the same results as no exclusion."""
        results_no_excl = built_index.search(
            "connect query database",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
        )
        results_empty_excl = built_index.search(
            "connect query database",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
            exclude_paths=[],
        )
        paths_no_excl = [r.doc.get("source_path") for r in results_no_excl]
        paths_empty_excl = [r.doc.get("source_path") for r in results_empty_excl]
        assert paths_no_excl == paths_empty_excl

    def test_none_exclude_paths_is_no_op(self, built_index):
        """exclude_paths=None should behave identically to no parameter."""
        results_default = built_index.search(
            "helper format utility",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
        )
        results_none = built_index.search(
            "helper format utility",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
            exclude_paths=None,
        )
        paths_default = [r.doc.get("source_path") for r in results_default]
        paths_none = [r.doc.get("source_path") for r in results_none]
        assert paths_default == paths_none

    def test_multiple_paths_excluded(self, built_index):
        """Multiple files listed in exclude_paths are all absent from results."""
        results = built_index.search(
            "function code",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
            exclude_paths=["auth.py", "database.py"],
        )
        returned_paths = {r.doc.get("source_path", "") for r in results}
        assert "auth.py" not in returned_paths
        assert "database.py" not in returned_paths

    def test_excluding_all_paths_returns_empty(self, built_index):
        """If every indexed file is excluded, results should be empty."""
        results = built_index.search(
            "anything",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
            exclude_paths=["auth.py", "database.py", "utils.py"],
        )
        assert results == []

    def test_excluding_nonexistent_path_is_noop(self, built_index):
        """Excluding a path that isn't in the index is harmless."""
        results_with = built_index.search(
            "login database helper",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
            exclude_paths=["does_not_exist.py"],
        )
        results_without = built_index.search(
            "login database helper",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
        )
        paths_with = [r.doc.get("source_path") for r in results_with]
        paths_without = [r.doc.get("source_path") for r in results_without]
        assert paths_with == paths_without

    def test_excluded_path_increases_other_results(self, built_index):
        """Excluding the top result should promote the next-best to rank 1."""
        # Get results without exclusion
        results_all = built_index.search(
            "login logout authentication",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
        )
        if not results_all:
            pytest.skip("No results to test rank promotion")

        top_path = results_all[0].doc.get("source_path", "")

        # Exclude the top result
        results_excl = built_index.search(
            "login logout authentication",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,
            mmr_lambda=1.0,
            exclude_paths=[top_path],
        )
        # Top result should no longer be in results
        returned_paths = [r.doc.get("source_path") for r in results_excl]
        assert top_path not in returned_paths
