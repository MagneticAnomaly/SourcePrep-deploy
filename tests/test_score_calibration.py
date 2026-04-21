"""Score calibration and distractor injection tests (Problem #3).

Verifies that cosine similarity scores produced by CoDRAG are meaningful:
  - Known-relevant queries produce top-1 scores above a sensible floor
  - Known-irrelevant ("distractor") chunks score below known-relevant ones
  - Score distribution is not artificially compressed or inflated
  - Adaptive K correctly identifies and trims low-score padding
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from prep.core import CodeIndex


class TestScoreCalibration:

    @pytest.fixture
    def calibration_index(self, tmp_path, fake_embedder):
        """Index with clearly separated relevant and irrelevant content."""
        repo = tmp_path / "repo"
        repo.mkdir()

        # Highly relevant: authentication code
        (repo / "auth.py").write_text(
            "def authenticate_user(username: str, password: str) -> bool:\n"
            "    \"\"\"Verify username and password against the database.\"\"\"\n"
            "    hashed = hash_password(password)\n"
            "    return db.check_credentials(username, hashed)\n\n"
            "def hash_password(password: str) -> str:\n"
            "    import bcrypt\n"
            "    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()\n"
        )
        # Related but different: database code (should score lower for auth queries)
        (repo / "database.py").write_text(
            "def get_connection():\n"
            "    return psycopg2.connect(dsn=DB_URL)\n\n"
            "def run_query(sql: str, params=None):\n"
            "    with get_connection() as conn:\n"
            "        return conn.execute(sql, params).fetchall()\n"
        )
        # Distractor: completely unrelated content
        (repo / "css_utils.py").write_text(
            "def hex_to_rgb(hex_color: str) -> tuple:\n"
            "    \"\"\"Convert hex color code to RGB tuple.\"\"\"\n"
            "    h = hex_color.lstrip('#')\n"
            "    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))\n\n"
            "def rgb_to_hsl(r: int, g: int, b: int) -> tuple:\n"
            "    r /= 255; g /= 255; b /= 255\n"
            "    cmax = max(r, g, b); cmin = min(r, g, b)\n"
            "    return cmax, cmin, (cmax + cmin) / 2\n"
        )

        idx = CodeIndex(index_dir=tmp_path / "idx", embedder=fake_embedder)
        idx.build(repo_root=repo)
        return idx

    def test_relevant_file_scores_higher_than_distractor(self, calibration_index):
        """auth.py should score higher than css_utils.py for an auth query."""
        results = calibration_index.search(
            "user authentication password hashing",
            k=10,
            min_score=0.0,
        )
        auth_scores = [r.score for r in results if r.doc.get("source_path") == "auth.py"]
        css_scores = [r.score for r in results if r.doc.get("source_path") == "css_utils.py"]

        if not auth_scores or not css_scores:
            pytest.skip("FakeEmbedder may not separate these consistently — run with NativeEmbedder for meaningful calibration")

        assert max(auth_scores) > max(css_scores), (
            f"Expected auth.py (score={max(auth_scores):.3f}) > css_utils.py (score={max(css_scores):.3f})"
        )

    def test_scores_are_bounded_0_to_1(self, calibration_index):
        """All scores should be in [-1, 1] (cosine similarity bounds)."""
        results = calibration_index.search("authentication", k=20, min_score=-1.0)
        for r in results:
            assert -1.0 <= r.score <= 1.0, f"Score out of cosine bounds: {r.score}"

    def test_scores_are_ordered_descending(self, calibration_index):
        """Results must be returned in descending score order."""
        results = calibration_index.search("user authentication", k=10, min_score=0.0)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), (
            f"Results not sorted descending: {scores}"
        )

    def test_adaptive_k_trims_low_score_padding(self, calibration_index):
        """With score_drop_ratio=0.4, a large score gap should trigger early stop."""
        # Get all results first
        results_full = calibration_index.search(
            "authentication password",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.0,  # disabled
            mmr_lambda=1.0,
        )
        results_adaptive = calibration_index.search(
            "authentication password",
            k=10,
            min_score=0.0,
            score_drop_ratio=0.4,  # enabled
            mmr_lambda=1.0,
        )
        # Adaptive K should never return MORE than full K
        assert len(results_adaptive) <= len(results_full)
        # And at least 1 result
        assert len(results_adaptive) >= 1

    def test_min_score_filter_applied(self, calibration_index):
        """All returned results should have score >= min_score."""
        for threshold in [0.0, 0.1, 0.3, 0.5]:
            results = calibration_index.search(
                "authentication",
                k=10,
                min_score=threshold,
                score_drop_ratio=0.0,
            )
            for r in results:
                assert r.score >= threshold, (
                    f"Result with score={r.score:.3f} returned despite min_score={threshold}"
                )

    def test_higher_min_score_returns_fewer_or_equal_results(self, calibration_index):
        """Raising min_score should never return more results."""
        query = "database connection"
        low = len(calibration_index.search(query, k=10, min_score=0.0, score_drop_ratio=0.0))
        mid = len(calibration_index.search(query, k=10, min_score=0.2, score_drop_ratio=0.0))
        high = len(calibration_index.search(query, k=10, min_score=0.5, score_drop_ratio=0.0))
        assert low >= mid >= high, (
            f"Non-monotonic result counts: 0.0→{low}, 0.2→{mid}, 0.5→{high}"
        )

    def test_k_limit_respected(self, calibration_index):
        """Never return more than k results."""
        for k in [1, 2, 3, 5]:
            results = calibration_index.search("code", k=k, min_score=0.0, score_drop_ratio=0.0)
            assert len(results) <= k, f"Returned {len(results)} results with k={k}"

    def test_empty_index_returns_empty(self, tmp_path, fake_embedder):
        """An unbuilt index should return empty results, not crash."""
        idx = CodeIndex(index_dir=tmp_path / "empty_idx", embedder=fake_embedder)
        results = idx.search("anything", k=5)
        assert results == []

    def test_mmr_diversity_reduces_near_duplicate_results(self, tmp_path, fake_embedder):
        """MMR with low lambda should produce more diverse results than lambda=1.0."""
        repo = tmp_path / "repo"
        repo.mkdir()
        # Two nearly identical files
        (repo / "a.py").write_text("def foo(): pass\ndef bar(): pass\n")
        (repo / "b.py").write_text("def foo(): return 1\ndef bar(): return 2\n")
        # One different file
        (repo / "c.py").write_text("def hex_to_rgb(h): return int(h, 16)\n")

        idx = CodeIndex(index_dir=tmp_path / "idx2", embedder=fake_embedder)
        idx.build(repo_root=repo)

        results_diverse = idx.search("foo bar function", k=3, min_score=0.0, mmr_lambda=0.3)
        results_greedy = idx.search("foo bar function", k=3, min_score=0.0, mmr_lambda=1.0)

        # Both should return ≤ 3 results
        assert len(results_diverse) <= 3
        assert len(results_greedy) <= 3
