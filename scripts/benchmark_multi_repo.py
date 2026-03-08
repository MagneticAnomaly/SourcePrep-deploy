#!/usr/bin/env -S /Volumes/4TB-BAD/HumanAI/CoDRAG/.venv/bin/python
"""Multi-repo large-context benchmark.

Runs Atlas, Group Reasoning, and Audit on multiple repos with
6 model configs. Uses dynamic num_predict from Phase 46 research.

Repos:
  - TEST2: React website (~210 files, has .codrag)
  - TEST3: React Native (~196 code files, has .codrag)
  - HomeColab: iOS Swift app (~1100 files, needs trace build)

Models:
  1. qwen3.5:35b-a3b Q4 no-think
  2. qwen3.5:35b-a3b Q4 think
  3. qwen3.5:35b-a3b-q8_0 no-think
  4. qwen3.5:35b-a3b-q8_0 think
  5. qwen3.5:122b-a10b no-think
  6. qwen3.5:122b-a10b think

Usage:
    .venv/bin/python scripts/benchmark_multi_repo.py [--repos test2,test3,homecolab] [--only-config N]
"""

import argparse
import json
import hashlib
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OLLAMA_URL = "http://127.0.0.1:11434"
RESULTS_BASE = PROJECT_ROOT / "results"

REPOS = {
    "test2": {
        "path": PROJECT_ROOT / "TEST2",
        "index": PROJECT_ROOT / "TEST2" / ".codrag",
        "name": "TEST2 (React Website)",
        "needs_build": False,
    },
    "test3": {
        "path": PROJECT_ROOT / "TEST3",
        "index": PROJECT_ROOT / "TEST3" / ".codrag",
        "name": "TEST3 (React Native)",
        "needs_build": False,
    },
    "homecolab": {
        "path": Path("/Volumes/Thunderbolt/XcodeProjects/HomeColab"),
        "index": Path("/Volumes/Thunderbolt/XcodeProjects/HomeColab/.codrag"),
        "name": "HomeColab (iOS Swift)",
        "needs_build": True,
        "exclude_globs": [
            "**/.git/**", "**/Pods/**", "**/DerivedData/**", "**/build/**",
            "**/.build/**",  # SPM build artifacts (26K files)
            "**/xcuserdata/**", "**/Legacy_Backups*/**", "**/backups/**",
            "**/node_modules/**", "**/data/**",
        ],
    },
}

# Phase 46 finding: think mode is counterproductive for prose tasks
# (Atlas, Audit) but genuinely helps for structured JSON (Group Reasoning).
# Each config specifies think separately for prose vs structured tasks.
CONFIGS = [
    {"id": "35b-q4",  "model": "qwen3.5:35b-a3b",     "think_prose": False, "think_structured": False, "timeout": 300.0},
    {"id": "35b-q4-grthink", "model": "qwen3.5:35b-a3b", "think_prose": False, "think_structured": True, "timeout": 600.0},
    {"id": "35b-q8",  "model": "qwen3.5:35b-a3b-q8_0", "think_prose": False, "think_structured": False, "timeout": 300.0},
    {"id": "35b-q8-grthink", "model": "qwen3.5:35b-a3b-q8_0", "think_prose": False, "think_structured": True, "timeout": 600.0},
    {"id": "122b",    "model": "qwen3.5:122b-a10b",    "think_prose": False, "think_structured": False, "timeout": 900.0},
    {"id": "122b-grthink", "model": "qwen3.5:122b-a10b", "think_prose": False, "think_structured": True, "timeout": 900.0},
]


def setup_logging(run_dir: Path):
    fh = logging.FileHandler(run_dir / "run.log")
    sh = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(sh)
    class Flush(logging.Filter):
        def filter(self, record):
            fh.flush()
            return True
    fh.addFilter(Flush())
    return logging.getLogger("multi_repo")


