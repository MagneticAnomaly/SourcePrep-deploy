"""
Gold query evaluation runner for Prep search + atlas quality.

Usage:
    # Legacy: search-quality eval (condition A baseline, uniform)
    python -m tests.eval.eval_runner --repo /path/to/prep
    python -m tests.eval.eval_runner --repo /path/to/prep --query gq-001

    # Phase 103 POC: atlas-mode with conditions
    python -m tests.eval.eval_runner --repo /path/to/prep --mode atlas --condition A
    python -m tests.eval.eval_runner --repo /path/to/prep --mode atlas --condition B --role security
    python -m tests.eval.eval_runner --repo /path/to/prep --mode atlas --condition B --role security --output-json results.json

Conditions (Phase 103 R3):
    A = uniform atlas (neutral RoleVector, no domain weighting)
    B = role-weighted sub-atlas (resolve_role(slug) → project_atlas_for_role)
    C, D = persona-prompt axes (future; requires LLM call wiring)
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@dataclass
class QueryResult:
    """Result of evaluating a single gold query."""
    query_id: str
    query: str
    passed: bool
    file_hits: int
    file_misses: int
    keyword_hits: int
    keyword_misses: int
    top_k_files: List[str]
    expected_files: List[str]
    score: float
    details: str
    # Phase 103 POC extensions (optional; defaulted for back-compat)
    mode: str = "search"           # search | atlas
    condition: str = "A"           # A | B | C | D
    role: Optional[str] = None     # role slug when condition == B or D
    atlas_chars: int = 0           # size of assembled context (atlas mode only)


def load_gold_queries(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load gold queries from JSON file."""
    if path is None:
        path = Path(__file__).parent / "gold_queries.json"
    return json.loads(path.read_text())


def evaluate_query(
    index: "CodeIndex",
    query_spec: Dict[str, Any],
    k: int = 10,
    verbose: bool = False,
) -> QueryResult:
    """Evaluate a single gold query against the index."""
    query_id = query_spec["id"]
    query = query_spec["query"]
    expected_files = query_spec.get("expected_files", [])
    expected_keywords = query_spec.get("expected_keywords", [])
    
    # Run search
    results = index.search(query, k=k)
    
    # Extract file paths from results
    result_files = []
    result_content = []
    for r in results:
        doc = r.doc if hasattr(r, 'doc') else r
        sp = doc.get("source_path", "")
        result_files.append(sp)
        result_content.append(doc.get("content", ""))
    
    # Check file hits (any expected file in top-k results)
    file_hits = 0
    file_misses = 0
    for ef in expected_files:
        # Normalize expected file path
        ef_normalized = ef.replace("\\", "/")
        found = any(ef_normalized in rf or rf.endswith(ef_normalized.split("/")[-1]) for rf in result_files)
        if found:
            file_hits += 1
        else:
            file_misses += 1
    
    # Check keyword hits (any expected keyword in result content)
    keyword_hits = 0
    keyword_misses = 0
    combined_content = " ".join(result_content).lower()
    for kw in expected_keywords:
        if kw.lower() in combined_content:
            keyword_hits += 1
        else:
            keyword_misses += 1
    
    # Calculate score
    total_expected = len(expected_files) + len(expected_keywords)
    total_hits = file_hits + keyword_hits
    score = total_hits / total_expected if total_expected > 0 else 1.0
    
    # Determine pass/fail (>= 50% hits)
    passed = score >= 0.5
    
    # Build details string
    details_parts = []
    if file_misses > 0:
        missed = [ef for ef in expected_files if not any(ef in rf for rf in result_files)]
        details_parts.append(f"Missing files: {missed}")
    if keyword_misses > 0:
        missed_kw = [kw for kw in expected_keywords if kw.lower() not in combined_content]
        details_parts.append(f"Missing keywords: {missed_kw}")
    
    return QueryResult(
        query_id=query_id,
        query=query,
        passed=passed,
        file_hits=file_hits,
        file_misses=file_misses,
        keyword_hits=keyword_hits,
        keyword_misses=keyword_misses,
        top_k_files=result_files[:5],
        expected_files=expected_files,
        score=score,
        details="; ".join(details_parts) if details_parts else "All expectations met",
    )


