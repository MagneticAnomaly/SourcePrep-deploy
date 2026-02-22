"""
CoDRAG Embedding Model Benchmark
=================================

Compares code embedding models on a realistic test fixture with
known query→answer ground truth pairs.

Measures: Recall@1, Recall@3, Recall@5, MRR, query-embed latency,
and full-search latency. Reports p50/p95/p99 latency percentiles.

Usage:
    # Baseline (current NativeEmbedder: nomic-embed-text-v1.5 ONNX, CPU)
    python scripts/benchmark_embeddings.py

    # Three-tier comparison (native ONNX + nomic-embed-text + nomic-embed-code)
    # Requires: ollama running with both models pulled
    python scripts/benchmark_embeddings.py --three-tiers

    # With a specific Ollama model
    python scripts/benchmark_embeddings.py --ollama nomic-embed-text
    python scripts/benchmark_embeddings.py --ollama manutic/nomic-embed-code

    # With sentence-transformers model (CodeRankEmbed, Jina, etc.)
    python scripts/benchmark_embeddings.py --st nomic-ai/CodeRankEmbed

    # All available models
    python scripts/benchmark_embeddings.py --all

    # Save results to JSON for documentation
    python scripts/benchmark_embeddings.py --three-tiers --output results/three_tier_benchmark.json
"""

import argparse
import json
import shutil
import sys
import time
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# CoDRAG uses Python 3.10+ union syntax (X | None). Fail early with a clear message.
if sys.version_info < (3, 10):
    print(
        f"ERROR: Python {sys.version_info.major}.{sys.version_info.minor} detected. "
        f"This script requires Python 3.10+.\n"
        f"Run with the project venv:\n"
        f"  /Volumes/4TB-BAD/HumanAI/CoDRAG/.venv/bin/python scripts/benchmark_embeddings.py --three-tiers\n"
        f"  # or: source .venv/bin/activate && python scripts/benchmark_embeddings.py --three-tiers",
        file=sys.stderr,
    )
    sys.exit(1)

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from codrag.core import CodeIndex, NativeEmbedder
from codrag.core.embedder import Embedder, EmbeddingResult, OllamaEmbedder

# ---------------------------------------------------------------------------
# Ground truth: query → expected top-1 file (relative to fixture root)
# ---------------------------------------------------------------------------

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "embedding_benchmark"

GROUND_TRUTH: List[Dict[str, str]] = [
    # --- Original 15 queries (10 files) ---
    {"query": "how does user authentication work", "expected_file": "src/auth.py"},
    {"query": "database connection pooling", "expected_file": "src/database.py"},
    {"query": "create a new user via the API", "expected_file": "src/api.py"},
    {"query": "password hashing", "expected_file": "src/auth.py"},
    {"query": "LRU cache implementation", "expected_file": "src/cache.py"},
    {"query": "retry on failure decorator", "expected_file": "src/utils.py"},
    {"query": "user data model fields", "expected_file": "src/models.py"},
    {"query": "run database migrations", "expected_file": "src/migrations.py"},
    {"query": "test user login", "expected_file": "tests/test_auth.py"},
    {"query": "API endpoint for deleting users", "expected_file": "src/api.py"},
    {"query": "configuration settings", "expected_file": "config.py"},
    {"query": "session management", "expected_file": "src/models.py"},
    {"query": "memoize function results", "expected_file": "src/cache.py"},
    {"query": "parse date string to datetime", "expected_file": "src/utils.py"},
    {"query": "user permissions and role based access control", "expected_file": "src/models.py"},
    # --- Expanded queries (12 new files) ---
    {"query": "rate limiting requests per client", "expected_file": "src/middleware.py"},
    {"query": "CORS middleware allowed origins whitelist", "expected_file": "src/middleware.py"},
    {"query": "validate email address format", "expected_file": "src/validation.py"},
    {"query": "password complexity requirements", "expected_file": "src/validation.py"},
    {"query": "serialize data to JSON with custom types", "expected_file": "src/serialization.py"},
    {"query": "export data to CSV format", "expected_file": "src/serialization.py"},
    {"query": "structured JSON log formatter", "expected_file": "src/logging_config.py"},
    {"query": "audit logger for login and permission change events", "expected_file": "src/logging_config.py"},
    {"query": "CLI argument parser for serve command", "expected_file": "src/cli.py"},
    {"query": "custom exception hierarchy with status codes", "expected_file": "src/errors.py"},
    {"query": "send email notification via SMTP", "expected_file": "src/notifications.py"},
    {"query": "webhook dispatch with retries", "expected_file": "src/notifications.py"},
    {"query": "schedule background job to run periodically", "expected_file": "src/scheduler.py"},
    {"query": "cancel a running scheduled task", "expected_file": "src/scheduler.py"},
    {"query": "TF-IDF full text search ranking", "expected_file": "src/search.py"},
    {"query": "cursor based pagination for API results", "expected_file": "src/pagination.py"},
    {"query": "event bus publish subscribe pattern", "expected_file": "src/events.py"},
    {"query": "database schema migration rollback", "expected_file": "src/migrations.py"},
    {"query": "health check readiness probe endpoint", "expected_file": "src/health.py"},
    {"query": "test rate limiter blocks excess requests", "expected_file": "tests/test_middleware.py"},
    {"query": "test input validation rejects bad email", "expected_file": "tests/test_validation.py"},
    {"query": "test scheduled job failure handling", "expected_file": "tests/test_scheduler.py"},
    {"query": "application architecture and request flow", "expected_file": "docs/ARCHITECTURE.md"},
    {"query": "deployment guide prerequisites and running locally", "expected_file": "docs/DEPLOYMENT.md"},
]


