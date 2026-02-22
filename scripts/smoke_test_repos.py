#!/usr/bin/env python3
"""Smoke test orchestrator — runs CoDRAG CodeIndex build+search across all
small/medium repos simultaneously, up to --workers at a time.

For each repo:
  1. Wipe .codrag/smoke/ (or entire .codrag/ with --clear-all)
  2. Build CodeIndex with NativeEmbedder (ONNX, CPU)
  3. Fire 1 probe query — verify search_hits > 0 and top_score > 0.05
  4. Report PASS / FAIL + chunks, build_time, top_score

Usage:
    python scripts/smoke_test_repos.py                       # all repos, 3 concurrent
    python scripts/smoke_test_repos.py --workers 5           # override concurrency
    python scripts/smoke_test_repos.py --filter real         # only real_repos
    python scripts/smoke_test_repos.py --filter sample       # only sample_repos
    python scripts/smoke_test_repos.py --clear-all           # wipe entire .codrag/
    python scripts/smoke_test_repos.py --keep                # keep .codrag/smoke/ after
    python scripts/smoke_test_repos.py --timeout 300         # per-repo timeout seconds
    python scripts/smoke_test_repos.py --output results.json # save JSON summary
"""

import argparse
import json
import shutil
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# ── ANSI colours ─────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

_PRINT_LOCK = threading.Lock()

def _log(*args, **kwargs):
    with _PRINT_LOCK:
        print(*args, **kwargs, flush=True)


# ── Repo catalogue ────────────────────────────────────────────────────────────
#
# Ordered smallest → largest for faster early feedback.
# max_files_hint is informational only (not enforced at runtime).

REAL_REPOS: List[Dict[str, Any]] = [
    {
        "name": "mini-redis-rust",
        "rel_path": "tests/eval/real_repos/mini-redis-rust",
        "lang": "Rust",
        "probe": "TCP connection server accept listen",
    },
    {
        "name": "cobra-go",
        "rel_path": "tests/eval/real_repos/cobra-go",
        "lang": "Go",
        "probe": "command root execute run",
    },
    {
        "name": "chi-go",
        "rel_path": "tests/eval/real_repos/chi-go",
        "lang": "Go",
        "probe": "router middleware handler HTTP request",
    },
    {
        "name": "hanami-ruby",
        "rel_path": "tests/eval/real_repos/hanami-ruby",
        "lang": "Ruby",
        "probe": "application framework router action",
    },
    {
        "name": "got-typescript",
        "rel_path": "tests/eval/real_repos/got-typescript",
        "lang": "TypeScript",
        "probe": "HTTP request options response headers",
    },
    {
        "name": "gin-go",
        "rel_path": "tests/eval/real_repos/gin-go",
        "lang": "Go",
        "probe": "HTTP engine router context handler",
    },
    {
        "name": "slim-php",
        "rel_path": "tests/eval/real_repos/slim-php",
        "lang": "PHP",
        "probe": "request response middleware route",
    },
    {
        "name": "click-python",
        "rel_path": "tests/eval/real_repos/click-python",
        "lang": "Python",
        "probe": "command decorator CLI option parameter",
    },
    {
        "name": "spark-java",
        "rel_path": "tests/eval/real_repos/spark-java",
        "lang": "Java",
        "probe": "HTTP route handler request response",
    },
    {
        "name": "ripgrep-rust",
        "rel_path": "tests/eval/real_repos/ripgrep-rust",
        "lang": "Rust",
        "probe": "search pattern regex match grep",
    },
    {
        "name": "cjson-c",
        "rel_path": "tests/eval/real_repos/cjson-c",
        "lang": "C",
        "probe": "JSON parse object string value",
    },
    {
        "name": "gson-java",
        "rel_path": "tests/eval/real_repos/gson-java",
        "lang": "Java",
        "probe": "JSON serialize deserialize object type",
    },
    {
        "name": "javalin-java",
        "rel_path": "tests/eval/real_repos/javalin-java",
        "lang": "Java",
        "probe": "HTTP server route context handler",
    },
    {
        "name": "alamofire-swift",
        "rel_path": "tests/eval/real_repos/alamofire-swift",
        "lang": "Swift",
        "probe": "HTTP request session response handler",
    },
    {
        "name": "sqlmodel-python",
        "rel_path": "tests/eval/real_repos/sqlmodel-python",
        "lang": "Python",
        "probe": "database model field query select",
    },
    # Larger repos — included but will take longer
    {
        "name": "okhttp-kotlin",
        "rel_path": "tests/eval/real_repos/okhttp-kotlin",
        "lang": "Kotlin",
        "probe": "HTTP client request response call",
    },
    {
        "name": "bat-rust",
        "rel_path": "tests/eval/real_repos/bat-rust",
        "lang": "Rust",
        "probe": "syntax highlighting file print output",
    },
]


