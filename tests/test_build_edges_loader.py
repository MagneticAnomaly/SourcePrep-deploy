"""Tests for the shared build-time edge loader (T-S2.5, scrutiny C2).

External edges (posted via POST /trace/external-edges) are a shipped
feature, but until now NO build stage read `trace_external_edges.jsonl` —
only the query-time TraceIndex did. Config files have no structural edges
of their own (no grammar), so build-time intelligence over them (clustering,
group_reasoning) never saw the relationships external tools pushed.

Contract pinned here:
- `load_all_build_edges(index_dir)` reads trace_edges.jsonl +
  trace_inferred_edges.jsonl + trace_external_edges.jsonl and tags each
  edge dict with its origin filename (``_edge_source_file``).
- Malformed lines in the external file are skipped with a warning
  (that file is appended/rewritten by an ingestion endpoint, so partial
  writes are possible); the two pipeline-owned files keep their strict
  parse (corruption there means a broken stage — fail loudly, as today).
- `ClusterSynthesizer.load_edges()` and `GroupReasoningEngine.load_edges()`
  delegate to the shared loader.
- End-to-end shape: two "config" file nodes joined ONLY by an external
  edge land in the same reasoning group via build_dependency_groups.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def idx_dir(tmp_path: Path) -> Path:
    d = tmp_path / "idx"
    d.mkdir()
    return d


STRUCTURAL_EDGE = {
    "id": "edge:contains:file:a.service:sym:x",
    "kind": "contains",
    "source": "file:a.service",
    "target": "sym:x@a.service:1",
    "metadata": {"confidence": 1.0},
}
INFERRED_EDGE = {
    "id": "inf-1",
    "kind": "imports",
    "source": "file:a.service",
    "target": "file:b.service",
    "metadata": {"confidence": 0.8},
}
EXTERNAL_EDGE = {
    "kind": "config_depends",
    "source": "file:etc/ssh/sshd_config",
    "target": "file:etc/ssh/sshd_config.d/10-local.conf",
    "origin": "config",
}


class TestLoadAllBuildEdges:
    def test_reads_all_three_files_and_tags_origin(self, idx_dir):
        from prep.core.trace.loaders import load_all_build_edges

        _write_jsonl(idx_dir / "trace_edges.jsonl", [STRUCTURAL_EDGE])
        _write_jsonl(idx_dir / "trace_inferred_edges.jsonl", [INFERRED_EDGE])
        _write_jsonl(idx_dir / "trace_external_edges.jsonl", [EXTERNAL_EDGE])

        edges = load_all_build_edges(idx_dir)
        assert len(edges) == 3
        by_src_file = {e["_edge_source_file"] for e in edges}
        assert by_src_file == {
            "trace_edges.jsonl",
            "trace_inferred_edges.jsonl",
            "trace_external_edges.jsonl",
        }
        # The external edge survives with its own payload intact
        ext = next(e for e in edges if e.get("origin") == "config")
        assert ext["source"] == "file:etc/ssh/sshd_config"
        assert ext["kind"] == "config_depends"

    def test_missing_external_file_behavior_unchanged(self, idx_dir):
        """No trace_external_edges.jsonl → exactly the old result set."""
        from prep.core.trace.loaders import load_all_build_edges

        _write_jsonl(idx_dir / "trace_edges.jsonl", [STRUCTURAL_EDGE])
        _write_jsonl(idx_dir / "trace_inferred_edges.jsonl", [INFERRED_EDGE])

        edges = load_all_build_edges(idx_dir)
        assert len(edges) == 2
        assert {e["kind"] for e in edges} == {"contains", "imports"}

    def test_no_edge_files_returns_empty(self, idx_dir):
        from prep.core.trace.loaders import load_all_build_edges

        assert load_all_build_edges(idx_dir) == []

    def test_malformed_external_line_skipped(self, idx_dir):
        """The external file is written by an ingestion endpoint, not the
        atomic pipeline writers — a truncated line must not kill clustering."""
        from prep.core.trace.loaders import load_all_build_edges

        _write_jsonl(idx_dir / "trace_edges.jsonl", [STRUCTURAL_EDGE])
        (idx_dir / "trace_external_edges.jsonl").write_text(
            json.dumps(EXTERNAL_EDGE) + "\n" + '{"source": "file:X", "tar' + "\n"
        )

        edges = load_all_build_edges(idx_dir)
        assert len(edges) == 2
        assert {e["kind"] for e in edges} == {"contains", "config_depends"}


class TestDelegation:
    def test_cluster_load_edges_includes_external(self, idx_dir):
        from prep.core.cluster import ClusterSynthesizer

        _write_jsonl(idx_dir / "trace_edges.jsonl", [STRUCTURAL_EDGE])
        _write_jsonl(idx_dir / "trace_external_edges.jsonl", [EXTERNAL_EDGE])

        engine = ClusterSynthesizer(llm=None, index_dir=idx_dir)  # type: ignore[arg-type]
        edges = engine.load_edges()
        kinds = {e["kind"] for e in edges}
        assert kinds == {"contains", "config_depends"}

    def test_group_reasoning_load_edges_includes_external(self, idx_dir):
        from prep.core.group_reasoning import GroupReasoningEngine

        _write_jsonl(idx_dir / "trace_edges.jsonl", [STRUCTURAL_EDGE])
        _write_jsonl(idx_dir / "trace_external_edges.jsonl", [EXTERNAL_EDGE])

        engine = GroupReasoningEngine(llm=None, index_dir=idx_dir)  # type: ignore[arg-type]
        edges = engine.load_edges()
        kinds = {e["kind"] for e in edges}
        assert kinds == {"contains", "config_depends"}


class TestEndToEndGroupFormation:
    def test_external_edge_places_config_files_in_same_group(self, idx_dir):
        """C3 acceptance shape: two config files whose ONLY connection is
        an external edge must form one reasoning group (pre-fix: they were
        singleton clusters and min_group_size dropped them)."""
        from prep.core.cluster import ClusterSynthesizer
        from prep.core.group_reasoning import build_dependency_groups

        # Epistemic set is keyed by node id; file node ids are file:-prefixed.
        from prep.core.epistemic_score import EpistemicEntry

        def _entry(nid: str) -> EpistemicEntry:
            return EpistemicEntry(
                node_id=nid, extended_summary="s",
                domain_tags=["config"], architecture_layer="host",
            )

        epistemic = {
            "file:etc/ssh/sshd_config": _entry("file:etc/ssh/sshd_config"),
            "file:etc/ssh/sshd_config.d/10-local.conf": _entry(
                "file:etc/ssh/sshd_config.d/10-local.conf"),
            "file:etc/fstab": _entry("file:etc/fstab"),
        }
        _write_jsonl(idx_dir / "trace_external_edges.jsonl", [EXTERNAL_EDGE])
        engine = ClusterSynthesizer(llm=None, index_dir=idx_dir)  # type: ignore[arg-type]

        groups = build_dependency_groups(epistemic, engine.load_edges())
        assert len(groups) == 1, f"expected 1 group, got {groups}"
        assert set(groups[0]) == {
            "file:etc/ssh/sshd_config",
            "file:etc/ssh/sshd_config.d/10-local.conf",
        }
