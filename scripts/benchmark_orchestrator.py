#!/usr/bin/env python3
"""
Phase 40 Benchmark Orchestrator
=================================

Queues and runs multiple concurrency benchmarks across different models
and concurrency settings, then produces a summary comparison report.

Usage:
    python scripts/benchmark_orchestrator.py \
        --repo-path /path/to/test/repo \
        --output-dir results/phase40_benchmarks

This will run all configured test matrix entries sequentially (one model
at a time to avoid VRAM contention), writing per-run JSON results and
a final summary CSV + JSON.

The full matrix takes several hours. You can safely Ctrl+C and resume —
completed runs are detected by their output files and skipped.

Test Matrix (default):
    Models: qwen3:4b, qwen3:8b, qwen3:30b-a3b-coder, qwen3.5:35b, qwen3.5:122b
    Concurrency: 1, 2, 4
    = 15 runs total
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")

# ── Test Matrix ──────────────────────────────────────────────────

# Each entry: (model_name, model_role, concurrency_levels)
# model_role: "both" = use for both small and large model slots
#             "small" = only fast-sync stages
#             "large" = only deep-enrichment stages
# Models are organized by their pipeline slot:
#   Fast/Instruct: qwen3:4b-instruct, qwen3:8b
#   Coder:         qwen3-coder:30b, deepseek-coder:6.7b
#   Deep/Thinking: qwen3.5:35b-a3b, qwen3.5:122b-a10b, deepseek-r1:32b
#
# Each test configures the model in the appropriate slot(s).
# model_role "both" = configure in all slots for simplicity.
# model_role "small" / "code" / "large" = configure in specific slot only.

DEFAULT_MATRIX: List[Dict[str, Any]] = [
    # ── Fast/Instruct models (small, fast per-token) ──
    {
        "model": "qwen3:4b-instruct",
        "model_role": "both",
        "concurrency_levels": [1, 2, 4],
        "description": "Smallest instruct model — fastest per-token, best concurrency scaling",
    },
    {
        "model": "qwen3:8b",
        "model_role": "both",
        "concurrency_levels": [1, 2, 4],
        "description": "Standard model — production default for most users",
    },
    # ── Coder models (code-specialized, MoE or dense) ──
    {
        "model": "deepseek-coder:6.7b",
        "model_role": "both",
        "concurrency_levels": [1, 2],
        "description": "Small coder — tests DeepSeek family JSON/think tag handling",
    },
    {
        "model": "qwen3-coder:30b",
        "model_role": "both",
        "concurrency_levels": [1, 2],
        "description": "Large coder — tests quality vs speed tradeoff with code-specialized model",
    },
    # ── Deep/Thinking models (large, reasoning-focused) ──
    {
        "model": "deepseek-r1:32b",
        "model_role": "both",
        "concurrency_levels": [1, 2],
        "description": "DeepSeek reasoning model — tests think tag handling from DeepSeek family",
    },
    {
        "model": "qwen3.5:35b-a3b",
        "model_role": "both",
        "concurrency_levels": [1, 2],
        "description": "Qwen 3.5 MoE — tests think tags + concurrency on workstation hardware",
    },
    {
        "model": "qwen3.5:122b-a10b",
        "model_role": "both",
        "concurrency_levels": [1],
        "description": "Ultra model — baseline only, needs 128GB+ (tests Qwen 3.5 think tags at scale)",
    },
]


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    return text.replace(":", "_").replace("/", "_").replace(".", "_").replace(" ", "_")


def run_single_benchmark(
    model: str,
    concurrency: int,
    repo_path: str,
    output_path: str,
    model_role: str = "both",
    stages: str = "all",
    ollama_url: str = "http://localhost:11434",
) -> Dict[str, Any]:
    """Run a single benchmark as a subprocess.

    Uses subprocess to ensure clean state between runs (no leaked
    model caches, thread pools, or VRAM allocations).
    """
    script = str(Path(__file__).parent / "benchmark_concurrency.py")

    cmd = [
        sys.executable, script,
        "--model", model,
        "--concurrency", str(concurrency),
        "--repo-path", repo_path,
        "--output", output_path,
        "--stages", stages,
        "--model-role", model_role,
        "--ollama-url", ollama_url,
    ]

    logger.info("Starting: %s concurrency=%d → %s", model, concurrency, output_path)
    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour max per run
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src")},
        )

        elapsed = time.monotonic() - start

        if result.returncode != 0:
            logger.error(
                "FAILED: %s c=%d (%.0fs)\nstderr: %s",
                model, concurrency, elapsed, result.stderr[-500:] if result.stderr else "(none)",
            )
            return {"status": "failed", "error": result.stderr[-500:], "duration_s": elapsed}

        logger.info("COMPLETED: %s c=%d in %.0fs", model, concurrency, elapsed)

        # Read the output JSON
        if Path(output_path).exists():
            with open(output_path) as f:
                return json.load(f)

        return {"status": "completed", "duration_s": elapsed}

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        logger.error("TIMEOUT: %s c=%d after %.0fs", model, concurrency, elapsed)
        return {"status": "timeout", "duration_s": elapsed}
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("ERROR: %s c=%d — %s", model, concurrency, e)
        return {"status": "error", "error": str(e), "duration_s": elapsed}


def unload_all_models(ollama_url: str = "http://localhost:11434") -> None:
    """Unload all models from Ollama to free VRAM between runs."""
    import requests

    try:
        resp = requests.get(f"{ollama_url}/api/ps", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("models", [])
            for m in models:
                name = m.get("name", "")
                if name:
                    logger.info("Unloading model '%s' to free VRAM...", name)
                    try:
                        requests.post(
                            f"{ollama_url}/api/generate",
                            json={"model": name, "keep_alive": 0},
                            timeout=30,
                        )
                    except Exception:
                        pass
    except Exception as e:
        logger.warning("Failed to unload models: %s", e)


def write_summary_csv(
    results: List[Dict[str, Any]],
    output_path: str,
) -> None:
    """Write a CSV summary of all benchmark results."""
    fieldnames = [
        "model", "concurrency", "status", "total_duration_s",
        "stage_structural", "stage_inferred_edges", "stage_catalogue",
        "stage_epistemic", "stage_clustering", "stage_atlas",
        "stage_deepening",
        "trace_nodes_count", "trace_edges_count",
        "augmented", "synthetic", "failed",
        "avg_epistemic_confidence", "epistemic_entries",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for r in results:
            row = {
                "model": r.get("model", ""),
                "concurrency": r.get("concurrency", ""),
                "status": r.get("status", ""),
                "total_duration_s": r.get("total_duration_s", ""),
            }

            # Flatten stage timings
            stages = r.get("stages", {})
            for stage_name in ["structural", "inferred_edges", "catalogue",
                              "epistemic", "clustering", "atlas", "deepening"]:
                # Try various key patterns
                for key in [stage_name, f"augment_{stage_name}", f"{stage_name}_enrichment",
                           f"cluster_synthesis", f"epistemic_enrichment"]:
                    if key in stages:
                        row[f"stage_{stage_name}"] = round(stages[key], 1)
                        break

            # Flatten quality metrics
            quality = r.get("quality", {})
            for qkey in ["trace_nodes_count", "trace_edges_count", "augmented",
                        "synthetic", "failed", "avg_epistemic_confidence", "epistemic_entries"]:
                if qkey in quality:
                    row[qkey] = quality[qkey]

            writer.writerow(row)

    logger.info("Summary CSV written to %s", output_path)


def write_summary_json(
    results: List[Dict[str, Any]],
    output_path: str,
) -> None:
    """Write a JSON summary with all results."""
    summary = {
        "benchmark_suite": "phase40_concurrency",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": len(results),
        "completed": sum(1 for r in results if r.get("status") == "completed"),
        "failed": sum(1 for r in results if r.get("status") != "completed"),
        "results": results,
    }

    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info("Summary JSON written to %s", output_path)


def print_summary_table(results: List[Dict[str, Any]]) -> None:
    """Print a formatted summary table to the console."""
    print("\n" + "=" * 80)
    print("PHASE 40 CONCURRENCY BENCHMARK RESULTS")
    print("=" * 80)
    print(f"{'Model':<30} {'C':>3} {'Status':>10} {'Time':>8} {'Nodes':>7} {'Epi.Conf':>9}")
    print("-" * 80)

    for r in results:
        model = r.get("model", "?")[:29]
        conc = r.get("concurrency", "?")
        status = r.get("status", "?")[:9]
        total = r.get("total_duration_s", 0)
        quality = r.get("quality", {})
        nodes = quality.get("trace_nodes_count", "")
        conf = quality.get("avg_epistemic_confidence", "")

        time_str = f"{total:.0f}s" if isinstance(total, (int, float)) else "?"
        conf_str = f"{conf:.3f}" if isinstance(conf, (int, float)) else ""

        print(f"{model:<30} {conc:>3} {status:>10} {time_str:>8} {nodes:>7} {conf_str:>9}")

    print("=" * 80)

    # Compute speedup for models with multiple concurrency levels
    by_model: Dict[str, List[Dict]] = {}
    for r in results:
        model = r.get("model", "?")
        by_model.setdefault(model, []).append(r)

    print("\nSPEEDUP ANALYSIS:")
    print("-" * 60)
    for model, runs in by_model.items():
        completed = [r for r in runs if r.get("status") == "completed"]
        if len(completed) < 2:
            continue
        baseline = next((r for r in completed if r.get("concurrency") == 1), completed[0])
        base_time = baseline.get("total_duration_s", 1)
        for r in completed:
            if r is not baseline:
                speedup = base_time / max(r.get("total_duration_s", 1), 0.1)
                print(f"  {model} c={r['concurrency']}: {speedup:.2f}x speedup vs c=1")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Phase 40 Benchmark Orchestrator — Queue multiple model/concurrency tests"
    )
    parser.add_argument("--repo-path", required=True, help="Path to test repository")
    parser.add_argument("--output-dir", default="results/phase40_benchmarks",
                       help="Directory for output files")
    parser.add_argument("--stages", choices=["all", "fast", "deep"], default="all",
                       help="Which pipeline stages to run")
    parser.add_argument("--ollama-url", default="http://localhost:11434",
                       help="Ollama API URL")
    parser.add_argument("--models", nargs="*",
                       help="Override model list (e.g., qwen3:4b qwen3:8b)")
    parser.add_argument("--concurrency-levels", nargs="*", type=int,
                       help="Override concurrency levels (e.g., 1 2 4)")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                       help="Skip runs that already have output files (default: True)")
    parser.add_argument("--no-skip-existing", action="store_false", dest="skip_existing",
                       help="Re-run all benchmarks even if output exists")
    parser.add_argument("--unload-between", action="store_true", default=True,
                       help="Unload models between runs to free VRAM (default: True)")
    parser.add_argument("--mode", choices=["accuracy", "speed", "both"], default="both",
                       help="Test mode: 'accuracy' runs sequential vs concurrent quality comparison first, "
                            "'speed' runs the full throughput matrix, 'both' runs accuracy then speed (default)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build test matrix
    if args.models:
        matrix = [
            {
                "model": m,
                "model_role": "both",
                "concurrency_levels": args.concurrency_levels or [1, 2, 4],
            }
            for m in args.models
        ]
    else:
        matrix = DEFAULT_MATRIX

    # Flatten matrix into individual runs
    runs: List[Tuple[str, str, int]] = []
    for entry in matrix:
        model = entry["model"]
        role = entry.get("model_role", "both")
        levels = entry.get("concurrency_levels", [1, 2, 4])
        if args.concurrency_levels:
            levels = args.concurrency_levels
        for c in levels:
            runs.append((model, role, c))

    total_runs = len(runs)
    logger.info("=" * 60)
    logger.info("PHASE 40 BENCHMARK ORCHESTRATOR")
    logger.info("Mode: %s", args.mode)
    logger.info("Test matrix: %d speed runs across %d models", total_runs, len(matrix))
    logger.info("Repo: %s", args.repo_path)
    logger.info("Output: %s", output_dir)
    logger.info("Stages: %s", args.stages)
    logger.info("=" * 60)

    orchestrator_start = time.monotonic()

    # ── Phase 1: Accuracy Tests ──────────────────────────────────
    # Run sequential (c=1) vs concurrent (c=2) for each model to verify
    # quality is not degraded. Must pass before speed tests.
    if args.mode in ("accuracy", "both"):
        accuracy_dir = output_dir / "accuracy"
        accuracy_dir.mkdir(parents=True, exist_ok=True)

        accuracy_models = list({entry["model"] for entry in matrix})
        logger.info("")
        logger.info("=" * 60)
        logger.info("PHASE 1: ACCURACY TESTS (%d models)", len(accuracy_models))
        logger.info("=" * 60)

        accuracy_script = str(Path(__file__).parent / "benchmark_accuracy.py")
        accuracy_results: List[Dict[str, Any]] = []

        for i, model in enumerate(accuracy_models, 1):
            slug = slugify(model)
            acc_output = str(accuracy_dir / f"accuracy_{slug}.json")

            if args.skip_existing and Path(acc_output).exists():
                logger.info("[%d/%d] Skipping accuracy test for %s (exists)", i, len(accuracy_models), model)
                try:
                    with open(acc_output) as f:
                        accuracy_results.append(json.load(f))
                except Exception:
                    pass
                continue

            logger.info("[%d/%d] Accuracy test: %s (c=1 vs c=2)", i, len(accuracy_models), model)

            if args.unload_between:
                unload_all_models(args.ollama_url)
                time.sleep(2)

            cmd = [
                sys.executable, accuracy_script,
                "--model", model,
                "--concurrency", "2",
                "--repo-path", args.repo_path,
                "--output", acc_output,
                "--stages", args.stages,
                "--ollama-url", args.ollama_url,
            ]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=14400,  # 4 hours (runs pipeline twice)
                    env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src")},
                )
                if Path(acc_output).exists():
                    with open(acc_output) as f:
                        acc_result = json.load(f)
                    accuracy_results.append(acc_result)
                    status = acc_result.get("status", "unknown")
                    logger.info("  → %s (speedup: %.2fx)", status.upper(), acc_result.get("speedup", 0))
                else:
                    logger.error("  → FAILED (no output)")
                    accuracy_results.append({"model": model, "status": "failed"})
            except subprocess.TimeoutExpired:
                logger.error("  → TIMEOUT")
                accuracy_results.append({"model": model, "status": "timeout"})
            except Exception as e:
                logger.error("  → ERROR: %s", e)
                accuracy_results.append({"model": model, "status": "error", "error": str(e)})

        # Print accuracy summary
        print("\n" + "=" * 60)
        print("ACCURACY TEST RESULTS")
        print("=" * 60)
        all_passed = True
        for r in accuracy_results:
            passed = r.get("status") == "passed"
            if not passed:
                all_passed = False
            icon = "✓" if passed else "✗"
            print(f"  {icon} {r.get('model', '?')}: {r.get('status', '?')} "
                  f"(speedup: {r.get('speedup', '?')}x)")
        print("=" * 60)

        if not all_passed and args.mode == "both":
            logger.warning("Some accuracy tests failed. Speed tests will still run.")

        # Write accuracy summary
        with open(str(accuracy_dir / "accuracy_summary.json"), "w") as f:
            json.dump({"results": accuracy_results, "all_passed": all_passed}, f, indent=2, default=str)

    if args.mode == "accuracy":
        total_elapsed = time.monotonic() - orchestrator_start
        logger.info("Accuracy-only mode complete in %.1f min", total_elapsed / 60)
        return

    # ── Phase 2: Speed Tests ─────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("PHASE 2: SPEED TESTS (%d runs)", total_runs)
    logger.info("=" * 60)

    all_results: List[Dict[str, Any]] = []
    completed = 0
    skipped = 0

    for i, (model, role, concurrency) in enumerate(runs, 1):
        slug = slugify(model)
        output_path = str(output_dir / f"bench_{slug}_c{concurrency}.json")

        logger.info(
            "\n[%d/%d] Model: %s  Concurrency: %d  Role: %s",
            i, total_runs, model, concurrency, role,
        )

        # Skip if output already exists
        if args.skip_existing and Path(output_path).exists():
            logger.info("  → Skipping (output exists): %s", output_path)
            try:
                with open(output_path) as f:
                    existing = json.load(f)
                all_results.append(existing)
                skipped += 1
            except Exception:
                pass
            continue

        # Unload models between runs to free VRAM
        if args.unload_between and i > 1:
            unload_all_models(args.ollama_url)
            time.sleep(2)  # Give Ollama time to free memory

        result = run_single_benchmark(
            model=model,
            concurrency=concurrency,
            repo_path=args.repo_path,
            output_path=output_path,
            model_role=role,
            stages=args.stages,
            ollama_url=args.ollama_url,
        )

        all_results.append(result)
        completed += 1

        # Write intermediate summary after each run
        write_summary_json(all_results, str(output_dir / "summary.json"))

        # Estimate remaining time
        elapsed = time.monotonic() - orchestrator_start
        avg_per_run = elapsed / (completed + skipped) if (completed + skipped) > 0 else 0
        remaining = avg_per_run * (total_runs - i)
        logger.info(
            "Progress: %d/%d complete, %d skipped. ETA: %.0f min",
            completed, total_runs, skipped, remaining / 60,
        )

    # Final summary
    total_elapsed = time.monotonic() - orchestrator_start

    write_summary_json(all_results, str(output_dir / "summary.json"))
    write_summary_csv(all_results, str(output_dir / "summary.csv"))
    print_summary_table(all_results)

    logger.info(
        "Orchestrator complete: %d runs (%d completed, %d skipped) in %.1f min",
        total_runs, completed, skipped, total_elapsed / 60,
    )


if __name__ == "__main__":
    main()