def build_repo_trace(repo_info, logger):
    """Build .codrag trace for a repo that doesn't have one."""
    from codrag.core.trace.builder import build_trace
    from codrag.core.llm_client import LLMClient
    from codrag.core.augmenter import TraceAugmenter
    from codrag.core.epistemic_enrichment import EpistemicEnricher
    from codrag.core.cluster import ClusterSynthesizer

    idx = repo_info["index"]
    repo_path = repo_info["path"]
    idx.mkdir(parents=True, exist_ok=True)

    nodes_path = idx / "trace_nodes.jsonl"
    if not nodes_path.exists():
        logger.info("Building structural trace...")
        t0 = time.monotonic()
        result = build_trace(
            repo_root=repo_path, index_dir=idx,
            exclude_globs=repo_info.get("exclude_globs", []),
            max_file_bytes=500_000,
        )
        logger.info("Structural trace: %.1fs — %s", time.monotonic() - t0, result)
        if not nodes_path.exists():
            logger.error("trace_nodes.jsonl not created")
            return False
    else:
        logger.info("Structural trace exists — skipping")

    nc = sum(1 for _ in open(nodes_path))
    logger.info("Nodes: %d", nc)

    client = LLMClient(OLLAMA_URL, "qwen3.5:35b-a3b", provider="ollama", timeout=180.0)
    orig = client.generate
    def patched(*a, **kw):
        kw.setdefault("think", False)
        return orig(*a, **kw)
    client.generate = patched

    if not (idx / "trace_augmented.jsonl").exists():
        logger.info("Running augmentation...")
        t0 = time.monotonic()
        aug = TraceAugmenter(index_dir=idx, repo_root=repo_path, llm_client=client)
        r = aug.run()
        logger.info("Augmentation: %s in %.1fs", r, time.monotonic() - t0)
    else:
        logger.info("Augmentation exists — skipping")

    if not (idx / "trace_epistemic.jsonl").exists():
        logger.info("Running epistemic enrichment...")
        t0 = time.monotonic()
        enr = EpistemicEnricher(index_dir=idx, repo_root=repo_path, llm=client)
        r = enr.run()
        logger.info("Epistemic: %s in %.1fs", r, time.monotonic() - t0)
    else:
        logger.info("Epistemic exists — skipping")

    if not (idx / "trace_modules.jsonl").exists():
        logger.info("Running cluster synthesis...")
        t0 = time.monotonic()
        syn = ClusterSynthesizer(index_dir=idx, llm=client)
        r = syn.run()
        logger.info("Clustering: %s in %.1fs", r, time.monotonic() - t0)
    else:
        logger.info("Modules exist — skipping")

    return True


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
    p = index_dir / "trace_epistemic.jsonl"
    if p.exists():
        for line in open(p):
            if line.strip():
                d = json.loads(line)
                epistemic[EpistemicEntry.from_dict(d).node_id] = EpistemicEntry.from_dict(d)
    edges = []
    for fn in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
        ep = index_dir / fn
        if ep.exists():
            for line in open(ep):
                if line.strip():
                    edges.append(json.loads(line))
    groups = build_dependency_groups(epistemic, edges)
    return epistemic, edges, groups


def select_groups(groups):
    small = [g for g in groups if len(g) <= 4]
    med = [g for g in groups if 5 <= len(g) <= 10]
    large = [g for g in groups if len(g) >= 11]
    sel = []
    if small: sel.extend(small[:2])
    if med: sel.extend(med[:2])
    if large: sel.extend(large[:1])
    return sel or groups[:5]


