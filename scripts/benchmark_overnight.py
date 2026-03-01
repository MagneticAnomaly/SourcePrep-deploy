#!/usr/bin/env python3
"""
Phase 40 Overnight Benchmark Suite
====================================

Comprehensive 6-hour test suite that collects maximum data across:
- Multiple models (7 models across 3 families)
- Multiple concurrency levels (1, 2, 4)
- Multiple test repos (diverse languages and sizes)
- Accuracy comparison (sequential vs concurrent)

Designed to run unattended overnight and produce a detailed report.

Usage:
    python scripts/benchmark_overnight.py

Output:
    results/overnight_YYYYMMDD_HHMMSS/
    ├── accuracy/           # Sequential vs concurrent quality comparison
    ├── speed/              # Per-model, per-concurrency timing data
    ├── repos/              # Per-repo results
    ├── summary.json        # Machine-readable summary
    ├── summary.csv         # Spreadsheet-friendly summary
    └── report.txt          # Human-readable report
"""

from __future__ import annotations

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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = str(PROJECT_ROOT / ".venv" / "bin" / "python3")
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
REPOS_DIR = PROJECT_ROOT / "tests" / "eval" / "real_repos"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("overnight")

# ── Test Configuration ───────────────────────────────────────

# Models organized by slot — tests both accuracy and think-tag handling
MODELS = {
    "fast": [
        {"name": "qwen3:4b-instruct", "desc": "Smallest instruct, fast per-token"},
        {"name": "qwen3:8b", "desc": "Standard production model"},
    ],
    "coder": [
        {"name": "deepseek-coder:6.7b", "desc": "DeepSeek coder family"},
        {"name": "qwen3-coder:30b", "desc": "Large Qwen coder MoE"},
    ],
    "deep": [
        {"name": "deepseek-r1:32b", "desc": "DeepSeek reasoning (think tags)"},
        {"name": "qwen3.5:35b-a3b", "desc": "Qwen 3.5 MoE (think tags)"},
        # {"name": "qwen3.5:122b-a10b", "desc": "Ultra — only if 128GB+ RAM"},
    ],
}

# Select repos that cover different languages and sizes
# Small repos (~20-50 files): fast iteration, good for accuracy tests
# Medium repos (~100+ files): realistic workload for speed tests
TEST_REPOS = {
    "small": [
        "click-python",      # Python, small
        "chi-go",            # Go, small
        "cjson-c",           # C, very small
        "mini-redis-rust",   # Rust, small
    ],
    "medium": [
        "sqlmodel-python",   # Python, medium
        "gin-go",            # Go, medium
        "got-typescript",    # TypeScript, medium
        "bat-rust",          # Rust, medium
        "javalin-java",      # Java, medium
    ],
    "large": [
        "okhttp-kotlin",     # Kotlin/Java, large
        "ripgrep-rust",      # Rust, large
    ],
}

CONCURRENCY_LEVELS = [1, 2, 4]


def run_subprocess(cmd: List[str], timeout: int = 7200, label: str = "") -> Tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")}
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error("TIMEOUT after %ds: %s", timeout, label)
        return -1, "", f"Timeout after {timeout}s"
    except Exception as e:
        logger.error("ERROR: %s — %s", label, e)
        return -2, "", str(e)


def pull_model(model: str) -> bool:
    """Pull a model via Ollama CLI."""
    logger.info("Pulling model '%s'...", model)
    code, out, err = run_subprocess(["ollama", "pull", model], timeout=3600, label=f"pull {model}")
    if code == 0:
        logger.info("Model '%s' ready", model)
        return True
    logger.error("Failed to pull '%s': %s", model, err[:200])
    return False


def unload_models() -> None:
    """Unload all models from Ollama VRAM."""
    import requests
    try:
        resp = requests.get("http://localhost:11434/api/ps", timeout=10)
        if resp.status_code == 200:
            for m in resp.json().get("models", []):
                name = m.get("name", "")
                if name:
                    requests.post(
                        "http://localhost:11434/api/generate",
                        json={"model": name, "keep_alive": 0},
                        timeout=30,
                    )
    except Exception:
        pass
    time.sleep(2)


def clean_repo_index(repo_path: str) -> None:
    """Delete pipeline output files for a clean run."""
    index_dir = Path(repo_path) / ".codrag"
    for fname in [
        "trace_augmented.jsonl", "trace_augmented_manifest.json",
        "trace_epistemic.jsonl",
        "trace_inferred_edges.jsonl", "trace_inferred_manifest.json",
        "trace_modules.jsonl", "trace_atlas.md",
    ]:
        fpath = index_dir / fname
        if fpath.exists():
            fpath.unlink()


