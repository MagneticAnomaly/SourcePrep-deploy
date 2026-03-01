#!/usr/bin/env python3
"""
Phase 40 Throughput Comparison — Find the optimal model × strategy sweet spot.
================================================================================

Tests different models and strategies on the same repo to find
the fastest items/sec while maintaining quality.

Strategies tested:
  1. Sequential (c=1) — baseline for each model
  2. Concurrent (c=2, c=4) — parallel single-item calls
  3. Batched (batch_size=5, 10) — multiple items per call (35b+ only)

Measures:
  - Items per second (the key throughput metric)
  - Total wall-clock time
  - Quality: augmentation success rate, parse failure rate

Usage:
    .venv/bin/python3 scripts/benchmark_throughput.py --repo-path tests/eval/real_repos/mini-redis-rust
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("throughput")


def unload_ollama_models():
    """Unload all models to get clean VRAM state."""
    import requests
    try:
        resp = requests.get("http://localhost:11434/api/ps", timeout=5)
        for m in resp.json().get("models", []):
            name = m.get("name", "")
            if name:
                requests.post("http://localhost:11434/api/generate",
                            json={"model": name, "keep_alive": 0}, timeout=30)
        time.sleep(2)
    except Exception:
        pass


def clean_index(repo_path: str):
    """Remove LLM-generated files to force fresh run."""
    index_dir = Path(repo_path) / ".codrag"
    for f in ["trace_augmented.jsonl", "trace_augmented_manifest.json",
              "trace_inferred_edges.jsonl", "trace_inferred_manifest.json"]:
        p = index_dir / f
        if p.exists():
            p.unlink()


def warm_model(model: str):
    """Send a small request to ensure model is loaded in VRAM."""
    import requests
    logger.info("Warming model '%s'...", model)
    try:
        requests.post("http://localhost:11434/api/generate", json={
            "model": model, "prompt": "Say ok", "stream": False,
            "options": {"num_predict": 5},
        }, timeout=120)
    except Exception as e:
        logger.warning("Warm failed: %s", e)


def run_catalogue_only(
    repo_path: str,
    model: str,
    concurrency: int = 1,
    batch_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Run ONLY the catalogue stage and measure throughput.
    
    This isolates the LLM-heavy stage for clean comparison.
    Returns timing and quality metrics.
    """
    from codrag.services.settings_store import settings
    from codrag.services.headless_runner import HeadlessConfig, HeadlessWorkerFactory
    from codrag.core.augmenter import TraceAugmenter, LLMClient, AugmentResult

    # Set concurrency
    config = settings.get("pipeline_config") or {}
    config["llm_concurrency_fast"] = concurrency
    config["llm_concurrency_code"] = concurrency
    config["llm_concurrency_deep"] = concurrency
    settings.set("pipeline_config", config)

    repo = Path(repo_path).resolve()
    index_dir = repo / ".codrag"

    # Create LLM client
    llm = LLMClient(
        endpoint_url="http://localhost:11434",
        model=model,
        provider="ollama",
        timeout=120.0,
    )

    # Optionally override batch profile for local batching test
    batch_profile = None
    if batch_override:
        from codrag.core.batch_profiles import BatchProfile, BatchProfileName, BatchStage
        if batch_override == "compact":
            from codrag.core.batch_profiles import PROFILE_COMPACT
            batch_profile = PROFILE_COMPACT
        elif batch_override == "standard":
            from codrag.core.batch_profiles import PROFILE_STANDARD
            batch_profile = PROFILE_STANDARD

    augmenter = TraceAugmenter(
        index_dir=index_dir,
        repo_root=str(repo),
        llm_client=llm,
        batch_profile=batch_profile,
    )

    start = time.monotonic()
    result = augmenter.run()
    elapsed = time.monotonic() - start

    total_items = result.augmented + result.synthetic + result.failed
    items_per_sec = total_items / elapsed if elapsed > 0 else 0

    return {
        "model": model,
        "concurrency": concurrency,
        "batch_profile": batch_override or "off",
        "duration_s": round(elapsed, 1),
        "total_items": total_items,
        "augmented": result.augmented,
        "synthetic": result.synthetic,
        "failed": result.failed,
        "items_per_sec": round(items_per_sec, 3),
        "avg_per_item_s": round(elapsed / max(total_items, 1), 2),
    }


def run_inferred_edges_only(
    repo_path: str,
    model: str,
    concurrency: int = 1,
) -> Dict[str, Any]:
    """Run ONLY the inferred edges stage and measure throughput."""
    from codrag.services.settings_store import settings
    from codrag.core.inferred_edges import InferredEdgesAnalyzer
    from codrag.core.augmenter import LLMClient

    config = settings.get("pipeline_config") or {}
    config["llm_concurrency_fast"] = concurrency
    config["llm_concurrency_code"] = concurrency
    config["llm_concurrency_deep"] = concurrency
    settings.set("pipeline_config", config)

    repo = Path(repo_path).resolve()
    index_dir = repo / ".codrag"

    llm = LLMClient(
        endpoint_url="http://localhost:11434",
        model=model,
        provider="ollama",
        timeout=120.0,
    )

    analyzer = InferredEdgesAnalyzer(
        index_dir=index_dir,
        repo_root=str(repo),
        llm_client=llm,
    )

    start = time.monotonic()
    result = analyzer.run()
    elapsed = time.monotonic() - start

    return {
        "model": model,
        "concurrency": concurrency,
        "duration_s": round(elapsed, 1),
        "files_analyzed": result.files_analyzed,
        "edges_written": result.edges_written,
        "failed": result.failed,
        "files_per_sec": round(result.files_analyzed / elapsed if elapsed > 0 else 0, 3),
    }


