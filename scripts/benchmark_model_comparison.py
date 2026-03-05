#!/usr/bin/env python3
"""Benchmark qwen3-14b vs qwen3.5-27b on real-world code enrichment tasks.

Sends identical prompts to both models via LM Studio's OpenAI-compatible API,
measuring speed (tokens/sec, wall time) and quality (JSON parse success,
confidence scores, summary relevance, domain tag accuracy).

Uses mini-redis-rust from tests/eval/real_repos/ as the test corpus.

Usage:
    python scripts/benchmark_model_comparison.py
    python scripts/benchmark_model_comparison.py --files 5    # limit files
    python scripts/benchmark_model_comparison.py --repo click-python
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Config ────────────────────────────────────────────────────────────

LMSTUDIO_BASE = "http://127.0.0.1:1234/v1"

MODELS = {
    "qwen3.5-9b": "qwen3.5-9b",
    "qwen3-14b": "qwen/qwen3-14b",
    "qwen3.5-27b": "qwen3.5-27b-mxfp8",
}

DEFAULT_REPO = "mini-redis-rust"
REPO_BASE = PROJECT_ROOT / "tests" / "eval" / "real_repos"

# ── Prompts (identical to pipeline) ───────────────────────────────────

FILE_ROLE_SYSTEM = """You are a code analyst. You classify files by their role in a codebase.
You MUST respond with valid JSON only."""

FILE_ROLE_PROMPT = """Classify this file's role in the codebase.

File: {file_path}
Symbols defined: {symbol_names}
Imports: {imports}

First 120 lines:
```
{head}
```

Respond with this exact JSON format:
{{"summary": "1 sentence file purpose", "role": "utility", "confidence": 0.85, "key_exports": ["symbol1", "symbol2"], "related_files": ["path/to/related.py"]}}

Where role is one of: api, core, model, utility, config, test, script, ui, documentation
related_files: list up to 5 files this file most likely relates to (by path)

JSON response:"""

EPISTEMIC_SYSTEM = """You are an expert software architect performing deep analysis of a codebase.
You produce structured, accurate analysis grounded in the actual code and documentation.
You MUST respond with valid JSON only. No markdown, no explanation outside the JSON."""

EPISTEMIC_CODE_PROMPT = """Perform deep epistemic analysis of this code file.

File: {file_path}
Language: {language}

Pass 1 summary: {pass1_summary}
Pass 1 role: {pass1_role}

Source excerpt:
```
{source_excerpt}
```

Respond with this exact JSON format:
{{"extended_summary": "2-4 sentence detailed description of this file's purpose, behavior, and significance in the codebase",
"domain_tags": ["tag1", "tag2"],
"architecture_layer": "business_logic",
"subsystem": "name-of-subsystem",
"staleness_risk": "low|medium|high",
"epistemic_confidence": 0.85}}

Where architecture_layer is one of: presentation, business_logic, data, infrastructure, configuration, testing, documentation, build, unknown
domain_tags: 1-4 descriptive tags for the domain this file operates in

