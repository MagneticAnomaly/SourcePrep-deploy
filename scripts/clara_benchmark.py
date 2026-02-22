#!/usr/bin/env python3
"""
CLaRa Compression Benchmark for CoDRAG — Phase 31

End-to-end benchmark that:
1. Connects to a running CoDRAG daemon + CLaRa server
2. Runs test queries at varying K / max_chars / max_new_tokens configs
3. Compares compressed vs uncompressed context quality
4. Saves raw results as JSON for downstream analysis

Usage:
    # Basic (requires CoDRAG daemon on :8400 + CLaRa on :8765)
    python scripts/clara_benchmark.py

    # Custom endpoints
    python scripts/clara_benchmark.py --codrag-url http://localhost:8400 --clara-url http://localhost:8765

    # Specific project
    python scripts/clara_benchmark.py --project-id my-project

    # Quick smoke test (2 queries, 1 config)
    python scripts/clara_benchmark.py --quick
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clara_benchmark")

# ---------------------------------------------------------------------------
# Test queries — designed to exercise different information needs
# ---------------------------------------------------------------------------

TEST_QUERIES: List[Dict[str, str]] = [
    {
        "id": "Q1",
        "query": "How does the trace builder work?",
        "type": "architectural",
        "expected_files": "trace.py",
    },
    {
        "id": "Q2",
        "query": "What happens when a file changes and the watcher triggers a rebuild?",
        "type": "multi-hop",
        "expected_files": "watcher, build_manager, index",
    },
    {
        "id": "Q3",
        "query": "Show me how CLaRa compression is integrated into the context endpoint",
        "type": "factual",
        "expected_files": "compressor.py, projects.py",
    },
    {
        "id": "Q4",
        "query": "How do path weights affect search results?",
        "type": "detailed",
        "expected_files": "index.py, repo_policy.py",
    },
    {
        "id": "Q5",
        "query": "What is the full pipeline from project creation to first search result?",
        "type": "breadth",
        "expected_files": "multiple (10+)",
    },
    {
        "id": "Q6",
        "query": "Debug: why might search return 0 results for a valid query?",
        "type": "debugging",
        "expected_files": "embedder, index, min_score",
    },
    {
        "id": "Q7",
        "query": "How does the MCP server route tool calls to the correct project?",
        "type": "integration",
        "expected_files": "mcp_server.py, mcp_tools.py",
    },
    {
        "id": "Q8",
        "query": "What are all the Pydantic request/response models used in the API?",
        "type": "enumeration",
        "expected_files": "all routers",
    },
    {
        "id": "Q9",
        "query": "Explain the epistemic scoring system and how scores are computed",
        "type": "domain-specific",
        "expected_files": "epistemic_score.py, epistemic_enrichment.py",
    },
    {
        "id": "Q10",
        "query": "How does atlas routing work to scope retrieval to subsystems?",
        "type": "complex",
        "expected_files": "atlas.py, index.py, projects.py",
    },
]

# ---------------------------------------------------------------------------
# Configuration matrix
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkConfig:
    """A single benchmark configuration to test."""
    name: str
    k: int
    max_chars: int
    compression: str  # "none" or "clara"
    compression_target_chars: int = 0
    max_new_tokens: int = 128
    trace_expand: bool = False
    trace_max_chars: int = 2000
    min_score: float = 0.15


DEFAULT_CONFIGS: List[BenchmarkConfig] = [
    # Baseline: current defaults, no compression
    BenchmarkConfig(
        name="baseline_k5",
        k=5, max_chars=6000, compression="none",
    ),
    BenchmarkConfig(
        name="baseline_k5_trace",
        k=5, max_chars=6000, compression="none",
        trace_expand=True, trace_max_chars=2000,
    ),

    # CLaRa: moderate expansion
    BenchmarkConfig(
        name="clara_k15",
        k=15, max_chars=20000, compression="clara",
        compression_target_chars=6000, max_new_tokens=256,
    ),
    BenchmarkConfig(
        name="clara_k15_trace",
        k=15, max_chars=20000, compression="clara",
        compression_target_chars=6000, max_new_tokens=256,
        trace_expand=True, trace_max_chars=8000,
    ),

    # CLaRa: full expansion
    BenchmarkConfig(
        name="clara_k30",
        k=30, max_chars=40000, compression="clara",
        compression_target_chars=6000, max_new_tokens=512,
    ),
    BenchmarkConfig(
        name="clara_k30_trace",
        k=30, max_chars=40000, compression="clara",
        compression_target_chars=6000, max_new_tokens=512,
        trace_expand=True, trace_max_chars=15000,
    ),

    # CLaRa: aggressive expansion
    BenchmarkConfig(
        name="clara_k50",
        k=50, max_chars=60000, compression="clara",
        compression_target_chars=6000, max_new_tokens=512,
    ),

    # CLaRa: max_new_tokens sweep (with K=30)
    BenchmarkConfig(
        name="clara_k30_tokens128",
        k=30, max_chars=40000, compression="clara",
        compression_target_chars=6000, max_new_tokens=128,
    ),
    BenchmarkConfig(
        name="clara_k30_tokens1024",
        k=30, max_chars=40000, compression="clara",
        compression_target_chars=6000, max_new_tokens=1024,
    ),
]

QUICK_CONFIGS: List[BenchmarkConfig] = [
    DEFAULT_CONFIGS[0],  # baseline_k5
    DEFAULT_CONFIGS[4],  # clara_k30
]


# ---------------------------------------------------------------------------
# Result structures
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Result of a single query under a single config."""
    query_id: str
    query_text: str
    query_type: str
    config_name: str

    # Raw response data
    context_text: str = ""
    context_chars: int = 0
    context_tokens_est: int = 0  # chars / 4 rough estimate

    # Compression metadata (if applicable)
    compression_enabled: bool = False
    compression_input_chars: int = 0
    compression_output_chars: int = 0
    compression_ratio: float = 1.0
    compression_time_ms: float = 0.0
    compression_error: Optional[str] = None

    # Performance
    total_time_ms: float = 0.0
    search_time_ms: float = 0.0

    # Quality signals
    num_files_referenced: int = 0
    file_paths_found: List[str] = field(default_factory=list)

    # Raw API response for debugging
    raw_response: Dict[str, Any] = field(default_factory=dict)

    error: Optional[str] = None