def run_accuracy_test(
    model: str,
    repo_path: str,
    output_path: str,
    concurrency: int = 2,
    stages: str = "fast",
) -> Optional[Dict[str, Any]]:
    """Run accuracy benchmark (sequential vs concurrent comparison)."""
    cmd = [
        VENV_PYTHON, str(SCRIPTS_DIR / "benchmark_accuracy.py"),
        "--model", model,
        "--concurrency", str(concurrency),
        "--repo-path", repo_path,
        "--output", output_path,
        "--stages", stages,
    ]
    label = f"accuracy {model} c={concurrency} {Path(repo_path).name}"
    logger.info("Running: %s", label)

    code, out, err = run_subprocess(cmd, timeout=7200, label=label)

    if Path(output_path).exists():
        with open(output_path) as f:
            return json.load(f)
    return {"status": "failed", "error": err[:500], "model": model}


def run_speed_test(
    model: str,
    concurrency: int,
    repo_path: str,
    output_path: str,
    stages: str = "fast",
) -> Optional[Dict[str, Any]]:
    """Run speed benchmark (single model + concurrency level)."""
    cmd = [
        VENV_PYTHON, str(SCRIPTS_DIR / "benchmark_concurrency.py"),
        "--model", model,
        "--concurrency", str(concurrency),
        "--repo-path", repo_path,
        "--output", output_path,
        "--stages", stages,
    ]
    label = f"speed {model} c={concurrency} {Path(repo_path).name}"
    logger.info("Running: %s", label)

    code, out, err = run_subprocess(cmd, timeout=7200, label=label)

    if Path(output_path).exists():
        with open(output_path) as f:
            return json.load(f)
    return {"status": "failed", "error": err[:500], "model": model, "concurrency": concurrency}


def write_report(results: Dict[str, Any], output_dir: Path) -> None:
    """Write a human-readable report."""
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("PHASE 40 OVERNIGHT BENCHMARK REPORT")
    report_lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    report_lines.append("=" * 70)
    report_lines.append("")

    # Accuracy results
    report_lines.append("ACCURACY TESTS (sequential c=1 vs concurrent c=2)")
    report_lines.append("-" * 70)
    for r in results.get("accuracy", []):
        model = r.get("model", "?")
        repo = Path(r.get("repo_path", "?")).name
        status = r.get("status", "?")
        speedup = r.get("speedup", "?")
        report_lines.append(f"  {status:>8}  {model:<30} {repo:<20} {speedup}x")

        # Quality details
        cmp = r.get("comparison", {})
        aug = cmp.get("augmentations", {})
        epi = cmp.get("epistemic", {})
        if aug:
            report_lines.append(f"           Role match: {aug.get('role_match_rate', 0):.1%}  "
                              f"Confidence delta: {aug.get('avg_confidence_delta', 0):.4f}")
        if epi:
            report_lines.append(f"           Layer match: {epi.get('architecture_layer_match_rate', 0):.1%}  "
                              f"Tag Jaccard: {epi.get('avg_domain_tag_jaccard', 0):.3f}")
    report_lines.append("")

    # Speed results
    report_lines.append("SPEED TESTS")
    report_lines.append("-" * 70)
    report_lines.append(f"{'Model':<30} {'C':>3} {'Repo':<20} {'Time':>8} {'Status':>10}")
    report_lines.append("-" * 70)
    for r in results.get("speed", []):
        model = r.get("model", "?")[:29]
        conc = r.get("concurrency", "?")
        repo = Path(r.get("repo_path", "?")).name[:19]
        total = r.get("total_duration_s", 0)
        status = r.get("status", "?")
        time_str = f"{total:.0f}s" if isinstance(total, (int, float)) else "?"
        report_lines.append(f"  {model:<30} {conc:>3} {repo:<20} {time_str:>8} {status:>10}")
    report_lines.append("")

    # Speedup analysis
    report_lines.append("SPEEDUP ANALYSIS")
    report_lines.append("-" * 70)
    by_key: Dict[str, List[Dict]] = {}
    for r in results.get("speed", []):
        if r.get("status") != "completed":
            continue
        key = f"{r.get('model', '?')}|{Path(r.get('repo_path', '?')).name}"
        by_key.setdefault(key, []).append(r)

    for key, runs in by_key.items():
        if len(runs) < 2:
            continue
        baseline = next((r for r in runs if r.get("concurrency") == 1), runs[0])
        base_time = baseline.get("total_duration_s", 1)
        model_name, repo_name = key.split("|")
        for r in runs:
            if r is not baseline:
                speedup = base_time / max(r.get("total_duration_s", 1), 0.1)
                report_lines.append(
                    f"  {model_name:<30} {repo_name:<20} c={r['concurrency']}: {speedup:.2f}x"
                )
    report_lines.append("")
    report_lines.append("=" * 70)

    report_text = "\n".join(report_lines)
    (output_dir / "report.txt").write_text(report_text)
    print(report_text)


