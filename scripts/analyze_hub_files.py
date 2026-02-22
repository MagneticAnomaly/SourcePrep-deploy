#!/usr/bin/env python3
"""Analyze trace graphs to identify hub files (Problem #2.4).

Hub files are files that appear as neighbors of many other files — like
__init__.py, utils.py, or common config modules. During trace expansion,
these hubs dilute relevance because they connect to everything.

Usage:
    python scripts/analyze_hub_files.py /path/to/project/.codrag/trace
    python scripts/analyze_hub_files.py /path/to/project/.codrag/trace --threshold 0.3
    python scripts/analyze_hub_files.py /path/to/project/.codrag/trace --top 20 --json
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def load_trace_data(trace_dir: Path) -> Tuple[Dict[str, Dict], List[Dict]]:
    """Load nodes and edges from a trace index directory."""
    nodes_path = trace_dir / "trace_nodes.jsonl"
    edges_path = trace_dir / "trace_edges.jsonl"

    if not nodes_path.exists() or not edges_path.exists():
        print(f"ERROR: Trace index not found at {trace_dir}", file=sys.stderr)
        print(f"  Expected: {nodes_path} and {edges_path}", file=sys.stderr)
        sys.exit(1)

    nodes: Dict[str, Dict] = {}
    with open(nodes_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                node = json.loads(line)
                nodes[node["id"]] = node

    edges: List[Dict] = []
    with open(edges_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                edges.append(json.loads(line))

    return nodes, edges


def analyze_hub_files(
    nodes: Dict[str, Dict],
    edges: List[Dict],
    threshold: float = 0.3,
    top_n: int = 20,
) -> Dict[str, Any]:
    """Analyze the trace graph for hub files.

    Args:
        nodes: Node dict keyed by node ID.
        edges: List of edge dicts with source/target/kind.
        threshold: A file is a "hub" if it connects to > threshold * total_files.
        top_n: Number of top files to report.

    Returns:
        Analysis results dict.
    """
    # Build file-level adjacency: which files connect to which other files
    # (collapse symbol-level edges to file-level)
    node_to_file: Dict[str, str] = {}
    for nid, node in nodes.items():
        fp = node.get("file_path") or node.get("source_path") or ""
        node_to_file[nid] = fp

    # Count unique file-to-file connections per file (undirected)
    file_neighbors: Dict[str, set] = defaultdict(set)
    edge_kind_counts: Counter = Counter()

    for edge in edges:
        src_file = node_to_file.get(edge["source"], "")
        tgt_file = node_to_file.get(edge["target"], "")
        kind = edge.get("kind", "unknown")
        edge_kind_counts[kind] += 1

        if src_file and tgt_file and src_file != tgt_file:
            file_neighbors[src_file].add(tgt_file)
            file_neighbors[tgt_file].add(src_file)

    all_files = set(node_to_file.values()) - {""}
    total_files = len(all_files)

    if total_files == 0:
        return {"error": "No files found in trace graph", "total_files": 0}

    # Rank files by neighbor count (descending)
    file_scores = []
    for fp in all_files:
        neighbor_count = len(file_neighbors.get(fp, set()))
        fanout_ratio = neighbor_count / total_files if total_files > 0 else 0.0
        file_scores.append({
            "file": fp,
            "neighbors": neighbor_count,
            "fanout_ratio": round(fanout_ratio, 4),
            "is_hub": fanout_ratio > threshold,
        })

    file_scores.sort(key=lambda x: -x["neighbors"])
    top_files = file_scores[:top_n]
    hub_files = [f for f in file_scores if f["is_hub"]]

    # Compute stats
    neighbor_counts = [len(file_neighbors.get(fp, set())) for fp in all_files]
    avg_neighbors = sum(neighbor_counts) / len(neighbor_counts) if neighbor_counts else 0
    median_neighbors = sorted(neighbor_counts)[len(neighbor_counts) // 2] if neighbor_counts else 0

    return {
        "total_files": total_files,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "edge_kinds": dict(edge_kind_counts.most_common()),
        "hub_threshold": threshold,
        "hub_count": len(hub_files),
        "hub_files": hub_files,
        "top_files": top_files,
        "stats": {
            "avg_neighbors": round(avg_neighbors, 2),
            "median_neighbors": median_neighbors,
            "max_neighbors": max(neighbor_counts) if neighbor_counts else 0,
            "files_with_zero_neighbors": sum(1 for c in neighbor_counts if c == 0),
        },
    }


def print_report(result: Dict[str, Any]) -> None:
    """Print a human-readable hub file report."""
    print(f"\n{'='*60}")
    print(f"Hub File Analysis")
    print(f"{'='*60}")
    print(f"  Files: {result['total_files']}  |  Nodes: {result['total_nodes']}  |  Edges: {result['total_edges']}")
    print(f"  Edge kinds: {result['edge_kinds']}")
    print()

    stats = result["stats"]
    print(f"  Neighbor distribution:")
    print(f"    avg={stats['avg_neighbors']}  median={stats['median_neighbors']}  max={stats['max_neighbors']}")
    print(f"    files with 0 neighbors: {stats['files_with_zero_neighbors']}")
    print()

    hub_files = result["hub_files"]
    threshold = result["hub_threshold"]
    print(f"  Hub files (fanout > {threshold:.0%} of all files): {len(hub_files)}")
    if hub_files:
        for h in hub_files:
            print(f"    {h['file']:60s}  neighbors={h['neighbors']}  fanout={h['fanout_ratio']:.1%}")
    else:
        print(f"    (none — no file connects to > {threshold:.0%} of all files)")
    print()

    print(f"  Top {len(result['top_files'])} files by neighbor count:")
    for f in result["top_files"]:
        hub_marker = " [HUB]" if f["is_hub"] else ""
        print(f"    {f['file']:60s}  neighbors={f['neighbors']:3d}  fanout={f['fanout_ratio']:.1%}{hub_marker}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Analyze trace graph for hub files")
    parser.add_argument("trace_dir", type=Path, help="Path to trace index directory")
    parser.add_argument("--threshold", type=float, default=0.3,
                        help="Fanout ratio threshold to classify as hub (default: 0.3 = 30%%)")
    parser.add_argument("--top", type=int, default=20, help="Number of top files to show")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    args = parser.parse_args()

    nodes, edges = load_trace_data(args.trace_dir)
    result = analyze_hub_files(nodes, edges, threshold=args.threshold, top_n=args.top)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)

    # Exit with code 0 if hubs found, 1 if no hubs (useful for scripting)
    sys.exit(0)


if __name__ == "__main__":
    main()
