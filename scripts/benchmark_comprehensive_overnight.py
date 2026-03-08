#!/usr/bin/env -S /Volumes/4TB-BAD/HumanAI/CoDRAG/.venv/bin/python
"""Comprehensive overnight benchmark: 6 model configs × 2 repos × large-context tasks.

Phase 1: Run missing CoDRAG configs (35b-a3b Q8 think, 122b-a10b think)
Phase 2: Build .codrag trace on LinuxBrain repo (structural trace + fast enrichment)
Phase 3: Run all 6 configs on LinuxBrain for large-context tasks

Models tested:
  1. qwen3.5:35b-a3b       Q4  no-think
  2. qwen3.5:35b-a3b       Q4  think
  3. qwen3.5:35b-a3b-q8_0  Q8  no-think
  4. qwen3.5:35b-a3b-q8_0  Q8  think
  5. qwen3.5:122b-a10b         no-think
  6. qwen3.5:122b-a10b         think

Usage:
    nohup .venv/bin/python -u scripts/benchmark_comprehensive_overnight.py > results/comprehensive_overnight.log 2>&1 < /dev/null &
"""

import argparse
import json
import hashlib
import logging
import os
import re
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

CODRAG_REPO = PROJECT_ROOT
CODRAG_INDEX = CODRAG_REPO / ".codrag"
LINUXBRAIN_REPO = Path("/Volumes/4TB-BAD/HumanAI/LinuxBrain")
LINUXBRAIN_INDEX = LINUXBRAIN_REPO / ".codrag"
OLLAMA_URL = "http://127.0.0.1:11434"
RESULTS_BASE = PROJECT_ROOT / "results"

# ── All 6 configs ─────────────────────────────────────────────────────

