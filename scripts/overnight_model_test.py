#!/usr/bin/env -S /Volumes/4TB-BAD/HumanAI/CoDRAG/.venv/bin/python
"""Overnight model comparison on the TEST repo (real Next.js marketing site).

Runs the full CoDRAG enrichment pipeline (augment → epistemic → cluster)
with 4 different model configurations, saving all artifacts and timing
for morning comparison.

Order:
  1. qwen3.5:9b      (Ollama, think=false)  — fast candidate
  2. qwen3.5:35b-a3b  (Ollama, think=false)  — fast+quality candidate
  3. qwen3.5:35b-a3b  (Ollama, think=true)   — does thinking help?
  4. qwen3.5:27b      (Ollama, think=false)  — current quality baseline

Usage:
    python scripts/overnight_model_test.py          # run all 4
    python scripts/overnight_model_test.py --only 1  # run just config #1
    nohup python scripts/overnight_model_test.py > results/overnight.log 2>&1 &
"""

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

# ── Setup ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

REPO_PATH = PROJECT_ROOT / "TEST"
INDEX_DIR = REPO_PATH / ".codrag"
OLLAMA_URL = "http://127.0.0.1:11434"
RESULTS_BASE = PROJECT_ROOT / "results"

# Files that constitute the enrichment overlay (wiped between runs)
ENRICHMENT_FILES = [
    "trace_augmented.jsonl",
    "trace_augment_manifest.json",
    "trace_epistemic.jsonl",
    "trace_modules.jsonl",
    "trace_group_reasoning.jsonl",
    "atlas.json",
]

# Files we KEEP between runs (structural trace — same for all models)
KEEP_FILES = [
    "trace_nodes.jsonl",
    "trace_edges.jsonl",
    "trace_manifest.json",
    "trace_inferred_edges.jsonl",
    "trace_inferred_manifest.json",
    "documents.json",
    "embeddings.npy",
    "knowledge_documents.json",
    "knowledge_embeddings.npy",
    "knowledge_manifest.json",
    "manifest.json",
    "fts.sqlite3",
    ".checkpoints",
]

# ── Model Configs ─────────────────────────────────────────────────────

CONFIGS = [
    {
        "id": "9b-nothink",
        "label": "qwen3.5:9b (no-think)",
        "model": "qwen3.5:9b",
        "think": False,
        "timeout": 180.0,
        "description": "Fast candidate — smallest qwen3.5, no thinking overhead",
    },
    {
        "id": "35b-a3b-nothink",
        "label": "qwen3.5:35b-a3b (no-think)",
        "model": "qwen3.5:35b-a3b",
        "think": False,
        "timeout": 180.0,
        "description": "Fast+quality candidate — MoE 3B active, no thinking",
    },
    {
        "id": "35b-a3b-think",
        "label": "qwen3.5:35b-a3b (think)",
        "model": "qwen3.5:35b-a3b",
        "think": True,
        "timeout": 600.0,
        "description": "Does thinking improve quality? MoE with full reasoning",
    },
    {
        "id": "27b-nothink",
        "label": "qwen3.5:27b (no-think)",
        "model": "qwen3.5:27b",
        "think": False,
        "timeout": 300.0,
        "description": "Quality baseline — dense 27B, no thinking",
    },
]

# ── Logging ───────────────────────────────────────────────────────────

def setup_logging(run_dir: Path):
    log_file = run_dir / "run.log"
    # Use unbuffered file handler so logs appear in real-time
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-5s %(name)s: %(message)s")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(sh)
    # Force flush after every log line
    class FlushFilter(logging.Filter):
        def filter(self, record):
            fh.flush()
            return True
    fh.addFilter(FlushFilter())
    return logging.getLogger("overnight")


# ── Pipeline Runner ───────────────────────────────────────────────────

def wipe_enrichment(index_dir: Path, logger):
    """Remove enrichment overlay files, preserving structural trace."""
    for fname in ENRICHMENT_FILES:
        fpath = index_dir / fname
        if fpath.exists():
            fpath.unlink()
            logger.info("  Removed %s", fname)


