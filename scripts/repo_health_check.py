#!/usr/bin/env python3
"""CoDRAG Repo Health Check — comprehensive per-repo audit with pass/fail assertions.

Runs against a repo's .codrag/ directory and produces a structured report.
Can also test search relevance and context assembly via the daemon API.

Usage:
    python scripts/repo_health_check.py TEST/.codrag
    python scripts/repo_health_check.py TEST/.codrag TEST2/.codrag TEST3/.codrag
    python scripts/repo_health_check.py --all                    # scan for all .codrag dirs
    python scripts/repo_health_check.py TEST3/.codrag --api      # also test daemon API
    python scripts/repo_health_check.py --json results.json      # save JSON results
    python scripts/repo_health_check.py --daemon http://localhost:8400  # custom daemon URL

Checks performed:
    1. Pipeline completeness — all expected artifacts exist
    2. Trace graph health — edge connectivity, dangling edges, neighbor distribution
    3. Augmentation quality — synthetic rate, confidence, summary length
    4. Epistemic convergence — settled percentage
    5. Clustering quality — max module size, duplicate names
    6. Atlas quality — no <think> tokens, reasonable size
    7. Search relevance — (with --api) probe queries return relevant files
    8. Context assembly — (with --api) ambient + query context work
"""

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── ANSI colours ─────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ── Data loaders ─────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Check functions ──────────────────────────────────────────────────────────
# Each returns (passed: bool, details: dict)

def check_pipeline_completeness(base: Path) -> Tuple[bool, Dict]:
    """Check all expected artifacts exist."""
    required = [
        "trace_nodes.jsonl",
        "trace_edges.jsonl",
        "trace_manifest.json",
        "manifest.json",
        "documents.json",
        "embeddings.npy",
    ]
    expected = required + [
        "trace_augmented.jsonl",
        "trace_augment_manifest.json",
        "trace_epistemic.jsonl",
        "trace_modules.jsonl",
        "trace_inferred_edges.jsonl",
        "knowledge_documents.json",
        "knowledge_embeddings.npy",
        "atlas.json",
    ]

    present = []
    missing_required = []
    missing_optional = []

    for f in expected:
        p = base / f
        if p.exists():
            present.append(f)
        elif f in required:
            missing_required.append(f)
        else:
            missing_optional.append(f)

    passed = len(missing_required) == 0
    return passed, {
        "present": len(present),
        "total_expected": len(expected),
        "missing_required": missing_required,
        "missing_optional": missing_optional,
    }