def _discover_sample_repos() -> List[Dict[str, Any]]:
    """Auto-discover generated sample repos."""
    base = PROJECT_ROOT / "tests" / "eval" / "sample_repos" / "generated"
    if not base.exists():
        return []
    repos = []
    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        lang = d.name.replace("_repo", "").capitalize()
        repos.append({
            "name": f"sample-{d.name}",
            "rel_path": str(d.relative_to(PROJECT_ROOT)),
            "lang": lang,
            "probe": "main function class module",
        })
    return repos


# ── Core smoke runner (one repo) ──────────────────────────────────────────────

def smoke_one(
    repo: Dict[str, Any],
    keep: bool = False,
    clear_all: bool = False,
) -> Dict[str, Any]:
    """Run a single smoke test. Thread-safe — no shared mutable state."""
    from codrag.core import CodeIndex, NativeEmbedder

    name = repo["name"]
    rel = repo["rel_path"]
    repo_path = (PROJECT_ROOT / rel) if not Path(rel).is_absolute() else Path(rel)

    result: Dict[str, Any] = {
        "name": name,
        "lang": repo["lang"],
        "path": str(repo_path),
        "status": "SKIP",
        "chunks": 0,
        "build_time_s": 0.0,
        "search_hits": 0,
        "top_score": 0.0,
        "error": None,
    }

    if not repo_path.exists():
        result["error"] = f"Path not found: {repo_path}"
        _log(f"  {YELLOW}SKIP{RESET}  {name}  {DIM}(path not found){RESET}")
        return result

    codrag_dir = repo_path / ".codrag"
    idx_dir = codrag_dir / "smoke"

    # ── Clear data ──────────────────────────────────────────────────────────
    try:
        if clear_all and codrag_dir.exists():
            shutil.rmtree(codrag_dir)
            _log(f"  {DIM}cleared .codrag/ for {name}{RESET}")
        elif idx_dir.exists():
            shutil.rmtree(idx_dir)
    except Exception as e:
        result["error"] = f"Clear failed: {e}"
        result["status"] = "FAIL"
        _log(f"  {RED}FAIL{RESET}  {name}  {DIM}clear error: {e}{RESET}")
        return result

    # ── Build ───────────────────────────────────────────────────────────────
    try:
        t0 = time.perf_counter()
        embedder = NativeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=repo_path)
        result["build_time_s"] = round(time.perf_counter() - t0, 1)

        docs = getattr(idx, "_documents", None) or []
        result["chunks"] = len(docs)

        if result["chunks"] == 0:
            result["status"] = "FAIL"
            result["error"] = "No chunks indexed (0 documents)"
            _log(
                f"  {RED}FAIL{RESET}  {name:<28} {DIM}{result['lang']:<12}{RESET} "
                f"0 chunks  {result['build_time_s']}s  — {result['error']}"
            )
            return result
    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"Build error: {e}"
        _log(f"  {RED}FAIL{RESET}  {name:<28} {DIM}{result['lang']:<12}{RESET} build error: {e}")
        return result
    finally:
        if not keep and idx_dir.exists() and result["status"] == "FAIL":
            shutil.rmtree(idx_dir, ignore_errors=True)

    # ── Search probe ────────────────────────────────────────────────────────
    try:
        hits = idx.search(repo["probe"], k=5, min_score=0.0)
        result["search_hits"] = len(hits)
        result["top_score"] = round(float(hits[0].score), 3) if hits else 0.0

        if result["search_hits"] == 0:
            result["status"] = "FAIL"
            result["error"] = "Search returned 0 results"
        elif result["top_score"] < 0.05:
            result["status"] = "FAIL"
            result["error"] = f"Top score too low: {result['top_score']:.3f}"
        else:
            result["status"] = "PASS"
    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"Search error: {e}"

    # ── Print live result ───────────────────────────────────────────────────
    status_str = (
        f"{GREEN}PASS{RESET}" if result["status"] == "PASS"
        else f"{RED}FAIL{RESET}"
    )
    _log(
        f"  {status_str}  {name:<28} {DIM}{result['lang']:<12}{RESET} "
        f"{result['chunks']:>5} chunks  {result['build_time_s']:>6.1f}s  "
        f"score={result['top_score']:.3f}"
        + (f"  {RED}{result['error']}{RESET}" if result["error"] else "")
    )

    # ── Cleanup ─────────────────────────────────────────────────────────────
    if not keep and idx_dir.exists():
        shutil.rmtree(idx_dir, ignore_errors=True)

    return result


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_all(
    repos: List[Dict[str, Any]],
    workers: int = 3,
    keep: bool = False,
    clear_all: bool = False,
    timeout: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Submit all repos to the thread pool, collect results."""
    _log(f"\n{BOLD}CoDRAG Smoke Tests{RESET}  ({len(repos)} repos, {workers} concurrent)\n")
    _log(f"  {'STATUS':<6}  {'NAME':<28} {'LANG':<12} {'CHUNKS':>6} {'BUILD':>7}  {'SCORE'}")
    _log(f"  {'-'*80}")

    results: List[Dict[str, Any]] = []
    futures: Dict[Future, Dict[str, Any]] = {}

    t_wall = time.perf_counter()

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="smoke") as pool:
        for repo in repos:
            fut = pool.submit(smoke_one, repo, keep, clear_all)
            futures[fut] = repo

        for fut in as_completed(futures, timeout=timeout):
            try:
                result = fut.result()
            except Exception as e:
                repo = futures[fut]
                result = {
                    "name": repo["name"],
                    "lang": repo["lang"],
                    "status": "FAIL",
                    "error": f"Unhandled exception: {e}",
                    "chunks": 0,
                    "build_time_s": 0.0,
                    "search_hits": 0,
                    "top_score": 0.0,
                }
                _log(f"  {RED}FAIL{RESET}  {repo['name']:<28} unhandled: {e}")
            results.append(result)

    wall = round(time.perf_counter() - t_wall, 1)

    # ── Summary ─────────────────────────────────────────────────────────────
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    skipped = [r for r in results if r["status"] == "SKIP"]

    _log(f"\n{BOLD}{'='*80}{RESET}")
    _log(f"{BOLD}RESULTS{RESET}  wall time: {wall}s")
    _log(f"  {GREEN}PASS: {len(passed)}{RESET}   {RED}FAIL: {len(failed)}{RESET}   {YELLOW}SKIP: {len(skipped)}{RESET}   Total: {len(results)}")

    if failed:
        _log(f"\n{BOLD}Failures:{RESET}")
        for r in failed:
            _log(f"  {RED}✗{RESET}  {r['name']:<28} {r.get('error', 'unknown error')}")

    if skipped:
        _log(f"\n{BOLD}Skipped:{RESET}")
        for r in skipped:
            _log(f"  {YELLOW}–{RESET}  {r['name']:<28} {r.get('error', 'path missing')}")

    _log(f"\n{BOLD}Passed:{RESET}")
    for r in sorted(passed, key=lambda x: x["build_time_s"]):
        _log(
            f"  {GREEN}✓{RESET}  {r['name']:<28} {DIM}{r['lang']:<12}{RESET} "
            f"{r['chunks']:>5} chunks  {r['build_time_s']:>6.1f}s  "
            f"score={r['top_score']:.3f}"
        )

    _log(f"\n{'='*80}\n")
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Orchestrated smoke tests for CoDRAG repos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workers", type=int, default=3,
        help="Max repos to build simultaneously (default: 3)",
    )
    parser.add_argument(
        "--filter", choices=["real", "sample", "all"], default="all",
        help="Which repo set to test (default: all)",
    )
    parser.add_argument(
        "--keep", action="store_true",
        help="Keep .codrag/smoke/ index after test (default: delete)",
    )
    parser.add_argument(
        "--clear-all", action="store_true",
        help="Wipe entire .codrag/ directory before each test (not just /smoke/)",
    )
    parser.add_argument(
        "--timeout", type=float, default=None,
        help="Max seconds to wait for all repos to finish (default: none)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Save JSON results to this path",
    )
    parser.add_argument(
        "--names", nargs="*", default=None,
        help="Run only these repo names (space-separated)",
    )
    args = parser.parse_args()

    # Pre-warm the NativeEmbedder (downloads model if needed — do this once
    # in the main thread before spawning workers)
    _log(f"{CYAN}Checking NativeEmbedder (ONNX model)...{RESET}")
    try:
        from codrag.core import NativeEmbedder
        embedder = NativeEmbedder()
        if not embedder.is_available():
            _log(f"{RED}NativeEmbedder not available. Run: pip install onnxruntime tokenizers huggingface-hub{RESET}")
            sys.exit(1)
        embedder.download_model()
        _log(f"{GREEN}✓ Model ready{RESET}")
    except Exception as e:
        _log(f"{RED}NativeEmbedder init failed: {e}{RESET}")
        sys.exit(1)

    # Build repo list
    real = REAL_REPOS
    sample = _discover_sample_repos()

    if args.filter == "real":
        repos = real
    elif args.filter == "sample":
        repos = sample
    else:
        repos = real + sample

    if args.names:
        repos = [r for r in repos if r["name"] in args.names]
        if not repos:
            _log(f"{RED}No repos matched: {args.names}{RESET}")
            sys.exit(1)

    results = run_all(
        repos,
        workers=args.workers,
        keep=args.keep,
        clear_all=args.clear_all,
        timeout=args.timeout,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        _log(f"Results saved to {args.output}")

    # Exit 1 if any failures
    failed = [r for r in results if r["status"] == "FAIL"]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
