#!/usr/bin/env python3
"""Quick re-run of just qwen3.5-27b augmentation with fixed max_tokens=4096.
Saves results alongside the original benchmark."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_model_comparison import (
    LMSTUDIO_BASE, MODELS, REPO_BASE,
    discover_files, run_augment_task, score_augment_quality, _speed_stats,
)

def main():
    repo_name = "mini-redis-rust"
    repo_path = REPO_BASE / repo_name
    files = discover_files(repo_path, max_files=10)
    
    model_id = MODELS["qwen3.5-27b"]
    model_label = "qwen3.5-27b"
    
    print(f"\n  RE-RUN: {model_label} augmentation with max_tokens=4096")
    print(f"  Files: {len(files)}\n")
    
    results = []
    t0 = time.monotonic()
    for i, fpath in enumerate(files):
        rel = fpath.relative_to(repo_path)
        print(f"  [{i+1}/{len(files)}] {rel}", end="", flush=True)
        r = run_augment_task(fpath, repo_path, model_id, model_label)
        results.append(r)
        status = "✓" if r.json_parsed else f"✗ {r.error}"
        print(f"  {r.wall_time_s:.1f}s  {r.tokens_per_sec:.0f} tok/s  conf={r.confidence:.2f}  {status}")
    
    total = time.monotonic() - t0
    print(f"\n  Total: {total:.1f}s")
    
    speed = _speed_stats(results)
    quality = score_augment_quality(results, repo_name)
    
    print(f"\n  Speed:")
    print(f"    Avg per file: {speed['avg_time_per_file_s']}s")
    print(f"    Avg tok/s:    {speed['avg_tokens_per_sec']}")
    print(f"  Quality:")
    print(f"    JSON parse:   {quality['json_parse_rate']:.0%}")
    print(f"    Avg conf:     {quality['avg_confidence']:.2f}")
    print(f"    Avg summary:  {quality['avg_summary_length']:.0f} chars")
    print(f"    Roles:        {quality['role_distribution']}")
    
    # Save
    outdir = Path(__file__).resolve().parent.parent / "results" / f"27b_rerun_{int(time.time())}"
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "results.json", "w") as f:
        json.dump({
            "speed": speed, "quality": quality,
            "raw": [{
                "file": r.file_path, "time": r.wall_time_s, "tps": r.tokens_per_sec,
                "parsed": r.json_parsed, "conf": r.confidence, "summary": r.summary,
                "role": r.role, "error": r.error,
            } for r in results]
        }, f, indent=2)
    print(f"\n  Saved to {outdir / 'results.json'}")

if __name__ == "__main__":
    main()