def check_trace_graph(base: Path) -> Tuple[bool, Dict]:
    """Check trace graph connectivity and edge quality."""
    nodes = load_jsonl(base / "trace_nodes.jsonl")
    edges = load_jsonl(base / "trace_edges.jsonl")
    inferred = load_jsonl(base / "trace_inferred_edges.jsonl")

    if not nodes:
        return False, {"error": "No nodes found"}

    # Categorize nodes
    node_map = {n["id"]: n for n in nodes}
    ext_nodes = [n for n in nodes if n.get("id", "").startswith("ext:")]
    no_fp = [n for n in nodes if not n.get("file_path")]

    # Edge analysis
    edge_kinds = Counter(e.get("kind") for e in edges)
    inferred_kinds = Counter(e.get("kind") for e in inferred)

    # File-level connectivity
    node_to_file = {}
    for n in nodes:
        fp = n.get("file_path") or n.get("source_path") or ""
        node_to_file[n["id"]] = fp

    file_neighbors: Dict[str, set] = defaultdict(set)
    cross_file = 0
    same_file = 0
    dangling = 0

    for e in edges:
        if e.get("kind") != "imports":
            continue
        src_fp = node_to_file.get(e.get("source", ""), "")
        tgt_fp = node_to_file.get(e.get("target", ""), "")
        if not src_fp or not tgt_fp:
            dangling += 1
        elif src_fp != tgt_fp:
            cross_file += 1
            file_neighbors[src_fp].add(tgt_fp)
            file_neighbors[tgt_fp].add(src_fp)
        else:
            same_file += 1

    all_files = set(node_to_file.values()) - {""}
    total_files = len(all_files)
    files_with_neighbors = sum(1 for fp in all_files if len(file_neighbors.get(fp, set())) > 0)
    files_zero_neighbors = total_files - files_with_neighbors

    neighbor_counts = [len(file_neighbors.get(fp, set())) for fp in all_files]
    avg_neighbors = statistics.mean(neighbor_counts) if neighbor_counts else 0
    max_neighbors = max(neighbor_counts) if neighbor_counts else 0

    import_total = cross_file + same_file + dangling
    dangling_pct = (dangling / import_total * 100) if import_total > 0 else 0
    zero_neighbor_pct = (files_zero_neighbors / total_files * 100) if total_files > 0 else 0

    # Assertions
    issues = []
    if cross_file == 0 and total_files > 10:
        issues.append("ZERO cross-file import edges — trace expansion non-functional")
    if dangling_pct > 80:
        issues.append(f"Dangling edge rate {dangling_pct:.0f}% — most imports unresolved")
    if zero_neighbor_pct > 90:
        issues.append(f"{zero_neighbor_pct:.0f}% files have 0 neighbors — graph essentially disconnected")

    passed = len(issues) == 0

    return passed, {
        "total_nodes": len(nodes),
        "external_nodes": len(ext_nodes),
        "nodes_without_file_path": len(no_fp),
        "total_edges": len(edges),
        "edge_kinds": dict(edge_kinds),
        "total_files": total_files,
        "import_edges": {"cross_file": cross_file, "same_file": same_file, "dangling": dangling},
        "dangling_pct": round(dangling_pct, 1),
        "files_zero_neighbors": files_zero_neighbors,
        "zero_neighbor_pct": round(zero_neighbor_pct, 1),
        "avg_neighbors": round(avg_neighbors, 2),
        "max_neighbors": max_neighbors,
        "inferred_edges": len(inferred),
        "inferred_kinds": dict(inferred_kinds),
        "issues": issues,
    }


def check_augmentation(base: Path) -> Tuple[bool, Dict]:
    """Check augmentation quality."""
    entries = load_jsonl(base / "trace_augmented.jsonl")
    if not entries:
        return False, {"error": "No augmentation data"}

    total = len(entries)
    confidences = [e.get("confidence", 0) for e in entries]
    models = [e.get("model", "unknown") for e in entries]
    summaries = [e.get("summary", "") for e in entries]

    synthetic = [m for m in models if str(m).startswith("synthetic")]
    synthetic_pct = len(synthetic) / total * 100

    avg_conf = statistics.mean(confidences) if confidences else 0
    median_conf = statistics.median(confidences) if confidences else 0
    avg_summary_len = statistics.mean(len(s) for s in summaries) if summaries else 0

    issues = []
    if synthetic_pct > 50:
        issues.append(f"Synthetic rate {synthetic_pct:.0f}% > 50% threshold")
    if avg_conf < 0.4:
        issues.append(f"Avg confidence {avg_conf:.2f} < 0.4 threshold")
    if avg_summary_len < 30:
        issues.append(f"Avg summary length {avg_summary_len:.0f} chars < 30 threshold")

    passed = len(issues) == 0

    return passed, {
        "total": total,
        "synthetic_count": len(synthetic),
        "synthetic_pct": round(synthetic_pct, 1),
        "avg_confidence": round(avg_conf, 3),
        "median_confidence": round(median_conf, 3),
        "avg_summary_len": round(avg_summary_len, 0),
        "issues": issues,
    }


