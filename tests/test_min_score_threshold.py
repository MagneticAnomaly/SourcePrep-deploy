"""Wave 1.2: min_score threshold analysis.

Answers the research question: are real relevant results above 0.25, or do
legitimate matches cluster between 0.15–0.25 (which would make raising the
default risky)?

Uses the embedding_benchmark fixture (10 files, 15 known queries) to:
  - Verify that all ground-truth expected files score > 0.15 at their query
  - Verify that most score > 0.25 (supporting a raise)
  - Verify that non-relevant queries produce mostly < 0.25 scores
  - Quantify how many results are lost when raising threshold 0.15→0.25
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from prep.core import CodeIndex, NativeEmbedder
from prep.core.embedder import FakeEmbedder

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "embedding_benchmark"

GROUND_TRUTH = [
    {"query": "how does user authentication work", "expected_file": "src/auth.py"},
    {"query": "database connection pooling", "expected_file": "src/database.py"},
    {"query": "create a new user via the API", "expected_file": "src/api.py"},
    {"query": "password hashing", "expected_file": "src/auth.py"},
    {"query": "LRU cache implementation", "expected_file": "src/cache.py"},
    {"query": "retry on failure decorator", "expected_file": "src/utils.py"},
    {"query": "user data model fields", "expected_file": "src/models.py"},
    {"query": "run database migrations", "expected_file": "src/database.py"},
    {"query": "test user login", "expected_file": "tests/test_auth.py"},
    {"query": "API endpoint for deleting users", "expected_file": "src/api.py"},
    {"query": "configuration settings", "expected_file": "config.py"},
    {"query": "session management", "expected_file": "src/models.py"},
    {"query": "memoize function results", "expected_file": "src/cache.py"},
    {"query": "parse date string to datetime", "expected_file": "src/utils.py"},
    {"query": "permission checking", "expected_file": "src/models.py"},
]


@pytest.fixture(scope="module")
def benchmark_index(tmp_path_factory):
    """Build a NativeEmbedder-backed index from the benchmark fixture."""
    if not FIXTURE_DIR.exists():
        pytest.skip("Embedding benchmark fixture not found")
    native = NativeEmbedder()
    if not native.is_available():
        pytest.skip("NativeEmbedder deps not installed (onnxruntime, tokenizers, huggingface-hub)")
    idx_dir = tmp_path_factory.mktemp("bench_idx")
    idx = CodeIndex(index_dir=idx_dir, embedder=native)
    idx.build(repo_root=FIXTURE_DIR)
    return idx


class TestMinScoreThreshold:

    def test_ground_truth_files_score_above_015(self, benchmark_index):
        """All known-relevant files must appear in top-10 with score > 0.15."""
        failures = []
        for gt in GROUND_TRUTH:
            results = benchmark_index.search(gt["query"], k=10, min_score=0.0)
            matching = [r for r in results if r.doc.get("source_path") == gt["expected_file"]]
            if not matching or max(r.score for r in matching) <= 0.15:
                best_score = max((r.score for r in matching), default=0.0)
                failures.append(f"{gt['query']!r} → {gt['expected_file']} (score={best_score:.3f})")
        assert not failures, f"Expected files scored ≤ 0.15:\n" + "\n".join(failures)

    def test_majority_of_ground_truth_score_above_025(self, benchmark_index):
        """At least 80% of known-relevant files should score > 0.25 (supports raising default)."""
        above_025 = 0
        for gt in GROUND_TRUTH:
            results = benchmark_index.search(gt["query"], k=10, min_score=0.0)
            matching = [r for r in results if r.doc.get("source_path") == gt["expected_file"]]
            if matching and max(r.score for r in matching) > 0.25:
                above_025 += 1
        ratio = above_025 / len(GROUND_TRUTH)
        assert ratio >= 0.80, (
            f"Only {above_025}/{len(GROUND_TRUTH)} ({ratio:.0%}) of ground-truth files score > 0.25. "
            f"Raising min_score to 0.25 would lose too many valid results."
        )

    def test_raising_threshold_does_not_eliminate_top_results(self, benchmark_index):
        """Raising min_score 0.15→0.25 should NOT eliminate the top-1 result for any GT query."""
        eliminated = []
        for gt in GROUND_TRUTH:
            results_low = benchmark_index.search(gt["query"], k=10, min_score=0.15)
            results_high = benchmark_index.search(gt["query"], k=10, min_score=0.25)
            if results_low and results_low[0].doc.get("source_path") == gt["expected_file"]:
                if not results_high or results_high[0].doc.get("source_path") != gt["expected_file"]:
                    eliminated.append(gt["query"])
        assert not eliminated, (
            f"Raising min_score to 0.25 eliminated top-1 GT result for:\n" +
            "\n".join(f"  {q!r}" for q in eliminated)
        )

    def test_low_min_score_result_count_vs_high(self, benchmark_index):
        """Report how many results are lost when raising threshold 0.15→0.25 (diagnostic)."""
        total_low = 0
        total_high = 0
        for gt in GROUND_TRUTH:
            total_low += len(benchmark_index.search(gt["query"], k=10, min_score=0.15))
            total_high += len(benchmark_index.search(gt["query"], k=10, min_score=0.25))
        # Just a smoke test — should not lose more than 50% of results
        assert total_high >= total_low * 0.5, (
            f"Raising threshold 0.15→0.25 cuts results from {total_low} to {total_high} "
            f"({total_high/total_low:.0%} retained) — too aggressive."
        )

    def test_irrelevant_query_produces_low_scores(self, benchmark_index):
        """A nonsensical query should not produce high-scoring results."""
        results = benchmark_index.search(
            "xyzzy flibbertigibbet quantum entanglement chocolate",
            k=5,
            min_score=0.0,
        )
        if results:
            # Top result should be low-confidence — not > 0.6 for a nonsense query
            assert results[0].score < 0.6, (
                f"Nonsense query got unexpectedly high score: {results[0].score:.3f} "
                f"for {results[0].doc.get('source_path')}"
            )

    def test_score_distribution_is_discriminative(self, benchmark_index):
        """The gap between the best-query top score and worst-query top score should be small.

        If the model is discriminative, all GT queries should produce a good top-1 score.
        A very low top-1 score on any GT query indicates the index may be misconfigured.
        """
        top_scores = []
        for gt in GROUND_TRUTH:
            results = benchmark_index.search(gt["query"], k=1, min_score=0.0)
            if results:
                top_scores.append(results[0].score)
        assert top_scores, "No results for any query"
        min_top = min(top_scores)
        assert min_top > 0.30, (
            f"Worst top-1 score across GT queries is {min_top:.3f} — below 0.30 suggests "
            f"the index or embedder may not be functioning correctly."
        )