@dataclass
class BenchmarkRun:
    """Complete benchmark run metadata + results."""
    timestamp: str
    codrag_url: str
    clara_url: str
    project_id: str
    clara_available: bool
    codrag_healthy: bool
    results: List[Dict[str, Any]] = field(default_factory=list)
    configs_tested: int = 0
    queries_tested: int = 0
    total_duration_s: float = 0.0


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

class ClaraBenchmark:
    """Runs the full CLaRa compression benchmark suite."""

    def __init__(
        self,
        codrag_url: str = "http://localhost:8400",
        clara_url: str = "http://localhost:8765",
        project_id: str = "",
        timeout_s: float = 120.0,
    ):
        self.codrag_url = codrag_url.rstrip("/")
        self.clara_url = clara_url.rstrip("/")
        self.project_id = project_id
        self.timeout_s = timeout_s

    # --- Health checks ---

    def check_codrag(self) -> bool:
        """Check if CoDRAG daemon is reachable."""
        try:
            r = requests.get(f"{self.codrag_url}/health", timeout=5)
            return r.status_code == 200
        except Exception as e:
            logger.error("CoDRAG daemon not reachable at %s: %s", self.codrag_url, e)
            return False

    def check_clara(self) -> bool:
        """Check if CLaRa server is reachable."""
        try:
            r = requests.get(f"{self.clara_url}/health", timeout=5)
            return r.status_code == 200
        except Exception as e:
            logger.warning("CLaRa server not reachable at %s: %s", self.clara_url, e)
            return False

    def resolve_project(self) -> str:
        """Resolve or auto-detect the project ID."""
        if self.project_id:
            return self.project_id
        try:
            r = requests.get(f"{self.codrag_url}/projects", timeout=10)
            data = r.json()
            projects = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(projects, list) and projects:
                pid = projects[0].get("id", "")
                logger.info("Auto-detected project: %s", pid)
                return pid
            elif isinstance(projects, dict):
                # might be wrapped
                for v in projects.values():
                    if isinstance(v, list) and v:
                        pid = v[0].get("id", "")
                        logger.info("Auto-detected project: %s", pid)
                        return pid
        except Exception as e:
            logger.error("Failed to list projects: %s", e)
        return ""

    # --- Core query execution ---

    def run_query(
        self,
        project_id: str,
        query: Dict[str, str],
        config: BenchmarkConfig,
    ) -> QueryResult:
        """Execute a single query under a single config."""
        result = QueryResult(
            query_id=query["id"],
            query_text=query["query"],
            query_type=query["type"],
            config_name=config.name,
        )

        payload: Dict[str, Any] = {
            "query": query["query"],
            "k": config.k,
            "max_chars": config.max_chars,
            "min_score": config.min_score,
            "compression": config.compression,
            "trace_expand": config.trace_expand,
            "trace_max_chars": config.trace_max_chars,
        }

        if config.compression == "clara":
            payload["compression_target_chars"] = config.compression_target_chars
            payload["compression_timeout_s"] = self.timeout_s

        t0 = time.monotonic()
        try:
            r = requests.post(
                f"{self.codrag_url}/projects/{project_id}/context",
                json=payload,
                timeout=self.timeout_s,
            )
            r.raise_for_status()
            data = r.json()
        except requests.Timeout:
            result.error = f"Timeout after {self.timeout_s}s"
            result.total_time_ms = (time.monotonic() - t0) * 1000
            return result
        except Exception as e:
            result.error = str(e)
            result.total_time_ms = (time.monotonic() - t0) * 1000
            return result

        elapsed_ms = (time.monotonic() - t0) * 1000
        result.total_time_ms = round(elapsed_ms, 1)

        # Unwrap envelope
        inner = data.get("data", data)
        result.raw_response = inner

        # Extract context
        ctx = inner.get("context", "")
        result.context_text = ctx
        result.context_chars = len(ctx)
        result.context_tokens_est = len(ctx) // 4

        # Extract compression metadata
        comp_meta = inner.get("compression") or inner.get("meta", {}).get("compression")
        if comp_meta and isinstance(comp_meta, dict):
            result.compression_enabled = True
            result.compression_input_chars = comp_meta.get("input_chars") or comp_meta.get("original_chars", 0)
            result.compression_output_chars = comp_meta.get("output_chars") or comp_meta.get("compressed_chars", 0)
            result.compression_ratio = comp_meta.get("ratio") or comp_meta.get("compression_ratio", 1.0)
            result.compression_time_ms = comp_meta.get("time_ms") or comp_meta.get("timing_ms", 0.0)
            result.compression_error = comp_meta.get("error")

        # Extract file references from context
        file_paths = self._extract_file_paths(ctx)
        result.file_paths_found = file_paths
        result.num_files_referenced = len(file_paths)

        return result

    def _extract_file_paths(self, text: str) -> List[str]:
        """Extract file paths mentioned in context text."""
        import re
        # Match patterns like "# File: path/to/file.py" or "--- path/to/file.py ---"
        # or common path patterns like src/codrag/core/index.py
        patterns = [
            r"# File:\s*(.+\.py)",
            r"---\s*(.+\.py)\s*---",
            r"(?:src/|tests/|packages/|scripts/)[\w/]+\.(?:py|ts|tsx|js|rs)",
        ]
        paths = set()
        for pattern in patterns:
            for match in re.findall(pattern, text):
                paths.add(match.strip())
        return sorted(paths)

    # --- Full benchmark ---

    def run(
        self,
        configs: List[BenchmarkConfig],
        queries: List[Dict[str, str]],
    ) -> BenchmarkRun:
        """Run the complete benchmark suite."""
        run = BenchmarkRun(
            timestamp=datetime.now(timezone.utc).isoformat(),
            codrag_url=self.codrag_url,
            clara_url=self.clara_url,
            project_id="",
            clara_available=False,
            codrag_healthy=False,
        )

        # Health checks
        run.codrag_healthy = self.check_codrag()
        if not run.codrag_healthy:
            logger.error("CoDRAG daemon not available. Aborting.")
            return run

        run.clara_available = self.check_clara()
        if not run.clara_available:
            logger.warning("CLaRa server not available. Compression tests will fail gracefully.")

        # Resolve project
        project_id = self.resolve_project()
        if not project_id:
            logger.error("No project found. Create a project first.")
            return run
        run.project_id = project_id

        # Filter configs: skip CLaRa configs if server unavailable
        active_configs = []
        for cfg in configs:
            if cfg.compression == "clara" and not run.clara_available:
                logger.warning("Skipping %s (CLaRa not available)", cfg.name)
                continue
            active_configs.append(cfg)

        total = len(active_configs) * len(queries)
        logger.info(
            "Starting benchmark: %d configs × %d queries = %d tests",
            len(active_configs), len(queries), total,
        )

        t_start = time.monotonic()
        done = 0

        for cfg in active_configs:
            logger.info("═" * 60)
            logger.info("Config: %s (K=%d, max_chars=%d, compression=%s)",
                       cfg.name, cfg.k, cfg.max_chars, cfg.compression)
            logger.info("═" * 60)

            for q in queries:
                done += 1
                logger.info(
                    "[%d/%d] %s — %s (%s)",
                    done, total, cfg.name, q["id"], q["type"],
                )

                result = self.run_query(project_id, q, cfg)

                if result.error:
                    logger.warning("  ✗ Error: %s", result.error)
                else:
                    comp_info = ""
                    if result.compression_enabled:
                        comp_info = (
                            f" | compression: {result.compression_input_chars}→"
                            f"{result.compression_output_chars} chars "
                            f"({result.compression_ratio:.1f}×, "
                            f"{result.compression_time_ms:.0f}ms)"
                        )
                    logger.info(
                        "  ✓ %d chars (~%d tokens), %d files, %.0fms%s",
                        result.context_chars,
                        result.context_tokens_est,
                        result.num_files_referenced,
                        result.total_time_ms,
                        comp_info,
                    )

                run.results.append(asdict(result))

        run.total_duration_s = round(time.monotonic() - t_start, 1)
        run.configs_tested = len(active_configs)
        run.queries_tested = len(queries)

        return run


