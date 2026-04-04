"""Tests for ManifestStore — Phase 72 Stage 1."""
import json
import time

import pytest
from pathlib import Path

from codrag.services.pipeline.manifest_store import ManifestStore
from codrag.services.pipeline.stages import StageId


@pytest.fixture
def idx_dir(tmp_path):
    return tmp_path


@pytest.fixture
def store(idx_dir):
    return ManifestStore(idx_dir)


# ── Provenance manifests ───────────────────────────────────────


class TestProvenanceManifest:
    def test_write_and_read_provenance(self, store):
        data = {"format_version": "2.0", "stage_id": "enrichment", "quality": {"total_items": 100}}
        store.write_provenance(StageId.ENRICHMENT, data)

        result = store.read_provenance(StageId.ENRICHMENT)
        assert result is not None
        assert result["stage_id"] == "enrichment"
        assert result["quality"]["total_items"] == 100

    def test_provenance_path_uses_stage_manifest_file(self, store):
        path = store.provenance_path(StageId.ENRICHMENT)
        assert path.name == "trace_epistemic_manifest.json"

    def test_provenance_path_structural(self, store):
        path = store.provenance_path(StageId.STRUCTURAL)
        assert path.name == "trace_manifest.json"

    def test_provenance_exists_false_when_missing(self, store):
        assert store.provenance_exists(StageId.ENRICHMENT) is False

    def test_provenance_exists_true_after_write(self, store):
        store.write_provenance(StageId.ENRICHMENT, {"stage_id": "enrichment"})
        assert store.provenance_exists(StageId.ENRICHMENT) is True

    def test_provenance_exists_false_when_empty(self, store):
        store.provenance_path(StageId.ENRICHMENT).write_text("")
        assert store.provenance_exists(StageId.ENRICHMENT) is False

    def test_provenance_mtime_returns_float(self, store):
        store.write_provenance(StageId.ENRICHMENT, {"stage_id": "enrichment"})
        mtime = store.provenance_mtime(StageId.ENRICHMENT)
        assert isinstance(mtime, float)
        assert mtime > 0

    def test_provenance_mtime_returns_zero_when_missing(self, store):
        assert store.provenance_mtime(StageId.ENRICHMENT) == 0.0

    def test_read_provenance_returns_none_when_missing(self, store):
        assert store.read_provenance(StageId.ENRICHMENT) is None

    def test_write_provenance_uses_atomic_write(self, store, idx_dir):
        store.write_provenance(StageId.ENRICHMENT, {"stage_id": "enrichment"})
        tmp_files = list(idx_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_read_provenance_handles_corrupt_json(self, store):
        path = store.provenance_path(StageId.ENRICHMENT)
        path.write_text("not valid json {{{")
        assert store.read_provenance(StageId.ENRICHMENT) is None

    def test_write_provenance_all_stages(self, store):
        """Every stage can have a provenance manifest written and read back."""
        for stage in StageId:
            store.write_provenance(stage, {"stage_id": stage.value})
            result = store.read_provenance(stage)
            assert result is not None
            assert result["stage_id"] == stage.value


# ── Worker hash manifests ──────────────────────────────────────


class TestWorkerHashManifest:
    def test_write_and_read_hashes(self, store):
        hashes = {"src/foo.py": "sha256:abc123", "src/bar.py": "sha256:def456"}
        store.write_hashes(StageId.INFERRED_EDGES, hashes)

        result = store.read_hashes(StageId.INFERRED_EDGES)
        assert result == hashes

    def test_hashes_path_inferred_edges(self, store):
        path = store.hashes_path(StageId.INFERRED_EDGES)
        assert path.name == "trace_inferred_hashes.json"

    def test_hashes_path_structural(self, store):
        """Structural hashes live INSIDE trace_manifest.json."""
        path = store.hashes_path(StageId.STRUCTURAL)
        assert path.name == "trace_manifest.json"

    def test_read_hashes_returns_empty_when_missing(self, store):
        assert store.read_hashes(StageId.INFERRED_EDGES) == {}

    def test_read_hashes_handles_corrupt_json(self, store):
        path = store.hashes_path(StageId.INFERRED_EDGES)
        path.write_text("corrupt!")
        assert store.read_hashes(StageId.INFERRED_EDGES) == {}

    def test_structural_hashes_read_from_file_hashes_key(self, store):
        manifest = {
            "built_at": "2026-04-04",
            "file_hashes": {"src/main.py": "sha256:aaa", "src/lib.py": "sha256:bbb"},
            "counts": {"nodes_total": 100},
        }
        store.write_provenance(StageId.STRUCTURAL, manifest)

        result = store.read_hashes(StageId.STRUCTURAL)
        assert result == {"src/main.py": "sha256:aaa", "src/lib.py": "sha256:bbb"}

    def test_structural_hashes_empty_when_no_file_hashes_key(self, store):
        manifest = {"built_at": "2026-04-04", "counts": {"nodes_total": 100}}
        store.write_provenance(StageId.STRUCTURAL, manifest)
        assert store.read_hashes(StageId.STRUCTURAL) == {}

    def test_format_version_guard_rejects_orchestrator_metadata(self, store):
        """Phase 60D-4: Hash file containing orchestrator metadata should be rejected."""
        path = store.hashes_path(StageId.INFERRED_EDGES)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "format_version": "2.0",
            "stage_id": "inferred_edges",
            "quality": {"total_items": 4139},
        }))
        assert store.read_hashes(StageId.INFERRED_EDGES) == {}

    def test_write_hashes_embedded_merges_into_provenance(self, store):
        """Writing embedded hashes preserves other provenance data."""
        store.write_provenance(StageId.STRUCTURAL, {
            "built_at": "2026-04-04",
            "counts": {"nodes_total": 100},
        })
        store.write_hashes(StageId.STRUCTURAL, {"src/a.py": "sha256:aaa"})

        provenance = store.read_provenance(StageId.STRUCTURAL)
        assert provenance["built_at"] == "2026-04-04"
        assert provenance["file_hashes"] == {"src/a.py": "sha256:aaa"}