# ── Phase 103 POC: atlas-mode evaluation ──────────────────────────────

def _neutral_role_vector(max_chars: int = 4000):
    """Build a neutral RoleVector for condition A (uniform atlas baseline).

    DESIGN NOTE (post-Run 03 methodology fix): earlier versions derived
    the neutral domain_affinity as the union of all BUILT_IN_ROLES.
    This made condition A drift every time any role's keyword list was
    tuned — confounding A-vs-B comparisons because tuning role X's
    domain_affinity also strengthened A's, which should be fixed.

    The neutral role now uses a small, stable, codebase-universal domain
    set derived from the highest-frequency tags actually present across
    all files (not from any role definition). This isolates the uniform
    baseline from role-tuning work and lets Run N+1 vs Run N on a single
    role be cleanly attributable to that role's calibration.

    Layer weights stay uniform at 1.0. Centrality neutral at 0.5. Detail
    full at 1.0. Budget matches practitioner tier so A never loses on
    pure size.
    """
    from prep.core.atlas.role_vectors import RoleVector

    all_layers = {
        "presentation": 1.0, "business_logic": 1.0, "data": 1.0,
        "infrastructure": 1.0, "configuration": 1.0, "testing": 1.0,
        "documentation": 1.0, "build": 1.0, "unknown": 1.0,
    }

    # Stable, codebase-universal terms. Chosen as the top-frequency
    # tags observed in trace_epistemic.jsonl for Prep (ui, testing, mcp,
    # react, typescript, documentation, python, security, pipeline-
    # orchestration, cli, dashboard, configuration, rag). NOT sourced
    # from BUILT_IN_ROLES — so role calibration work below does not
    # leak into the uniform baseline.
    neutral_domains = [
        "ui", "testing", "mcp", "react", "typescript", "documentation",
        "python", "pipeline-orchestration", "cli", "dashboard",
        "configuration", "rag", "fastapi", "indexing", "storybook",
    ]

    return RoleVector(
        role_id="_neutral",
        display_name="Neutral (uniform baseline)",
        layer_weights=all_layers,
        domain_affinity=neutral_domains,
        centrality_weight=0.5,
        detail_level=1.0,
        max_chars=max_chars,
    )


def assemble_atlas_context(
    index_dir: Path,
    condition: str,
    role_slug: Optional[str] = None,
    atlas_content: str = "",
) -> str:
    """Assemble the context string an agent would receive for a given condition.

    This is the Phase 103 POC's primary measurement primitive — the thing
    `prep(role=...)` returns in production.

    - Condition A → neutral role vector (uniform baseline)
    - Condition B → resolved role vector (knowledge-honing thesis)
    - Conditions C/D → same as A/B for now; persona wrapping is applied later
      by the LLM-call layer (not yet wired)
    """
    from prep.core.atlas.role_projection import project_atlas_for_role
    from prep.core.atlas.role_resolver import resolve_role

    if condition in ("A", "C"):
        role_vec = _neutral_role_vector()
    elif condition in ("B", "D"):
        if not role_slug:
            raise ValueError(f"Condition {condition} requires --role <slug>")
        role_vec = resolve_role(role_slug)
    else:
        raise ValueError(f"Unknown condition: {condition}")

    return project_atlas_for_role(role_vec, index_dir, atlas_content=atlas_content)


