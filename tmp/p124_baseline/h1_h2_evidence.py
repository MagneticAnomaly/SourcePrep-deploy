#!/usr/bin/env python3
"""Phase 124 §0 baseline: quantify H1 (docs->module coverage) and
H2 (orphan .md files in atlas segments) on the SourcePrep project.

Read-only. Writes RESULTS_BASELINE.md inputs to stdout / a json file.
No imports of prep packages — runs on stock python3.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("/Volumes/4TB-BAD/HumanAI/CoDRAG")
SP   = REPO / ".sourceprep"

# Match plausible source-file paths inside markdown text.
# We require an extension we care about and a path-like prefix.
PATH_RE = re.compile(
    r"\b((?:[A-Za-z0-9_./\-]+/)?[A-Za-z0-9_./\-]+\.(?:py|ts|tsx|js|jsx|rs|md))\b"
)


def load_modules() -> list[dict]:
    out = []
    with (SP / "trace_modules.jsonl").open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def load_segments() -> dict[str, set[str]]:
    """seg_id -> set of file paths. Authoritative source is the
    segments manifest (the per-segment .json files store rendered
    content + dir_path but no file list)."""
    out: dict[str, set[str]] = {}
    manifest = json.loads((SP / "atlas_segments_manifest.json").read_text())
    for entry in manifest:
        sid = entry.get("id") or entry.get("segment_id") or "?"
        files = entry.get("file_paths") or []
        out[sid] = set(f for f in files if isinstance(f, str))
    return out


def extract_paths(text: str) -> set[str]:
    """Extract candidate file paths from markdown text."""
    raw = set(PATH_RE.findall(text))
    # Drop obvious noise
    cleaned = set()
    for r in raw:
        if r.startswith("./"):
            r = r[2:]
        if "/" not in r and not r.endswith(".md"):
            # bare names like "package.json" — skip
            continue
        if r.startswith(("http", "www.", "//")):
            continue
        cleaned.add(r)
    return cleaned


def file_to_segment(segments: dict[str, set[str]]) -> dict[str, str]:
    """Reverse index: file path -> segment id (first match wins)."""
    out: dict[str, str] = {}
    for seg, files in segments.items():
        for f in files:
            if f not in out:
                out[f] = seg
    return out


def main() -> int:
    modules = load_modules()
    segments = load_segments()
    file_seg = file_to_segment(segments)

    print(f"# Phase 124 baseline — H1/H2 evidence")
    print(f"")
    print(f"## Inputs")
    print(f"- Modules in trace_modules.jsonl: {len(modules)}")
    print(f"- Atlas segments on disk:         {len(segments)}")
    seg_file_counts = {s: len(f) for s, f in segments.items()}
    print(f"- Files indexed across segments:  {sum(seg_file_counts.values())}")
    print(f"- Per-segment file counts:")
    for s, c in sorted(seg_file_counts.items(), key=lambda x: -x[1]):
        print(f"    {s:<48} {c:>6}")

    docs_root = REPO / "docs"
    md_files = sorted(p for p in docs_root.rglob("*.md"))
    print(f"\n- Markdown files under docs/: {len(md_files)}")

    # Build per-md mentioned paths
    mentions: dict[str, set[str]] = {}
    parse_errors = 0
    for md in md_files:
        try:
            text = md.read_text(errors="replace")
        except Exception:
            parse_errors += 1
            continue
        rel = str(md.relative_to(REPO))
        mentions[rel] = extract_paths(text)
    total_mentions = sum(len(v) for v in mentions.values())
    print(f"- Raw path mentions extracted:    {total_mentions}")
    print(f"- Markdown read errors:           {parse_errors}")

    # ────────────────────────────────────────────────
    # H1: per-module relevant-doc coverage
    # ────────────────────────────────────────────────
    print(f"\n## H1 — per-module relevant-doc coverage")
    print(f"For each module, count the number of docs/*.md files that mention at least one of its member_files.\n")

    docs_for_module: dict[str, set[str]] = defaultdict(set)
    for mod in modules:
        mid = mod.get("module_id") or mod.get("name") or "?"
        members = set(mod.get("member_files") or [])
        # Filter to actual code files (drop bundled .md)
        code_members = {m for m in members if not m.endswith(".md")}
        if not code_members:
            continue
        for md_path, paths in mentions.items():
            if paths & code_members:
                docs_for_module[mid].add(md_path)

    code_module_count = sum(
        1 for m in modules
        if any(not f.endswith(".md") for f in (m.get("member_files") or []))
    )
    covered = len(docs_for_module)
    cov_pct = 100.0 * covered / max(code_module_count, 1)

    print(f"- Code-bearing modules: {code_module_count}")
    print(f"- Modules with >=1 relevant doc: {covered} ({cov_pct:.1f}%)")

    bucket = Counter()
    for mid in [m.get("module_id") or m.get("name") for m in modules]:
        n = len(docs_for_module.get(mid, []))
        if n == 0:
            bucket["0"] += 1
        elif n <= 2:
            bucket["1-2"] += 1
        elif n <= 5:
            bucket["3-5"] += 1
        elif n <= 10:
            bucket["6-10"] += 1
        else:
            bucket["11+"] += 1
    print(f"\nDistribution of relevant-doc count per module:")
    for k in ("0", "1-2", "3-5", "6-10", "11+"):
        print(f"    {k:<6} modules: {bucket[k]}")

    # Top 10 modules by doc richness — these are the WIN cases
    top = sorted(docs_for_module.items(), key=lambda x: -len(x[1]))[:10]
    print(f"\nTop 10 modules by relevant-doc count (highest leverage if T4 lands):")
    name_by_id = {(m.get("module_id") or m.get("name")): m.get("name", "?") for m in modules}
    for mid, ds in top:
        print(f"    {len(ds):>3}  {name_by_id.get(mid, mid)[:60]}")

    # ────────────────────────────────────────────────
    # H2: orphan .md files in atlas segments
    # ────────────────────────────────────────────────
    print(f"\n## H2 — .md files orphaned from the code they describe")
    print(f"For each .md file under docs/, look up the segment it landed in,")
    print(f"then check whether the code paths it MENTIONS land in the SAME segment.\n")

    md_in_seg = 0
    md_orphan = 0
    md_partial = 0
    md_no_mentions = 0
    md_unsegmented = 0

    seg_drop_counter: Counter = Counter()  # (md_seg -> code_seg) edges

    for md_path, paths in mentions.items():
        md_seg = file_seg.get(md_path)
        if md_seg is None:
            md_unsegmented += 1
            continue
        code_paths = {p for p in paths if not p.endswith(".md")}
        if not code_paths:
            md_no_mentions += 1
            continue
        same_seg = sum(1 for p in code_paths if file_seg.get(p) == md_seg)
        diff_seg = sum(1 for p in code_paths if file_seg.get(p) and file_seg[p] != md_seg)
        if same_seg and not diff_seg:
            md_in_seg += 1
        elif diff_seg and not same_seg:
            md_orphan += 1
            for p in code_paths:
                cs = file_seg.get(p)
                if cs and cs != md_seg:
                    seg_drop_counter[(md_seg, cs)] += 1
        elif same_seg and diff_seg:
            md_partial += 1

    print(f"- .md files with mentions, fully in same segment as their code: {md_in_seg}")
    print(f"- .md files with mentions, fully orphaned (zero same-segment):  {md_orphan}")
    print(f"- .md files with mentions, partially orphaned (some same):      {md_partial}")
    print(f"- .md files with no resolvable code mentions:                   {md_no_mentions}")
    print(f"- .md files not present in any segment (unsegmented):           {md_unsegmented}")

    print(f"\nTop 10 cross-segment edges (md_segment -> code_segment, mention count):")
    for (ms, cs), n in seg_drop_counter.most_common(10):
        print(f"    {n:>5}  {ms[:36]:<36} -> {cs}")

    # Write a JSON dump alongside for the harness to ingest later
    out_json = {
        "modules_total": len(modules),
        "code_modules_total": code_module_count,
        "modules_with_relevant_docs": covered,
        "module_doc_distribution": dict(bucket),
        "md_total": len(md_files),
        "md_in_segment": md_in_seg,
        "md_orphan": md_orphan,
        "md_partial": md_partial,
        "md_no_mentions": md_no_mentions,
        "md_unsegmented": md_unsegmented,
        "segments": seg_file_counts,
        "top_module_doc_richness": [
            {"module": name_by_id.get(mid, mid), "doc_count": len(ds)}
            for mid, ds in top
        ],
    }
    out_path = Path("/Volumes/4TB-BAD/HumanAI/CoDRAG/tmp/p124_baseline/h1_h2_results.json")
    out_path.write_text(json.dumps(out_json, indent=2))
    print(f"\nJSON dump: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