# ---------------------------------------------------------------------------
# Sentence-Transformers embedder adapter
# ---------------------------------------------------------------------------

class SentenceTransformerEmbedder(Embedder):
    """Adapter for sentence-transformers models to CoDRAG's Embedder interface."""

    def __init__(self, model_name: str, query_prefix: str = "", doc_prefix: str = ""):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("pip install sentence-transformers torch")

        print(f"  Loading {model_name} via sentence-transformers...")
        self.model = SentenceTransformer(model_name, trust_remote_code=True)
        self.model_name = model_name
        self.query_prefix = query_prefix
        self.doc_prefix = doc_prefix
        print(f"  Loaded. Dim={self.model.get_sentence_embedding_dimension()}")

    def embed(self, text: str) -> EmbeddingResult:
        prefixed = self.doc_prefix + text
        vec = self.model.encode(prefixed, normalize_embeddings=True)
        return EmbeddingResult(vector=vec.tolist(), model=self.model_name)

    def embed_query(self, text: str) -> EmbeddingResult:
        prefixed = self.query_prefix + text
        vec = self.model.encode(prefixed, normalize_embeddings=True)
        return EmbeddingResult(vector=vec.tolist(), model=self.model_name)

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        prefixed = [self.doc_prefix + t for t in texts]
        vecs = self.model.encode(prefixed, normalize_embeddings=True, batch_size=32)
        return [
            EmbeddingResult(vector=v.tolist(), model=self.model_name) for v in vecs
        ]


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def build_index(embedder: Any, label: str) -> CodeIndex:
    """Build a CoDRAG index from the benchmark fixture."""
    index_dir = FIXTURE_DIR / ".codrag" / f"bench_{label}"
    if index_dir.exists():
        shutil.rmtree(index_dir)

    idx = CodeIndex(index_dir=index_dir, embedder=embedder)
    idx.build(repo_root=FIXTURE_DIR)
    return idx