# ── Quality metrics ────────────────────────────────────────────


class TestQualityAndStats:
    def test_read_quality_from_provenance(self, store):
        data = {"quality": {"total_items": 100, "processed": 95, "avg_confidence": 0.87}}
        store.write_provenance(StageId.ENRICHMENT, data)

        quality = store.read_quality(StageId.ENRICHMENT)
        assert quality is not None
        assert quality["total_items"] == 100
        assert quality["avg_confidence"] == 0.87

    def test_read_quality_returns_none_when_missing(self, store):
        assert store.read_quality(StageId.ENRICHMENT) is None

    def test_read_quality_returns_none_when_no_quality_key(self, store):
        store.write_provenance(StageId.ENRICHMENT, {"stage_id": "enrichment"})
        assert store.read_quality(StageId.ENRICHMENT) is None

    def test_read_graph_stats_from_structural_manifest(self, store):
        manifest = {"counts": {"nodes_total": 51072, "edges_total": 78589}}
        store.write_provenance(StageId.STRUCTURAL, manifest)

        stats = store.read_graph_stats()
        assert stats["node_count"] == 51072
        assert stats["edge_count"] == 78589

    def test_read_graph_stats_fallback_files_parsed(self, store):
        manifest = {"counts": {"files_parsed": 1348}}
        store.write_provenance(StageId.STRUCTURAL, manifest)

        stats = store.read_graph_stats()
        assert stats["node_count"] == 1348

    def test_read_graph_stats_defaults_to_zeros(self, store):
        stats = store.read_graph_stats()
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0

    def test_age_summary_all_stages(self, store):
        summary = store.age_summary()
        assert len(summary) == 11

    def test_age_summary_shows_present_and_missing(self, store):
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        summary = store.age_summary()
        assert summary["structural"]["status"] == "present"
        assert summary["enrichment"]["status"] == "missing"

    def test_age_summary_present_has_age_hours(self, store):
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        summary = store.age_summary()
        assert "age_hours" in summary["structural"]
        assert "last_modified" in summary["structural"]

    def test_touch_provenance_mtime(self, store):
        store.write_provenance(StageId.ENRICHMENT, {"stage_id": "enrichment"})
        target_mtime = time.time() - 3600  # 1 hour ago
        store.touch_provenance_mtime(StageId.ENRICHMENT, target_mtime)

        actual = store.provenance_mtime(StageId.ENRICHMENT)
        assert actual == pytest.approx(target_mtime, abs=1.0)

    def test_touch_provenance_mtime_noop_when_missing(self, store):
        # Should not raise
        store.touch_provenance_mtime(StageId.ENRICHMENT, time.time())
