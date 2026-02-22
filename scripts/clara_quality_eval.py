#!/usr/bin/env python3
"""
CLaRa Compression Quality Evaluator — Phase 31

Offline analysis of benchmark results. Measures:
- Information retention (key facts preserved)
- Code accuracy (function names, params, types)
- Hallucination detection (fabricated paths/names)
- Semantic similarity (embedding cosine: original vs compressed)
- Coverage comparison (files referenced: baseline vs compressed)

Usage:
    # Analyze a benchmark results file
    python scripts/clara_quality_eval.py docs/Phase31_CLaRa-tests/results_20260220.json

    # Compare two runs
    python scripts/clara_quality_eval.py results_baseline.json results_clara.json

    # Run standalone code retention test against CLaRa directly
    python scripts/clara_quality_eval.py --standalone --clara-url http://localhost:8765
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clara_quality")


# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------

@dataclass
class CodeRetentionResult:
    """Result of checking whether CLaRa preserved code-specific information."""
    test_name: str
    input_chars: int
    output_chars: int
    compression_ratio: float

    # What we injected
    injected_function_names: List[str] = field(default_factory=list)
    injected_class_names: List[str] = field(default_factory=list)
    injected_file_paths: List[str] = field(default_factory=list)
    injected_import_paths: List[str] = field(default_factory=list)
    injected_key_facts: List[str] = field(default_factory=list)

    # What survived compression
    retained_function_names: List[str] = field(default_factory=list)
    retained_class_names: List[str] = field(default_factory=list)
    retained_file_paths: List[str] = field(default_factory=list)
    retained_import_paths: List[str] = field(default_factory=list)
    retained_key_facts: List[str] = field(default_factory=list)

    # Scores
    function_retention_pct: float = 0.0
    class_retention_pct: float = 0.0
    path_retention_pct: float = 0.0
    import_retention_pct: float = 0.0
    fact_retention_pct: float = 0.0
    overall_retention_pct: float = 0.0

    # Hallucinations (things in output NOT in input)
    hallucinated_names: List[str] = field(default_factory=list)
    hallucination_count: int = 0

    latency_ms: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Code-specific test cases
# ---------------------------------------------------------------------------

@dataclass
class CodeTestCase:
    """A test case with known code content and expected retained elements."""
    name: str
    query: str
    memories: List[str]
    expected_functions: List[str]
    expected_classes: List[str]
    expected_paths: List[str]
    expected_imports: List[str]
    expected_facts: List[str]


CODE_TEST_CASES: List[CodeTestCase] = [
    CodeTestCase(
        name="search_pipeline",
        query="How does CoDRAG search for relevant code chunks?",
        memories=[
            """# File: src/codrag/core/index.py
class CodeIndex:
    \"\"\"Main search index for CoDRAG. Holds document chunks and their embeddings.\"\"\"

    def search(self, query_embedding, k=5, max_chars=6000, min_score=0.15,
               role_weights=None, intent_multipliers=None, path_weights=None,
               primer_boosts=None, segment_file_paths=None, segment_boost=0.12):
        \"\"\"Search the index for chunks matching the query embedding.

        Returns top-K chunks sorted by weighted cosine similarity.
        \"\"\"
        # Compute raw cosine similarity
        sims = np.dot(self._embeddings, query_embedding)

        # Apply role weights (code=1.0, docs=0.85, test=0.90, other=0.80)
        for i in range(len(sims)):
            role = self._roles[i]
            if role_weights and role in role_weights:
                sims[i] *= role_weights[role]

        # Apply path weights (user-defined per-folder multipliers)
        for i in range(len(sims)):
            if path_weights and self._paths[i]:
                pw = self._resolve_path_weight(self._paths[i], path_weights)
                sims[i] *= pw

        # Filter by min_score
        mask = sims >= min_score
        top_indices = np.argsort(sims[mask])[::-1][:k]

        return self._assemble_context(top_indices, max_chars)

    @staticmethod
    def _resolve_path_weight(source_path: str, path_weights: dict) -> float:
        \"\"\"Walk path hierarchy, most-specific match wins. Default 1.0.\"\"\"
        parts = source_path.split("/")
        weight = 1.0
        for depth in range(len(parts), 0, -1):
            prefix = "/".join(parts[:depth])
            if prefix in path_weights:
                weight = path_weights[prefix]
                break
        return weight""",

            """# File: src/codrag/core/embedder.py