def _percentile(data: List[float], p: float) -> float:
    """Compute the p-th percentile of a sorted list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def run_benchmark(idx: CodeIndex, label: str, embedder: Any) -> Dict[str, Any]:
    """Run all ground truth queries and compute metrics.

    Measures two latency components separately:
    - embed_ms: time to embed the query string only
    - search_ms: full search including embed + cosine similarity + ranking
    """
    results = []
    embed_latencies: List[float] = []
    search_latencies: List[float] = []

    embed_fn = getattr(embedder, "embed_query", embedder.embed)

    for gt in GROUND_TRUTH:
        query = gt["query"]
        expected = gt["expected_file"]

        # Embed-only latency
        t0 = time.perf_counter()
        embed_fn(query)
        embed_latencies.append((time.perf_counter() - t0) * 1000)

        # Full search latency
        t0 = time.perf_counter()
        search_results = idx.search(query, k=10, min_score=0.0)
        search_latencies.append((time.perf_counter() - t0) * 1000)

        # Find rank of expected file
        rank = None
        result_files = []
        for i, sr in enumerate(search_results):
            sp = sr.doc.get("source_path", "")
            result_files.append(sp)
            if sp == expected and rank is None:
                rank = i + 1  # 1-indexed

        top_scores = [sr.score for sr in search_results[:3]]
        results.append({
            "query": query,
            "expected": expected,
            "rank": rank,
            "top_result": result_files[0] if result_files else None,
            "top_3": result_files[:3],
            "top_score": search_results[0].score if search_results else 0.0,
            "top_3_scores": top_scores,
        })

    # Accuracy metrics
    n = len(results)
    recall_1 = sum(1 for r in results if r["rank"] == 1) / n
    recall_3 = sum(1 for r in results if r["rank"] is not None and r["rank"] <= 3) / n
    recall_5 = sum(1 for r in results if r["rank"] is not None and r["rank"] <= 5) / n
    mrr = statistics.mean(
        [1.0 / r["rank"] if r["rank"] is not None else 0.0 for r in results]
    )

    # Score distribution
    all_top_scores = [r["top_score"] for r in results if r["top_score"] > 0]

    return {
        "model": label,
        "recall_at_1": recall_1,
        "recall_at_3": recall_3,
        "recall_at_5": recall_5,
        "mrr": mrr,
        # Embed-only latency (query vector generation)
        "embed_p50_ms": _percentile(embed_latencies, 50),
        "embed_p95_ms": _percentile(embed_latencies, 95),
        "embed_p99_ms": _percentile(embed_latencies, 99),
        # Full search latency (embed + cosine sim + ranking)
        "search_p50_ms": _percentile(search_latencies, 50),
        "search_p95_ms": _percentile(search_latencies, 95),
        "search_p99_ms": _percentile(search_latencies, 99),
        # Score distribution
        "avg_top_score": statistics.mean(all_top_scores) if all_top_scores else 0.0,
        "min_top_score": min(all_top_scores) if all_top_scores else 0.0,
        "details": results,
    }


def print_results(result: Dict[str, Any]) -> None:
    """Pretty-print benchmark results."""
    n = len(GROUND_TRUTH)
    print(f"\n{'='*60}")
    print(f"Model: {result['model']}")
    print(f"{'='*60}")
    print(f"  Recall@1:  {result['recall_at_1']:.1%}  ({int(result['recall_at_1'] * n)}/{n})")
    print(f"  Recall@3:  {result['recall_at_3']:.1%}  ({int(result['recall_at_3'] * n)}/{n})")
    print(f"  Recall@5:  {result['recall_at_5']:.1%}  ({int(result['recall_at_5'] * n)}/{n})")
    print(f"  MRR:       {result['mrr']:.3f}")
    print(f"  Avg top-1 score:  {result['avg_top_score']:.3f}  (min: {result['min_top_score']:.3f})")
    print(f"  Embed latency:   p50={result['embed_p50_ms']:.1f}ms  p95={result['embed_p95_ms']:.1f}ms  p99={result['embed_p99_ms']:.1f}ms")
    print(f"  Search latency:  p50={result['search_p50_ms']:.1f}ms  p95={result['search_p95_ms']:.1f}ms  p99={result['search_p99_ms']:.1f}ms")

    # Show misses
    misses = [r for r in result["details"] if r["rank"] is None or r["rank"] > 5]
    if misses:
        print(f"\n  Misses (not in top 5):")
        for m in misses:
            print(f"    Query: {m['query']!r}")
            print(f"    Expected: {m['expected']} | Got: {m['top_result']}")
    else:
        print(f"\n  All queries found expected file in top 5!")


def print_comparison(all_results: List[Dict[str, Any]]) -> None:
    """Print side-by-side comparison table."""
    print(f"\n{'='*100}")
    print("COMPARISON SUMMARY")
    print(f"{'='*100}")
    print(f"{'Model':<40} {'R@1':>5} {'R@3':>5} {'R@5':>5} {'MRR':>6} {'Emb p50':>8} {'Emb p95':>8} {'Srch p50':>9} {'Srch p95':>9}")
    print("-" * 100)
    for r in sorted(all_results, key=lambda x: -x["mrr"]):
        print(
            f"{r['model']:<40} "
            f"{r['recall_at_1']:>4.0%} "
            f"{r['recall_at_3']:>4.0%} "
            f"{r['recall_at_5']:>4.0%} "
            f"{r['mrr']:>6.3f} "
            f"{r['embed_p50_ms']:>7.1f}ms "
            f"{r['embed_p95_ms']:>7.1f}ms "
            f"{r['search_p50_ms']:>8.1f}ms "
            f"{r['search_p95_ms']:>8.1f}ms"
        )
    print("-" * 100)
    print("  Emb = query-only embed time   Srch = full search (embed + cosine sim + ranking)")


# ---------------------------------------------------------------------------
# Model configurations
# ---------------------------------------------------------------------------

MODELS = {
    "native": {
        "label": "nomic-embed-text-v1.5 (ONNX, CPU)",
        "factory": lambda: NativeEmbedder(),
        "requires": "native",
        "tier": 3,
    },
    "nomic-text-ollama": {
        "label": "nomic-embed-text (Ollama)",
        "factory": lambda: OllamaEmbedder(model="nomic-embed-text"),
        "requires": "ollama",
        "tier": 2,
    },
    "nomic-code-ollama": {
        "label": "nomic-embed-code (7B, Ollama) [recommended]",
        "factory": lambda: OllamaEmbedder(model="manutic/nomic-embed-code"),
        "requires": "ollama",
        "tier": 1,
    },
    "nomic-v2-moe-ollama": {
        # Tested 2026-02-20: R@1=92.3%, MRR=0.957, embed_p50=97ms.
        # No ONNX export exists on HF (SafeTensors-only). v1.5 ONNX wins on
        # both accuracy (R@1 97.4%) and latency (6.9ms). Not the default.
        "label": "nomic-embed-text-v2-moe (Ollama)",
        "factory": lambda: OllamaEmbedder(model="nomic-embed-text-v2-moe"),
        "requires": "ollama",
        "tier": None,
    },
    "coderank": {
        "label": "CodeRankEmbed (137M, ST)",
        "factory": lambda: SentenceTransformerEmbedder(
            "nomic-ai/CodeRankEmbed",
            query_prefix="Represent this query for searching relevant code: ",
            doc_prefix="",
        ),
        "requires": "sentence-transformers",
        "tier": None,
    },
    "jina-code": {
        "label": "Jina Code V2 (137M, ST)",
        "factory": lambda: SentenceTransformerEmbedder(
            "jinaai/jina-embeddings-v2-base-code",
            query_prefix="",
            doc_prefix="",
        ),
        "requires": "sentence-transformers",
        "tier": None,
    },
}

# The three production tiers (native ONNX + Ollama text + Ollama code)
THREE_TIER_KEYS = ["native", "nomic-text-ollama", "nomic-code-ollama"]


def check_requirements(req: str) -> bool:
    """Check if a model's requirements are met."""
    if req == "native":
        return NativeEmbedder().is_available()
    elif req == "sentence-transformers":
        try:
            import sentence_transformers  # noqa: F401
            return True
        except ImportError:
            return False
    elif req == "ollama":
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CoDRAG Embedding Model Benchmark")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(MODELS.keys()),
        default=["native"],
        help="Models to benchmark (default: native)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Benchmark all available models",
    )
    parser.add_argument(
        "--three-tiers",
        action="store_true",
        dest="three_tiers",
        help="Run the three production tiers: ONNX (CPU), nomic-embed-text (Ollama), nomic-embed-code (Ollama)",
    )
    parser.add_argument(
        "--st",
        type=str,
        help="Benchmark a custom sentence-transformers model by name",
    )
    parser.add_argument(
        "--ollama",
        type=str,
        help="Benchmark a custom Ollama model by name",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Save results to JSON file",
    )
    args = parser.parse_args()

    if not FIXTURE_DIR.exists():
        print(f"ERROR: Fixture directory not found: {FIXTURE_DIR}")
        sys.exit(1)

    # Determine which models to run
    model_keys = []
    if args.all:
        model_keys = list(MODELS.keys())
    elif args.three_tiers:
        model_keys = THREE_TIER_KEYS
    else:
        model_keys = args.models

    all_results = []

    for key in model_keys:
        cfg = MODELS[key]
        print(f"\n--- Checking {cfg['label']} ---")

        if not check_requirements(cfg["requires"]):
            print(f"  SKIPPED: {cfg['requires']} not available")
            continue

        try:
            print(f"  Building index...")
            embedder = cfg["factory"]()
            start = time.time()
            idx = build_index(embedder, key)
            build_time = time.time() - start
            stats = idx.stats()
            print(f"  Index built: {stats.get('total_documents', 0)} chunks in {build_time:.1f}s")

            print(f"  Running queries...")
            result = run_benchmark(idx, cfg["label"], embedder)
            result["build_time_s"] = build_time
            result["total_chunks"] = stats.get("total_documents", 0)
            print_results(result)
            all_results.append(result)

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Custom sentence-transformers model
    if args.st:
        print(f"\n--- Custom ST: {args.st} ---")
        try:
            embedder = SentenceTransformerEmbedder(args.st)
            idx = build_index(embedder, args.st.replace("/", "_"))
            result = run_benchmark(idx, f"ST: {args.st}", embedder)
            print_results(result)
            all_results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Custom Ollama model
    if args.ollama:
        print(f"\n--- Custom Ollama: {args.ollama} ---")
        try:
            embedder = OllamaEmbedder(model=args.ollama)
            idx = build_index(embedder, args.ollama.replace("/", "_"))
            result = run_benchmark(idx, f"Ollama: {args.ollama}", embedder)
            print_results(result)
            all_results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Comparison
    if len(all_results) > 1:
        print_comparison(all_results)

    # Save results
    if args.output and all_results:
        # Strip detailed results for cleaner JSON
        summary = []
        for r in all_results:
            s = {k: v for k, v in r.items() if k != "details"}
            summary.append(s)
        output_path = Path(args.output)
        output_path.write_text(json.dumps(summary, indent=2))
        print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