def save_enrichment(index_dir: Path, dest_dir: Path, logger):
    """Copy enrichment files to results directory for comparison."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for fname in ENRICHMENT_FILES:
        src = index_dir / fname
        if src.exists():
            shutil.copy2(src, dest_dir / fname)
            logger.info("  Saved %s (%d bytes)", fname, src.stat().st_size)


def count_enrichment_stats(index_dir: Path) -> Dict[str, Any]:
    """Read enrichment files and compute summary stats."""
    stats: Dict[str, Any] = {}

    # Augmentations
    aug_path = index_dir / "trace_augmented.jsonl"
    if aug_path.exists():
        entries = []
        with open(aug_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        stats["augmented_count"] = len(entries)
        confs = [e.get("confidence", 0) for e in entries if "confidence" in e]
        stats["augment_avg_confidence"] = sum(confs) / len(confs) if confs else 0
        roles = {}
        for e in entries:
            r = e.get("role", "unknown")
            roles[r] = roles.get(r, 0) + 1
        stats["augment_roles"] = roles
        # Collect summaries for quality review
        stats["augment_summaries"] = {
            e.get("node_id", "?"): e.get("summary", "")[:200]
            for e in entries if e.get("kind") == "file" or e.get("node_id", "").startswith("file:")
        }
    else:
        stats["augmented_count"] = 0

    # Epistemic
    epi_path = index_dir / "trace_epistemic.jsonl"
    if epi_path.exists():
        entries = []
        with open(epi_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        stats["epistemic_count"] = len(entries)
        confs = [e.get("epistemic_confidence", 0) for e in entries]
        stats["epistemic_avg_confidence"] = sum(confs) / len(confs) if confs else 0
        layers = {}
        for e in entries:
            l = e.get("architecture_layer", "unknown")
            layers[l] = layers.get(l, 0) + 1
        stats["epistemic_layers"] = layers
        all_tags = []
        for e in entries:
            all_tags.extend(e.get("domain_tags", []))
        stats["epistemic_unique_tags"] = len(set(all_tags))
        tag_counts = {}
        for t in all_tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
        stats["epistemic_top_tags"] = dict(sorted(tag_counts.items(), key=lambda x: -x[1])[:15])
        stats["epistemic_summaries"] = {
            e.get("node_id", "?"): e.get("extended_summary", "")[:200]
            for e in entries
        }
    else:
        stats["epistemic_count"] = 0

    # Modules
    mod_path = index_dir / "trace_modules.jsonl"
    if mod_path.exists():
        entries = []
        with open(mod_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        stats["module_count"] = len(entries)
        stats["module_names"] = [e.get("name", e.get("module_id", "?")) for e in entries]
    else:
        stats["module_count"] = 0

    return stats


def run_pipeline(config: Dict[str, Any], run_dir: Path, logger) -> Dict[str, Any]:
    """Run the full enrichment pipeline with a specific model config."""
    from codrag.core.llm_client import LLMClient
    from codrag.core.augmenter import TraceAugmenter
    from codrag.core.epistemic_enrichment import EpistemicEnricher
    from codrag.core.cluster import ClusterSynthesizer

    result = {
        "config": config,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stages": {},
    }

    # Create LLM client
    client = LLMClient(
        endpoint_url=OLLAMA_URL,
        model=config["model"],
        provider="ollama",
        timeout=config["timeout"],
    )

    think = config["think"]
    logger.info("LLM client: model=%s think=%s timeout=%.0f", config["model"], think, config["timeout"])

    # ── Stage 1: Augmentation ─────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 1: Augmentation (Pass 1)")
    logger.info("=" * 60)

    augmenter = TraceAugmenter(
        index_dir=INDEX_DIR,
        repo_root=REPO_PATH,
        llm_client=client,
    )
    # Patch the LLM generate calls to pass think parameter
    original_generate = client.generate
    def patched_generate(*args, **kwargs):
        kwargs.setdefault("think", think)
        return original_generate(*args, **kwargs)
    client.generate = patched_generate

    t0 = time.monotonic()
    try:
        aug_result = augmenter.run()
        aug_time = time.monotonic() - t0
        result["stages"]["augment"] = {
            "status": "success",
            "duration_s": round(aug_time, 1),
            "total_nodes": aug_result.total_nodes,
            "augmented": aug_result.augmented,
            "skipped": aug_result.skipped,
            "synthetic": aug_result.synthetic,
            "errors": aug_result.errors[:10],
        }
        logger.info("Augmentation complete: %d augmented, %d skipped in %.1fs",
                     aug_result.augmented, aug_result.skipped, aug_time)
    except Exception as e:
        aug_time = time.monotonic() - t0
        result["stages"]["augment"] = {
            "status": "error",
            "duration_s": round(aug_time, 1),
            "error": str(e),
        }
        logger.error("Augmentation FAILED after %.1fs: %s", aug_time, e, exc_info=True)

    # ── Stage 2: Epistemic Enrichment ─────────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 2: Epistemic Enrichment (Pass 2)")
    logger.info("=" * 60)

    enricher = EpistemicEnricher(
        index_dir=INDEX_DIR,
        repo_root=REPO_PATH,
        llm=client,
    )

    t0 = time.monotonic()
    try:
        epi_result = enricher.run()
        epi_time = time.monotonic() - t0
        result["stages"]["epistemic"] = {
            "status": "success",
            "duration_s": round(epi_time, 1),
            **{k: v for k, v in epi_result.items() if k != "entries"},
        }
        logger.info("Epistemic complete: %s in %.1fs", 
                     {k: v for k, v in epi_result.items() if k not in ("entries",)}, epi_time)
    except Exception as e:
        epi_time = time.monotonic() - t0
        result["stages"]["epistemic"] = {
            "status": "error",
            "duration_s": round(epi_time, 1),
            "error": str(e),
        }
        logger.error("Epistemic FAILED after %.1fs: %s", epi_time, e, exc_info=True)

    # ── Stage 3: Cluster Synthesis ────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 3: Cluster Synthesis (Pass 3)")
    logger.info("=" * 60)

    synthesizer = ClusterSynthesizer(
        index_dir=INDEX_DIR,
        llm=client,
    )

    t0 = time.monotonic()
    try:
        cluster_result = synthesizer.run()
        cluster_time = time.monotonic() - t0
        result["stages"]["cluster"] = {
            "status": "success",
            "duration_s": round(cluster_time, 1),
            **{k: v for k, v in cluster_result.items()},
        }
        logger.info("Clustering complete: %s in %.1fs", cluster_result, cluster_time)
    except Exception as e:
        cluster_time = time.monotonic() - t0
        result["stages"]["cluster"] = {
            "status": "error",
            "duration_s": round(cluster_time, 1),
            "error": str(e),
        }
        logger.error("Clustering FAILED after %.1fs: %s", cluster_time, e, exc_info=True)

    # ── Collect stats ─────────────────────────────────────────────────
    result["enrichment_stats"] = count_enrichment_stats(INDEX_DIR)
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["total_duration_s"] = round(
        sum(s.get("duration_s", 0) for s in result["stages"].values()), 1
    )

    return result


# ── Main Orchestrator ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Overnight model comparison on TEST repo")
    parser.add_argument("--only", type=int, help="Run only config N (1-indexed)")
    parser.add_argument("--skip-trace", action="store_true", help="Skip trace rebuild (use existing)")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_BASE / f"overnight_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(run_dir)
    logger.info("=" * 70)
    logger.info("  OVERNIGHT MODEL COMPARISON")
    logger.info("  Repo: %s", REPO_PATH)
    logger.info("  Index: %s", INDEX_DIR)
    logger.info("  Results: %s", run_dir)
    logger.info("  Configs: %d", len(CONFIGS))
    logger.info("=" * 70)

    # Verify Ollama is running and models are available
    import requests
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        available = {m["name"] for m in resp.json().get("models", [])}
        for cfg in CONFIGS:
            if cfg["model"] in available:
                logger.info("  ✓ %s", cfg["model"])
            else:
                logger.error("  ✗ %s NOT AVAILABLE — run: ollama pull %s", cfg["model"], cfg["model"])
                sys.exit(1)
    except Exception as e:
        logger.error("Cannot connect to Ollama: %s", e)
        sys.exit(1)

    # Verify structural trace exists
    if not (INDEX_DIR / "trace_nodes.jsonl").exists():
        logger.error("No trace_nodes.jsonl found. Run the structural trace first (codrag build).")
        sys.exit(1)

    node_count = sum(1 for _ in open(INDEX_DIR / "trace_nodes.jsonl"))
    edge_count = sum(1 for _ in open(INDEX_DIR / "trace_edges.jsonl"))
    logger.info("Structural trace: %d nodes, %d edges", node_count, edge_count)

    # Determine which configs to run
    configs_to_run = CONFIGS
    if args.only:
        idx = args.only - 1
        if 0 <= idx < len(CONFIGS):
            configs_to_run = [CONFIGS[idx]]
        else:
            logger.error("--only must be 1-%d", len(CONFIGS))
            sys.exit(1)

    all_results = {}
    overall_start = time.monotonic()

    for i, config in enumerate(configs_to_run):
        config_start = time.monotonic()
        logger.info("")
        logger.info("#" * 70)
        logger.info("  CONFIG %d/%d: %s", i + 1, len(configs_to_run), config["label"])
        logger.info("  %s", config["description"])
        logger.info("#" * 70)

        # Wipe enrichment files for clean run
        logger.info("Wiping enrichment files...")
        wipe_enrichment(INDEX_DIR, logger)

        # Run pipeline
        result = run_pipeline(config, run_dir, logger)

        # Save enrichment artifacts
        config_dir = run_dir / config["id"]
        logger.info("Saving enrichment artifacts to %s...", config_dir)
        save_enrichment(INDEX_DIR, config_dir, logger)

        # Save result JSON
        with open(config_dir / "result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)

        all_results[config["id"]] = result

        config_time = time.monotonic() - config_start
        logger.info("Config %s completed in %.1fs (%.1f min)",
                     config["id"], config_time, config_time / 60)

    overall_time = time.monotonic() - overall_start

    # ── Summary Report ────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 70)
    logger.info("  OVERNIGHT RUN COMPLETE")
    logger.info("  Total time: %.1fs (%.1f min)", overall_time, overall_time / 60)
    logger.info("=" * 70)

    summary_lines = []
    summary_lines.append("")
    summary_lines.append("%-25s %8s %8s %8s %8s %6s %6s %6s" % (
        "Config", "Augment", "Epist.", "Cluster", "Total", "Aug#", "Epi#", "Mod#"))
    summary_lines.append("-" * 85)

    for cfg_id, res in all_results.items():
        stages = res.get("stages", {})
        aug_t = stages.get("augment", {}).get("duration_s", 0)
        epi_t = stages.get("epistemic", {}).get("duration_s", 0)
        clu_t = stages.get("cluster", {}).get("duration_s", 0)
        total = res.get("total_duration_s", 0)
        stats = res.get("enrichment_stats", {})
        aug_n = stats.get("augmented_count", 0)
        epi_n = stats.get("epistemic_count", 0)
        mod_n = stats.get("module_count", 0)

        summary_lines.append("%-25s %7.0fs %7.0fs %7.0fs %7.0fs %6d %6d %6d" % (
            cfg_id, aug_t, epi_t, clu_t, total, aug_n, epi_n, mod_n))

    for line in summary_lines:
        logger.info(line)

    # Quality comparison
    logger.info("")
    logger.info("QUALITY COMPARISON:")
    logger.info("-" * 70)
    for cfg_id, res in all_results.items():
        stats = res.get("enrichment_stats", {})
        logger.info("")
        logger.info("  %s:", cfg_id)
        logger.info("    Augment: %d items, avg conf=%.2f",
                     stats.get("augmented_count", 0),
                     stats.get("augment_avg_confidence", 0))
        logger.info("    Roles: %s", stats.get("augment_roles", {}))
        logger.info("    Epistemic: %d items, avg conf=%.2f, %d unique tags",
                     stats.get("epistemic_count", 0),
                     stats.get("epistemic_avg_confidence", 0),
                     stats.get("epistemic_unique_tags", 0))
        logger.info("    Layers: %s", stats.get("epistemic_layers", {}))
        logger.info("    Top tags: %s", stats.get("epistemic_top_tags", {}))
        logger.info("    Modules: %d — %s", stats.get("module_count", 0),
                     stats.get("module_names", []))

    # Save combined results
    with open(run_dir / "summary.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    logger.info("\nAll results saved to %s", run_dir)


if __name__ == "__main__":
    main()
