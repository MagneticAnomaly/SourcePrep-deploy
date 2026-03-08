#!/usr/bin/env -S /Volumes/4TB-BAD/HumanAI/CoDRAG/.venv/bin/python
"""8-10 hour overnight benchmark: large-context tasks on the CoDRAG repo itself.

Tests Atlas, Group Reasoning, and Audit Summary across 6 model configurations
on a real 1300+ file monorepo to stress context window handling and measure
quality at scale.

Models:
  1. qwen3.5:35b-a3b       (Q4, no-think)  — fast baseline
  2. qwen3.5:35b-a3b       (Q4, think)     — deep reasoning on MoE
  3. qwen3.5:35b-a3b-q8_0  (Q8, no-think)  — does higher quant help?
  4. qwen3.5:27b            (Q4, no-think)  — dense baseline
  5. qwen3.5:27b-q8_0       (Q8, no-think)  — higher quant dense
  6. qwen3.5:122b-a10b      (no-think)      — big MoE, 10B active

Strategy:
  - Atlas: Cap module input to top 100 modules (~18K tokens) to fit context.
    Also test with top 50 (~9K tokens) to measure quality vs context size.
  - Group Reasoning: Sample 5 representative groups (2 small, 2 medium, 1 large).
  - Audit Summary: Use existing enrichment data + atlas as input.

Usage:
    nohup .venv/bin/python -u scripts/benchmark_large_context_codrag.py > results/codrag_overnight.log 2>&1 < /dev/null &
"""

import argparse
import json
import hashlib
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Setup ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

REPO_PATH = PROJECT_ROOT
INDEX_DIR = REPO_PATH / ".codrag"
OLLAMA_URL = "http://127.0.0.1:11434"
RESULTS_BASE = PROJECT_ROOT / "results"

# ── Model Configs ─────────────────────────────────────────────────────

