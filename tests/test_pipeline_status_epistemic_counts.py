"""Regression test for /pipeline/status epistemic counts (Graph Scope ratio).

The Graph Scope panel renders `enriched_nodes / total_file_nodes`. A prior
revision computed `total_file_nodes` via an unfiltered line count of
`trace_nodes.jsonl`, which contains every node kind (file, symbol, section,
external_module). That made the panel show absurd ratios like "24/311 nodes
enriched" — 311 was every node, but the numerator only counts files.

Canonical source: trace_manifest.json["file_hashes"] holds one entry per
parsed file = one kind:file node. This test locks that contract so the
units of the numerator and denominator stay aligned.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    with server._project_build_lock:
        server._project_build_threads.clear()
        server._project_last_build_result.clear()
        server._project_last_build_error.clear()
    with server._project_trace_build_lock:
        server._project_trace_build_threads.clear()
    return TestClient(app)


def _add_embedded_project(client: TestClient, repo_root: Path) -> str:
    res = client.post(
        "/projects",
        json={"path": str(repo_root), "name": "test", "mode": "embedded"},
    )
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def _idx_dir(pid: str) -> Path:
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project
    return Path(project_index_dir(require_project(pid)))


def _epistemic(client: TestClient, pid: str) -> dict:
    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    return res.json()["data"]["stages"]["enrichment"]


def _seed_graph(idx_dir: Path, *, file_count: int, symbol_count: int) -> None:
    """Write a trace_manifest.json + trace_nodes.jsonl that mimics a real index.

    file_hashes contains `file_count` entries (the canonical source of truth
    for kind:file nodes). The jsonl contains `file_count + symbol_count`
    lines mixing kind:file and kind:symbol entries.
    """
    idx_dir.mkdir(parents=True, exist_ok=True)
    file_hashes = {f"src/file_{i}.py": f"hash{i}" for i in range(file_count)}
    (idx_dir / "trace_manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "counts": {"nodes": file_count + symbol_count, "edges": 0},
                "file_hashes": file_hashes,
            },
            indent=2,
        )
    )
    lines = []
    for i in range(file_count):
        lines.append(json.dumps({"id": f"file:src/file_{i}.py", "kind": "file"}))
    for i in range(symbol_count):
        # Pretty-print spacing to mimic `json.dumps(..., indent=2)`-style
        # output. The previous fallback grepped '"kind":"file"' which fails
        # against this whitespace and silently returned 0.
        lines.append('{"id": "sym:foo_%d", "kind": "symbol"}' % i)
    (idx_dir / "trace_nodes.jsonl").write_text("\n".join(lines) + "\n")


def test_total_file_nodes_uses_file_hashes_not_unfiltered_line_count(client, tmp_path):
    """Reproduces the user-visible "24/311 nodes enriched" bug.

    Before the fix: total_file_nodes leaked the unfiltered line count
    (file_count + symbol_count). Numerator and denominator were in
    different units, so the panel rendered nonsense like 24/311.
    """
    pid = _add_embedded_project(client, tmp_path)
    _seed_graph(_idx_dir(pid), file_count=24, symbol_count=287)

    ep = _epistemic(client, pid)
    assert ep["total_file_nodes"] == 24, (
        f"total_file_nodes must equal file_hashes count (kind:file only), "
        f"got {ep['total_file_nodes']}"
    )
    assert ep["total_nodes"] == 311
    # The panel computes enriched/total_file_nodes — these must be the same
    # unit so the ratio is interpretable.
    assert ep["total_file_nodes"] <= ep["total_nodes"]


def test_total_file_nodes_falls_back_to_jsonl_when_manifest_missing(client, tmp_path):
    """If trace_manifest.json is missing/unreadable, do not render a misleading
    ratio: fall back to the raw line count for both fields. The user sees
    100% (X/X) instead of nonsense (X/Y where Y≫X)."""
    pid = _add_embedded_project(client, tmp_path)
    idx_dir = _idx_dir(pid)
    idx_dir.mkdir(parents=True, exist_ok=True)
    # Write only the jsonl — no manifest.
    (idx_dir / "trace_nodes.jsonl").write_text(
        '{"id": "file:a", "kind": "file"}\n'
        '{"id": "sym:b", "kind": "symbol"}\n'
    )
    ep = _epistemic(client, pid)
    assert ep["total_file_nodes"] == ep["total_nodes"] == 2