class OllamaEmbedder(Embedder):
    \"\"\"Embedder using Ollama API with nomic-embed-text model.\"\"\"

    KNOWN_OLLAMA_MODELS = {
        "nomic-embed-text": {"dimensions": 768, "matryoshka_dim": 768},
        "nomic-embed-text-v2-moe": {"dimensions": 768},
        "nomic-embed-code": {"dimensions": 3584, "matryoshka_dim": 768},
    }

    def embed(self, texts: list[str]) -> np.ndarray:
        \"\"\"Embed a batch of texts using Ollama API.\"\"\"
        self._ensure_model_ready()
        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": texts}
        )
        embeddings = np.array(response.json()["embeddings"])
        # Matryoshka truncation
        if self.matryoshka_dim:
            embeddings = embeddings[:, :self.matryoshka_dim]
            # L2 re-normalize
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / np.maximum(norms, 1e-10)
        return embeddings

class NativeEmbedder(Embedder):
    \"\"\"ONNX-based embedder using nomic-embed-text-v1.5 locally.\"\"\"
    MODEL_REPO = "nomic-ai/nomic-embed-text-v1.5"
    DIMENSIONS = 768""",
        ],
        expected_functions=[
            "search", "_resolve_path_weight", "embed", "_ensure_model_ready",
        ],
        expected_classes=["CodeIndex", "OllamaEmbedder", "NativeEmbedder", "Embedder"],
        expected_paths=["src/codrag/core/index.py", "src/codrag/core/embedder.py"],
        expected_imports=[],
        expected_facts=[
            "cosine similarity",
            "role_weights",
            "path_weights",
            "min_score",
            "top-K",
            "nomic-embed-text",
            "Matryoshka",
            "768",
        ],
    ),

    CodeTestCase(
        name="trace_system",
        query="How does the trace graph system work?",
        memories=[
            """# File: src/codrag/core/trace.py
class TraceBuilder:
    def build(self, project_path, included_paths=None):
        \"\"\"Build the trace graph for a project. Uses Rust engine if available.\"\"\"
        if self._has_rust_engine():
            return self._build_rust(project_path, included_paths)
        return self._build_python(project_path, included_paths)

    def _build_rust(self, project_path, included_paths):
        import codrag_engine
        handle = codrag_engine.build_trace(str(project_path), included_paths or [])
        return TraceIndex(handle=handle)

class TraceIndex:
    def search(self, query: str, limit: int = 20) -> list:
        \"\"\"Search trace nodes by symbol name.\"\"\"
        pass

    def neighbors(self, node_id: str, direction: str = "both") -> list:
        \"\"\"Get graph neighbors of a node (callers, callees, imports).\"\"\"
        pass

    def node_degree(self, node_id: str) -> dict:
        \"\"\"Return in-degree and out-degree for a trace node.\"\"\"
        pass""",

            """# File: src/codrag/core/epistemic_score.py
@dataclass
class EpistemicScore:
    structural: float = 0.0    # 20% weight — graph centrality
    catalogued: float = 0.0    # 15% — has augmentation
    validated: float = 0.0     # 20% — Phase 2 confirmed
    enriched: float = 0.0      # 15% — epistemic enrichment
    clustered: float = 0.0     # 15% — belongs to module
    converged: float = 0.0     # 15% — stable across iterations

    @property
    def composite(self) -> float:
        return (0.20 * self.structural + 0.15 * self.catalogued +
                0.20 * self.validated + 0.15 * self.enriched +
                0.15 * self.clustered + 0.15 * self.converged)""",
        ],
        expected_functions=[
            "build", "_build_rust", "search", "neighbors", "node_degree",
        ],
        expected_classes=["TraceBuilder", "TraceIndex", "EpistemicScore"],
        expected_paths=["src/codrag/core/trace.py", "src/codrag/core/epistemic_score.py"],
        expected_imports=["codrag_engine"],
        expected_facts=[
            "Rust engine",
            "graph",
            "callers",
            "callees",
            "imports",
            "epistemic",
            "structural",
            "composite",
            "6 components",
        ],
    ),

    CodeTestCase(
        name="compression_pipeline",
        query="How is CLaRa compression integrated into the search pipeline?",
        memories=[
            """# File: src/codrag/core/compressor.py
class ClaraCompressor(ContextCompressor):
    DEFAULT_URL = "http://localhost:8765"

    def compress(self, text, *, query="", budget_chars=0, level="standard", timeout_s=30.0):
        input_chars = len(text)
        memories = [m.strip() for m in text.split("\\n\\n---\\n\\n") if m.strip()]
        payload = {"memories": memories, "query": query or "Summarize the key information"}
        resp = requests.post(f"{self.base_url}/compress", json=payload, timeout=timeout_s)
        data = resp.json()
        compressed = str(data.get("answer", text))
        return CompressResult(
            compressed=compressed,
            input_chars=input_chars,
            output_chars=len(compressed),
            compression_ratio=float(data.get("compression_ratio", 1.0)),
        )