def _stem(token: str) -> str:
    """Lightweight morphological stem for loose keyword matching.

    Strips common English suffixes so 'atomically' / 'atomicity' both match
    'atomic'.  This is intentionally minimal — full Porter stemming would
    be overkill for code identifiers and slow on hot paths.
    """
    t = token.lower().strip()
    for suf in ("icity", "ically", "ation", "ations", "ized", "ization",
                "ing", "ers", "er", "ed", "es", "s", "ly", "ic", "al"):
        if len(t) > len(suf) + 2 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def _keyword_matches(kw: str, text_lower: str) -> bool:
    """Loose keyword match: exact substring OR stem substring.

    Atlas text lives at module granularity; expected keywords in our gold
    queries are often function names or code tokens.  We accept either
    direct substring hit or stem-form hit so that 'atomic' matches
    'atomicity', '_swap' matches 'swap', 'persist' matches 'persisted'.
    """
    kl = kw.lower()
    if kl in text_lower:
        return True
    stem = _stem(kl.lstrip("_"))
    if len(stem) >= 4 and stem in text_lower:
        return True
    return False


def _file_matches(ef: str, text_lower: str) -> Tuple[bool, str]:
    """Loose file match with graceful degradation.

    Returns (matched, match_kind):
      - ("full")     : full normalized path substring in atlas
      - ("basename") : file basename in atlas (e.g. 'index.py')
      - ("parent")   : parent directory path in atlas (e.g. 'core/')
      - ("module")   : any ancestor directory token in atlas
      - else ("", False)

    Atlas text typically names modules, not specific files, so a
    parent-directory hit is legitimate partial credit.
    """
    ef_normalized = ef.replace("\\", "/").lower()
    parts = [p for p in ef_normalized.split("/") if p]

    if ef_normalized in text_lower:
        return True, "full"

    basename = parts[-1] if parts else ""
    if basename and basename in text_lower:
        return True, "basename"

    # Drop the filename; try parent dir like "core/atlas/"
    if len(parts) >= 2:
        parent_dir = "/".join(parts[:-1]) + "/"
        if parent_dir in text_lower:
            return True, "parent"

    # Finally try any distinctive module segment (len >= 3 to avoid 'src', 'py')
    for seg in reversed(parts[:-1]):
        if len(seg) >= 4 and seg in text_lower:
            return True, "module"

    return False, ""


def evaluate_query_atlas(
    query_spec: Dict[str, Any],
    atlas_text: str,
    condition: str,
    role_slug: Optional[str] = None,
    verbose: bool = False,
) -> QueryResult:
    """Evaluate a gold query against assembled atlas text.

    Whereas `evaluate_query` measures search-index quality, this measures
    whether the context we'd HAND to an agent via `prep(role=...)` contains
    the files/keywords needed for the task.

    Scoring (post-R3 baseline Run 01 tuning):
      - File hit: full path / basename / parent dir / module-ancestor match.
      - Keyword hit: substring OR stem-form substring.
    Both are 'loose' — atlas lives at module granularity, and the gold set
    was written for search-quality eval (function-level).  Loose matching
    reconciles the mismatch without removing signal.
    """
    query_id = query_spec["id"]
    query = query_spec["query"]
    expected_files = query_spec.get("expected_files", [])
    expected_keywords = query_spec.get("expected_keywords", [])

    atlas_lower = atlas_text.lower()

    file_hits = 0
    file_misses = 0
    mentioned_files: List[str] = []
    file_match_detail: List[str] = []
    for ef in expected_files:
        matched, kind = _file_matches(ef, atlas_lower)
        if matched:
            file_hits += 1
            mentioned_files.append(ef)
            file_match_detail.append(f"{ef} ({kind})")
        else:
            file_misses += 1

    keyword_hits = 0
    keyword_misses = 0
    for kw in expected_keywords:
        if _keyword_matches(kw, atlas_lower):
            keyword_hits += 1
        else:
            keyword_misses += 1

    total_expected = len(expected_files) + len(expected_keywords)
    total_hits = file_hits + keyword_hits
    score = total_hits / total_expected if total_expected > 0 else 1.0
    passed = score >= 0.5

    details_parts: List[str] = []
    if file_hits > 0 and verbose:
        details_parts.append(f"File hits: {file_match_detail}")
    if file_misses > 0:
        missed = [ef for ef in expected_files if ef not in mentioned_files]
        details_parts.append(f"Missing files: {missed}")
    if keyword_misses > 0:
        missed_kw = [kw for kw in expected_keywords if not _keyword_matches(kw, atlas_lower)]
        details_parts.append(f"Missing keywords: {missed_kw}")

    return QueryResult(
        query_id=query_id,
        query=query,
        passed=passed,
        file_hits=file_hits,
        file_misses=file_misses,
        keyword_hits=keyword_hits,
        keyword_misses=keyword_misses,
        top_k_files=mentioned_files[:5],
        expected_files=expected_files,
        score=score,
        details="; ".join(details_parts) if details_parts else "All expectations met",
        mode="atlas",
        condition=condition,
        role=role_slug,
        atlas_chars=len(atlas_text),
    )