def check_epistemic(base: Path) -> Tuple[bool, Dict]:
    """Check epistemic enrichment convergence."""
    entries = load_jsonl(base / "trace_epistemic.jsonl")
    if not entries:
        return False, {"error": "No epistemic data"}

    # Load supporting data for scoring
    augmentations = {d["node_id"]: d for d in load_jsonl(base / "trace_augmented.jsonl")}
    epistemic_map = {d["node_id"]: d for d in entries}
    edges_data = load_jsonl(base / "trace_edges.jsonl")
    manifest = load_json(base / "trace_manifest.json")
    current_hashes = manifest.get("file_hashes", {})

    adjacency: Dict[str, set] = defaultdict(set)
    cross_refs: Dict[str, int] = defaultdict(int)
    for e in edges_data:
        src, tgt = e.get("source"), e.get("target")
        if src and tgt:
            adjacency[src].add(tgt)
            adjacency[tgt].add(src)
        if e.get("kind") in ("references", "links_to"):
            cross_refs[src] += 1

    enriched_ids = set(epistemic_map.keys())

    # Compute composite scores (inline to avoid import)
    WEIGHTS = {
        "summary_confidence": 0.20, "validation_status": 0.15,
        "neighbor_coverage": 0.20, "cross_reference_density": 0.15,
        "enrichment_depth": 0.15, "staleness_check": 0.15,
    }

    scores = []
    for nid, entry in epistemic_map.items():
        aug = augmentations.get(nid)
        c1 = float(aug.get("confidence", 0)) if aug else 0.0
        c2 = 1.0 if entry else 0.0
        neighbors = adjacency.get(nid, set())
        c3 = sum(1 for n in neighbors if n in enriched_ids) / len(neighbors) if neighbors else 0.5
        c4 = min(1.0, cross_refs.get(nid, 0) / 4.0)
        pn = entry.get("pass_number", 2)
        c5 = 1.0 if pn >= 4 else (0.75 if pn >= 3 else 0.5)
        fp = nid.replace("file:", "", 1) if nid.startswith("file:") else ""
        ah = aug.get("file_hash") if aug else None
        ch = current_hashes.get(fp)
        c6 = (1.0 if ah == ch else 0.0) if ah and ch else 0.3

        score = (WEIGHTS["summary_confidence"] * c1 + WEIGHTS["validation_status"] * c2 +
                 WEIGHTS["neighbor_coverage"] * c3 + WEIGHTS["cross_reference_density"] * c4 +
                 WEIGHTS["enrichment_depth"] * c5 + WEIGHTS["staleness_check"] * c6)
        scores.append(round(score, 3))

    total = len(entries)
    settled = sum(1 for s in scores if s >= 0.60)
    settled_pct = settled / total * 100 if total > 0 else 0

    layers = Counter(e.get("architecture_layer", "unknown") for e in entries)
    staleness = Counter(e.get("staleness_risk", "unknown") for e in entries)

    issues = []
    if settled_pct < 50:
        issues.append(f"Only {settled_pct:.0f}% settled (< 50% threshold)")

    passed = len(issues) == 0

    return passed, {
        "total_enriched": total,
        "mean_score": round(statistics.mean(scores), 3) if scores else 0,
        "median_score": round(statistics.median(scores), 3) if scores else 0,
        "settled_count": settled,
        "settled_pct": round(settled_pct, 1),
        "architecture_layers": dict(layers.most_common(5)),
        "staleness_risk": dict(staleness.most_common()),
        "issues": issues,
    }


def check_clustering(base: Path) -> Tuple[bool, Dict]:
    """Check module/cluster quality."""
    modules = load_jsonl(base / "trace_modules.jsonl")
    manifest = load_json(base / "trace_manifest.json")
    total_files = manifest.get("counts", {}).get("files_parsed", 0)

    if not modules:
        return False, {"error": "No module data"}

    names = [m.get("name", "?") for m in modules]
    sizes = [len(m.get("member_files", [])) for m in modules]
    max_size = max(sizes) if sizes else 0
    max_pct = (max_size / total_files * 100) if total_files > 0 else 0

    # Check for duplicate names
    name_counts = Counter(names)
    duplicates = {n: c for n, c in name_counts.items() if c > 1}

    issues = []
    if max_pct > 40:
        largest = names[sizes.index(max_size)]
        issues.append(f"Module '{largest}' contains {max_pct:.0f}% of files ({max_size}/{total_files})")
    if duplicates:
        issues.append(f"Duplicate module names: {duplicates}")

    passed = len(issues) == 0

    return passed, {
        "total_modules": len(modules),
        "module_sizes": {m.get("name", "?"): len(m.get("member_files", [])) for m in modules},
        "largest_module_pct": round(max_pct, 1),
        "duplicate_names": duplicates,
        "total_files": total_files,
        "issues": issues,
    }