def test_atlas(client, think, atlas_obj, modules, epistemic, graph_stats, hub_files, module_cap, logger):
    from codrag.core.atlas.prompts import ATLAS_SYSTEM, ATLAS_PROMPT
    from codrag.core.atlas.routing import compute_atlas_budget, MIN_ATLAS_CHARS

    sorted_mods = sorted(modules, key=lambda x: -x.get("file_count", 0))[:module_cap]
    fc = graph_stats.get("file_count", 0)
    budget = compute_atlas_budget(fc)
    tc = max(MIN_ATLAS_CHARS, budget)
    mc = int(tc * 1.3)

    mt = atlas_obj._format_modules(sorted_mods)
    lt = atlas_obj._format_layers(epistemic)
    st = atlas_obj._format_graph_stats(graph_stats)
    ht = atlas_obj._format_hubs(hub_files)

    system = ATLAS_SYSTEM.format(target_chars=tc, max_chars=mc)
    prompt = ATLAS_PROMPT.format(module_summaries=mt, architecture_layers=lt,
                                 graph_stats=st, hub_files=ht, target_chars=tc, max_chars=mc)

    pc = len(system) + len(prompt)
    pt = pc // 4
    # Phase 46: Dynamic num_predict
    if pt < 5000:
        np_ = 4096
    elif pt < 15000:
        np_ = 16384
    else:
        np_ = 32768

    logger.info("  Atlas (%d mods): ~%d tok input, np=%d, think=%s", module_cap, pt, np_, think)
    t0 = time.monotonic()
    try:
        text, tokens = client.generate(prompt, system=system, num_predict=np_,
                                        json_mode=False, temperature=0.3, think=think)
        dur = time.monotonic() - t0
        content = text
        if "<think>" in content:
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        logger.info("    → %d chars, %d tokens, %.1fs", len(content), tokens, dur)
        return {"status": "success", "duration_s": round(dur, 1), "tokens": tokens,
                "prompt_chars": pc, "module_cap": module_cap, "content": content,
                "char_count": len(content), "num_predict": np_}
    except Exception as e:
        logger.error("    → FAILED: %s", e)
        return {"status": "error", "duration_s": round(time.monotonic() - t0, 1),
                "error": str(e), "prompt_chars": pc}