def run_evaluation_atlas(
    repo_root: Path,
    condition: str,
    role_slug: Optional[str] = None,
    query_ids: Optional[List[str]] = None,
    verbose: bool = False,
) -> List[QueryResult]:
    """Atlas-mode evaluation driver (Phase 103 POC).

    Assembles context via the real role projection path, then scores each
    gold query against that context.
    """
    gold = load_gold_queries()
    queries = gold["queries"]
    if query_ids:
        queries = [q for q in queries if q["id"] in query_ids]
    if not queries:
        print("No queries to evaluate")
        return []

    # Locate index: daemon embedded mode uses .prep/ directly;
    # CodeIndex.build() writes to .prep/index/. Prefer whichever has
    # trace_modules.jsonl (what role projection actually consumes).
    candidates = [repo_root / ".prep", repo_root / ".prep" / "index"]
    index_dir = next((c for c in candidates if (c / "trace_modules.jsonl").exists()), None)
    if index_dir is None:
        # Fall back to whichever exists so project_atlas_for_role can still
        # report its "No codebase data" fallback — useful for smoke tests.
        index_dir = next((c for c in candidates if c.exists()), candidates[0])
        print(f"Warning: no trace_modules.jsonl found. Using {index_dir} (atlas will likely be minimal).")

    atlas_text = assemble_atlas_context(
        index_dir=index_dir,
        condition=condition,
        role_slug=role_slug,
    )

    header = f"Condition {condition}" + (f" (role={role_slug})" if role_slug else " (uniform)")
    print(f"{header} — assembled atlas: {len(atlas_text):,} chars")
    print()

    results: List[QueryResult] = []
    for query_spec in queries:
        result = evaluate_query_atlas(
            query_spec=query_spec,
            atlas_text=atlas_text,
            condition=condition,
            role_slug=role_slug,
            verbose=verbose,
        )
        results.append(result)

        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"{status} [{result.query_id}] {result.query}")
        print(f"       Score: {result.score:.1%} | Files: {result.file_hits}/{result.file_hits + result.file_misses} | Keywords: {result.keyword_hits}/{result.keyword_hits + result.keyword_misses}")
        if verbose or not result.passed:
            if result.details != "All expectations met":
                print(f"       Details: {result.details}")
        print()

    return results


def write_results_json(results: List[QueryResult], path: Path) -> None:
    """Write structured results for cross-run aggregation (R1/R2/R3 need this)."""
    payload = {
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "avg_score": (sum(r.score for r in results) / len(results)) if results else 0.0,
            "mode": results[0].mode if results else None,
            "condition": results[0].condition if results else None,
            "role": results[0].role if results else None,
        },
        "results": [asdict(r) for r in results],
    }
    path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote structured results to {path}")