# ---------------------------------------------------------------------------
# Output & reporting
# ---------------------------------------------------------------------------

def save_results(run: BenchmarkRun, output_path: Path) -> None:
    """Save benchmark results to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(asdict(run), f, indent=2, default=str)
    logger.info("Results saved to %s", output_path)


def print_summary(run: BenchmarkRun) -> None:
    """Print a summary table to stdout."""
    print("\n" + "═" * 80)
    print("  CLaRa Benchmark Summary")
    print("═" * 80)
    print(f"  Timestamp:    {run.timestamp}")
    print(f"  Project:      {run.project_id}")
    print(f"  CoDRAG:       {'✓' if run.codrag_healthy else '✗'} {run.codrag_url}")
    print(f"  CLaRa:        {'✓' if run.clara_available else '✗'} {run.clara_url}")
    print(f"  Duration:     {run.total_duration_s:.1f}s")
    print(f"  Tests run:    {len(run.results)}")
    print()

    # Group by config
    by_config: Dict[str, List[Dict]] = {}
    for r in run.results:
        cfg = r["config_name"]
        by_config.setdefault(cfg, []).append(r)

    header = f"{'Config':<28} {'Avg Chars':>10} {'Avg Tokens':>11} {'Avg Files':>10} {'Avg ms':>8} {'Comp Ratio':>11} {'Errors':>7}"
    print(header)
    print("─" * len(header))

    for cfg_name, results in by_config.items():
        ok_results = [r for r in results if not r.get("error")]
        if not ok_results:
            print(f"{cfg_name:<28} {'— all errors —':>50} {len(results):>7}")
            continue

        avg_chars = sum(r["context_chars"] for r in ok_results) / len(ok_results)
        avg_tokens = sum(r["context_tokens_est"] for r in ok_results) / len(ok_results)
        avg_files = sum(r["num_files_referenced"] for r in ok_results) / len(ok_results)
        avg_ms = sum(r["total_time_ms"] for r in ok_results) / len(ok_results)
        errors = len(results) - len(ok_results)

        comp_results = [r for r in ok_results if r.get("compression_enabled")]
        avg_ratio = ""
        if comp_results:
            avg_r = sum(r["compression_ratio"] for r in comp_results) / len(comp_results)
            avg_ratio = f"{avg_r:.1f}×"

        print(
            f"{cfg_name:<28} {avg_chars:>10.0f} {avg_tokens:>11.0f} "
            f"{avg_files:>10.1f} {avg_ms:>8.0f} {avg_ratio:>11} {errors:>7}"
        )

    print()


# ---------------------------------------------------------------------------
# Direct CLaRa test (bypasses CoDRAG, tests CLaRa server directly)
# ---------------------------------------------------------------------------

def run_direct_clara_test(clara_url: str) -> None:
    """Quick direct test of CLaRa server with code-like content."""
    logger.info("Running direct CLaRa test at %s", clara_url)

    # Simulate code chunks as memories
    test_memories = [
        """# File: src/codrag/core/index.py