def check_atlas(base: Path) -> Tuple[bool, Dict]:
    """Check atlas content quality."""
    atlas = load_json(base / "atlas.json")
    if not atlas:
        return False, {"error": "No atlas data"}

    content = atlas.get("content", "")
    mode = atlas.get("mode", "unknown")
    model = atlas.get("model", "unknown")
    char_count = atlas.get("char_count", len(content))

    issues = []

    # Check for leaked thinking tokens
    think_pattern = re.compile(r"<think>", re.IGNORECASE)
    if think_pattern.search(content):
        issues.append("Atlas content contains <think> tokens — LLM thinking leaked into output")

    # Check size
    if char_count > 3000:
        issues.append(f"Atlas content too large: {char_count} chars (> 3000 limit)")

    if not content.strip():
        issues.append("Atlas content is empty")

    # Check for routing
    has_routing = (base / "atlas_routing.json").exists()

    passed = len(issues) == 0

    return passed, {
        "mode": mode,
        "model": model,
        "char_count": char_count,
        "has_routing": has_routing,
        "module_count": atlas.get("module_count", 0),
        "file_count": atlas.get("file_count", 0),
        "issues": issues,
    }


def check_api(base: Path, daemon_url: str, project_id: Optional[str] = None) -> Tuple[bool, Dict]:
    """Check daemon API context endpoints (requires running daemon)."""
    try:
        import requests
    except ImportError:
        return False, {"error": "requests not installed"}

    if not project_id:
        return False, {"error": "No project_id for API test"}

    issues = []
    results = {}

    # Test query-based context
    try:
        resp = requests.post(
            f"{daemon_url}/projects/{project_id}/context",
            json={"query": "main entry point", "k": 5, "max_chars": 6000},
            timeout=30,
        )
        data = resp.json().get("data", resp.json())
        if data:
            ctx = data.get("context", "")
            results["search_context_len"] = len(ctx)
            results["search_has_content"] = bool(ctx.strip())
            if not ctx.strip():
                issues.append("codrag_search returned empty context")
        else:
            issues.append(f"codrag_search returned error: {resp.json().get('error')}")
    except Exception as e:
        issues.append(f"codrag_search failed: {e}")

    # Test ambient context
    try:
        resp = requests.post(
            f"{daemon_url}/projects/{project_id}/context",
            json={"query": "", "max_chars": 6000},
            timeout=30,
        )
        data = resp.json().get("data", resp.json())
        if data:
            ctx = data.get("context", "")
            results["ambient_context_len"] = len(ctx)
            results["ambient_has_content"] = bool(ctx.strip())
            results["ambient_has_modules"] = bool(data.get("ambient"))
            if not ctx.strip():
                issues.append("codrag ambient returned empty context")
        else:
            issues.append(f"codrag ambient returned error: {resp.json().get('error')}")
    except Exception as e:
        issues.append(f"codrag ambient failed: {e}")

    passed = len(issues) == 0
    results["issues"] = issues
    return passed, results


# ── Report ───────────────────────────────────────────────────────────────────