def run_evaluation(
    repo_root: Path,
    query_ids: Optional[List[str]] = None,
    k: int = 10,
    verbose: bool = False,
) -> List[QueryResult]:
    """Run evaluation on gold queries."""
    from prep.core import CodeIndex, FakeEmbedder, OllamaEmbedder
    
    # Load gold queries
    gold = load_gold_queries()
    queries = gold["queries"]
    
    # Filter by query IDs if specified
    if query_ids:
        queries = [q for q in queries if q["id"] in query_ids]
    
    if not queries:
        print("No queries to evaluate")
        return []
    
    # Find or create index
    index_dir = repo_root / ".prep" / "index"
    
    # Try to use real embedder, fall back to fake
    try:
        embedder = OllamaEmbedder()
        # Quick connectivity check
        embedder.embed("test")
    except Exception:
        print("Warning: Ollama not available, using FakeEmbedder (results will be random)")
        embedder = FakeEmbedder()
    
    index = CodeIndex(index_dir=index_dir, embedder=embedder)
    
    if not index.is_loaded():
        print(f"Index not found at {index_dir}")
        print("Building index... (this may take a while)")
        index.build(repo_root=repo_root)
    
    # Run evaluations
    results = []
    for query_spec in queries:
        result = evaluate_query(index, query_spec, k=k, verbose=verbose)
        results.append(result)
        
        # Print result
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"{status} [{result.query_id}] {result.query}")
        print(f"       Score: {result.score:.1%} | Files: {result.file_hits}/{result.file_hits + result.file_misses} | Keywords: {result.keyword_hits}/{result.keyword_hits + result.keyword_misses}")
        
        if verbose or not result.passed:
            print(f"       Top files: {result.top_k_files[:3]}")
            if result.details != "All expectations met":
                print(f"       Details: {result.details}")
        print()
    
    return results


def print_summary(results: List[QueryResult]) -> None:
    """Print evaluation summary."""
    if not results:
        return
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    avg_score = sum(r.score for r in results) / total
    
    print("=" * 60)
    print(f"SUMMARY: {passed}/{total} queries passed ({passed/total:.0%})")
    print(f"Average score: {avg_score:.1%}")
    
    # Group by category
    by_category: Dict[str, List[QueryResult]] = {}
    gold = load_gold_queries()
    for q in gold["queries"]:
        cat = q.get("category", "unknown")
        qid = q["id"]
        for r in results:
            if r.query_id == qid:
                by_category.setdefault(cat, []).append(r)
    
    print("\nBy category:")
    for cat, cat_results in sorted(by_category.items()):
        cat_passed = sum(1 for r in cat_results if r.passed)
        cat_total = len(cat_results)
        print(f"  {cat}: {cat_passed}/{cat_total}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Prep search + atlas quality")
    parser.add_argument("--repo", type=Path, required=True, help="Repository root path")
    parser.add_argument("--query", type=str, action="append", help="Specific query ID(s) to run")
    parser.add_argument("--k", type=int, default=10, help="Number of search results (search mode)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    # Phase 103 POC flags
    parser.add_argument(
        "--mode",
        choices=["search", "atlas"],
        default="search",
        help="search = index-quality eval (legacy); atlas = role-projection eval (Phase 103)",
    )
    parser.add_argument(
        "--condition",
        choices=["A", "B", "C", "D"],
        default="A",
        help="A=uniform baseline, B=role-weighted (thesis), C/D=persona axes (future)",
    )
    parser.add_argument(
        "--role",
        type=str,
        default=None,
        help="Role slug (e.g. 'security', 'engineering'); required for condition B/D",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Write structured results to a JSON file (for cross-run aggregation)",
    )

    args = parser.parse_args()

    if not args.repo.exists():
        print(f"Error: Repository path does not exist: {args.repo}")
        sys.exit(1)

    print(f"Evaluating against: {args.repo}")
    print(f"Mode: {args.mode} | Condition: {args.condition}" + (f" | Role: {args.role}" if args.role else ""))
    print()

    if args.mode == "atlas":
        if args.condition in ("B", "D") and not args.role:
            print(f"Error: condition {args.condition} requires --role <slug>")
            sys.exit(1)
        results = run_evaluation_atlas(
            repo_root=args.repo,
            condition=args.condition,
            role_slug=args.role,
            query_ids=args.query,
            verbose=args.verbose,
        )
    else:
        results = run_evaluation(
            repo_root=args.repo,
            query_ids=args.query,
            k=args.k,
            verbose=args.verbose,
        )

    print_summary(results)

    if args.output_json:
        write_results_json(results, args.output_json)

    # Exit with error if any failed
    if any(not r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