def test_groups(client, think, epistemic, edges, groups, logger):
    from codrag.core.group_reasoning import GROUP_REASONING_SYSTEM, GROUP_REASONING_PROMPT, GroupReasoningEngine
    from codrag.core.llm_client import _parse_json_response

    engine = GroupReasoningEngine.__new__(GroupReasoningEngine)
    engine.llm = client
    np_ = 8192
    results = []
    total_dur = 0.0

    for i, members in enumerate(groups):
        gid = hashlib.md5("|".join(sorted(members)).encode()).hexdigest()[:10]
        md = engine._build_member_details(members, epistemic)
        ie = engine._build_internal_edges(members, edges)
        prompt = GROUP_REASONING_PROMPT.format(file_count=len(members), member_details=md, internal_edges=ie)
        pc = len(GROUP_REASONING_SYSTEM) + len(prompt)
        logger.info("  Group %d/%d (%d files, ~%d tok)", i+1, len(groups), len(members), pc//4)

        t0 = time.monotonic()
        try:
            text, tokens = client.generate(prompt, system=GROUP_REASONING_SYSTEM,
                                            num_predict=np_, json_mode=False, think=think, temperature=0.6)
            dur = time.monotonic() - t0
            total_dur += dur
            parsed = _parse_json_response(text)
            pattern = (parsed or {}).get("pattern", "FAIL")
            logger.info("    → %s, %.1fs", pattern[:50], dur)
            results.append({"group_id": gid, "member_count": len(members),
                           "duration_s": round(dur, 1), "tokens": tokens,
                           "parsed_ok": parsed is not None,
                           "pattern": (parsed or {}).get("pattern", ""),
                           "coupling_risks": len((parsed or {}).get("coupling_risks", [])),
                           "confidence": (parsed or {}).get("confidence", 0),
                           "architectural_insight": ((parsed or {}).get("architectural_insight", "") or "")[:300]})
        except Exception as e:
            dur = time.monotonic() - t0
            total_dur += dur
            logger.error("    → FAILED: %s", e)
            results.append({"group_id": gid, "member_count": len(members),
                           "duration_s": round(dur, 1), "error": str(e), "parsed_ok": False})

    ok = sum(1 for r in results if r.get("parsed_ok"))
    return {"total_groups": len(groups), "parse_success": ok,
            "total_duration_s": round(total_dur, 1), "groups": results}


def test_audit(client, think, index_dir, repo_name, logger):
    from codrag.core.audit.prompts import AUDIT_SUMMARY_SYSTEM, AUDIT_SUMMARY_PROMPT

    atlas_content = ""
    ap = index_dir / "atlas.json"
    if ap.exists():
        try: atlas_content = json.load(open(ap)).get("content", "")[:3000]
        except: pass

    modules = []
    mp = index_dir / "trace_modules.jsonl"
    if mp.exists():
        for line in open(mp):
            if line.strip(): modules.append(json.loads(line))

    findings = []
    ep = index_dir / "trace_epistemic.jsonl"
    if ep.exists():
        for line in open(ep):
            if line.strip():
                d = json.loads(line)
                for debt in d.get("tech_debt", [])[:1]:
                    findings.append(f"- WARNING: {d.get('node_id','').replace('file:','')}: {debt}")

    ft = "\n".join(findings[:40]) or "(no findings)"
    nc = sum(1 for _ in open(index_dir / "trace_nodes.jsonl")) if (index_dir / "trace_nodes.jsonl").exists() else 0
    ec = sum(1 for _ in open(index_dir / "trace_edges.jsonl")) if (index_dir / "trace_edges.jsonl").exists() else 0

    prompt = AUDIT_SUMMARY_PROMPT.format(
        project_name=repo_name, file_count=nc, node_count=nc, edge_count=ec,
        module_count=len(modules), atlas_content=atlas_content or "(no atlas)",
        finding_count=len(findings), critical_count=0,
        warning_count=len(findings), findings_formatted=ft)

    pc = len(AUDIT_SUMMARY_SYSTEM) + len(prompt)
    np_ = 16384
    logger.info("  Audit: ~%d tok input, np=%d, think=%s", pc//4, np_, think)

    t0 = time.monotonic()
    try:
        text, tokens = client.generate(prompt=prompt, system=AUDIT_SUMMARY_SYSTEM,
                                        json_mode=False, temperature=0.3, num_predict=np_, think=think)
        dur = time.monotonic() - t0
        content = text
        if "<think>" in content:
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        logger.info("    → %d chars, %.1fs", len(content), dur)
        return {"status": "success", "duration_s": round(dur, 1), "tokens": tokens,
                "content": content, "char_count": len(content)}
    except Exception as e:
        logger.error("    → FAILED: %s", e)
        return {"status": "error", "duration_s": round(time.monotonic() - t0, 1), "error": str(e)}


def run_repo(repo_key, repo_info, configs, run_dir, logger):
    idx = repo_info["index"]
    logger.info("Loading %s data...", repo_info["name"])

    atlas_obj, modules, epistemic_summary, graph_stats, hub_files = load_atlas_data(idx)
    epi_entries, edges, all_groups = load_group_data(idx)
    rep_groups = select_groups(all_groups)

    mc = min(len(modules), 100)
    logger.info("  %d modules (cap %d), %d groups (%d selected), %d files",
                len(modules), mc, len(all_groups), len(rep_groups), graph_stats.get("file_count", 0))

    from codrag.core.llm_client import LLMClient
    results = {}

    for ci, cfg in enumerate(configs):
        logger.info("")
        think_prose = cfg.get("think_prose", False)
        think_gr = cfg.get("think_structured", False)
        label = f"{cfg['model']} prose={'think' if think_prose else 'no-think'} GR={'think' if think_gr else 'no-think'}"
        logger.info("--- %s | Config %d/%d: %s ---", repo_key, ci+1, len(configs), label)

        client = LLMClient(OLLAMA_URL, cfg["model"], provider="ollama", timeout=cfg["timeout"])

        # Pre-flight
        try:
            t0 = time.monotonic()
            client.generate('{"ok":true}', num_predict=20, think=think_gr)
            logger.info("  Pre-flight OK (%.1fs)", time.monotonic() - t0)
        except Exception as e:
            logger.error("  Pre-flight FAILED: %s — skipping", e)
            results[cfg["id"]] = {"status": "preflight_failed", "error": str(e)}
            continue

        cr = {}
        cr["atlas"] = test_atlas(client, think_prose, atlas_obj, modules, epistemic_summary,
                                  graph_stats, hub_files, mc, logger)
        cr["group_reasoning"] = test_groups(client, think_gr, epi_entries, edges, rep_groups, logger)
        cr["audit"] = test_audit(client, think_prose, idx, repo_info["name"], logger)

        # Save
        cd = run_dir / repo_key / cfg["id"]
        cd.mkdir(parents=True, exist_ok=True)
        with open(cd / "result.json", "w") as f:
            json.dump(cr, f, indent=2, default=str)
        if cr["atlas"].get("content"):
            with open(cd / "atlas_output.txt", "w") as f:
                f.write(cr["atlas"]["content"])
        if cr["audit"].get("content"):
            with open(cd / "audit_output.md", "w") as f:
                f.write(cr["audit"]["content"])
        if cr["group_reasoning"].get("groups"):
            with open(cd / "groups.json", "w") as f:
                json.dump(cr["group_reasoning"]["groups"], f, indent=2, default=str)

        results[cfg["id"]] = cr
        logger.info("  Saved %s/%s", repo_key, cfg["id"])

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", default="test2,test3,homecolab",
                        help="Comma-separated repo keys to test")
    parser.add_argument("--only-config", type=int, help="Run only config N (1-indexed)")
    args = parser.parse_args()

    repo_keys = [r.strip() for r in args.repos.split(",")]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_BASE / f"multi_repo_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(run_dir)
    logger.info("=" * 60)
    logger.info("  MULTI-REPO LARGE-CONTEXT BENCHMARK")
    logger.info("  Repos: %s", ", ".join(repo_keys))
    logger.info("  Results: %s", run_dir)
    logger.info("=" * 60)

    configs = CONFIGS
    if args.only_config:
        idx = args.only_config - 1
        if 0 <= idx < len(CONFIGS):
            configs = [CONFIGS[idx]]

    all_results = {}
    overall_t0 = time.monotonic()

    for rk in repo_keys:
        if rk not in REPOS:
            logger.error("Unknown repo: %s", rk)
            continue
        ri = REPOS[rk]
        logger.info("")
        logger.info("=" * 60)
        logger.info("  REPO: %s", ri["name"])
        logger.info("=" * 60)

        # Build trace if needed
        if ri.get("needs_build") and not (ri["index"] / "trace_epistemic.jsonl").exists():
            logger.info("Building trace for %s...", ri["name"])
            ok = build_repo_trace(ri, logger)
            if not ok:
                logger.error("Trace build failed — skipping %s", rk)
                continue

        if not (ri["index"] / "trace_epistemic.jsonl").exists():
            logger.error("No epistemic data for %s — skipping", rk)
            continue

        all_results[rk] = run_repo(rk, ri, configs, run_dir, logger)

    total = time.monotonic() - overall_t0
    logger.info("")
    logger.info("=" * 60)
    logger.info("  COMPLETE: %.1f min", total / 60)
    logger.info("=" * 60)

    # Summary table
    for rk, rdata in all_results.items():
        logger.info("")
        logger.info("--- %s ---", rk)
        logger.info("%-20s %7s %7s %7s %5s %5s", "Config", "Atlas", "GR", "Audit", "A#", "Au#")
        for cid, cr in rdata.items():
            if not isinstance(cr, dict) or "atlas" not in cr:
                continue
            a = cr.get("atlas", {})
            g = cr.get("group_reasoning", {})
            au = cr.get("audit", {})
            logger.info("%-20s %6.0fs %6.0fs %6.0fs %5d %5d",
                        cid, a.get("duration_s", 0), g.get("total_duration_s", 0),
                        au.get("duration_s", 0), a.get("char_count", 0), au.get("char_count", 0))

    with open(run_dir / "summary.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    logger.info("\nSaved to %s", run_dir)


if __name__ == "__main__":
    main()