CONFIGS = [
    {
        "id": "35b-a3b-q4-nothink",
        "label": "qwen3.5:35b-a3b Q4 (no-think)",
        "model": "qwen3.5:35b-a3b",
        "think": False,
        "timeout": 300.0,
    },
    {
        "id": "35b-a3b-q4-think",
        "label": "qwen3.5:35b-a3b Q4 (think)",
        "model": "qwen3.5:35b-a3b",
        "think": True,
        "timeout": 600.0,
    },
    {
        "id": "35b-a3b-q8-nothink",
        "label": "qwen3.5:35b-a3b Q8 (no-think)",
        "model": "qwen3.5:35b-a3b-q8_0",
        "think": False,
        "timeout": 300.0,
    },
    {
        "id": "35b-a3b-q8-think",
        "label": "qwen3.5:35b-a3b Q8 (think)",
        "model": "qwen3.5:35b-a3b-q8_0",
        "think": True,
        "timeout": 600.0,
    },
    {
        "id": "122b-a10b-nothink",
        "label": "qwen3.5:122b-a10b (no-think)",
        "model": "qwen3.5:122b-a10b",
        "think": False,
        "timeout": 900.0,
    },
    {
        "id": "122b-a10b-think",
        "label": "qwen3.5:122b-a10b (think)",
        "model": "qwen3.5:122b-a10b",
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
    class FlushFilter(logging.Filter):
        def filter(self, record):
            fh.flush()
            return True
    fh.addFilter(FlushFilter())
    return logging.getLogger("comprehensive")


# ── Phase 2: Build LinuxBrain trace ───────────────────────────────────

def build_linuxbrain_trace(logger):
    """Build structural trace + fast enrichment on LinuxBrain."""
    from codrag.core.trace.builder import build_trace
    from codrag.core.llm_client import LLMClient
    from codrag.core.augmenter import TraceAugmenter
    from codrag.core.epistemic_enrichment import EpistemicEnricher
    from codrag.core.cluster import ClusterSynthesizer

    idx_dir = LINUXBRAIN_INDEX
    idx_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Structural trace (Rust engine, no LLM needed)
    nodes_path = idx_dir / "trace_nodes.jsonl"
    edges_path = idx_dir / "trace_edges.jsonl"

    if nodes_path.exists():
        node_count = sum(1 for _ in open(nodes_path))
        edge_count = sum(1 for _ in open(edges_path)) if edges_path.exists() else 0
        logger.info("Structural trace already exists: %d nodes, %d edges — skipping rebuild", node_count, edge_count)
        trace_time = 0.0
    else:
        logger.info("Building structural trace on LinuxBrain...")
        t0 = time.monotonic()

        exclude_globs = [
            "**/.git/**", "**/.venv/**", "**/node_modules/**", "**/__pycache__/**",
            "**/build/**", "**/dist/**", "**/.pytest_cache/**", "**/deep_thinking_logs/**",
            "**/.orchids/**", "**/Docs_Halley/**",  # large doc dump, skip for speed
            "**/data/**",       # 24GB model weights/datasets — not code
            "**/installers/**", # 920MB built installers — not code
        ]

        result = build_trace(
            repo_root=LINUXBRAIN_REPO,
            index_dir=idx_dir,
            exclude_globs=exclude_globs,
            max_file_bytes=500_000,  # 500KB max per file
        )

        trace_time = time.monotonic() - t0
        logger.info("Structural trace: %.1fs — %s", trace_time, result)

        if not nodes_path.exists():
            logger.error("trace_nodes.jsonl not created — trace build failed")
            return False

        node_count = sum(1 for _ in open(nodes_path))
        edge_count = sum(1 for _ in open(edges_path)) if edges_path.exists() else 0
        logger.info("LinuxBrain trace: %d nodes, %d edges", node_count, edge_count)

    # Step 2: Fast augmentation with fastest model
    logger.info("Running fast augmentation on LinuxBrain (35b-a3b Q4, no-think)...")
    client = LLMClient(
        endpoint_url=OLLAMA_URL,
        model="qwen3.5:35b-a3b",
        provider="ollama",
        timeout=180.0,
    )

    # Patch think=False
    orig_gen = client.generate
    def patched(*a, **kw):
        kw.setdefault("think", False)
        return orig_gen(*a, **kw)
    client.generate = patched

    augmenter = TraceAugmenter(
        index_dir=idx_dir,
        repo_root=LINUXBRAIN_REPO,
        llm_client=client,
    )
    t0 = time.monotonic()
    aug_result = augmenter.run()
    aug_time = time.monotonic() - t0
    logger.info("Augmentation: %d augmented, %d skipped in %.1fs",
                aug_result.augmented, aug_result.skipped, aug_time)

    # Step 3: Fast epistemic enrichment
    logger.info("Running epistemic enrichment on LinuxBrain...")
    enricher = EpistemicEnricher(
        index_dir=idx_dir,
        repo_root=LINUXBRAIN_REPO,
        llm=client,
    )
    t0 = time.monotonic()
    epi_result = enricher.run()
    epi_time = time.monotonic() - t0
    logger.info("Epistemic: %s in %.1fs", epi_result, epi_time)

    # Step 4: Cluster synthesis
    logger.info("Running cluster synthesis on LinuxBrain...")
    synthesizer = ClusterSynthesizer(
        index_dir=idx_dir,
        llm=client,
    )
    t0 = time.monotonic()
    cluster_result = synthesizer.run()
    cluster_time = time.monotonic() - t0
    logger.info("Clustering: %s in %.1fs", cluster_result, cluster_time)

    total_time = trace_time + aug_time + epi_time + cluster_time
    logger.info("LinuxBrain trace build COMPLETE: %.1fs (%.1f min)", total_time, total_time / 60)

    return True


# ── Large-Context Test Functions ──────────────────────────────────────

def load_atlas_data(index_dir):
    from codrag.core.atlas.generator import CodebaseAtlas
    atlas = CodebaseAtlas(index_dir=index_dir, project_root=index_dir.parent)
    modules = atlas._load_modules()
    epistemic = atlas._load_epistemic_summary()
    graph_stats = atlas._load_graph_stats()
    hub_files = atlas._identify_hubs(graph_stats)
    return atlas, modules, epistemic, graph_stats, hub_files


def load_group_data(index_dir):
    from codrag.core.group_reasoning import build_dependency_groups
    from codrag.core.epistemic_score import EpistemicEntry

    epistemic = {}
    epi_path = index_dir / "trace_epistemic.jsonl"
    if epi_path.exists():
        with open(epi_path) as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    entry = EpistemicEntry.from_dict(d)
                    epistemic[entry.node_id] = entry

    edges = []
    for fname in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
        p = index_dir / fname
        if p.exists():
            with open(p) as f:
                for line in f:
                    if line.strip():
                        edges.append(json.loads(line))

    groups = build_dependency_groups(epistemic, edges)
    return epistemic, edges, groups


def select_representative_groups(groups):
    small = [g for g in groups if len(g) <= 4]
    medium = [g for g in groups if 5 <= len(g) <= 10]
    large = [g for g in groups if len(g) >= 11]
    selected = []
    if small: selected.extend(small[:2])
    if medium: selected.extend(medium[:2])
    if large: selected.extend(large[:1])
    if len(selected) < 3:
        selected = groups[:5]
    return selected


def test_atlas(client, think, atlas_obj, modules, epistemic, graph_stats, hub_files,
               module_cap, logger):
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
        module_summaries=module_text, architecture_layers=layer_text,
        graph_stats=stats_text, hub_files=hub_text,
        target_chars=target_chars, max_chars=max_chars,
    )

    prompt_chars = len(system) + len(prompt)
    prompt_tokens_est = prompt_chars // 4
    # Phase 46: Dynamic num_predict based on input size
    # Small inputs (<5K tokens): model self-terminates ~2.5K, no need for huge budget
    # Large inputs (>10K tokens): model utilizes budget proportionally
    if prompt_tokens_est < 5000:
        num_predict = 4096
    elif prompt_tokens_est < 15000:
        num_predict = 16384
    else:
        num_predict = 32768
    # think mode budget is handled by llm_client.py (3× auto-scale)
    logger.info("Atlas (top %d mods): prompt=%d chars (~%d tokens), num_predict=%d, think=%s",
                module_cap, prompt_chars, prompt_tokens_est, num_predict, think)

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
        return {
            "status": "success", "duration_s": round(duration, 1), "tokens": tokens,
            "prompt_chars": prompt_chars, "module_cap": module_cap,
            "content": content, "char_count": len(content), "num_predict": num_predict,
        }
    except Exception as e:
        return {
            "status": "error", "duration_s": round(time.monotonic() - t0, 1),
            "error": str(e), "content": "", "prompt_chars": prompt_chars,
        }


def test_group_reasoning(client, think, epistemic, edges, groups, logger):
    from codrag.core.group_reasoning import (
        GroupReasoningEngine, GROUP_REASONING_SYSTEM, GROUP_REASONING_PROMPT,
    )
    from codrag.core.llm_client import _parse_json_response

    # Use a dummy index_dir for the engine (we only need the helper methods)
    engine = GroupReasoningEngine.__new__(GroupReasoningEngine)
    engine.llm = client

    # Phase 46: Group Reasoning JSON is naturally bounded (~1-3K tokens)
    # but give headroom for complex groups
    num_predict = 8192
    # think mode budget scaling handled by llm_client.py (3× auto-scale)
    group_results = []
    total_duration = 0.0

    for i, members in enumerate(groups):
        gid = "group:" + hashlib.md5("|".join(sorted(members)).encode()).hexdigest()[:10]
        member_details = engine._build_member_details(members, epistemic)
        internal_edges = engine._build_internal_edges(members, edges)

        prompt = GROUP_REASONING_PROMPT.format(
            file_count=len(members), member_details=member_details,
            internal_edges=internal_edges,
        )
        prompt_chars = len(GROUP_REASONING_SYSTEM) + len(prompt)
        logger.info("  Group %d/%d (%s): %d files, prompt=%d chars",
                     i + 1, len(groups), gid, len(members), prompt_chars)

        t0 = time.monotonic()
        try:
            text, tokens = client.generate(
                prompt, system=GROUP_REASONING_SYSTEM,
                num_predict=num_predict, json_mode=False, think=think, temperature=0.6,
            )
            duration = time.monotonic() - t0
            total_duration += duration
            parsed = _parse_json_response(text)
            group_results.append({
                "group_id": gid, "member_count": len(members),
                "members": [m.replace("file:", "") for m in members[:5]],
                "prompt_chars": prompt_chars, "duration_s": round(duration, 1),
                "tokens": tokens, "parsed_ok": parsed is not None,
                "pattern": parsed.get("pattern", "") if parsed else "",
                "data_flow": parsed.get("data_flow", "")[:300] if parsed else "",
                "coupling_risks": parsed.get("coupling_risks", []) if parsed else [],
                "blast_radius_count": len(parsed.get("blast_radius", [])) if parsed else 0,
                "architectural_insight": parsed.get("architectural_insight", "")[:500] if parsed else "",
                "confidence": parsed.get("confidence", 0) if parsed else 0,
            })
            logger.info("    → %s, %.1fs, %d tokens",
                         (parsed or {}).get("pattern", "FAIL")[:60], duration, tokens)
        except Exception as e:
            duration = time.monotonic() - t0
            total_duration += duration
            group_results.append({
                "group_id": gid, "member_count": len(members),
                "duration_s": round(duration, 1), "error": str(e), "parsed_ok": False,
            })
            logger.error("    → FAILED: %s", e)

    parse_ok = sum(1 for g in group_results if g.get("parsed_ok"))
    return {
        "status": "success", "total_groups": len(groups),
        "parse_success": parse_ok, "parse_fail": len(groups) - parse_ok,
        "total_duration_s": round(total_duration, 1),
        "avg_duration_s": round(total_duration / max(len(groups), 1), 1),
        "groups": group_results,
    }


def test_audit_summary(client, think, index_dir, repo_name, logger):
    from codrag.core.audit.prompts import AUDIT_SUMMARY_SYSTEM, AUDIT_SUMMARY_PROMPT

    atlas_content = ""
    atlas_path = index_dir / "atlas.json"
    if atlas_path.exists():
        try:
            atlas_content = json.load(open(atlas_path)).get("content", "")[:3000]
        except Exception:
            pass

    modules = []
    mod_path = index_dir / "trace_modules.jsonl"
    if mod_path.exists():
        with open(mod_path) as f:
            for line in f:
                if line.strip():
                    modules.append(json.loads(line))

    findings_lines = []
    epi_path = index_dir / "trace_epistemic.jsonl"
    if epi_path.exists():
        with open(epi_path) as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    for debt in d.get("tech_debt", [])[:1]:
                        fp = d.get("node_id", "").replace("file:", "")
                        findings_lines.append(f"- WARNING: {fp}: {debt}")

    findings_text = "\n".join(findings_lines[:40]) or "(no findings)"
    node_count = sum(1 for _ in open(index_dir / "trace_nodes.jsonl")) if (index_dir / "trace_nodes.jsonl").exists() else 0
    edge_count = sum(1 for _ in open(index_dir / "trace_edges.jsonl")) if (index_dir / "trace_edges.jsonl").exists() else 0

    prompt = AUDIT_SUMMARY_PROMPT.format(
        project_name=repo_name, file_count=node_count, node_count=node_count,
        edge_count=edge_count, module_count=len(modules),
        atlas_content=atlas_content or "(no atlas yet)",
        finding_count=len(findings_lines), critical_count=0,
        warning_count=len(findings_lines), findings_formatted=findings_text,
    )

    prompt_chars = len(AUDIT_SUMMARY_SYSTEM) + len(prompt)
    # Phase 46: Audit reports benefit from generous output budget
    num_predict = 16384
    logger.info("Audit: prompt=%d chars, num_predict=%d, think=%s", prompt_chars, num_predict, think)

    t0 = time.monotonic()
    try:
        text, tokens = client.generate(
            prompt=prompt, system=AUDIT_SUMMARY_SYSTEM,
            json_mode=False, temperature=0.3, num_predict=num_predict, think=think,
        )
        duration = time.monotonic() - t0
        content = text
        if "<think>" in content:
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return {
            "status": "success", "duration_s": round(duration, 1), "tokens": tokens,
            "prompt_chars": prompt_chars, "content": content,
            "char_count": len(content), "num_predict": num_predict,
        }
    except Exception as e:
        return {
            "status": "error", "duration_s": round(time.monotonic() - t0, 1),
            "error": str(e), "content": "", "prompt_chars": prompt_chars,
        }


# ── Run benchmark on a repo ──────────────────────────────────────────

def run_repo_benchmark(repo_name, index_dir, configs_to_run, run_dir, logger):
    """Run all configs on a single repo's index."""
    logger.info("Loading data from %s...", index_dir)
    atlas_obj, all_modules, epistemic_summary, graph_stats, hub_files = load_atlas_data(index_dir)
    epistemic_entries, edges, all_groups = load_group_data(index_dir)
    rep_groups = select_representative_groups(all_groups)

    logger.info("  Modules: %d, Groups: %d total → %d selected, Files: %d",
                len(all_modules), len(all_groups), len(rep_groups),
                graph_stats.get("file_count", 0))

    from codrag.core.llm_client import LLMClient
    repo_results = {}

    for ci, config in enumerate(configs_to_run):
        logger.info("")
        logger.info("## %s — Config %d/%d: %s",
                     repo_name, ci + 1, len(configs_to_run), config["label"])

        client = LLMClient(
            endpoint_url=OLLAMA_URL, model=config["model"],
            provider="ollama", timeout=config["timeout"],
        )
        think = config["think"]

        # Pre-flight
        logger.info("Pre-flight...")
        try:
            t0 = time.monotonic()
            text, _ = client.generate('Respond: {"ok":true}', num_predict=20, think=think)
            logger.info("Pre-flight OK (%.1fs)", time.monotonic() - t0)
        except Exception as e:
            logger.error("Pre-flight FAILED: %s — skipping", e)
            repo_results[config["id"]] = {"status": "preflight_failed", "error": str(e)}
            continue

        cfg_result = {"config": config}

        # Atlas top 50
        logger.info("--- Atlas (top 50 mods) ---")
        cfg_result["atlas_50"] = test_atlas(
            client, think, atlas_obj, all_modules, epistemic_summary,
            graph_stats, hub_files, 50, logger,
        )

        # Atlas top 100
        logger.info("--- Atlas (top 100 mods) ---")
        cfg_result["atlas_100"] = test_atlas(
            client, think, atlas_obj, all_modules, epistemic_summary,
            graph_stats, hub_files, 100, logger,
        )

        # Group reasoning
        logger.info("--- Group Reasoning (%d groups) ---", len(rep_groups))
        cfg_result["group_reasoning"] = test_group_reasoning(
            client, think, epistemic_entries, edges, rep_groups, logger,
        )

        # Audit
        logger.info("--- Audit Summary ---")
        cfg_result["audit_summary"] = test_audit_summary(
            client, think, index_dir, repo_name, logger,
        )

        # Save per-config
        cfg_dir = run_dir / repo_name / config["id"]
        cfg_dir.mkdir(parents=True, exist_ok=True)
        with open(cfg_dir / "result.json", "w") as f:
            json.dump(cfg_result, f, indent=2, default=str)

        for key in ("atlas_50", "atlas_100"):
            content = cfg_result.get(key, {}).get("content", "")
            if content:
                with open(cfg_dir / f"{key}_output.txt", "w") as f:
                    f.write(content)

        audit = cfg_result.get("audit_summary", {}).get("content", "")
        if audit:
            with open(cfg_dir / "audit_summary.md", "w") as f:
                f.write(audit)

        gr = cfg_result.get("group_reasoning", {})
        if gr.get("groups"):
            with open(cfg_dir / "group_reasoning.json", "w") as f:
                json.dump(gr["groups"], f, indent=2, default=str)

        repo_results[config["id"]] = cfg_result
        logger.info("Config %s saved", config["id"])

    return repo_results


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-codrag-missing", action="store_true",
                        help="Skip the 2 missing CoDRAG configs")
    parser.add_argument("--skip-linuxbrain-build", action="store_true",
                        help="Skip building LinuxBrain trace (use existing)")
    parser.add_argument("--only-config", type=int,
                        help="Run only config N (1-indexed)")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_BASE / f"comprehensive_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(run_dir)
    logger.info("=" * 70)
    logger.info("  COMPREHENSIVE OVERNIGHT BENCHMARK")
    logger.info("  CoDRAG: %s", CODRAG_INDEX)
    logger.info("  LinuxBrain: %s", LINUXBRAIN_REPO)
    logger.info("  Results: %s", run_dir)
    logger.info("=" * 70)

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
    if args.only_config:
        idx = args.only_config - 1
        if 0 <= idx < len(CONFIGS):
            configs_to_run = [CONFIGS[idx]]

    overall_start = time.monotonic()
    all_results = {}

    # ══════════════════════════════════════════════════════════════
    # PHASE 1: Missing CoDRAG configs (Q8 think + 122b think)
    # ══════════════════════════════════════════════════════════════
    if not args.skip_codrag_missing:
        codrag_missing = [c for c in configs_to_run if c["id"] in ("35b-a3b-q8-think", "122b-a10b-think")]
        if codrag_missing:
            logger.info("")
            logger.info("=" * 70)
            logger.info("  PHASE 1: Missing CoDRAG configs (%d)", len(codrag_missing))
            logger.info("=" * 70)
            codrag_results = run_repo_benchmark("codrag", CODRAG_INDEX, codrag_missing, run_dir, logger)
            all_results["codrag_missing"] = codrag_results
        else:
            logger.info("No missing CoDRAG configs to run")

    # ══════════════════════════════════════════════════════════════
    # PHASE 2: Build LinuxBrain trace
    # ══════════════════════════════════════════════════════════════
    # Check if LinuxBrain trace is COMPLETE (has enrichment, not just structural)
    lb_needs_build = not LINUXBRAIN_INDEX.exists() or not (LINUXBRAIN_INDEX / "trace_epistemic.jsonl").exists()
    if not args.skip_linuxbrain_build and lb_needs_build:
        logger.info("")
        logger.info("=" * 70)
        logger.info("  PHASE 2: Building LinuxBrain .codrag trace")
        if LINUXBRAIN_INDEX.exists():
            logger.info("  (partial index found — completing enrichment)")
        logger.info("=" * 70)
        t0 = time.monotonic()
        ok = build_linuxbrain_trace(logger)
        if not ok:
            logger.error("LinuxBrain trace build FAILED — skipping LinuxBrain tests")
        else:
            logger.info("LinuxBrain trace built in %.1f min", (time.monotonic() - t0) / 60)
    elif not lb_needs_build:
        logger.info("LinuxBrain .codrag complete — skipping build")
    else:
        logger.info("Skipping LinuxBrain build (--skip-linuxbrain-build)")

    # ══════════════════════════════════════════════════════════════
    # PHASE 3: Run all 6 configs on LinuxBrain
    # ══════════════════════════════════════════════════════════════
    if LINUXBRAIN_INDEX.exists() and (LINUXBRAIN_INDEX / "trace_epistemic.jsonl").exists():
        logger.info("")
        logger.info("=" * 70)
        logger.info("  PHASE 3: LinuxBrain large-context benchmark (%d configs)", len(configs_to_run))
        logger.info("=" * 70)
        lb_results = run_repo_benchmark("linuxbrain", LINUXBRAIN_INDEX, configs_to_run, run_dir, logger)
        all_results["linuxbrain"] = lb_results
    else:
        logger.info("LinuxBrain index not ready — skipping Phase 3")

    # ══════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════
    overall_time = time.monotonic() - overall_start
    logger.info("")
    logger.info("=" * 70)
    logger.info("  COMPREHENSIVE BENCHMARK COMPLETE")
    logger.info("  Total: %.1fs (%.1f min)", overall_time, overall_time / 60)
    logger.info("=" * 70)

    # Print summary tables
    for repo_key in ("codrag_missing", "linuxbrain"):
        repo_data = all_results.get(repo_key, {})
        if not repo_data:
            continue
        logger.info("")
        logger.info("--- %s ---", repo_key.upper())
        logger.info("%-25s %6s %6s %8s %8s %6s %5s %5s %5s",
                     "Config", "A50", "A100", "GR", "Parse", "Audit", "A50#", "A100#", "Aud#")
        for cfg_id, res in repo_data.items():
            if isinstance(res, dict) and "atlas_50" in res:
                a50 = res.get("atlas_50", {})
                a100 = res.get("atlas_100", {})
                g = res.get("group_reasoning", {})
                au = res.get("audit_summary", {})
                logger.info(
                    "%-25s %5.0fs %5.0fs %7.0fs %3d/%-3d %5.0fs %5d %5d %5d",
                    cfg_id,
                    a50.get("duration_s", 0), a100.get("duration_s", 0),
                    g.get("total_duration_s", 0),
                    g.get("parse_success", 0), g.get("total_groups", 0),
                    au.get("duration_s", 0),
                    a50.get("char_count", 0), a100.get("char_count", 0),
                    au.get("char_count", 0),
                )

    with open(run_dir / "summary.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    logger.info("\nAll results saved to %s", run_dir)


if __name__ == "__main__":
    main()