JSON response:"""


# ── LM Studio Client ─────────────────────────────────────────────────

def lmstudio_chat(
    model: str,
    system: str,
    user: str,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> Tuple[str, Dict[str, Any]]:
    """Call LM Studio chat completion, return (text, usage_dict).
    
    Uses 4096 max_tokens by default to accommodate thinking models
    (qwen3/3.5) which generate <think>...</think> blocks before the JSON.
    """
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }).encode("utf-8")

    req = Request(
        f"{LMSTUDIO_BASE}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return text, usage


def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from model output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Try to extract JSON from model response."""
    text = strip_think_tags(text)
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code block
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try finding first { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ── File Discovery ────────────────────────────────────────────────────

def discover_files(repo_path: Path, max_files: Optional[int] = None) -> List[Path]:
    """Find source code files in the repo."""
    extensions = {".rs", ".py", ".ts", ".tsx", ".js", ".go", ".java", ".kt",
                  ".c", ".h", ".cpp", ".rb", ".php", ".swift", ".cs"}
    files = []
    for f in sorted(repo_path.rglob("*")):
        if f.is_file() and f.suffix in extensions and ".codrag" not in str(f):
            files.append(f)
    if max_files:
        files = files[:max_files]
    return files


def extract_imports(content: str, lang: str) -> List[str]:
    """Extract import lines from source."""
    patterns = {
        ".rs": r"^(?:use |extern crate |mod ).*",
        ".py": r"^(?:import |from ).*",
        ".go": r'^(?:import |\t").*',
        ".ts": r"^(?:import |export ).*",
        ".js": r"^(?:import |const .* = require).*",
    }
    pat = patterns.get(lang, r"^(?:import |#include ).*")
    return re.findall(pat, content, re.MULTILINE)[:10]


def extract_symbols(content: str, lang: str) -> List[str]:
    """Extract top-level symbol names from source."""
    patterns = {
        ".rs": r"(?:pub\s+)?(?:fn|struct|enum|trait|impl|type|const|static)\s+(\w+)",
        ".py": r"^(?:def|class)\s+(\w+)",
        ".go": r"^(?:func|type|var|const)\s+(\w+)",
        ".ts": r"^(?:export\s+)?(?:function|class|interface|type|const|let)\s+(\w+)",
    }
    pat = patterns.get(lang, r"(?:fn|def|class|func|struct)\s+(\w+)")
    return re.findall(pat, content, re.MULTILINE)[:15]


def detect_language(path: Path) -> str:
    ext_map = {
        ".rs": "rust", ".py": "python", ".go": "go", ".ts": "typescript",
        ".js": "javascript", ".java": "java", ".kt": "kotlin", ".c": "c",
        ".cpp": "cpp", ".rb": "ruby", ".php": "php", ".swift": "swift",
    }
    return ext_map.get(path.suffix, "unknown")


# ── Benchmark Tasks ───────────────────────────────────────────────────

@dataclass
class TaskResult:
    file_path: str
    task: str  # "augment" or "epistemic"
    model: str
    wall_time_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_per_sec: float = 0.0
    json_parsed: bool = False
    confidence: float = 0.0
    summary: str = ""
    role: str = ""
    domain_tags: List[str] = field(default_factory=list)
    architecture_layer: str = ""
    raw_response: str = ""
    error: str = ""


def run_augment_task(file_path: Path, repo_root: Path, model_id: str, model_label: str) -> TaskResult:
    """Run a Pass 1 (augmentation) task on a single file."""
    result = TaskResult(
        file_path=str(file_path.relative_to(repo_root)),
        task="augment",
        model=model_label,
    )
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lang = detect_language(file_path)
        imports = extract_imports(content, file_path.suffix)
        symbols = extract_symbols(content, file_path.suffix)
        head = "\n".join(content.splitlines()[:120])

        prompt = FILE_ROLE_PROMPT.format(
            file_path=file_path.relative_to(repo_root),
            symbol_names=", ".join(symbols) if symbols else "(none found)",
            imports="; ".join(imports) if imports else "(none)",
            head=head,
            content_label="First 120 lines",
        )

        t0 = time.monotonic()
        raw, usage = lmstudio_chat(model_id, FILE_ROLE_SYSTEM, prompt)
        result.wall_time_s = time.monotonic() - t0
        result.raw_response = raw
        result.prompt_tokens = usage.get("prompt_tokens", 0)
        result.completion_tokens = usage.get("completion_tokens", 0)

        if result.completion_tokens > 0 and result.wall_time_s > 0:
            result.tokens_per_sec = result.completion_tokens / result.wall_time_s

        parsed = parse_json_response(raw)
        if parsed:
            result.json_parsed = True
            result.confidence = float(parsed.get("confidence", 0))
            result.summary = parsed.get("summary", "")
            result.role = parsed.get("role", "")
        else:
            result.error = "JSON parse failed"

    except Exception as e:
        result.error = str(e)
    return result


def run_epistemic_task(
    file_path: Path, repo_root: Path, model_id: str, model_label: str,
    pass1_summary: str = "", pass1_role: str = "",
) -> TaskResult:
    """Run a Pass 2 (epistemic enrichment) task on a single file."""
    result = TaskResult(
        file_path=str(file_path.relative_to(repo_root)),
        task="epistemic",
        model=model_label,
    )
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lang = detect_language(file_path)
        excerpt = "\n".join(content.splitlines()[:200])

        prompt = EPISTEMIC_CODE_PROMPT.format(
            file_path=file_path.relative_to(repo_root),
            language=lang,
            pass1_summary=pass1_summary or "(not yet available)",
            pass1_role=pass1_role or "unknown",
            source_excerpt=excerpt,
        )

        t0 = time.monotonic()
        raw, usage = lmstudio_chat(model_id, EPISTEMIC_SYSTEM, prompt, max_tokens=2048)
        result.wall_time_s = time.monotonic() - t0
        result.raw_response = raw
        result.prompt_tokens = usage.get("prompt_tokens", 0)
        result.completion_tokens = usage.get("completion_tokens", 0)

        if result.completion_tokens > 0 and result.wall_time_s > 0:
            result.tokens_per_sec = result.completion_tokens / result.wall_time_s

        parsed = parse_json_response(raw)
        if parsed:
            result.json_parsed = True
            result.confidence = float(parsed.get("epistemic_confidence", 0))
            result.summary = parsed.get("extended_summary", "")
            result.domain_tags = parsed.get("domain_tags", [])
            result.architecture_layer = parsed.get("architecture_layer", "")
        else:
            result.error = "JSON parse failed"

    except Exception as e:
        result.error = str(e)
    return result


# ── Quality Scoring ──────────────────────────────────────────────────

def score_augment_quality(results: List[TaskResult], repo_name: str) -> Dict[str, Any]:
    """Evaluate augmentation quality."""
    valid = [r for r in results if r.json_parsed]
    return {
        "total_files": len(results),
        "json_parse_rate": len(valid) / len(results) if results else 0,
        "avg_confidence": statistics.mean([r.confidence for r in valid]) if valid else 0,
        "confidence_stdev": statistics.stdev([r.confidence for r in valid]) if len(valid) > 1 else 0,
        "role_distribution": _count_values([r.role for r in valid]),
        "avg_summary_length": statistics.mean([len(r.summary) for r in valid]) if valid else 0,
        "errors": [r.error for r in results if r.error],
    }


def score_epistemic_quality(results: List[TaskResult], repo_name: str) -> Dict[str, Any]:
    """Evaluate epistemic enrichment quality."""
    valid = [r for r in results if r.json_parsed]
    all_tags = []
    for r in valid:
        all_tags.extend(r.domain_tags)
    return {
        "total_files": len(results),
        "json_parse_rate": len(valid) / len(results) if results else 0,
        "avg_confidence": statistics.mean([r.confidence for r in valid]) if valid else 0,
        "confidence_stdev": statistics.stdev([r.confidence for r in valid]) if len(valid) > 1 else 0,
        "layer_distribution": _count_values([r.architecture_layer for r in valid]),
        "unique_domain_tags": len(set(all_tags)),
        "top_domain_tags": _count_values(all_tags),
        "avg_summary_length": statistics.mean([len(r.summary) for r in valid]) if valid else 0,
        "errors": [r.error for r in results if r.error],
    }


def _count_values(items: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ── Main Runner ──────────────────────────────────────────────────────

def run_benchmark(
    repo_name: str,
    max_files: Optional[int] = None,
    skip_epistemic: bool = False,
) -> Dict[str, Any]:
    """Run the full benchmark for both models."""
    repo_path = REPO_BASE / repo_name
    if not repo_path.exists():
        print(f"ERROR: repo not found: {repo_path}")
        sys.exit(1)

    files = discover_files(repo_path, max_files)
    print(f"\n{'='*70}")
    print(f"  BENCHMARK: {repo_name} ({len(files)} files)")
    print(f"{'='*70}\n")

    all_results: Dict[str, Dict[str, List[TaskResult]]] = {}

    for model_label, model_id in MODELS.items():
        print(f"\n--- Model: {model_label} ({model_id}) ---\n")
        all_results[model_label] = {"augment": [], "epistemic": []}

        # Pass 1: Augmentation
        print(f"  Pass 1 (Augmentation) — {len(files)} files")
        pass1_start = time.monotonic()
        for i, fpath in enumerate(files):
            rel = fpath.relative_to(repo_path)
            print(f"    [{i+1}/{len(files)}] {rel}", end="", flush=True)
            r = run_augment_task(fpath, repo_path, model_id, model_label)
            all_results[model_label]["augment"].append(r)
            status = "✓" if r.json_parsed else f"✗ {r.error}"
            print(f"  {r.wall_time_s:.1f}s  {r.tokens_per_sec:.0f} tok/s  {status}")
        pass1_dur = time.monotonic() - pass1_start
        print(f"  Pass 1 total: {pass1_dur:.1f}s")

        # Pass 2: Epistemic enrichment
        if not skip_epistemic:
            print(f"\n  Pass 2 (Epistemic Enrichment) — {len(files)} files")
            pass2_start = time.monotonic()
            augments = all_results[model_label]["augment"]
            for i, fpath in enumerate(files):
                rel = fpath.relative_to(repo_path)
                aug = augments[i] if i < len(augments) else None
                p1_summary = aug.summary if aug and aug.json_parsed else ""
                p1_role = aug.role if aug and aug.json_parsed else ""

                print(f"    [{i+1}/{len(files)}] {rel}", end="", flush=True)
                r = run_epistemic_task(
                    fpath, repo_path, model_id, model_label,
                    pass1_summary=p1_summary, pass1_role=p1_role,
                )
                all_results[model_label]["epistemic"].append(r)
                status = "✓" if r.json_parsed else f"✗ {r.error}"
                print(f"  {r.wall_time_s:.1f}s  {r.tokens_per_sec:.0f} tok/s  {status}")
            pass2_dur = time.monotonic() - pass2_start
            print(f"  Pass 2 total: {pass2_dur:.1f}s")

    # ── Report ────────────────────────────────────────────────────────
    report = generate_report(all_results, repo_name, skip_epistemic)
    return report


def generate_report(
    all_results: Dict[str, Dict[str, List[TaskResult]]],
    repo_name: str,
    skip_epistemic: bool,
) -> Dict[str, Any]:
    """Generate comparison report."""
    report: Dict[str, Any] = {"repo": repo_name, "models": {}}

    print(f"\n\n{'='*70}")
    print(f"  RESULTS: {repo_name}")
    print(f"{'='*70}\n")

    for model_label in MODELS:
        aug_results = all_results[model_label]["augment"]
        epi_results = all_results[model_label]["epistemic"]

        aug_speed = _speed_stats(aug_results)
        aug_quality = score_augment_quality(aug_results, repo_name)

        model_report = {
            "augment": {"speed": aug_speed, "quality": aug_quality},
        }

        print(f"  {model_label}")
        print(f"  {'─'*40}")
        print(f"  Pass 1 (Augmentation):")
        print(f"    Total time:     {aug_speed['total_time_s']:.1f}s")
        print(f"    Avg per file:   {aug_speed['avg_time_per_file_s']:.1f}s")
        print(f"    Avg tok/s:      {aug_speed['avg_tokens_per_sec']:.1f}")
        print(f"    JSON parse:     {aug_quality['json_parse_rate']:.0%}")
        print(f"    Avg confidence: {aug_quality['avg_confidence']:.2f}")
        print(f"    Avg summary:    {aug_quality['avg_summary_length']:.0f} chars")
        print(f"    Roles:          {aug_quality['role_distribution']}")

        if not skip_epistemic and epi_results:
            epi_speed = _speed_stats(epi_results)
            epi_quality = score_epistemic_quality(epi_results, repo_name)
            model_report["epistemic"] = {"speed": epi_speed, "quality": epi_quality}

            print(f"  Pass 2 (Epistemic Enrichment):")
            print(f"    Total time:     {epi_speed['total_time_s']:.1f}s")
            print(f"    Avg per file:   {epi_speed['avg_time_per_file_s']:.1f}s")
            print(f"    Avg tok/s:      {epi_speed['avg_tokens_per_sec']:.1f}")
            print(f"    JSON parse:     {epi_quality['json_parse_rate']:.0%}")
            print(f"    Avg confidence: {epi_quality['avg_confidence']:.2f}")
            print(f"    Avg summary:    {epi_quality['avg_summary_length']:.0f} chars")
            print(f"    Unique tags:    {epi_quality['unique_domain_tags']}")
            print(f"    Top tags:       {dict(list(epi_quality['top_domain_tags'].items())[:8])}")
            print(f"    Layers:         {epi_quality['layer_distribution']}")

        report["models"][model_label] = model_report
        print()

    # ── Head-to-head comparison ───────────────────────────────────────
    labels = list(MODELS.keys())
    if len(labels) == 2:
        a, b = labels
        print(f"\n  HEAD-TO-HEAD: {a} vs {b}")
        print(f"  {'─'*50}")

        a_aug = _speed_stats(all_results[a]["augment"])
        b_aug = _speed_stats(all_results[b]["augment"])
        speedup_aug = b_aug["total_time_s"] / a_aug["total_time_s"] if a_aug["total_time_s"] > 0 else 0

        print(f"  Augmentation speed:  {a}={a_aug['total_time_s']:.0f}s  {b}={b_aug['total_time_s']:.0f}s  ({speedup_aug:.1f}x)")

        a_aq = score_augment_quality(all_results[a]["augment"], repo_name)
        b_aq = score_augment_quality(all_results[b]["augment"], repo_name)
        print(f"  Augmentation conf:   {a}={a_aq['avg_confidence']:.2f}  {b}={b_aq['avg_confidence']:.2f}")

        if not skip_epistemic:
            a_epi = all_results[a]["epistemic"]
            b_epi = all_results[b]["epistemic"]
            if a_epi and b_epi:
                a_es = _speed_stats(a_epi)
                b_es = _speed_stats(b_epi)
                speedup_epi = b_es["total_time_s"] / a_es["total_time_s"] if a_es["total_time_s"] > 0 else 0
                print(f"  Epistemic speed:     {a}={a_es['total_time_s']:.0f}s  {b}={b_es['total_time_s']:.0f}s  ({speedup_epi:.1f}x)")

                a_eq = score_epistemic_quality(a_epi, repo_name)
                b_eq = score_epistemic_quality(b_epi, repo_name)
                print(f"  Epistemic conf:      {a}={a_eq['avg_confidence']:.2f}  {b}={b_eq['avg_confidence']:.2f}")
                print(f"  Unique tags:         {a}={a_eq['unique_domain_tags']}  {b}={b_eq['unique_domain_tags']}")

        # Per-file quality comparison
        print(f"\n  PER-FILE COMPARISON (Augmentation):")
        print(f"  {'File':<40} {'14b conf':>9} {'27b conf':>9} {'14b role':<12} {'27b role':<12}")
        print(f"  {'─'*82}")
        a_augs = all_results[a]["augment"]
        b_augs = all_results[b]["augment"]
        for i in range(min(len(a_augs), len(b_augs))):
            ra, rb = a_augs[i], b_augs[i]
            fname = ra.file_path[:38]
            ac = f"{ra.confidence:.2f}" if ra.json_parsed else "FAIL"
            bc = f"{rb.confidence:.2f}" if rb.json_parsed else "FAIL"
            ar = ra.role if ra.json_parsed else "—"
            br = rb.role if rb.json_parsed else "—"
            print(f"  {fname:<40} {ac:>9} {bc:>9} {ar:<12} {br:<12}")

    # Save raw results
    outdir = PROJECT_ROOT / "results" / f"model_comparison_{int(time.time())}"
    outdir.mkdir(parents=True, exist_ok=True)
    results_file = outdir / "results.json"

    serializable = {}
    for model_label, tasks in all_results.items():
        serializable[model_label] = {}
        for task_name, task_results in tasks.items():
            serializable[model_label][task_name] = [
                {
                    "file_path": r.file_path,
                    "task": r.task,
                    "model": r.model,
                    "wall_time_s": r.wall_time_s,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "tokens_per_sec": r.tokens_per_sec,
                    "json_parsed": r.json_parsed,
                    "confidence": r.confidence,
                    "summary": r.summary,
                    "role": r.role,
                    "domain_tags": r.domain_tags,
                    "architecture_layer": r.architecture_layer,
                    "error": r.error,
                }
                for r in task_results
            ]

    with open(results_file, "w") as f:
        json.dump({"report": report, "raw": serializable}, f, indent=2)
    print(f"\n  Results saved to: {results_file}")

    return report


def _speed_stats(results: List[TaskResult]) -> Dict[str, float]:
    """Compute speed statistics from a list of task results."""
    if not results:
        return {"total_time_s": 0, "avg_time_per_file_s": 0, "avg_tokens_per_sec": 0,
                "median_time_s": 0, "p95_time_s": 0}

    times = [r.wall_time_s for r in results]
    tps = [r.tokens_per_sec for r in results if r.tokens_per_sec > 0]

    sorted_times = sorted(times)
    p95_idx = min(int(len(sorted_times) * 0.95), len(sorted_times) - 1)

    return {
        "total_time_s": round(sum(times), 1),
        "avg_time_per_file_s": round(statistics.mean(times), 1),
        "median_time_s": round(statistics.median(times), 1),
        "p95_time_s": round(sorted_times[p95_idx], 1),
        "avg_tokens_per_sec": round(statistics.mean(tps), 1) if tps else 0,
    }


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Benchmark qwen3-14b vs qwen3.5-27b")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Repo name in tests/eval/real_repos/")
    parser.add_argument("--files", type=int, default=None, help="Max files to test")
    parser.add_argument("--augment-only", action="store_true", help="Skip epistemic pass")
    args = parser.parse_args()

    # Verify LM Studio is running
    try:
        req = Request(f"{LMSTUDIO_BASE}/models")
        with urlopen(req, timeout=5) as resp:
            models_data = json.loads(resp.read().decode("utf-8"))
        loaded = [m["id"] for m in models_data.get("data", [])]
        print(f"LM Studio models loaded: {len(loaded)}")
        for mid in MODELS.values():
            if mid in loaded:
                print(f"  ✓ {mid}")
            else:
                print(f"  ✗ {mid} NOT LOADED — please load in LM Studio")
                sys.exit(1)
    except URLError:
        print("ERROR: Cannot connect to LM Studio at", LMSTUDIO_BASE)
        sys.exit(1)

    run_benchmark(args.repo, max_files=args.files, skip_epistemic=args.augment_only)


if __name__ == "__main__":
    main()
