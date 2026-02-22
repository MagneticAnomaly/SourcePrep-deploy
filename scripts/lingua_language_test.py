#!/usr/bin/env python3
"""
LLMLingua-2 Language Compression Test — Phase 31C

Tests LLMLingua-2 on the NATURAL LANGUAGE content in CoDRAG's pipeline,
using the same test data and evaluation harness as the CLaRa language tests
(Phase 31B) for direct comparison.

Content types tested:
1. Augmentation summaries (trace_augmented.jsonl)
2. Epistemic enrichments (trace_epistemic.jsonl)
3. Module descriptions (trace_modules.jsonl)
4. User markdown documentation chunks
5. Atlas segment descriptions

Usage:
    python scripts/lingua_language_test.py
    python scripts/lingua_language_test.py --quick          # 2 scenarios
    python scripts/lingua_language_test.py --level aggressive
    python scripts/lingua_language_test.py --model microsoft/llmlingua-2-xlm-roberta-large-meetingbank
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Reuse test data from CLaRa language tests
sys.path.insert(0, str(Path(__file__).resolve().parent))
from clara_language_test import (
    SCENARIOS,
    QUICK_SCENARIOS,
    LanguageTestScenario,
    LanguageTestResult,
    check_items,
    detect_hallucinated_files,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lingua_language")


# ---------------------------------------------------------------------------
# Standalone LLMLingua-2 wrapper (avoids codrag import chain)
# ---------------------------------------------------------------------------

FORCE_TOKENS = [
    "\n", "---", "|",
    "@", "/",
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".rs", ".go", ".rb", ".java", ".swift",
    ".md", ".css", ".html", ".json", ".toml", ".yaml", ".yml",
    "[", "]", "score=",
    "?", "!",
    ":", "::", "->", "=>",
    "(", ")",
]

LEVEL_RATES = {
    "light": 0.6,
    "standard": 0.4,
    "aggressive": 0.25,
}


@dataclass
class CompressResultLocal:
    compressed: str = ""
    input_chars: int = 0
    output_chars: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    compression_ratio: float = 1.0
    timing_ms: float = 0.0
    error: Optional[str] = None


class LinguaCompressorLocal:
    """Standalone wrapper for LLMLingua-2 (no codrag dependency)."""

    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._compressor = None

    def _ensure_loaded(self) -> bool:
        if self._compressor is not None:
            return True
        from llmlingua import PromptCompressor
        logger.info("Loading LLMLingua-2 model %s on %s …", self.model_name, self.device)
        t0 = time.monotonic()
        self._compressor = PromptCompressor(
            model_name=self.model_name,
            use_llmlingua2=True,
            device_map=self.device,
        )
        logger.info("LLMLingua-2 model loaded in %.1fs", time.monotonic() - t0)
        return True

    def compress(self, text: str, *, query: str = "", level: str = "standard") -> CompressResultLocal:
        input_chars = len(text)
        if not text.strip():
            return CompressResultLocal(compressed=text, input_chars=input_chars, output_chars=input_chars)

        self._ensure_loaded()
        rate = LEVEL_RATES.get(level, 0.4)

        t0 = time.monotonic()
        try:
            result = self._compressor.compress_prompt(
                text,
                rate=rate,
                force_tokens=FORCE_TOKENS,
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000
            return CompressResultLocal(
                compressed=text, input_chars=input_chars, output_chars=input_chars,
                timing_ms=elapsed_ms, error=str(exc),
            )

        elapsed_ms = (time.monotonic() - t0) * 1000
        compressed = str(result.get("compressed_prompt", text))
        output_chars = len(compressed)
        origin_tokens = int(result.get("origin_tokens", 0))
        compressed_tokens = int(result.get("compressed_tokens", 0))
        ratio_str = result.get("ratio", "1.0x")
        try:
            ratio = float(str(ratio_str).rstrip("x"))
        except (ValueError, TypeError):
            ratio = input_chars / max(output_chars, 1)

        return CompressResultLocal(
            compressed=compressed, input_chars=input_chars, output_chars=output_chars,
            input_tokens=origin_tokens, output_tokens=compressed_tokens,
            compression_ratio=round(ratio, 2), timing_ms=round(elapsed_ms, 1),
        )


# ---------------------------------------------------------------------------
# LLMLingua-2 runner
# ---------------------------------------------------------------------------

def run_scenario_lingua(
    compressor: Any,  # LinguaCompressor instance
    scenario: LanguageTestScenario,
    level: str = "standard",
) -> LanguageTestResult:
    """Run a single language test scenario using LinguaCompressor."""
    all_input = "\n\n---\n\n".join(scenario.memories)

    result = LanguageTestResult(
        scenario_name=scenario.name,
        query=scenario.query,
        content_types=scenario.content_types,
        input_chars=len(all_input),
        input_memories=len(scenario.memories),
        facts_total=len(scenario.expected_facts),
        file_refs_total=len(scenario.expected_file_refs),
        concepts_total=len(scenario.expected_concepts),
    )

    compress_result = compressor.compress(
        all_input,
        query=scenario.query,
        level=level,
    )

    result.latency_ms = compress_result.timing_ms

    if compress_result.error:
        result.error = compress_result.error
        return result

    output = compress_result.compressed
    result.output_chars = compress_result.output_chars
    result.compression_ratio = compress_result.compression_ratio
    result.output_preview = output[:500]

    # Check retention
    result.facts_retained, result.facts_pct = check_items(output, scenario.expected_facts)
    result.file_refs_retained, result.file_refs_pct = check_items(output, scenario.expected_file_refs)
    result.concepts_retained, result.concepts_pct = check_items(output, scenario.expected_concepts)

    # Overall
    all_expected = scenario.expected_facts + scenario.expected_file_refs + scenario.expected_concepts
    _, result.overall_retention_pct = check_items(output, all_expected)

    # Hallucination
    result.hallucinated_names = detect_hallucinated_files(output, all_input)

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_results(
    results: List[LanguageTestResult],
    clara_baseline: Optional[Dict] = None,
    level: str = "standard",
) -> None:
    """Print comparison table."""
    print("\n" + "═" * 80)
    print(f"  LLMLingua-2 Language Compression Results (level={level})")
    print("═" * 80)

    for r in results:
        status = "✓" if not r.error else f"✗ {r.error[:40]}"
        print(f"\n  [{status}] {r.scenario_name}")
        print(f"      Types:       {', '.join(r.content_types)}")
        print(f"      Input:       {r.input_memories} memories, {r.input_chars:,} chars")
        print(f"      Output:      {r.output_chars:,} chars ({r.compression_ratio}× compression)")
        print(f"      Latency:     {r.latency_ms:.0f}ms")
        if not r.error:
            print(f"      Facts:       {len(r.facts_retained)}/{r.facts_total} ({r.facts_pct:.0f}%)")
            print(f"      File refs:   {len(r.file_refs_retained)}/{r.file_refs_total} ({r.file_refs_pct:.0f}%)")
            print(f"      Concepts:    {len(r.concepts_retained)}/{r.concepts_total} ({r.concepts_pct:.0f}%)")
            print(f"      Overall:     {r.overall_retention_pct:.0f}%")
            if r.hallucinated_names:
                print(f"      Halluc:      {len(r.hallucinated_names)} ({', '.join(r.hallucinated_names[:5])})")
            else:
                print(f"      Halluc:      0 ✅")
            print(f"      Preview:     {r.output_preview[:200]}...")

    ok = [r for r in results if not r.error]
    if ok:
        avg_facts = sum(r.facts_pct for r in ok) / len(ok)
        avg_refs = sum(r.file_refs_pct for r in ok) / len(ok)
        avg_concepts = sum(r.concepts_pct for r in ok) / len(ok)
        avg_overall = sum(r.overall_retention_pct for r in ok) / len(ok)
        avg_ratio = sum(r.compression_ratio for r in ok) / len(ok)
        avg_latency = sum(r.latency_ms for r in ok) / len(ok)
        avg_halluc = sum(len(r.hallucinated_names) for r in ok) / len(ok)

        print("\n" + "─" * 60)
        print(f"  LLMLINGUA-2 SUMMARY (level={level})")
        print("─" * 60)
        print(f"  Tests passed:      {len(ok)}/{len(results)}")
        print(f"  Avg facts:         {avg_facts:.0f}%")
        print(f"  Avg file refs:     {avg_refs:.0f}%")
        print(f"  Avg concepts:      {avg_concepts:.0f}%")
        print(f"  Avg overall:       {avg_overall:.0f}%")
        print(f"  Avg compression:   {avg_ratio:.1f}×")
        print(f"  Avg latency:       {avg_latency:.0f}ms")
        print(f"  Avg hallucinations:{avg_halluc:.1f}")

        if clara_baseline:
            print("\n" + "─" * 60)
            print("  LLMLINGUA-2 vs CLaRa COMPARISON")
            print("─" * 60)
            print(f"  {'Metric':<25} {'CLaRa (31B)':>15} {'LLMLingua-2':>15} {'Delta':>10}")
            print(f"  {'─'*25} {'─'*15} {'─'*15} {'─'*10}")

            cb = clara_baseline
            print(f"  {'Overall retention':<25} {cb['overall']:>14.0f}% {avg_overall:>14.0f}% {avg_overall - cb['overall']:>+9.0f}%")
            print(f"  {'File/path refs':<25} {cb['refs']:>14.0f}% {avg_refs:>14.0f}% {avg_refs - cb['refs']:>+9.0f}%")
            print(f"  {'Key facts':<25} {cb['facts']:>14.0f}% {avg_facts:>14.0f}% {avg_facts - cb['facts']:>+9.0f}%")
            print(f"  {'Concepts':<25} {cb['concepts']:>14.0f}% {avg_concepts:>14.0f}% {avg_concepts - cb['concepts']:>+9.0f}%")
            print(f"  {'Hallucinations':<25} {cb['halluc']:>15.1f} {avg_halluc:>15.1f} {avg_halluc - cb['halluc']:>+10.1f}")
            print(f"  {'Compression ratio':<25} {cb['ratio']:>14.1f}× {avg_ratio:>14.1f}×")
            print(f"  {'Latency (ms)':<25} {cb['latency']:>14.0f} {avg_latency:>14.0f}")

        # Pass/fail gates
        print("\n" + "─" * 60)
        print("  DECISION GATES")
        print("─" * 60)
        gates = [
            ("Overall retention ≥60%", avg_overall >= 60),
            ("File refs ≥50%", avg_refs >= 50),
            ("Concepts ≥70%", avg_concepts >= 70),
            ("Hallucinations <3 avg", avg_halluc < 3),
            ("Latency <3000ms avg", avg_latency < 3000),
        ]
        all_pass = True
        for name, passed in gates:
            all_pass = all_pass and passed
            print(f"  {'✅' if passed else '❌'} {name}")

        print(f"\n  {'🎉 ALL GATES PASSED' if all_pass else '⚠️  Some gates failed'}")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="LLMLingua-2 Language Compression Test")
    parser.add_argument("--model", default="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--level", default="standard", choices=["light", "standard", "aggressive"])
    parser.add_argument("--quick", action="store_true", help="Run 2 scenarios only")
    parser.add_argument("--output", default="", help="Output JSON path")
    parser.add_argument("--all-levels", action="store_true", help="Test all 3 levels")
    args = parser.parse_args()

    scenarios = QUICK_SCENARIOS if args.quick else list(SCENARIOS)

    # CLaRa baseline (from Phase 31B results)
    clara_baseline = {
        "overall": 20.0,
        "refs": 8.0,
        "facts": 9.0,
        "concepts": 38.0,
        "halluc": 0.7,
        "ratio": 2.0,
        "latency": 30335.0,
    }

    levels = ["light", "standard", "aggressive"] if args.all_levels else [args.level]
    all_results: Dict[str, List[LanguageTestResult]] = {}

    for level in levels:
        logger.info("=" * 60)
        logger.info("Testing level=%s with model=%s on %s", level, args.model, args.device)
        logger.info("=" * 60)

        compressor = LinguaCompressorLocal(
            model_name=args.model,
            device=args.device,
        )

        results: List[LanguageTestResult] = []
        for i, sc in enumerate(scenarios, 1):
            logger.info("[%d/%d] %s (%d memories, types: %s)",
                        i, len(scenarios), sc.name, len(sc.memories),
                        ", ".join(sc.content_types))

            r = run_scenario_lingua(compressor, sc, level=level)
            results.append(r)

            if r.error:
                logger.warning("  ✗ %s", r.error)
            else:
                logger.info("  ✓ %d→%d chars (%.1f×), overall=%.0f%%, %.0fms",
                           r.input_chars, r.output_chars, r.compression_ratio,
                           r.overall_retention_pct, r.latency_ms)

        all_results[level] = results
        print_results(results, clara_baseline, level=level)

    # Save
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path(f"docs/Phase31_CLaRa-replacement/lingua_results_{ts}.json")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    save_data = {}
    for level, results in all_results.items():
        save_data[level] = [asdict(r) for r in results]

    with open(out_path, "w") as f:
        json.dump(save_data, f, indent=2, default=str)
    logger.info("Results saved to %s", out_path)


if __name__ == "__main__":
    main()