CONFIGS = [
    {
        "id": "35b-a3b-q4-nothink",
        "label": "qwen3.5:35b-a3b Q4 (no-think)",
        "model": "qwen3.5:35b-a3b",
        "think": False,
        "timeout": 300.0,
        "description": "Fast MoE baseline — overnight winner",
    },
    {
        "id": "35b-a3b-q4-think",
        "label": "qwen3.5:35b-a3b Q4 (think)",
        "model": "qwen3.5:35b-a3b",
        "think": True,
        "timeout": 600.0,
        "description": "MoE with reasoning — best group quality on TEST",
    },
    {
        "id": "35b-a3b-q8-nothink",
        "label": "qwen3.5:35b-a3b Q8 (no-think)",
        "model": "qwen3.5:35b-a3b-q8_0",
        "think": False,
        "timeout": 300.0,
        "description": "Higher quantization MoE — does precision help?",
    },
    {
        "id": "27b-q4-nothink",
        "label": "qwen3.5:27b Q4 (no-think)",
        "model": "qwen3.5:27b",
        "think": False,
        "timeout": 600.0,
        "description": "Dense baseline — 27.8B active params",
    },
    {
        "id": "27b-q8-nothink",
        "label": "qwen3.5:27b Q8 (no-think)",
        "model": "qwen3.5:27b-q8_0",
        "think": False,
        "timeout": 600.0,
        "description": "Higher quantization dense — does precision help?",
    },
    {
        "id": "122b-a10b-nothink",
        "label": "qwen3.5:122b-a10b (no-think)",
        "model": "qwen3.5:122b-a10b",
        "think": False,
        "timeout": 900.0,
        "description": "Big MoE — 10B active params, does scale help?",
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
    class FlushFilter(logging.Filter):
        def filter(self, record):
            fh.flush()
            return True
    fh.addFilter(FlushFilter())
    return logging.getLogger("codrag_overnight")


# ── Data Loading ──────────────────────────────────────────────────────

def load_atlas_data():
    """Load all data the Atlas generator uses."""
    from codrag.core.atlas.generator import CodebaseAtlas
    atlas = CodebaseAtlas(index_dir=INDEX_DIR, project_root=REPO_PATH)
    modules = atlas._load_modules()
    epistemic = atlas._load_epistemic_summary()
    graph_stats = atlas._load_graph_stats()
    hub_files = atlas._identify_hubs(graph_stats)
    return atlas, modules, epistemic, graph_stats, hub_files


def load_group_data():
    """Load epistemic entries and edges for group reasoning."""
    from codrag.core.group_reasoning import build_dependency_groups
    from codrag.core.epistemic_score import EpistemicEntry

    epistemic = {}
    with open(INDEX_DIR / "trace_epistemic.jsonl") as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                entry = EpistemicEntry.from_dict(d)
                epistemic[entry.node_id] = entry

    edges = []
    for fname in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
        p = INDEX_DIR / fname
        if p.exists():
            with open(p) as f:
                for line in f:
                    if line.strip():
                        edges.append(json.loads(line))

    groups = build_dependency_groups(epistemic, edges)
    return epistemic, edges, groups


def select_representative_groups(groups):
    """Pick 5 representative groups: 2 small (2-4), 2 medium (5-10), 1 large (11-15)."""
    small = [g for g in groups if len(g) <= 4]
    medium = [g for g in groups if 5 <= len(g) <= 10]
    large = [g for g in groups if len(g) >= 11]

    selected = []
    if small:
        selected.extend(small[:2])
    if medium:
        selected.extend(medium[:2])
    if large:
        selected.extend(large[:1])

    # If we don't have enough variety, just take first 5
    if len(selected) < 3:
        selected = groups[:5]

    return selected


# ── Test Functions ────────────────────────────────────────────────────

def test_atlas(client, think, atlas_obj, modules, epistemic, graph_stats, hub_files,
               module_cap, logger):
    """Run Atlas with capped module count."""
    from codrag.core.atlas.prompts import ATLAS_SYSTEM, ATLAS_PROMPT
    from codrag.core.atlas.routing import compute_atlas_budget, MIN_ATLAS_CHARS

    sorted_mods = sorted(modules, key=lambda x: -x.get("file_count", 0))[:module_cap]

    file_count = graph_stats.get("file_count", 0)
    budget = compute_atlas_budget(file_count)
    target_chars = max(MIN_ATLAS_CHARS, budget)
    max_chars = int(target_chars * 1.3)

    module_text = atlas_obj._format_modules(sorted_mods)
    layer_text = atlas_obj._format_layers(epistemic)
    stats_text = atlas_obj._format_graph_stats(graph_stats)
    hub_text = atlas_obj._format_hubs(hub_files)

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
    num_predict = 8192 if think else 4096

    logger.info("Atlas (top %d modules): prompt=%d chars (~%d tokens), think=%s",
                module_cap, prompt_chars, prompt_chars // 4, think)

    t0 = time.monotonic()
    try:
        text, tokens = client.generate(
            prompt, system=system, num_predict=num_predict,
            json_mode=False, temperature=0.3, think=think,
        )
        duration = time.monotonic() - t0

        content = text
        if "<think>" in content:
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        result = {
            "status": "success",
            "duration_s": round(duration, 1),
            "tokens": tokens,
            "prompt_chars": prompt_chars,
            "module_cap": module_cap,
            "content": content,
            "char_count": len(content),
            "num_predict": num_predict,
        }
        logger.info("Atlas (%d mods): %d chars, %d tokens in %.1fs",
                     module_cap, len(content), tokens, duration)
    except Exception as e:
        duration = time.monotonic() - t0
        result = {
            "status": "error",
            "duration_s": round(duration, 1),
            "error": str(e),
            "content": "",
            "prompt_chars": prompt_chars,
            "module_cap": module_cap,
        }
        logger.error("Atlas FAILED after %.1fs: %s", duration, e)

    return result


def test_group_reasoning(client, think, epistemic, edges, groups, logger):
    """Run Group Reasoning on selected representative groups."""
    from codrag.core.group_reasoning import (
        GroupReasoningEngine, GROUP_REASONING_SYSTEM, GROUP_REASONING_PROMPT,
    )
    from codrag.core.llm_client import _parse_json_response

    engine = GroupReasoningEngine(llm=client, index_dir=INDEX_DIR)
    num_predict = 8192 if think else 4096
    group_results = []
    total_duration = 0.0

    for i, members in enumerate(groups):
        gid = "group:" + hashlib.md5("|".join(sorted(members)).encode()).hexdigest()[:10]

        member_details = engine._build_member_details(members, epistemic)
        internal_edges = engine._build_internal_edges(members, edges)

        prompt = GROUP_REASONING_PROMPT.format(
            file_count=len(members),
            member_details=member_details,
            internal_edges=internal_edges,
        )

        prompt_chars = len(GROUP_REASONING_SYSTEM) + len(prompt)
        logger.info("  Group %d/%d (%s): %d files, prompt=%d chars, think=%s",
                     i + 1, len(groups), gid, len(members), prompt_chars, think)

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
                "members": [m.replace("file:", "") for m in members[:5]],
                "prompt_chars": prompt_chars,
                "duration_s": round(duration, 1),
                "tokens": tokens,
                "parsed_ok": parsed is not None,
                "pattern": parsed.get("pattern", "") if parsed else "",
                "data_flow": parsed.get("data_flow", "")[:300] if parsed else "",
                "coupling_risks": parsed.get("coupling_risks", []) if parsed else [],
                "blast_radius_count": len(parsed.get("blast_radius", [])) if parsed else 0,
                "architectural_insight": parsed.get("architectural_insight", "")[:500] if parsed else "",
                "confidence": parsed.get("confidence", 0) if parsed else 0,
            })
            logger.info("    → pattern=%s, %.1fs, %d tokens, parsed=%s",
                         (parsed or {}).get("pattern", "FAIL")[:60], duration, tokens,
                         parsed is not None)
        except Exception as e:
            duration = time.monotonic() - t0
            total_duration += duration
            group_results.append({
                "group_id": gid,
                "member_count": len(members),
                "duration_s": round(duration, 1),
                "error": str(e),
                "parsed_ok": False,
            })
            logger.error("    → FAILED: %s (%.1fs)", e, duration)

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


def test_audit_summary(client, think, logger):
    """Run Audit Summary with CoDRAG's real data."""
    from codrag.core.audit.prompts import AUDIT_SUMMARY_SYSTEM, AUDIT_SUMMARY_PROMPT

    # Load existing atlas
    atlas_content = ""
    atlas_path = INDEX_DIR / "atlas.json"
    if atlas_path.exists():
        try:
            with open(atlas_path) as f:
                atlas_data = json.load(f)
            atlas_content = atlas_data.get("content", "")[:3000]
        except Exception:
            pass

    # Load modules
    modules = []
    mod_path = INDEX_DIR / "trace_modules.jsonl"
    if mod_path.exists():
        with open(mod_path) as f:
            for line in f:
                if line.strip():
                    modules.append(json.loads(line))

    # Build findings from epistemic data
    findings_lines = []
    with open(INDEX_DIR / "trace_epistemic.jsonl") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                debts = d.get("tech_debt", [])
                fp = d.get("node_id", "").replace("file:", "")
                for debt in debts[:1]:
                    findings_lines.append(f"- WARNING: {fp}: {debt}")
    # Cap findings to avoid prompt bloat
    findings_text = "\n".join(findings_lines[:40]) if findings_lines else "(no findings)"

    node_count = sum(1 for _ in open(INDEX_DIR / "trace_nodes.jsonl"))
    edge_count = sum(1 for _ in open(INDEX_DIR / "trace_edges.jsonl"))

    prompt = AUDIT_SUMMARY_PROMPT.format(
        project_name="CoDRAG",
        file_count=1341,
        node_count=node_count,
        edge_count=edge_count,
        module_count=len(modules),
        atlas_content=atlas_content or "(no atlas yet)",
        finding_count=len(findings_lines),
        critical_count=0,
        warning_count=len(findings_lines),
        findings_formatted=findings_text,
    )

    prompt_chars = len(AUDIT_SUMMARY_SYSTEM) + len(prompt)
    num_predict = 8192 if think else 4096

    logger.info("Audit Summary: prompt=%d chars (~%d tokens), think=%s",
                prompt_chars, prompt_chars // 4, think)

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

        content = text
        if "<think>" in content:
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
        logger.error("Audit FAILED after %.1fs: %s", duration, e)

    return result


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, help="Run only config N (1-indexed)")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_BASE / f"codrag_large_ctx_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(run_dir)
    logger.info("=" * 70)
    logger.info("  CODRAG LARGE-CONTEXT OVERNIGHT BENCHMARK")
    logger.info("  Repo: %s (1341 files, 4927 nodes, 19690 edges)", REPO_PATH)
    logger.info("  Index: %s", INDEX_DIR)
    logger.info("  Results: %s", run_dir)
    logger.info("  Configs: %d models × 3 tasks", len(CONFIGS))
    logger.info("=" * 70)

    # Pre-load shared data
    logger.info("Loading shared data...")
    atlas_obj, all_modules, epistemic_summary, graph_stats, hub_files = load_atlas_data()
    epistemic_entries, edges, all_groups = load_group_data()
    representative_groups = select_representative_groups(all_groups)

    logger.info("  Modules: %d total (will cap to 50 and 100 for Atlas)", len(all_modules))
    logger.info("  Groups: %d total, %d selected for testing", len(all_groups), len(representative_groups))
    for i, g in enumerate(representative_groups):
        logger.info("    Group %d: %d files", i + 1, len(g))

    # Verify models
    import requests
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        available = {m["name"] for m in resp.json().get("models", [])}
        for cfg in CONFIGS:
            tag = "✓" if cfg["model"] in available else "✗ MISSING"
            logger.info("  %s %s (%.1f GB)", tag, cfg["model"],
                        next((m["size"] / 1e9 for m in resp.json()["models"]
                              if m["name"] == cfg["model"]), 0))
    except Exception as e:
        logger.error("Cannot connect to Ollama: %s", e)
        sys.exit(1)

    from codrag.core.llm_client import LLMClient

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

    for ci, config in enumerate(configs_to_run):
        config_start = time.monotonic()
        logger.info("")
        logger.info("#" * 70)
        logger.info("  CONFIG %d/%d: %s", ci + 1, len(configs_to_run), config["label"])
        logger.info("  %s", config["description"])
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
        try:
            text, _ = client.generate('Respond: {"ok":true}', num_predict=20, think=think)
            logger.info("Pre-flight OK (%.1fs): %s", time.monotonic() - t0, text.strip()[:50])
        except Exception as e:
            logger.error("Pre-flight FAILED: %s — skipping config", e)
            all_results[config["id"]] = {"config": config, "status": "preflight_failed", "error": str(e)}
            continue

        config_result = {"config": config}

        # ── Test 1a: Atlas with top 50 modules ──
        logger.info("")
        logger.info("--- TEST 1a: Atlas (top 50 modules, ~9K tokens) ---")
        config_result["atlas_50"] = test_atlas(
            client, think, atlas_obj, all_modules, epistemic_summary,
            graph_stats, hub_files, 50, logger,
        )

        # ── Test 1b: Atlas with top 100 modules ──
        logger.info("")
        logger.info("--- TEST 1b: Atlas (top 100 modules, ~18K tokens) ---")
        config_result["atlas_100"] = test_atlas(
            client, think, atlas_obj, all_modules, epistemic_summary,
            graph_stats, hub_files, 100, logger,
        )

        # ── Test 2: Group Reasoning (5 representative groups) ──
        logger.info("")
        logger.info("--- TEST 2: Group Reasoning (%d groups) ---", len(representative_groups))
        config_result["group_reasoning"] = test_group_reasoning(
            client, think, epistemic_entries, edges, representative_groups, logger,
        )

        # ── Test 3: Audit Summary ──
        logger.info("")
        logger.info("--- TEST 3: Audit Summary ---")
        config_result["audit_summary"] = test_audit_summary(client, think, logger)

        # Save per-config results
        config_dir = run_dir / config["id"]
        config_dir.mkdir(exist_ok=True)
        with open(config_dir / "result.json", "w") as f:
            json.dump(config_result, f, indent=2, default=str)

        # Save readable outputs
        for key in ("atlas_50", "atlas_100"):
            content = config_result.get(key, {}).get("content", "")
            if content:
                with open(config_dir / f"{key}_output.txt", "w") as f:
                    f.write(content)

        audit_content = config_result.get("audit_summary", {}).get("content", "")
        if audit_content:
            with open(config_dir / "audit_summary.md", "w") as f:
                f.write(audit_content)

        gr = config_result.get("group_reasoning", {})
        if gr.get("groups"):
            with open(config_dir / "group_reasoning.json", "w") as f:
                json.dump(gr["groups"], f, indent=2, default=str)

        config_time = time.monotonic() - config_start
        all_results[config["id"]] = config_result
        logger.info("")
        logger.info("Config %s completed in %.1fs (%.1f min)",
                     config["id"], config_time, config_time / 60)

    overall_time = time.monotonic() - overall_start

    # ── Summary ──
    logger.info("")
    logger.info("=" * 70)
    logger.info("  CODRAG LARGE-CONTEXT BENCHMARK COMPLETE")
    logger.info("  Total: %.1fs (%.1f min)", overall_time, overall_time / 60)
    logger.info("=" * 70)

    hdr = f"{'Config':<25} {'A50':>6} {'A100':>6} {'GR':>8} {'GR Parse':>8} {'Audit':>6} {'A50#':>5} {'A100#':>5} {'Aud#':>5}"
    logger.info(hdr)
    logger.info("-" * len(hdr))

    for cfg_id, res in all_results.items():
        if res.get("status") == "preflight_failed":
            logger.info(f"{cfg_id:<25} PREFLIGHT FAILED: {res.get('error', '?')[:40]}")
            continue
        a50 = res.get("atlas_50", {})
        a100 = res.get("atlas_100", {})
        g = res.get("group_reasoning", {})
        au = res.get("audit_summary", {})

        logger.info(
            f"{cfg_id:<25} "
            f"{a50.get('duration_s', 0):>5.0f}s "
            f"{a100.get('duration_s', 0):>5.0f}s "
            f"{g.get('total_duration_s', 0):>7.0f}s "
            f"{g.get('parse_success', 0):>3}/{g.get('total_groups', 0):<3} "
            f"{au.get('duration_s', 0):>5.0f}s "
            f"{a50.get('char_count', 0):>5} "
            f"{a100.get('char_count', 0):>5} "
            f"{au.get('char_count', 0):>5}"
        )

    # Save combined
    with open(run_dir / "summary.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    logger.info("\nAll results saved to %s", run_dir)


if __name__ == "__main__":
    main()
