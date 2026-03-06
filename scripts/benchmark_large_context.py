#!/usr/bin/env -S /Volumes/4TB-BAD/HumanAI/CoDRAG/.venv/bin/python
"""Benchmark large-context pipeline tasks: Atlas, Group Reasoning, Audit.

Tests quality and speed of "whole-repo scope" LLM calls that ingest
massive context windows, comparing:
  1. qwen3.5:35b-a3b (no-think)
  2. qwen3.5:35b-a3b (think)
  3. qwen3.5:27b (no-think)
  4. qwen3.5:27b (think)

For each model config, runs:
  - Atlas generation (single call, all-modules context)
  - Group Reasoning (per-group calls, think=True by default)
  - Audit Summary (single call, findings + atlas context)

Saves full output text for manual quality review.

Usage:
    python scripts/benchmark_large_context.py
    python scripts/benchmark_large_context.py --only 1   # run just config #1
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Setup ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

REPO_PATH = PROJECT_ROOT / "TEST"
INDEX_DIR = REPO_PATH / ".codrag"
OLLAMA_URL = "http://127.0.0.1:11434"
RESULTS_BASE = PROJECT_ROOT / "results"

# ── Model Configs ─────────────────────────────────────────────────────

CONFIGS = [
    {
        "id": "35b-a3b-nothink",
        "label": "qwen3.5:35b-a3b (no-think)",
        "model": "qwen3.5:35b-a3b",
        "think": False,
        "timeout": 300.0,
    },
    {
        "id": "35b-a3b-think",
        "label": "qwen3.5:35b-a3b (think)",
        "model": "qwen3.5:35b-a3b",
        "think": True,
        "timeout": 600.0,
    },
    {
        "id": "27b-nothink",
        "label": "qwen3.5:27b (no-think)",
        "model": "qwen3.5:27b",
        "think": False,
        "timeout": 600.0,
    },
    {
        "id": "27b-think",
        "label": "qwen3.5:27b (think)",
        "model": "qwen3.5:27b",
        "think": True,
        "timeout": 900.0,
    },
]

# ── Logging ───────────────────────────────────────────────────────────

def setup_logging(run_dir: Path):
    fh = logging.FileHandler(run_dir / "run.log")
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
    # Flush after every line
    class FlushFilter(logging.Filter):
        def filter(self, record):
            fh.flush()
            return True
    fh.addFilter(FlushFilter())
    return logging.getLogger("benchmark_large_context")


# ── Test Functions ────────────────────────────────────────────────────

def test_atlas(client, think: bool, logger) -> Dict[str, Any]:
    """Run Atlas generation and capture the full output."""
    from codrag.core.atlas.generator import CodebaseAtlas

    # Patch think parameter onto client
    orig_generate = client.generate
    def patched(*args, **kwargs):
        kwargs.setdefault("think", think)
        return orig_generate(*args, **kwargs)
    client.generate = patched

    atlas = CodebaseAtlas(index_dir=INDEX_DIR, llm=client, project_root=REPO_PATH)

    t0 = time.monotonic()
    try:
        doc = atlas.generate()
        duration = time.monotonic() - t0
        result = {
            "status": "success",
            "duration_s": round(duration, 1),
            "content": doc.content,
            "char_count": doc.char_count,
            "mode": doc.mode,
        }
        logger.info("Atlas: %d chars in %.1fs (%s)", doc.char_count, duration, doc.mode)
    except Exception as e:
        duration = time.monotonic() - t0
        result = {
            "status": "error",
            "duration_s": round(duration, 1),
            "error": str(e),
            "content": "",
        }
        logger.error("Atlas FAILED: %s", e)

    # Restore original
    client.generate = orig_generate
    return result


def test_atlas_with_think_override(client, think: bool, logger) -> Dict[str, Any]:
    """Run Atlas generation but OVERRIDE the hardcoded think=False.

    The Atlas generator hardcodes think=False. This test patches the LLM
    client to intercept the call and apply our desired think setting,
    letting us compare think vs no-think for Atlas quality.
    """
    from codrag.core.atlas.generator import CodebaseAtlas
    from codrag.core.atlas.prompts import ATLAS_SYSTEM, ATLAS_PROMPT
    from codrag.core.atlas.routing import compute_atlas_budget, MIN_ATLAS_CHARS

    atlas = CodebaseAtlas(index_dir=INDEX_DIR, llm=client, project_root=REPO_PATH)

    # Load the same data the Atlas would load
    modules = atlas._load_modules()
    epistemic = atlas._load_epistemic_summary()
    graph_stats = atlas._load_graph_stats()
    hub_files = atlas._identify_hubs(graph_stats)

    file_count = graph_stats.get("file_count", 0)
    budget = compute_atlas_budget(file_count)
    target_chars = max(MIN_ATLAS_CHARS, budget)
    max_chars = int(target_chars * 1.3)

    module_text = atlas._format_modules(modules)
    layer_text = atlas._format_layers(epistemic)
    stats_text = atlas._format_graph_stats(graph_stats)
    hub_text = atlas._format_hubs(hub_files)

    system = ATLAS_SYSTEM.format(target_chars=target_chars, max_chars=max_chars)
    prompt = ATLAS_PROMPT.format(
        module_summaries=module_text,
        architecture_layers=layer_text,
        graph_stats=stats_text,
        hub_files=hub_text,
        target_chars=target_chars,
        max_chars=max_chars,
    )

    prompt_chars = len(system) + len(prompt)
    logger.info("Atlas prompt: %d chars (system=%d, user=%d), think=%s",
                prompt_chars, len(system), len(prompt), think)

    # Use higher num_predict for think mode (thinking tokens + output)
    num_predict = 8192 if think else 4096

    t0 = time.monotonic()
    try:
        text, tokens = client.generate(
            prompt, system=system, num_predict=num_predict,
            json_mode=False, temperature=0.3, think=think,
        )
        duration = time.monotonic() - t0
        # Strip think tags if present
        content = text
        if "<think>" in content:
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        result = {
            "status": "success",
            "duration_s": round(duration, 1),
            "tokens": tokens,
            "prompt_chars": prompt_chars,
            "content": content,
            "raw_text": text[:500] if text != content else "",
            "char_count": len(content),
            "num_predict": num_predict,
        }
        logger.info("Atlas: %d chars, %d tokens in %.1fs (think=%s)",
                     len(content), tokens, duration, think)
    except Exception as e:
        duration = time.monotonic() - t0
        result = {
            "status": "error",
            "duration_s": round(duration, 1),
            "error": str(e),
            "content": "",
            "prompt_chars": prompt_chars,
        }
        logger.error("Atlas FAILED: %s", e)

    return result


def test_group_reasoning(client, think: bool, logger) -> Dict[str, Any]:
    """Run Group Reasoning and capture full outputs."""
    from codrag.core.group_reasoning import (
        GroupReasoningEngine, build_dependency_groups, GROUP_REASONING_SYSTEM,
        GROUP_REASONING_PROMPT, compute_group_fingerprint,
    )
    from codrag.core.llm_client import _parse_json_response
    from codrag.core.epistemic_score import EpistemicEntry

    engine = GroupReasoningEngine(llm=client, index_dir=INDEX_DIR)
    epistemic = engine.load_epistemic()
    edges = engine.load_edges()

    if not epistemic:
        return {"status": "skipped", "reason": "no epistemic data"}

    groups = build_dependency_groups(epistemic, edges)
    logger.info("Group Reasoning: %d groups from %d epistemic entries", len(groups), len(epistemic))

    if not groups:
        return {"status": "skipped", "reason": "no dependency groups"}

    # Use higher num_predict for think mode
    num_predict = 8192 if think else 4096

    group_results = []
    total_duration = 0.0

    for i, members in enumerate(groups):
        import hashlib
        gid = "group:" + hashlib.md5("|".join(sorted(members)).encode()).hexdigest()[:10]

        member_details = engine._build_member_details(members, epistemic)
        internal_edges = engine._build_internal_edges(members, edges)

        prompt = GROUP_REASONING_PROMPT.format(
            file_count=len(members),
            member_details=member_details,
            internal_edges=internal_edges,
        )

        prompt_chars = len(GROUP_REASONING_SYSTEM) + len(prompt)
        logger.info("  Group %s: %d files, prompt=%d chars, think=%s",
                     gid, len(members), prompt_chars, think)

        t0 = time.monotonic()
        try:
            text, tokens = client.generate(
                prompt, system=GROUP_REASONING_SYSTEM,
                num_predict=num_predict,
                json_mode=False, think=think,
                temperature=0.6,
            )
            duration = time.monotonic() - t0
            total_duration += duration

            parsed = _parse_json_response(text)
            group_results.append({
                "group_id": gid,
                "member_count": len(members),
                "members": [m.replace("file:", "") for m in members],
                "prompt_chars": prompt_chars,
                "duration_s": round(duration, 1),
                "tokens": tokens,
                "parsed_ok": parsed is not None,
                "pattern": parsed.get("pattern", "") if parsed else "",
                "data_flow": parsed.get("data_flow", "")[:300] if parsed else "",
                "coupling_risks": parsed.get("coupling_risks", []) if parsed else [],
                "blast_radius": parsed.get("blast_radius", []) if parsed else [],
                "architectural_insight": parsed.get("architectural_insight", "")[:500] if parsed else "",
                "confidence": parsed.get("confidence", 0) if parsed else 0,
                "raw_text": text[:200] if not parsed else "",
            })
            logger.info("  Group %s: pattern=%s, %.1fs, %d tokens",
                         gid, (parsed or {}).get("pattern", "PARSE_FAIL"), duration, tokens)
        except Exception as e:
            duration = time.monotonic() - t0
            total_duration += duration
            group_results.append({
                "group_id": gid,
                "member_count": len(members),
                "duration_s": round(duration, 1),
                "error": str(e),
            })
            logger.error("  Group %s FAILED: %s", gid, e)

    parse_ok = sum(1 for g in group_results if g.get("parsed_ok"))
    return {
        "status": "success",
        "total_groups": len(groups),
        "parse_success": parse_ok,
        "parse_fail": len(groups) - parse_ok,
        "total_duration_s": round(total_duration, 1),
        "avg_duration_s": round(total_duration / len(groups), 1) if groups else 0,
        "num_predict": num_predict,
        "groups": group_results,
    }


def test_audit_summary(client, think: bool, logger) -> Dict[str, Any]:
    """Run a single Audit Summary call to test large-context synthesis.

    We don't run the full audit pipeline (which requires Tier 1 analyzers).
    Instead we construct a realistic prompt from existing enrichment data.
    """
    from codrag.core.audit.prompts import AUDIT_SUMMARY_SYSTEM, AUDIT_SUMMARY_PROMPT

    # Load Atlas content
    atlas_content = ""
    atlas_path = INDEX_DIR / "atlas.json"
    if atlas_path.exists():
        try:
            with open(atlas_path) as f:
                atlas_data = json.load(f)
            atlas_content = atlas_data.get("content", "")[:3000]
        except Exception:
            pass

    # Load modules for module status section
    modules = []
    mod_path = INDEX_DIR / "trace_modules.jsonl"
    if mod_path.exists():
        with open(mod_path) as f:
            for line in f:
                if line.strip():
                    modules.append(json.loads(line))

    # Build synthetic findings from epistemic data
    findings_lines = []
    epi_path = INDEX_DIR / "trace_epistemic.jsonl"
    if epi_path.exists():
        with open(epi_path) as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    debts = d.get("tech_debt", [])
                    fp = d.get("node_id", "").replace("file:", "")
                    for debt in debts[:2]:
                        findings_lines.append(f"- WARNING: {fp}: {debt}")
                    if d.get("epistemic_confidence", 1.0) < 0.8:
                        findings_lines.append(f"- INFO: {fp}: Low confidence ({d.get('epistemic_confidence', 0):.2f})")

    findings_text = "\n".join(findings_lines[:30]) if findings_lines else "(no findings)"

    # Count nodes/edges
    node_count = sum(1 for _ in open(INDEX_DIR / "trace_nodes.jsonl")) if (INDEX_DIR / "trace_nodes.jsonl").exists() else 0
    edge_count = sum(1 for _ in open(INDEX_DIR / "trace_edges.jsonl")) if (INDEX_DIR / "trace_edges.jsonl").exists() else 0

    prompt = AUDIT_SUMMARY_PROMPT.format(
        project_name="DebateHaus Marketing",
        file_count=44,
        node_count=node_count,
        edge_count=edge_count,
        module_count=len(modules),
        atlas_content=atlas_content or "(no atlas yet)",
        finding_count=len(findings_lines),
        critical_count=0,
        warning_count=sum(1 for f in findings_lines if "WARNING" in f),
        findings_formatted=findings_text,
    )

    prompt_chars = len(AUDIT_SUMMARY_SYSTEM) + len(prompt)
    num_predict = 8192 if think else 4096

    logger.info("Audit Summary: prompt=%d chars, think=%s, num_predict=%d",
                prompt_chars, think, num_predict)

    t0 = time.monotonic()
    try:
        text, tokens = client.generate(
            prompt=prompt,
            system=AUDIT_SUMMARY_SYSTEM,
            json_mode=False,
            temperature=0.3,
            num_predict=num_predict,
            think=think,
        )
        duration = time.monotonic() - t0

        # Strip think tags
        content = text
        if "<think>" in content:
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        result = {
            "status": "success",
            "duration_s": round(duration, 1),
            "tokens": tokens,
            "prompt_chars": prompt_chars,
            "content": content,
            "char_count": len(content),
            "num_predict": num_predict,
        }
        logger.info("Audit Summary: %d chars, %d tokens in %.1fs",
                     len(content), tokens, duration)
    except Exception as e:
        duration = time.monotonic() - t0
        result = {
            "status": "error",
            "duration_s": round(duration, 1),
            "error": str(e),
            "content": "",
            "prompt_chars": prompt_chars,
        }
        logger.error("Audit Summary FAILED: %s", e)

    return result


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Benchmark large-context pipeline tasks")
    parser.add_argument("--only", type=int, help="Run only config N (1-indexed)")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_BASE / f"large_context_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(run_dir)
    logger.info("=" * 70)
    logger.info("  LARGE-CONTEXT BENCHMARK: Atlas + Group Reasoning + Audit")
    logger.info("  Repo: %s", REPO_PATH)
    logger.info("  Index: %s", INDEX_DIR)
    logger.info("  Results: %s", run_dir)
    logger.info("=" * 70)

    # Verify enrichment data exists (from overnight run)
    for f in ["trace_augmented.jsonl", "trace_epistemic.jsonl", "trace_modules.jsonl"]:
        if not (INDEX_DIR / f).exists():
            logger.error("Missing %s — run the full pipeline first", f)
            sys.exit(1)

    # First, restore enrichment data from the best overnight run (35b-a3b-nothink)
    # so all models are tested against the same enrichment baseline
    best_run = RESULTS_BASE / "overnight_20260306_082919" / "35b-a3b-nothink"
    if best_run.exists():
        import shutil
        for f in ["trace_augmented.jsonl", "trace_augment_manifest.json",
                   "trace_epistemic.jsonl", "trace_modules.jsonl"]:
            src = best_run / f
            if src.exists():
                shutil.copy2(src, INDEX_DIR / f)
        logger.info("Restored enrichment data from %s", best_run)
    else:
        logger.info("Using existing enrichment data in %s", INDEX_DIR)

    # Verify Ollama
    import requests
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        available = {m["name"] for m in resp.json().get("models", [])}
        for cfg in CONFIGS:
            tag = "✓" if cfg["model"] in available else "✗ MISSING"
            logger.info("  %s %s", tag, cfg["model"])
    except Exception as e:
        logger.error("Cannot connect to Ollama: %s", e)
        sys.exit(1)

    configs_to_run = CONFIGS
    if args.only:
        idx = args.only - 1
        if 0 <= idx < len(CONFIGS):
            configs_to_run = [CONFIGS[idx]]
        else:
            logger.error("--only must be 1-%d", len(CONFIGS))
            sys.exit(1)

    from codrag.core.llm_client import LLMClient

    all_results = {}

    for i, config in enumerate(configs_to_run):
        logger.info("")
        logger.info("#" * 70)
        logger.info("  CONFIG %d/%d: %s", i + 1, len(configs_to_run), config["label"])
        logger.info("#" * 70)

        client = LLMClient(
            endpoint_url=OLLAMA_URL,
            model=config["model"],
            provider="ollama",
            timeout=config["timeout"],
        )
        think = config["think"]

        # Pre-flight
        logger.info("Pre-flight LLM test...")
        t0 = time.monotonic()
        text, _ = client.generate('Respond: {"ok":true}', num_predict=20, think=think)
        logger.info("Pre-flight OK (%.1fs): %s", time.monotonic() - t0, text.strip()[:50])

        config_result = {"config": config}

        # ── Test 1: Atlas ──
        logger.info("")
        logger.info("--- TEST 1: Atlas Generation (think=%s) ---", think)
        config_result["atlas"] = test_atlas_with_think_override(client, think, logger)

        # ── Test 2: Group Reasoning ──
        logger.info("")
        logger.info("--- TEST 2: Group Reasoning (think=%s) ---", think)
        config_result["group_reasoning"] = test_group_reasoning(client, think, logger)

        # ── Test 3: Audit Summary ──
        logger.info("")
        logger.info("--- TEST 3: Audit Summary (think=%s) ---", think)
        config_result["audit_summary"] = test_audit_summary(client, think, logger)

        # Save per-config results
        config_dir = run_dir / config["id"]
        config_dir.mkdir(exist_ok=True)
        with open(config_dir / "result.json", "w") as f:
            json.dump(config_result, f, indent=2, default=str)

        # Save atlas content as readable text
        atlas_content = config_result.get("atlas", {}).get("content", "")
        if atlas_content:
            with open(config_dir / "atlas_output.txt", "w") as f:
                f.write(atlas_content)

        # Save audit content
        audit_content = config_result.get("audit_summary", {}).get("content", "")
        if audit_content:
            with open(config_dir / "audit_summary.md", "w") as f:
                f.write(audit_content)

        # Save group reasoning outputs
        gr = config_result.get("group_reasoning", {})
        if gr.get("groups"):
            with open(config_dir / "group_reasoning.json", "w") as f:
                json.dump(gr["groups"], f, indent=2, default=str)

        all_results[config["id"]] = config_result
        logger.info("Config %s saved to %s", config["id"], config_dir)

    # ── Summary ──
    logger.info("")
    logger.info("=" * 70)
    logger.info("  LARGE-CONTEXT BENCHMARK COMPLETE")
    logger.info("=" * 70)

    header = f"{'Config':<20} {'Atlas':>8} {'Atlas #':>7} {'GR Time':>8} {'GR Parse':>8} {'Audit':>8} {'Audit #':>7}"
    logger.info(header)
    logger.info("-" * len(header))

    for cfg_id, res in all_results.items():
        a = res.get("atlas", {})
        g = res.get("group_reasoning", {})
        au = res.get("audit_summary", {})

        atlas_t = f"{a.get('duration_s', 0):.0f}s"
        atlas_c = f"{a.get('char_count', 0)}"
        gr_t = f"{g.get('total_duration_s', 0):.0f}s"
        gr_p = f"{g.get('parse_success', 0)}/{g.get('total_groups', 0)}"
        au_t = f"{au.get('duration_s', 0):.0f}s"
        au_c = f"{au.get('char_count', 0)}"

        logger.info(f"{cfg_id:<20} {atlas_t:>8} {atlas_c:>7} {gr_t:>8} {gr_p:>8} {au_t:>8} {au_c:>7}")

    # Save combined results
    with open(run_dir / "summary.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    logger.info("\nAll results saved to %s", run_dir)


if __name__ == "__main__":
    main()