class CodeIndex:
    def search(self, query_embedding, k=5, max_chars=6000, min_score=0.15,
               role_weights=None, path_weights=None, segment_file_paths=None):
        \"\"\"Search the index for chunks matching the query embedding.\"\"\"
        sims = cosine_similarity(query_embedding, self._embeddings)
        # Apply role weights, intent multipliers, path weights
        for i, score in enumerate(sims):
            w = 1.0
            if role_weights and self._roles[i]:
                w *= role_weights.get(self._roles[i], 1.0)
            if path_weights and self._paths[i]:
                pw = self._resolve_path_weight(self._paths[i], path_weights)
                w *= pw
            sims[i] = score * w
        # Sort and return top-K
        top_indices = np.argsort(sims)[::-1][:k]
        return [self._chunks[i] for i in top_indices if sims[i] >= min_score]""",

        """# File: src/codrag/core/trace.py
class TraceBuilder:
    def build(self, project_path, included_paths=None):
        \"\"\"Build the trace graph for a project.\"\"\"
        if self._has_rust_engine():
            return self._build_rust(project_path, included_paths)
        return self._build_python(project_path, included_paths)

    def _build_rust(self, project_path, included_paths):
        \"\"\"Use the Rust engine for fast trace building.\"\"\"
        import codrag_engine
        handle = codrag_engine.build_trace(str(project_path), included_paths or [])
        return TraceIndex(handle=handle)""",

        """# File: src/codrag/core/compressor.py
