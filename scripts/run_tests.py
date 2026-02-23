import argparse
import json
import subprocess
import sys
from pathlib import Path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON on {path.name}:{i}: {e}") from e
    return items


def validate_trace_dir(trace_dir: Path) -> None:
    manifest_path = trace_dir / "trace_manifest.json"
    nodes_path = trace_dir / "trace_nodes.jsonl"
    edges_path = trace_dir / "trace_edges.jsonl"

    for p in (manifest_path, nodes_path, edges_path):
        if not p.exists():
            raise FileNotFoundError(f"Missing required trace file: {p}")

    manifest = _read_json(manifest_path)
    nodes = _read_jsonl(nodes_path)
    edges = _read_jsonl(edges_path)

    node_ids = []
    for n in nodes:
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            raise ValueError("One or more nodes missing required field: id")
        node_ids.append(nid)

        kind = n.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"Node {nid} missing required field: kind")

        name = n.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"Node {nid} missing required field: name")

        fp = n.get("file_path")
        # External dependency nodes (ext:*) don't have file_path — that's expected
        is_external = nid.startswith("ext:")
        if not is_external:
            if not isinstance(fp, str) or not fp:
                raise ValueError(f"Node {nid} missing required field: file_path")
            if fp.startswith("/") or ":\\" in fp or "\\" in fp:
                raise ValueError(f"Node {nid} has non-portable file_path: {fp}")

        span = n.get("span")
        if span is not None:
            if not isinstance(span, dict):
                raise ValueError(f"Node {nid} span must be null or object")
            if not isinstance(span.get("start_line"), int) or not isinstance(span.get("end_line"), int):
                raise ValueError(f"Node {nid} span must have start_line/end_line ints")

        meta = n.get("metadata")
        if not isinstance(meta, dict):
            raise ValueError(f"Node {nid} missing required field: metadata (object)")

    node_id_set = set(node_ids)
    if len(node_id_set) != len(node_ids):
        raise ValueError("Duplicate node IDs detected")

    edge_ids: list[str] = []
    for e in edges:
        eid = e.get("id")
        if not isinstance(eid, str) or not eid:
            raise ValueError("Edge missing required field: id")
        edge_ids.append(eid)

        kind = e.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"Edge {eid} missing required field: kind")

        src = e.get("source")
        tgt = e.get("target")
        if src not in node_id_set:
            raise ValueError(f"Edge source not found in nodes: {src}")
        if tgt not in node_id_set:
            raise ValueError(f"Edge target not found in nodes: {tgt}")

        meta = e.get("metadata")
        if not isinstance(meta, dict):
            raise ValueError(f"Edge {eid} missing required field: metadata (object)")

    if len(set(edge_ids)) != len(edge_ids):
        raise ValueError("Duplicate edge IDs detected")

    counts = manifest.get("counts", {})
    if isinstance(counts, dict):
        expected_nodes = counts.get("nodes")
        expected_edges = counts.get("edges")

        if expected_nodes is not None and expected_nodes != len(nodes):
            raise ValueError(f"Manifest nodes count mismatch: {expected_nodes} != {len(nodes)}")

        if expected_edges is not None and expected_edges != len(edges):
            raise ValueError(f"Manifest edges count mismatch: {expected_edges} != {len(edges)}")


def _maybe_run_pytest(repo_root: Path) -> int:
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        print("[run_tests] No ./tests directory found; skipping pytest.")
        return 0

    print("[run_tests] Running pytest...")
    proc = subprocess.run([sys.executable, "-m", "pytest"], cwd=str(repo_root))
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CoDRAG checks (pytest + trace validation)")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repo root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--trace-dir",
        default=None,
        help="Directory containing trace_manifest.json + trace_nodes.jsonl + trace_edges.jsonl",
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip running pytest",
    )

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    rc = 0

    if args.trace_dir:
        trace_dir = Path(args.trace_dir).resolve()
        print(f"[run_tests] Validating trace output: {trace_dir}")
        try:
            validate_trace_dir(trace_dir)
            print("[run_tests] Trace validation OK")
        except Exception as e:
            print(f"[run_tests] Trace validation FAILED: {e}")
            rc = 1

    if not args.skip_pytest:
        rc = max(rc, _maybe_run_pytest(repo_root))

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