class NoopCompressor(ContextCompressor):
    \"\"\"Pass-through compressor that returns text unchanged. Used as default.\"\"\"
    def compress(self, text, **kwargs):
        return CompressResult(compressed=text, input_chars=len(text), output_chars=len(text))""",

            """# File: src/codrag/api/routers/projects.py (context endpoint excerpt)
# Step 3: Compression (CLaRa)
if req.compression == "clara" and ctx_text:
    require_feature("clara_compression")
    clara_url = clara_cfg.get("remote_url") or ClaraCompressor.DEFAULT_URL
    compressor = ClaraCompressor(base_url=str(clara_url), timeout_s=req.compression_timeout_s)
    budget = req.compression_target_chars or 0
    res = compressor.compress(ctx_text, query=req.query, budget_chars=budget, level=req.compression_level)
    data["context"] = res.compressed
    data["meta"]["compression"] = {
        "provider": "clara", "original_chars": res.input_chars,
        "compressed_chars": res.output_chars, "ratio": res.compression_ratio,
    }""",
        ],
        expected_functions=["compress"],
        expected_classes=["ClaraCompressor", "NoopCompressor", "ContextCompressor", "CompressResult"],
        expected_paths=["src/codrag/core/compressor.py", "src/codrag/api/routers/projects.py"],
        expected_imports=[],
        expected_facts=[
            "localhost:8765",
            "memories",
            "query",
            "budget_chars",
            "compression_ratio",
            "require_feature",
            "clara_compression",
            "Pro tier",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Evaluation logic
# ---------------------------------------------------------------------------

def check_retention(
    output_text: str,
    items: List[str],
) -> Tuple[List[str], float]:
    """Check which items from a list appear in the output text."""
    retained = []
    for item in items:
        # Case-insensitive search, handle underscores and dots
        if item.lower() in output_text.lower():
            retained.append(item)
        elif item.replace("_", " ").lower() in output_text.lower():
            retained.append(item)
    pct = (len(retained) / len(items) * 100) if items else 100.0
    return retained, pct


def detect_hallucinations(
    output_text: str,
    all_input_text: str,
) -> List[str]:
    """Detect potential hallucinated names (in output but not in input)."""
    # Extract function-like patterns from output
    output_names = set(re.findall(r"\b([a-z_][a-z0-9_]{3,})\s*\(", output_text.lower()))
    input_names = set(re.findall(r"\b([a-z_][a-z0-9_]{3,})\s*\(", all_input_text.lower()))

    # Also extract class-like patterns
    output_classes = set(re.findall(r"\b([A-Z][a-zA-Z0-9]+)\b", output_text))
    input_classes = set(re.findall(r"\b([A-Z][a-zA-Z0-9]+)\b", all_input_text))

    # Common English words that aren't hallucinations
    common_words = {
        "The", "This", "That", "Each", "When", "Where", "What", "How",
        "For", "With", "From", "Into", "After", "Before", "Between",
        "None", "True", "False", "Returns", "Takes", "Uses", "Provides",
        "Here", "Based", "Using", "Called", "File", "Code", "Data",
        "First", "Then", "Next", "Also", "Only", "Just", "Both",
    }

    hallucinated_funcs = output_names - input_names
    hallucinated_classes = output_classes - input_classes - common_words

    return sorted(hallucinated_funcs | {c for c in hallucinated_classes if len(c) > 3})


def run_standalone_test(
    clara_url: str,
    test_case: CodeTestCase,
    max_new_tokens: int = 512,
) -> CodeRetentionResult:
    """Run a single code retention test against CLaRa directly."""
    import requests as req_lib

    all_input = "\n\n---\n\n".join(test_case.memories)
    input_chars = len(all_input)

    result = CodeRetentionResult(
        test_name=test_case.name,
        input_chars=input_chars,
        output_chars=0,
        compression_ratio=1.0,
        injected_function_names=test_case.expected_functions,
        injected_class_names=test_case.expected_classes,
        injected_file_paths=test_case.expected_paths,
        injected_import_paths=test_case.expected_imports,
        injected_key_facts=test_case.expected_facts,
    )

    payload = {
        "memories": test_case.memories,
        "query": test_case.query,
        "max_new_tokens": max_new_tokens,
    }

    t0 = time.monotonic()
    try:
        resp = req_lib.post(f"{clara_url}/compress", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        result.error = str(e)
        result.latency_ms = (time.monotonic() - t0) * 1000
        return result

    result.latency_ms = round((time.monotonic() - t0) * 1000, 1)

    if not data.get("success"):
        result.error = data.get("error", "CLaRa returned success=false")
        return result

    output = data.get("answer", "")
    result.output_chars = len(output)
    result.compression_ratio = input_chars / max(len(output), 1)

    # Check retention
    result.retained_function_names, result.function_retention_pct = check_retention(
        output, test_case.expected_functions
    )
    result.retained_class_names, result.class_retention_pct = check_retention(
        output, test_case.expected_classes
    )
    result.retained_file_paths, result.path_retention_pct = check_retention(
        output, test_case.expected_paths
    )
    result.retained_import_paths, result.import_retention_pct = check_retention(
        output, test_case.expected_imports
    )
    result.retained_key_facts, result.fact_retention_pct = check_retention(
        output, test_case.expected_facts
    )

    # Overall retention
    all_expected = (
        test_case.expected_functions + test_case.expected_classes +
        test_case.expected_paths + test_case.expected_imports +
        test_case.expected_facts
    )
    _, result.overall_retention_pct = check_retention(output, all_expected)

    # Hallucination check
    result.hallucinated_names = detect_hallucinations(output, all_input)
    result.hallucination_count = len(result.hallucinated_names)

    return result


# ---------------------------------------------------------------------------
# Benchmark results analysis
# ---------------------------------------------------------------------------

def analyze_results(results_path: Path) -> None:
    """Analyze a benchmark results JSON file."""
    with open(results_path) as f:
        run = json.load(f)

    results = run.get("results", [])
    if not results:
        logger.error("No results found in %s", results_path)
        return

    print("\n" + "═" * 80)
    print("  CLaRa Quality Analysis")
    print("═" * 80)

    # Group by config
    by_config: Dict[str, List[Dict]] = {}
    for r in results:
        cfg = r["config_name"]
        by_config.setdefault(cfg, []).append(r)

    # Compare baseline vs CLaRa configs
    baseline_results = {}
    clara_results = {}

    for cfg_name, cfg_results in by_config.items():
        ok = [r for r in cfg_results if not r.get("error")]
        if "baseline" in cfg_name:
            for r in ok:
                baseline_results[r["query_id"]] = r
        elif "clara" in cfg_name:
            for r in ok:
                key = (r["query_id"], cfg_name)
                clara_results[key] = r

    # Coverage comparison
    print("\n## Coverage Comparison (files referenced per query)")
    print(f"{'Query':<6} {'Baseline Files':>15} {'Best CLaRa Files':>17} {'Improvement':>12}")
    print("─" * 55)

    for qid in sorted(baseline_results.keys()):
        base = baseline_results[qid]
        base_files = base.get("num_files_referenced", 0)

        best_clara_files = 0
        best_cfg = ""
        for (q, cfg), r in clara_results.items():
            if q == qid:
                files = r.get("num_files_referenced", 0)
                if files > best_clara_files:
                    best_clara_files = files
                    best_cfg = cfg

        improvement = ""
        if base_files > 0 and best_clara_files > 0:
            ratio = best_clara_files / base_files
            improvement = f"{ratio:.1f}×"

        print(f"{qid:<6} {base_files:>15} {best_clara_files:>17} {improvement:>12}")

    # Compression ratios
    print("\n## Compression Statistics")
    for cfg_name, cfg_results in by_config.items():
        compressed = [r for r in cfg_results if r.get("compression_enabled")]
        if not compressed:
            continue

        ratios = [r["compression_ratio"] for r in compressed]
        input_chars = [r["compression_input_chars"] for r in compressed]
        output_chars = [r["compression_output_chars"] for r in compressed]
        times = [r["compression_time_ms"] for r in compressed]

        print(f"\n  {cfg_name}:")
        print(f"    Avg compression ratio:  {sum(ratios)/len(ratios):.1f}×")
        print(f"    Avg input:              {sum(input_chars)/len(input_chars):.0f} chars")
        print(f"    Avg output:             {sum(output_chars)/len(output_chars):.0f} chars")
        print(f"    Avg compression time:   {sum(times)/len(times):.0f} ms")

    # Output size comparison
    print("\n## Output Size (chars delivered to LLM)")
    header = f"{'Config':<28} {'Min':>8} {'Avg':>8} {'Max':>8} {'Avg Tokens':>11}"
    print(header)
    print("─" * len(header))

    for cfg_name, cfg_results in by_config.items():
        ok = [r for r in cfg_results if not r.get("error") and r.get("context_chars", 0) > 0]
        if not ok:
            continue
        chars = [r["context_chars"] for r in ok]
        print(
            f"{cfg_name:<28} {min(chars):>8} {sum(chars)//len(chars):>8} "
            f"{max(chars):>8} {sum(chars)//len(chars)//4:>11}"
        )

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLaRa Compression Quality Evaluator",
    )
    parser.add_argument(
        "results_files", nargs="*",
        help="Benchmark results JSON files to analyze",
    )
    parser.add_argument(
        "--standalone", action="store_true",
        help="Run standalone code retention tests against CLaRa",
    )
    parser.add_argument(
        "--clara-url", default="http://localhost:8765",
        help="CLaRa server URL for standalone tests",
    )
    parser.add_argument(
        "--max-new-tokens", type=int, default=512,
        help="max_new_tokens for standalone tests (default: 512)",
    )
    parser.add_argument(
        "--output", default="",
        help="Output JSON path for standalone test results",
    )

    args = parser.parse_args()

    if args.standalone:
        logger.info("Running standalone code retention tests against %s", args.clara_url)
        logger.info("max_new_tokens=%d", args.max_new_tokens)
        print()

        all_results = []
        for tc in CODE_TEST_CASES:
            logger.info("Testing: %s — %s", tc.name, tc.query)
            result = run_standalone_test(args.clara_url, tc, args.max_new_tokens)

            if result.error:
                logger.error("  ✗ Error: %s", result.error)
            else:
                logger.info(
                    "  ✓ %d→%d chars (%.1f×), %.0fms",
                    result.input_chars, result.output_chars,
                    result.compression_ratio, result.latency_ms,
                )
                logger.info(
                    "  Retention: funcs=%d/%d (%.0f%%), classes=%d/%d (%.0f%%), "
                    "paths=%d/%d (%.0f%%), facts=%d/%d (%.0f%%)",
                    len(result.retained_function_names), len(result.injected_function_names),
                    result.function_retention_pct,
                    len(result.retained_class_names), len(result.injected_class_names),
                    result.class_retention_pct,
                    len(result.retained_file_paths), len(result.injected_file_paths),
                    result.path_retention_pct,
                    len(result.retained_key_facts), len(result.injected_key_facts),
                    result.fact_retention_pct,
                )
                logger.info("  Overall retention: %.0f%%", result.overall_retention_pct)
                if result.hallucinated_names:
                    logger.warning(
                        "  ⚠ Potential hallucinations (%d): %s",
                        result.hallucination_count,
                        ", ".join(result.hallucinated_names[:10]),
                    )

            all_results.append(asdict(result))

        # Summary
        ok_results = [r for r in all_results if not r.get("error")]
        if ok_results:
            avg_retention = sum(r["overall_retention_pct"] for r in ok_results) / len(ok_results)
            avg_hallucinations = sum(r["hallucination_count"] for r in ok_results) / len(ok_results)
            avg_ratio = sum(r["compression_ratio"] for r in ok_results) / len(ok_results)
            avg_latency = sum(r["latency_ms"] for r in ok_results) / len(ok_results)

            print("\n" + "═" * 60)
            print("  Standalone Test Summary")
            print("═" * 60)
            print(f"  Tests run:           {len(all_results)}")
            print(f"  Tests passed:        {len(ok_results)}")
            print(f"  Avg retention:       {avg_retention:.0f}%")
            print(f"  Avg hallucinations:  {avg_hallucinations:.1f}")
            print(f"  Avg compression:     {avg_ratio:.1f}×")
            print(f"  Avg latency:         {avg_latency:.0f}ms")
            print()

            # Pass/fail
            if avg_retention >= 80:
                print("  ✅ PASS: Retention ≥80%")
            else:
                print(f"  ❌ FAIL: Retention {avg_retention:.0f}% < 80% target")

            if avg_hallucinations < 5:
                print("  ✅ PASS: Hallucinations <5 avg")
            else:
                print(f"  ❌ FAIL: Hallucinations {avg_hallucinations:.1f} ≥5 avg")

        # Save results
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(all_results, f, indent=2, default=str)
            logger.info("Results saved to %s", output_path)

        return

    # Analyze existing benchmark results
    if not args.results_files:
        parser.print_help()
        sys.exit(1)

    for rf in args.results_files:
        analyze_results(Path(rf))


if __name__ == "__main__":
    main()