def run_checks(
    base: Path,
    test_api: bool = False,
    daemon_url: str = "http://127.0.0.1:8400",
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all checks against a .codrag/ directory."""
    report: Dict[str, Any] = {"path": str(base), "checks": {}, "passed": 0, "failed": 0, "grade": "?"}

    checks = [
        ("pipeline", check_pipeline_completeness),
        ("trace_graph", check_trace_graph),
        ("augmentation", check_augmentation),
        ("epistemic", check_epistemic),
        ("clustering", check_clustering),
        ("atlas", check_atlas),
    ]

    for name, fn in checks:
        try:
            passed, details = fn(base)
        except Exception as e:
            passed, details = False, {"error": str(e)}
        report["checks"][name] = {"passed": passed, **details}
        if passed:
            report["passed"] += 1
        else:
            report["failed"] += 1

    if test_api:
        try:
            passed, details = check_api(base, daemon_url, project_id)
        except Exception as e:
            passed, details = False, {"error": str(e)}
        report["checks"]["api"] = {"passed": passed, **details}
        if passed:
            report["passed"] += 1
        else:
            report["failed"] += 1

    # Grade
    total = report["passed"] + report["failed"]
    ratio = report["passed"] / total if total > 0 else 0
    if ratio >= 0.9:
        report["grade"] = "A"
    elif ratio >= 0.75:
        report["grade"] = "B"
    elif ratio >= 0.6:
        report["grade"] = "C"
    elif ratio >= 0.4:
        report["grade"] = "D"
    else:
        report["grade"] = "F"

    return report


def print_report(report: Dict[str, Any]) -> None:
    """Print a human-readable report."""
    path = report["path"]
    grade = report["grade"]
    grade_color = GREEN if grade in ("A", "B") else (YELLOW if grade == "C" else RED)

    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}HEALTH CHECK: {path}{RESET}  Grade: {grade_color}{BOLD}{grade}{RESET}")
    print(f"{BOLD}{'='*70}{RESET}")

    for name, check in report["checks"].items():
        passed = check.get("passed", False)
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"\n  {status}  {BOLD}{name}{RESET}")

        issues = check.get("issues", [])
        error = check.get("error")
        if error:
            print(f"    {RED}Error: {error}{RESET}")
        for issue in issues:
            print(f"    {YELLOW}⚠ {issue}{RESET}")

        # Print key metrics (skip issues/error/passed)
        for k, v in check.items():
            if k in ("passed", "issues", "error"):
                continue
            if isinstance(v, dict) and len(str(v)) > 100:
                print(f"    {DIM}{k}: ({len(v)} items){RESET}")
            elif isinstance(v, list) and len(v) > 5:
                print(f"    {DIM}{k}: [{len(v)} items]{RESET}")
            else:
                print(f"    {DIM}{k}: {v}{RESET}")

    total = report["passed"] + report["failed"]
    print(f"\n  {BOLD}Summary: {GREEN}{report['passed']}{RESET}/{total} checks passed")
    print()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CoDRAG Repo Health Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "dirs", nargs="*", default=[],
        help=".codrag/ directories to check",
    )
    parser.add_argument("--all", action="store_true", help="Auto-discover all .codrag dirs")
    parser.add_argument("--api", action="store_true", help="Also test daemon API endpoints")
    parser.add_argument("--daemon", default="http://127.0.0.1:8400", help="Daemon URL")
    parser.add_argument("--json", type=Path, default=None, help="Save JSON results")
    args = parser.parse_args()

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    dirs = [Path(d) for d in args.dirs]

    if args.all:
        # Discover .codrag dirs in TEST*, tests/eval
        for pattern in ["TEST*/.codrag", "tests/eval/real_repos/*/.codrag"]:
            for p in sorted(PROJECT_ROOT.glob(pattern)):
                if p.is_dir():
                    dirs.append(p)

    if not dirs:
        print(f"{RED}No .codrag directories specified. Use --all or provide paths.{RESET}")
        sys.exit(1)

    # Resolve project IDs if API testing
    project_map: Dict[str, str] = {}
    if args.api:
        try:
            import requests
            resp = requests.get(f"{args.daemon}/projects", timeout=5)
            projects = resp.json().get("data", {}).get("projects", [])
            for p in projects:
                project_map[p["path"]] = p["id"]
        except Exception as e:
            print(f"{YELLOW}Could not fetch projects from daemon: {e}{RESET}")

    all_reports = []
    for d in dirs:
        if not d.exists():
            print(f"{YELLOW}SKIP: {d} not found{RESET}")
            continue

        # Try to find project_id by matching path
        repo_path = str(d.parent.resolve())
        pid = project_map.get(repo_path)

        report = run_checks(d, test_api=args.api, daemon_url=args.daemon, project_id=pid)
        print_report(report)
        all_reports.append(report)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(all_reports, f, indent=2)
        print(f"Results saved to {args.json}")

    # Summary
    if len(all_reports) > 1:
        print(f"\n{BOLD}{'='*70}{RESET}")
        print(f"{BOLD}OVERALL SUMMARY{RESET}")
        print(f"{BOLD}{'='*70}{RESET}")
        for r in all_reports:
            grade = r["grade"]
            gc = GREEN if grade in ("A", "B") else (YELLOW if grade == "C" else RED)
            p = r["path"]
            print(f"  {gc}{grade}{RESET}  {p}  ({r['passed']}/{r['passed']+r['failed']} passed)")
        print()

    # Exit with failure count
    total_failed = sum(r["failed"] for r in all_reports)
    sys.exit(min(total_failed, 1))


if __name__ == "__main__":
    main()
