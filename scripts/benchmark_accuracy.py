#!/usr/bin/env python3
"""
Phase 40 Accuracy Benchmark — Verify concurrent execution matches sequential quality.
======================================================================================

Runs the pipeline TWICE with the same model:
  1. Sequential (concurrency=1) — baseline
  2. Concurrent (concurrency=N) — test

Then compares output quality between the two runs:
  - Augmentation summaries similarity
  - Epistemic confidence distribution
  - Edge counts and types
  - Cluster membership stability

This answers: "Does concurrency degrade output quality?"

Usage:
    python scripts/benchmark_accuracy.py \
        --model qwen3:8b \
        --concurrency 2 \
        --repo-path /path/to/test/repo \
        --output results/accuracy_qwen3_8b_c2.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("accuracy")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    entries = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    return entries


def snapshot_outputs(index_dir: Path) -> Dict[str, Any]:
    """Capture all pipeline output files as a snapshot for comparison."""
    snapshot: Dict[str, Any] = {}

    # Augmentations
    aug_entries = load_jsonl(index_dir / "trace_augmented.jsonl")
    snapshot["augmentations"] = {e["node_id"]: e for e in aug_entries}
    snapshot["augmentation_count"] = len(aug_entries)

    # Epistemic
    epi_entries = load_jsonl(index_dir / "trace_epistemic.jsonl")
    snapshot["epistemic"] = {e["node_id"]: e for e in epi_entries}
    snapshot["epistemic_count"] = len(epi_entries)

    # Inferred edges
    edge_entries = load_jsonl(index_dir / "trace_inferred_edges.jsonl")
    snapshot["inferred_edges"] = edge_entries
    snapshot["inferred_edge_count"] = len(edge_entries)

    # Modules
    mod_entries = load_jsonl(index_dir / "trace_modules.jsonl")
    snapshot["modules"] = {e.get("module_id", ""): e for e in mod_entries}
    snapshot["module_count"] = len(mod_entries)

    # Structural (should be identical between runs)
    node_entries = load_jsonl(index_dir / "trace_nodes.jsonl")
    snapshot["node_count"] = len(node_entries)

    return snapshot


def compare_augmentations(base: Dict, test: Dict) -> Dict[str, Any]:
    """Compare augmentation outputs between sequential and concurrent runs."""
    base_augs = base.get("augmentations", {})
    test_augs = test.get("augmentations", {})

    common_ids = set(base_augs.keys()) & set(test_augs.keys())
    only_base = set(base_augs.keys()) - set(test_augs.keys())
    only_test = set(test_augs.keys()) - set(base_augs.keys())

    # Compare summaries
    summary_matches = 0
    role_matches = 0
    confidence_diffs = []

    for nid in common_ids:
        b = base_augs[nid]
        t = test_augs[nid]

        # Exact summary match is unlikely (LLM is non-deterministic)
        # but role should usually match
        if b.get("role") == t.get("role"):
            role_matches += 1

        # Summaries: check if they're roughly the same length/content
        b_sum = b.get("summary", "")
        t_sum = t.get("summary", "")
        if b_sum == t_sum:
            summary_matches += 1

        # Confidence delta
        b_conf = float(b.get("confidence", 0))
        t_conf = float(t.get("confidence", 0))
        confidence_diffs.append(abs(b_conf - t_conf))

    return {
        "total_base": len(base_augs),
        "total_test": len(test_augs),
        "common": len(common_ids),
        "only_in_base": len(only_base),
        "only_in_test": len(only_test),
        "role_match_rate": role_matches / max(len(common_ids), 1),
        "exact_summary_match_rate": summary_matches / max(len(common_ids), 1),
        "avg_confidence_delta": sum(confidence_diffs) / max(len(confidence_diffs), 1),
        "max_confidence_delta": max(confidence_diffs) if confidence_diffs else 0,
    }


def compare_epistemic(base: Dict, test: Dict) -> Dict[str, Any]:
    """Compare epistemic enrichment between sequential and concurrent runs."""
    base_epi = base.get("epistemic", {})
    test_epi = test.get("epistemic", {})

    common_ids = set(base_epi.keys()) & set(test_epi.keys())

    confidence_diffs = []
    layer_matches = 0
    tag_overlap_scores = []

    for nid in common_ids:
        b = base_epi[nid]
        t = test_epi[nid]

        # Epistemic confidence delta
        b_conf = float(b.get("epistemic_confidence", 0))
        t_conf = float(t.get("epistemic_confidence", 0))
        confidence_diffs.append(abs(b_conf - t_conf))

        # Architecture layer match
        if b.get("architecture_layer") == t.get("architecture_layer"):
            layer_matches += 1

        # Domain tag overlap (Jaccard similarity)
        b_tags = set(b.get("domain_tags", []))
        t_tags = set(t.get("domain_tags", []))
        if b_tags or t_tags:
            jaccard = len(b_tags & t_tags) / max(len(b_tags | t_tags), 1)
            tag_overlap_scores.append(jaccard)

    return {
        "total_base": len(base_epi),
        "total_test": len(test_epi),
        "common": len(common_ids),
        "avg_confidence_delta": sum(confidence_diffs) / max(len(confidence_diffs), 1),
        "max_confidence_delta": max(confidence_diffs) if confidence_diffs else 0,
        "architecture_layer_match_rate": layer_matches / max(len(common_ids), 1),
        "avg_domain_tag_jaccard": sum(tag_overlap_scores) / max(len(tag_overlap_scores), 1),
    }


def compare_edges(base: Dict, test: Dict) -> Dict[str, Any]:
    """Compare inferred edges between sequential and concurrent runs."""
    base_edges = base.get("inferred_edges", [])
    test_edges = test.get("inferred_edges", [])

    # Normalize edge IDs for comparison
    base_ids = {e.get("id", "") for e in base_edges}
    test_ids = {e.get("id", "") for e in test_edges}

    return {
        "base_count": len(base_edges),
        "test_count": len(test_edges),
        "common": len(base_ids & test_ids),
        "only_in_base": len(base_ids - test_ids),
        "only_in_test": len(test_ids - base_ids),
        "overlap_rate": len(base_ids & test_ids) / max(len(base_ids | test_ids), 1),
    }


def compare_modules(base: Dict, test: Dict) -> Dict[str, Any]:
    """Compare cluster modules between sequential and concurrent runs."""
    base_mods = base.get("modules", {})
    test_mods = test.get("modules", {})

    # Compare by member file overlap
    member_overlaps = []
    for mid in set(base_mods.keys()) & set(test_mods.keys()):
        b_files = set(base_mods[mid].get("member_files", []))
        t_files = set(test_mods[mid].get("member_files", []))
        if b_files or t_files:
            jaccard = len(b_files & t_files) / max(len(b_files | t_files), 1)
            member_overlaps.append(jaccard)

    return {
        "base_count": len(base_mods),
        "test_count": len(test_mods),
        "common_ids": len(set(base_mods.keys()) & set(test_mods.keys())),
        "avg_member_overlap": sum(member_overlaps) / max(len(member_overlaps), 1),
    }


def run_pipeline_with_config(
    repo_path: str,
    concurrency_fast: int,
    concurrency_deep: int,
    model: str,
    ollama_url: str = "http://localhost:11434",
    stages: str = "all",
) -> float:
    """Run the pipeline with specified concurrency. Returns duration in seconds."""
    from codrag.services.settings_store import settings
    from codrag.services.headless_runner import (
        HeadlessConfig,
        HeadlessWorkerFactory,
        HEADLESS_STAGES,
    )

    # Set concurrency
    config = settings.get("pipeline_config") or {}
    config["llm_concurrency_fast"] = concurrency_fast
    config["llm_concurrency_code"] = concurrency_fast
    config["llm_concurrency_deep"] = concurrency_deep
    settings.set("pipeline_config", config)

    logger.info("Running pipeline: model=%s fast=%d deep=%d stages=%s",
                model, concurrency_fast, concurrency_deep, stages)

    repo = Path(repo_path).resolve()
    index_dir = repo / ".codrag"
    index_dir.mkdir(parents=True, exist_ok=True)

    headless_config = HeadlessConfig(
        repo_path=str(repo),
        model_provider="local",
        model_name=model,
    )

    factory = HeadlessWorkerFactory(
        repo_root=repo,
        index_dir=index_dir,
        config=headless_config,
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

    fast_stages = {"structural", "inferred_edges", "catalogue", "validation", "knowledge"}
    deep_stages = {"enrichment", "clustering", "atlas", "deepening", "deep_knowledge"}

    def progress_cb(message: str, current: int, total: int) -> None:
        pass

    start = time.monotonic()

    for stage_id, stage_label in HEADLESS_STAGES:
        if stages == "fast" and stage_id not in fast_stages:
            continue
        if stages == "deep" and stage_id not in deep_stages:
            continue

        worker = workers[stage_id]
        logger.info("  %s", stage_label)
        try:
            worker(progress_cb)
        except Exception as e:
            logger.error("  FAILED: %s — %s", stage_id, e)
            if stage_id == "structural":
                break

    return time.monotonic() - start


def reset_pipeline_output(repo_path: str) -> None:
    """Delete pipeline output files to force a clean re-run."""
    index_dir = Path(repo_path) / ".codrag"
    for fname in [
        "trace_augmented.jsonl", "trace_augmented_manifest.json",
        "trace_epistemic.jsonl",
        "trace_inferred_edges.jsonl", "trace_inferred_manifest.json",
        "trace_modules.jsonl",
    ]:
        fpath = index_dir / fname
        if fpath.exists():
            fpath.unlink()
            logger.info("Deleted %s", fpath)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 40 Accuracy Benchmark — Sequential vs Concurrent quality comparison"
    )
    parser.add_argument("--model", required=True, help="Ollama model name")
    parser.add_argument("--concurrency", type=int, default=2,
                       help="Concurrency level for test run (baseline is always 1)")
    parser.add_argument("--repo-path", required=True, help="Path to test repository")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--stages", choices=["all", "fast", "deep"], default="all")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    args = parser.parse_args()

    result: Dict[str, Any] = {
        "benchmark": "phase40_accuracy",
        "model": args.model,
        "concurrency_test": args.concurrency,
        "repo_path": args.repo_path,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # Initialize settings store
    from codrag.services.settings_store import settings
    data_dir = Path(os.environ.get("CODRAG_DATA_DIR", str(Path.home() / ".codrag")))
    data_dir.mkdir(parents=True, exist_ok=True)
    settings.init(data_dir / "codrag_settings.db")

    index_dir = Path(args.repo_path) / ".codrag"

    # ── Run 1: Sequential baseline (c=1) ──
    logger.info("=" * 60)
    logger.info("RUN 1: SEQUENTIAL BASELINE (concurrency=1)")
    logger.info("=" * 60)

    reset_pipeline_output(args.repo_path)
    duration_base = run_pipeline_with_config(
        args.repo_path, concurrency_fast=1, concurrency_deep=1,
        model=args.model, ollama_url=args.ollama_url, stages=args.stages,
    )
    snapshot_base = snapshot_outputs(index_dir)
    result["baseline_duration_s"] = round(duration_base, 2)
    logger.info("Baseline complete in %.1fs", duration_base)

    # ── Run 2: Concurrent test (c=N) ──
    logger.info("=" * 60)
    logger.info("RUN 2: CONCURRENT TEST (concurrency=%d)", args.concurrency)
    logger.info("=" * 60)

    reset_pipeline_output(args.repo_path)
    duration_test = run_pipeline_with_config(
        args.repo_path, concurrency_fast=args.concurrency, concurrency_deep=args.concurrency,
        model=args.model, ollama_url=args.ollama_url, stages=args.stages,
    )
    snapshot_test = snapshot_outputs(index_dir)
    result["test_duration_s"] = round(duration_test, 2)
    result["speedup"] = round(duration_base / max(duration_test, 0.1), 2)
    logger.info("Test complete in %.1fs (%.2fx speedup)", duration_test, result["speedup"])

    # ── Compare ──
    logger.info("=" * 60)
    logger.info("COMPARING OUTPUTS")
    logger.info("=" * 60)

    result["comparison"] = {
        "augmentations": compare_augmentations(snapshot_base, snapshot_test),
        "epistemic": compare_epistemic(snapshot_base, snapshot_test),
        "inferred_edges": compare_edges(snapshot_base, snapshot_test),
        "modules": compare_modules(snapshot_base, snapshot_test),
    }

    # ── Verdict ──
    aug_cmp = result["comparison"]["augmentations"]
    epi_cmp = result["comparison"]["epistemic"]

    # Quality is "acceptable" if:
    # - Role match rate > 80%
    # - Avg epistemic confidence delta < 0.1
    # - Architecture layer match rate > 70%
    # - Domain tag Jaccard > 0.6
    checks = {
        "role_match": aug_cmp["role_match_rate"] >= 0.80,
        "confidence_stable": epi_cmp["avg_confidence_delta"] <= 0.10,
        "layer_match": epi_cmp["architecture_layer_match_rate"] >= 0.70,
        "tag_overlap": epi_cmp["avg_domain_tag_jaccard"] >= 0.60,
    }
    result["quality_checks"] = checks
    result["quality_passed"] = all(checks.values())
    result["status"] = "passed" if result["quality_passed"] else "degraded"
    result["finished_at"] = datetime.now(timezone.utc).isoformat()

    # ── Report ──
    logger.info("")
    logger.info("=" * 60)
    logger.info("ACCURACY VERDICT: %s", "PASSED" if result["quality_passed"] else "DEGRADED")
    logger.info("=" * 60)
    logger.info("Speedup: %.2fx (%s → %s)",
                result["speedup"],
                f"{duration_base:.0f}s",
                f"{duration_test:.0f}s")
    logger.info("Role match rate: %.1f%%", aug_cmp["role_match_rate"] * 100)
    logger.info("Avg epistemic confidence delta: %.4f", epi_cmp["avg_confidence_delta"])
    logger.info("Architecture layer match: %.1f%%", epi_cmp["architecture_layer_match_rate"] * 100)
    logger.info("Domain tag Jaccard: %.3f", epi_cmp["avg_domain_tag_jaccard"])
    for check, passed in checks.items():
        logger.info("  %s %s", "✓" if passed else "✗", check)
    logger.info("=" * 60)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info("Results written to %s", args.output)

    sys.exit(0 if result["quality_passed"] else 1)


if __name__ == "__main__":
    main()
