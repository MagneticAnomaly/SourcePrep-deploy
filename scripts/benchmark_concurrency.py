#!/usr/bin/env python3
"""
Phase 40 Concurrency Benchmark — Single Model Test
====================================================

Runs a full CoDRAG pipeline build with a specific model and concurrency
setting, measuring wall-clock time per stage and total throughput.

Usage:
    python scripts/benchmark_concurrency.py \
        --model qwen3:8b \
        --concurrency 2 \
        --repo-path /path/to/test/repo \
        --output results/bench_qwen3_8b_c2.json

The script:
1. Pulls the model via Ollama (if not already present)
2. Sets llm_concurrency in pipeline_config
3. Runs the full pipeline (fast sync + deep enrichment)
4. Records per-stage timing, total duration, and quality metrics
5. Writes a JSON results file

Requires: CoDRAG daemon running, Ollama running.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark")


def pull_model(model: str, base_url: str = "http://localhost:11434") -> bool:
    """Ensure the model is pulled in Ollama."""
    import requests

    logger.info("Checking if model '%s' is available...", model)
    try:
        resp = requests.post(
            f"{base_url}/api/show",
            json={"name": model},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Model '%s' already available", model)
            return True
    except Exception:
        pass

    logger.info("Pulling model '%s' (this may take a while)...", model)
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max for large models
        )
        if result.returncode == 0:
            logger.info("Model '%s' pulled successfully", model)
            return True
        else:
            logger.error("Failed to pull model '%s': %s", model, result.stderr)
            return False
    except subprocess.TimeoutExpired:
        logger.error("Model pull timed out after 1 hour")
        return False
    except FileNotFoundError:
        logger.error("ollama command not found. Is Ollama installed?")
        return False


def set_concurrency(concurrency: int) -> None:
    """Set llm_concurrency in the pipeline config (all three model slots)."""
    from codrag.services.settings_store import settings

    config = settings.get("pipeline_config") or {}
    val = max(1, min(8, concurrency))
    config["llm_concurrency"] = val
    config["llm_concurrency_fast"] = val
    config["llm_concurrency_code"] = val
    config["llm_concurrency_deep"] = val
    settings.set("pipeline_config", config)
    logger.info("Set llm_concurrency=%d (fast=%d, code=%d, deep=%d)", val, val, val, val)


def set_model_config(
    model: str,
    model_role: str = "small",
    base_url: str = "http://localhost:11434",
) -> None:
    """Configure the LLM model in settings."""
    from codrag.services.settings_store import settings

    llm_config = settings.get("llm_config") or {}

    if model_role == "small":
        llm_config["small_model"] = {
            "provider": "ollama",
            "model": model,
            "endpoint": base_url,
        }
    elif model_role == "large":
        llm_config["large_model"] = {
            "provider": "ollama",
            "model": model,
            "endpoint": base_url,
        }
    elif model_role == "both":
        llm_config["small_model"] = {
            "provider": "ollama",
            "model": model,
            "endpoint": base_url,
        }
        llm_config["large_model"] = {
            "provider": "ollama",
            "model": model,
            "endpoint": base_url,
        }

    settings.set("llm_config", llm_config)
    logger.info("Set %s model to '%s'", model_role, model)


def run_pipeline(
    repo_path: str,
    stages: str = "all",
) -> Dict[str, Any]:
    """Run the pipeline using HeadlessWorkerFactory (no server needed).

    Returns a dict with per-stage timing and counts.
    """
    from codrag.services.headless_runner import (
        HeadlessConfig,
        HeadlessWorkerFactory,
        HEADLESS_STAGES,
    )

    repo = Path(repo_path).resolve()
    index_dir = repo / ".codrag"
    index_dir.mkdir(parents=True, exist_ok=True)

    # Read the model from settings (set by set_model_config earlier)
    from codrag.services.settings_store import settings
    llm_config = settings.get("llm_config") or {}
    small_cfg = llm_config.get("small_model", {})

    config = HeadlessConfig(
        repo_path=str(repo),
        model_provider="local",
        model_name=small_cfg.get("model", "qwen3:4b-instruct"),
    )

    factory = HeadlessWorkerFactory(
        repo_root=repo,
        index_dir=index_dir,
        config=config,
    )

    workers = {
        "structural":      factory.structural_worker,
        "inferred_edges":  factory.inferred_edges_worker,
        "catalogue":       factory.catalogue_worker,
        "validation":      factory.validation_worker,
        "knowledge":       factory.knowledge_worker,
        "enrichment":      factory.epistemic_worker,
        "clustering":      factory.cluster_worker,
        "atlas":           factory.atlas_worker,
        "deepening":       factory.deepening_worker,
        "deep_knowledge":  factory.deep_knowledge_worker,
    }

    # Determine which stages to run
    fast_stages = {"structural", "inferred_edges", "catalogue", "validation", "knowledge"}
    deep_stages = {"enrichment", "clustering", "atlas", "deepening", "deep_knowledge"}

    results: Dict[str, Any] = {
        "stages": {},
        "total_duration_s": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    stage_times: Dict[str, float] = {}

    def progress_cb(message: str, current: int, total: int) -> None:
        pass  # Silent — timing is captured per-stage

    start = time.monotonic()

    for stage_id, stage_label in HEADLESS_STAGES:
        if stages == "fast" and stage_id not in fast_stages:
            continue
        if stages == "deep" and stage_id not in deep_stages:
            continue

        worker = workers[stage_id]
        logger.info("--- %s ---", stage_label)

        stage_start = time.monotonic()
        try:
            details = worker(progress_cb)
            stage_dur = time.monotonic() - stage_start
            stage_times[stage_id] = round(stage_dur, 2)
            results[stage_id] = details
            logger.info("  OK: %.1fs %s", stage_dur, json.dumps(details)[:200])
        except Exception as e:
            stage_dur = time.monotonic() - stage_start
            stage_times[stage_id] = round(stage_dur, 2)
            logger.error("  FAILED: %s (%.1fs)", e, stage_dur)
            results.setdefault("errors", []).append({"stage": stage_id, "error": str(e)})
            if stage_id == "structural":
                break  # Fatal

    total = time.monotonic() - start
    results["stages"] = stage_times
    results["total_duration_s"] = round(total, 2)
    results["finished_at"] = datetime.now(timezone.utc).isoformat()

    return results


def collect_quality_metrics(repo_path: str) -> Dict[str, Any]:
    """Collect quality metrics from the pipeline output."""
    index_dir = Path(repo_path) / ".codrag"
    metrics: Dict[str, Any] = {}

    # Count nodes and edges
    for fname in ["trace_nodes.jsonl", "trace_edges.jsonl", "trace_inferred_edges.jsonl",
                   "trace_augmented.jsonl", "trace_epistemic.jsonl", "trace_modules.jsonl"]:
        fpath = index_dir / fname
        if fpath.exists():
            count = sum(1 for line in open(fpath) if line.strip())
            metrics[fname.replace(".jsonl", "_count")] = count

    # Read augmentation manifest for quality stats
    manifest_path = index_dir / "trace_augmented_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            metrics["augmented"] = manifest.get("augmented", 0)
            metrics["synthetic"] = manifest.get("synthetic", 0)
            metrics["failed"] = manifest.get("failed", 0)
        except Exception:
            pass

    # Average epistemic confidence
    epistemic_path = index_dir / "trace_epistemic.jsonl"
    if epistemic_path.exists():
        confidences = []
        with open(epistemic_path) as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        conf = entry.get("epistemic_confidence", 0)
                        if isinstance(conf, (int, float)):
                            confidences.append(float(conf))
                    except Exception:
                        pass
        if confidences:
            metrics["avg_epistemic_confidence"] = round(sum(confidences) / len(confidences), 4)
            metrics["epistemic_entries"] = len(confidences)

    return metrics


def run_benchmark(
    model: str,
    concurrency: int,
    repo_path: str,
    output_path: Optional[str] = None,
    stages: str = "all",
    model_role: str = "both",
    ollama_url: str = "http://localhost:11434",
) -> Dict[str, Any]:
    """Run a complete benchmark for one model + concurrency setting."""

    result: Dict[str, Any] = {
        "benchmark": "phase40_concurrency",
        "model": model,
        "concurrency": concurrency,
        "repo_path": repo_path,
        "stages": stages,
        "model_role": model_role,
        "ollama_url": ollama_url,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # 1. Pull model
    if not pull_model(model, ollama_url):
        result["error"] = f"Failed to pull model {model}"
        result["status"] = "failed"
        return result

    # 2. Initialize settings store
    from codrag.services.settings_store import settings
    data_dir = Path(os.environ.get("CODRAG_DATA_DIR", str(Path.home() / ".codrag")))
    data_dir.mkdir(parents=True, exist_ok=True)
    settings.init(data_dir / "codrag_settings.db")

    # 3. Configure
    set_concurrency(concurrency)
    set_model_config(model, model_role=model_role, base_url=ollama_url)

    # 4. Run pipeline
    logger.info("=" * 60)
    logger.info("BENCHMARK: model=%s concurrency=%d stages=%s", model, concurrency, stages)
    logger.info("=" * 60)

    pipeline_results = run_pipeline(repo_path, stages=stages)
    result.update(pipeline_results)

    # 5. Collect quality metrics
    quality = collect_quality_metrics(repo_path)
    result["quality"] = quality

    # 6. Summary
    result["status"] = "error" if "error" in result else "completed"
    result["finished_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 60)
    logger.info("RESULT: %s in %.1fs", result["status"], result.get("total_duration_s", 0))
    if quality:
        logger.info("QUALITY: %s", json.dumps(quality, indent=2))
    logger.info("=" * 60)

    # 7. Write output
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info("Results written to %s", output_path)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Phase 40 Concurrency Benchmark — Single Model Test"
    )
    parser.add_argument("--model", required=True, help="Ollama model name (e.g., qwen3:8b)")
    parser.add_argument("--concurrency", type=int, default=1, help="LLM concurrency (1-8)")
    parser.add_argument("--repo-path", required=True, help="Path to test repository")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--stages", choices=["all", "fast", "deep"], default="all",
                       help="Which pipeline stages to run")
    parser.add_argument("--model-role", choices=["small", "large", "both"], default="both",
                       help="Which model slot to configure")
    parser.add_argument("--ollama-url", default="http://localhost:11434",
                       help="Ollama API URL")
    args = parser.parse_args()

    result = run_benchmark(
        model=args.model,
        concurrency=args.concurrency,
        repo_path=args.repo_path,
        output_path=args.output,
        stages=args.stages,
        model_role=args.model_role,
        ollama_url=args.ollama_url,
    )

    if result.get("status") != "completed":
        sys.exit(1)


if __name__ == "__main__":
    main()