class ClaraCompressor(ContextCompressor):
    DEFAULT_URL = "http://localhost:8765"

    def compress(self, text, *, query="", budget_chars=0, level="standard", timeout_s=30.0):
        memories = [m.strip() for m in text.split("\\n\\n---\\n\\n") if m.strip()]
        payload = {"memories": memories, "query": query or "Summarize the key information"}
        resp = requests.post(f"{self.base_url}/compress", json=payload, timeout=timeout_s)
        data = resp.json()
        return CompressResult(compressed=data.get("answer", text), ...)""",
    ]

    test_query = "How does search work in CoDRAG and how is compression applied to results?"

    for max_tokens in [128, 256, 512]:
        logger.info("  Testing max_new_tokens=%d...", max_tokens)
        payload = {
            "memories": test_memories,
            "query": test_query,
            "max_new_tokens": max_tokens,
        }
        t0 = time.monotonic()
        try:
            r = requests.post(f"{clara_url}/compress", json=payload, timeout=60)
            elapsed = (time.monotonic() - t0) * 1000
            data = r.json()

            if data.get("success"):
                answer = data.get("answer", "")
                logger.info(
                    "    ✓ %d chars output, ratio=%.1f×, latency=%.0fms",
                    len(answer),
                    data.get("compression_ratio", 0),
                    elapsed,
                )
                logger.info("    Answer preview: %s", answer[:200])
            else:
                logger.warning("    ✗ CLaRa error: %s", data.get("error"))
        except Exception as e:
            logger.error("    ✗ Request failed: %s", e)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLaRa Compression Benchmark for CoDRAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--codrag-url", default="http://localhost:8400",
        help="CoDRAG daemon URL (default: http://localhost:8400)",
    )
    parser.add_argument(
        "--clara-url", default="http://localhost:8765",
        help="CLaRa server URL (default: http://localhost:8765)",
    )
    parser.add_argument(
        "--project-id", default="",
        help="CoDRAG project ID (auto-detect if not set)",
    )
    parser.add_argument(
        "--output", default="",
        help="Output JSON path (default: docs/Phase31_CLaRa-tests/results_<timestamp>.json)",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick smoke test (2 queries, 2 configs)",
    )
    parser.add_argument(
        "--direct-test", action="store_true",
        help="Run direct CLaRa server test (bypasses CoDRAG)",
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0,
        help="Per-request timeout in seconds (default: 120)",
    )

    args = parser.parse_args()

    # Direct CLaRa test mode
    if args.direct_test:
        run_direct_clara_test(args.clara_url)
        return

    # Full benchmark
    benchmark = ClaraBenchmark(
        codrag_url=args.codrag_url,
        clara_url=args.clara_url,
        project_id=args.project_id,
        timeout_s=args.timeout,
    )

    configs = QUICK_CONFIGS if args.quick else DEFAULT_CONFIGS
    queries = TEST_QUERIES[:2] if args.quick else TEST_QUERIES

    run = benchmark.run(configs, queries)

    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"docs/Phase31_CLaRa-tests/results_{ts}.json")

    save_results(run, output_path)
    print_summary(run)

    # Exit code
    errors = sum(1 for r in run.results if r.get("error"))
    if errors > 0:
        logger.warning("%d/%d tests had errors", errors, len(run.results))
    if not run.codrag_healthy:
        sys.exit(1)


if __name__ == "__main__":
    main()