def main():
    start_time = time.monotonic()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / "results" / f"overnight_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "accuracy").mkdir(exist_ok=True)
    (output_dir / "speed").mkdir(exist_ok=True)

    logger.info("=" * 70)
    logger.info("PHASE 40 OVERNIGHT BENCHMARK SUITE")
    logger.info("Output: %s", output_dir)
    logger.info("Max runtime: 6 hours")
    logger.info("=" * 70)

    all_results: Dict[str, List[Dict]] = {"accuracy": [], "speed": []}

    # ── Phase 1: Pull all models ──────────────────────────────
    logger.info("")
    logger.info("PHASE 1: Pulling models")
    available_models = []
    for slot, models in MODELS.items():
        for m in models:
            if pull_model(m["name"]):
                available_models.append(m["name"])
            else:
                logger.warning("Skipping '%s' — pull failed", m["name"])

    logger.info("Available models: %s", available_models)

    # ── Phase 2: Accuracy tests (small repos, fast stages) ────
    logger.info("")
    logger.info("=" * 70)
    logger.info("PHASE 2: ACCURACY TESTS")
    logger.info("=" * 70)

    for model in available_models:
        for repo_name in TEST_REPOS["small"]:
            repo_path = str(REPOS_DIR / repo_name)
            if not Path(repo_path).exists():
                continue

            slug = model.replace(":", "_").replace(".", "_")
            out_path = str(output_dir / "accuracy" / f"acc_{slug}_{repo_name}.json")

            if Path(out_path).exists():
                logger.info("Skipping (exists): %s", out_path)
                with open(out_path) as f:
                    all_results["accuracy"].append(json.load(f))
                continue

            # Check time budget
            elapsed = time.monotonic() - start_time
            if elapsed > 5.5 * 3600:  # 5.5 hours — save 30 min for reporting
                logger.warning("Time budget nearly exhausted (%.1f hrs), stopping accuracy tests", elapsed / 3600)
                break

            unload_models()
            clean_repo_index(repo_path)

            result = run_accuracy_test(
                model=model,
                repo_path=repo_path,
                output_path=out_path,
                concurrency=2,
                stages="fast",  # Fast stages only for accuracy (faster iteration)
            )
            if result:
                all_results["accuracy"].append(result)

            # Write intermediate summary
            with open(str(output_dir / "summary.json"), "w") as f:
                json.dump(all_results, f, indent=2, default=str)

        # Check time budget between models
        elapsed = time.monotonic() - start_time
        if elapsed > 5.5 * 3600:
            break

    # ── Phase 3: Speed tests (medium repos, multiple concurrency levels) ──
    logger.info("")
    logger.info("=" * 70)
    logger.info("PHASE 3: SPEED TESTS")
    logger.info("=" * 70)

    for model in available_models:
        for conc in CONCURRENCY_LEVELS:
            for repo_name in TEST_REPOS["small"] + TEST_REPOS["medium"][:2]:
                repo_path = str(REPOS_DIR / repo_name)
                if not Path(repo_path).exists():
                    continue

                slug = model.replace(":", "_").replace(".", "_")
                out_path = str(output_dir / "speed" / f"speed_{slug}_c{conc}_{repo_name}.json")

                if Path(out_path).exists():
                    logger.info("Skipping (exists): %s", out_path)
                    try:
                        with open(out_path) as f:
                            all_results["speed"].append(json.load(f))
                    except Exception:
                        pass
                    continue

                # Check time budget
                elapsed = time.monotonic() - start_time
                if elapsed > 5.5 * 3600:
                    logger.warning("Time budget nearly exhausted (%.1f hrs), stopping speed tests", elapsed / 3600)
                    break

                unload_models()
                clean_repo_index(repo_path)

                result = run_speed_test(
                    model=model,
                    concurrency=conc,
                    repo_path=repo_path,
                    output_path=out_path,
                    stages="fast",
                )
                if result:
                    all_results["speed"].append(result)

                # Write intermediate summary
                with open(str(output_dir / "summary.json"), "w") as f:
                    json.dump(all_results, f, indent=2, default=str)

            elapsed = time.monotonic() - start_time
            if elapsed > 5.5 * 3600:
                break
        elapsed = time.monotonic() - start_time
        if elapsed > 5.5 * 3600:
            break

    # ── Phase 4: Report ───────────────────────────────────────
    total_elapsed = time.monotonic() - start_time

    all_results["meta"] = {
        "started_at": timestamp,
        "total_duration_s": round(total_elapsed, 1),
        "total_duration_h": round(total_elapsed / 3600, 2),
        "accuracy_tests": len(all_results["accuracy"]),
        "speed_tests": len(all_results["speed"]),
        "models_tested": available_models,
    }

    # Final summary files
    with open(str(output_dir / "summary.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    write_report(all_results, output_dir)

    logger.info("")
    logger.info("=" * 70)
    logger.info("OVERNIGHT SUITE COMPLETE")
    logger.info("Duration: %.1f hours", total_elapsed / 3600)
    logger.info("Accuracy tests: %d", len(all_results["accuracy"]))
    logger.info("Speed tests: %d", len(all_results["speed"]))
    logger.info("Results: %s", output_dir)
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