def ensure_structural(repo_path: str):
    """Make sure structural trace exists."""
    from codrag.services.headless_runner import HeadlessConfig, HeadlessWorkerFactory
    repo = Path(repo_path).resolve()
    index_dir = repo / ".codrag"
    nodes_path = index_dir / "trace_nodes.jsonl"
    
    if nodes_path.exists():
        count = sum(1 for line in open(nodes_path) if line.strip())
        if count > 0:
            return count

    config = HeadlessConfig(repo_path=str(repo))
    factory = HeadlessWorkerFactory(repo_root=repo, index_dir=index_dir, config=config)
    result = factory.structural_worker(lambda m, c, t: None)
    return result.get("nodes", 0)


def main():
    parser = argparse.ArgumentParser(description="Phase 40 Throughput Comparison")
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--output", default="results/throughput_comparison.json")
    parser.add_argument("--models", nargs="*",
                       default=["qwen3:4b-instruct", "qwen3:8b", "qwen3.5:35b-a3b"])
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Init settings store
    from codrag.services.settings_store import settings
    data_dir = Path.home() / ".codrag"
    data_dir.mkdir(exist_ok=True)
    settings.init(data_dir / "codrag_settings.db")

    # Ensure structural trace exists
    logger.info("Ensuring structural trace...")
    node_count = ensure_structural(args.repo_path)
    logger.info("Structural trace: %d nodes", node_count)

    # ── Test Matrix ──────────────────────────────────────────
    tests = []

    for model in args.models:
        # Sequential baseline
        tests.append({"model": model, "concurrency": 1, "batch": None, "label": f"{model} c=1"})
        # Concurrent
        tests.append({"model": model, "concurrency": 2, "batch": None, "label": f"{model} c=2"})

        # For 35b+ models: also test batching (they're smart enough)
        if "35b" in model or "32b" in model or "122b" in model:
            tests.append({"model": model, "concurrency": 1, "batch": "compact",
                         "label": f"{model} batch=compact"})

    all_results = []
    
    logger.info("=" * 70)
    logger.info("THROUGHPUT COMPARISON: %d tests on %s", len(tests), Path(args.repo_path).name)
    logger.info("=" * 70)

    for i, test in enumerate(tests, 1):
        model = test["model"]
        conc = test["concurrency"]
        batch = test["batch"]
        label = test["label"]

        logger.info("")
        logger.info("[%d/%d] %s", i, len(tests), label)
        logger.info("-" * 50)

        # Clean + warm
        clean_index(args.repo_path)
        unload_ollama_models()
        warm_model(model)

        # Run catalogue (the main LLM-heavy stage)
        try:
            result = run_catalogue_only(
                repo_path=args.repo_path,
                model=model,
                concurrency=conc,
                batch_override=batch,
            )
            result["label"] = label
            all_results.append(result)

            logger.info("  → %d items in %.1fs = %.3f items/sec  (aug=%d, syn=%d, fail=%d)",
                       result["total_items"], result["duration_s"], result["items_per_sec"],
                       result["augmented"], result["synthetic"], result["failed"])
        except Exception as e:
            logger.error("  → FAILED: %s", e)
            all_results.append({"label": label, "model": model, "error": str(e)})

        # Save intermediate
        with open(args.output, "w") as f:
            json.dump({"results": all_results, "repo": args.repo_path}, f, indent=2, default=str)

    # ── Summary Table ────────────────────────────────────────
    print()
    print("=" * 80)
    print("THROUGHPUT COMPARISON RESULTS")
    print("=" * 80)
    print(f"{'Label':<35} {'Time':>7} {'Items':>6} {'Items/s':>8} {'Aug':>5} {'Fail':>5} {'Avg/item':>9}")
    print("-" * 80)

    for r in all_results:
        if "error" in r:
            print(f"{r['label']:<35} {'FAILED':>7}")
            continue
        print(f"{r['label']:<35} {r['duration_s']:>6.1f}s {r['total_items']:>6} "
              f"{r['items_per_sec']:>7.3f}/s {r['augmented']:>5} {r['failed']:>5} "
              f"{r['avg_per_item_s']:>8.2f}s")

    # Best throughput
    valid = [r for r in all_results if "error" not in r and r.get("items_per_sec", 0) > 0]
    if valid:
        best = max(valid, key=lambda r: r["items_per_sec"])
        print()
        print(f"BEST THROUGHPUT: {best['label']} at {best['items_per_sec']:.3f} items/sec")
        
        baseline = next((r for r in valid if r.get("concurrency") == 1 and "batch" not in r.get("label", "")), valid[0])
        if baseline != best:
            speedup = best["items_per_sec"] / baseline["items_per_sec"]
            print(f"  vs baseline ({baseline['label']}): {speedup:.2f}x faster")

    print("=" * 80)
    print(f"Results saved: {args.output}")


if __name__ == "__main__":
    main()
