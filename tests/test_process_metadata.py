"""
Tests for Phase 49: Process Metadata & Data Provenance.

Tests:
- StageManifest serialization/deserialization
- Provenance helpers (version, hashing, quality aggregation)
- PipelineRunMetadata lifecycle
- PipelineRunHistory CRUD
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest


# ── StageManifest Tests ──────────────────────────────────────────

class TestStageManifest:
    def test_roundtrip(self):
        from prep.core.stage_manifest import StageManifest
        m = StageManifest(
            stage_id="catalogue",
            run_id="run-abc",
            project_id="proj-1",
            codrag_version="0.9.0",
            engine_backend="rust",
            started_at="2026-03-11T23:45:00Z",
            finished_at="2026-03-11T23:47:30Z",
            elapsed_seconds=150.5,
            model={"provider": "ollama", "model_name": "qwen3:14b"},
            quality={"total_items": 247, "avg_confidence": 0.87},
        )
        d = m.to_dict()
        assert d["stage_id"] == "catalogue"
        assert d["run_id"] == "run-abc"
        assert d["codrag_version"] == "0.9.0"
        assert d["model"]["provider"] == "ollama"
        assert d["quality"]["avg_confidence"] == 0.87

        m2 = StageManifest.from_dict(d)
        assert m2.stage_id == "catalogue"
        assert m2.model["model_name"] == "qwen3:14b"

    def test_save_load(self, tmp_path):
        from prep.core.stage_manifest import (
            StageManifest, save_stage_manifest, load_stage_manifest,
        )
        m = StageManifest(stage_id="enrichment", codrag_version="0.9.0")
        path = tmp_path / "test_manifest.json"
        save_stage_manifest(m, path)
        assert path.exists()

        loaded = load_stage_manifest(path)
        assert loaded is not None
        assert loaded.stage_id == "enrichment"

    def test_load_missing(self, tmp_path):
        from prep.core.stage_manifest import load_stage_manifest
        result = load_stage_manifest(tmp_path / "nonexistent.json")
        assert result is None

    def test_create_stage_manifest(self):
        from prep.core.stage_manifest import create_stage_manifest
        m = create_stage_manifest("catalogue", run_id="run-1", project_id="proj-1")
        assert m.stage_id == "catalogue"
        assert m.run_id == "run-1"
        assert m.started_at is not None
        assert m.codrag_version != ""

    def test_minimal_manifest(self):
        from prep.core.stage_manifest import StageManifest
        m = StageManifest()
        d = m.to_dict()
        assert d["format_version"] == "2.0"
        assert d["stage_id"] == ""
        assert "model" not in d
        assert "quality" not in d

    def test_optional_fields_excluded_when_none(self):
        from prep.core.stage_manifest import StageManifest
        m = StageManifest(stage_id="test")
        d = m.to_dict()
        assert "run_id" not in d
        assert "model" not in d
        assert "quality" not in d
        assert "errors" not in d


# ── Provenance Tests ─────────────────────────────────────────────

class TestProvenance:
    def test_get_codrag_version(self):
        from prep.core.provenance import get_codrag_version
        v = get_codrag_version()
        assert isinstance(v, str)

    def test_get_engine_backend(self):
        from prep.core.provenance import get_engine_backend
        backend = get_engine_backend()
        assert backend in ("rust", "python")

    def test_compute_file_hash(self, tmp_path):
        from prep.core.provenance import compute_file_hash
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = compute_file_hash(f)
        assert h != ""
        assert ":" in h  # format is "algorithm:hexdigest"

    def test_compute_file_hash_missing(self, tmp_path):
        from prep.core.provenance import compute_file_hash
        h = compute_file_hash(tmp_path / "nonexistent.txt")
        assert h == ""

    def test_get_file_metadata(self, tmp_path):
        from prep.core.provenance import get_file_metadata
        f = tmp_path / "test.jsonl"
        f.write_text('{"a":1}\n{"b":2}\n{"c":3}\n')
        meta = get_file_metadata(f)
        assert meta["size_bytes"] > 0
        assert meta["item_count"] == 3
        assert "hash" in meta

    def test_get_file_metadata_missing(self, tmp_path):
        from prep.core.provenance import get_file_metadata
        meta = get_file_metadata(tmp_path / "nonexistent.jsonl")
        assert meta == {}

    def test_aggregate_quality_metrics(self, tmp_path):
        from prep.core.provenance import aggregate_quality_metrics
        f = tmp_path / "test.jsonl"
        entries = [
            {"confidence": 0.9},
            {"confidence": 0.8},
            {"confidence": 0.7},
        ]
        f.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        q = aggregate_quality_metrics(f, "confidence")
        assert q["total_items"] == 3
        assert q["processed"] == 3
        assert abs(q["avg_confidence"] - 0.8) < 0.01
        assert q["min_confidence"] == 0.7
        assert q["max_confidence"] == 0.9
        assert q["success_rate"] == 1.0

    def test_aggregate_quality_with_missing_field(self, tmp_path):
        from prep.core.provenance import aggregate_quality_metrics
        f = tmp_path / "test.jsonl"
        entries = [
            {"confidence": 0.9},
            {"other_field": "no confidence"},
            {"confidence": 0.7},
        ]
        f.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        q = aggregate_quality_metrics(f, "confidence")
        assert q["total_items"] == 3
        assert q["processed"] == 2
        assert q["failed"] == 1

    def test_compute_throughput(self):
        from prep.core.provenance import compute_throughput
        t = compute_throughput(100, 10.0)
        assert t["items_per_second"] == 10.0
        assert "bytes_per_second" not in t

    def test_compute_throughput_with_bytes(self):
        from prep.core.provenance import compute_throughput
        t = compute_throughput(100, 10.0, total_bytes=50000)
        assert t["items_per_second"] == 10.0
        assert t["bytes_per_second"] == 5000.0

    def test_compute_throughput_zero_elapsed(self):
        from prep.core.provenance import compute_throughput
        t = compute_throughput(100, 0)
        assert t == {}

    def test_extract_model_info(self):
        from prep.core.provenance import extract_model_info_from_llm_client

        class FakeLLM:
            provider = "ollama"
            endpoint_id = "local-ollama"
            model = "qwen3:14b"
            base_url = "http://localhost:11434"

        info = extract_model_info_from_llm_client(FakeLLM())
        assert info["provider"] == "ollama"
        assert info["model_name"] == "qwen3:14b"

    def test_extract_model_info_none(self):
        from prep.core.provenance import extract_model_info_from_llm_client
        assert extract_model_info_from_llm_client(None) == {}

    def test_model_breakdown_single_model(self, tmp_path):
        from prep.core.provenance import aggregate_model_breakdown
        f = tmp_path / "test.jsonl"
        entries = [
            {"model": "qwen3:14b", "confidence": 0.9},
            {"model": "qwen3:14b", "confidence": 0.8},
            {"model": "qwen3:14b", "confidence": 0.7},
        ]
        f.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        result = aggregate_model_breakdown(f)
        # Single model → returns None (no breakdown needed)
        assert result is None

    def test_model_breakdown_two_models(self, tmp_path):
        from prep.core.provenance import aggregate_model_breakdown
        f = tmp_path / "test.jsonl"
        entries = [
            {"model": "qwen3:8b", "confidence": 0.8},
            {"model": "qwen3:8b", "confidence": 0.7},
            {"model": "qwen3:14b", "confidence": 0.9},
            {"model": "qwen3:14b", "confidence": 0.85},
            {"model": "qwen3:14b", "confidence": 0.95},
        ]
        f.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        result = aggregate_model_breakdown(f)
        assert result is not None
        assert len(result) == 2
        # Sorted by count descending — 14b has 3, 8b has 2
        assert result[0]["model"] == "qwen3:14b"
        assert result[0]["count"] == 3
        assert result[0]["percentage"] == 60.0
        assert abs(result[0]["avg_confidence"] - 0.9) < 0.01
        assert result[1]["model"] == "qwen3:8b"
        assert result[1]["count"] == 2
        assert result[1]["percentage"] == 40.0

    def test_model_breakdown_three_models(self, tmp_path):
        from prep.core.provenance import aggregate_model_breakdown
        f = tmp_path / "test.jsonl"
        entries = [
            {"model": "a", "confidence": 0.9},
            {"model": "b", "confidence": 0.8},
            {"model": "b", "confidence": 0.7},
            {"model": "c", "confidence": 0.6},
        ]
        f.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        result = aggregate_model_breakdown(f)
        assert result is not None
        assert len(result) == 3
        assert result[0]["model"] == "b"  # 2 entries, most common

    def test_model_breakdown_missing_file(self, tmp_path):
        from prep.core.provenance import aggregate_model_breakdown
        result = aggregate_model_breakdown(tmp_path / "nonexistent.jsonl")
        assert result is None

    def test_model_breakdown_empty_file(self, tmp_path):
        from prep.core.provenance import aggregate_model_breakdown
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        result = aggregate_model_breakdown(f)
        assert result is None

    def test_model_breakdown_no_model_field(self, tmp_path):
        from prep.core.provenance import aggregate_model_breakdown
        f = tmp_path / "test.jsonl"
        entries = [
            {"confidence": 0.9},
            {"confidence": 0.8},
        ]
        f.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        # All entries map to "unknown" → single model → None
        result = aggregate_model_breakdown(f)
        assert result is None

    def test_model_breakdown_epistemic_confidence(self, tmp_path):
        from prep.core.provenance import aggregate_model_breakdown
        f = tmp_path / "test.jsonl"
        entries = [
            {"model": "qwen3.5-27b", "epistemic_confidence": 0.92},
            {"model": "qwen3:14b", "epistemic_confidence": 0.85},
        ]
        f.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        result = aggregate_model_breakdown(f, confidence_field="epistemic_confidence")
        assert result is not None
        assert len(result) == 2
        # Both have 1 entry each, sorted alphabetically by count (tie), then by insertion
        for r in result:
            assert "avg_confidence" in r


# ── PipelineRunMetadata Tests ────────────────────────────────────

class TestPipelineRunMetadata:
    def test_create_run_metadata(self):
        from prep.services.pipeline_metadata import create_run_metadata
        meta = create_run_metadata(
            run_id="run-1",
            project_id="proj-1",
            group="fast_sync",
            stage_ids=["structural", "catalogue", "knowledge"],
        )
        assert meta.run_id == "run-1"
        assert meta.project_id == "proj-1"
        assert meta.group == "fast_sync"
        assert meta.status == "running"
        assert len(meta.stages) == 3
        assert meta.stages[0].stage_id == "structural"
        assert meta.started_at is not None
        assert meta.codrag_version != ""

    def test_mark_stage_completed(self):
        from prep.services.pipeline_metadata import (
            create_run_metadata, mark_stage_completed,
        )
        meta = create_run_metadata("run-1", "proj-1", "fast_sync", ["structural", "catalogue"])
        mark_stage_completed(meta, "structural", worker_result={
            "stage": "structural",
            "nodes": 247,
            "_model_info": {"provider": "rust", "model_name": "tree-sitter"},
            "_stage_timing": {"started_at": time.time() - 10, "elapsed": 10.0},
        })
        s = meta.stages[0]
        assert s.status == "completed"
        assert s.finished_at is not None
        assert s.elapsed_seconds == 10.0
        assert s.model["provider"] == "rust"
        assert meta.models_used["structural"]["provider"] == "rust"
        # Private keys should be stripped from worker_result
        assert "_model_info" not in s.worker_result
        assert "_stage_timing" not in s.worker_result
        assert s.worker_result["nodes"] == 247

    def test_mark_stage_failed(self):
        from prep.services.pipeline_metadata import (
            create_run_metadata, mark_stage_failed,
        )
        meta = create_run_metadata("run-1", "proj-1", "fast_sync", ["structural"])
        mark_stage_failed(meta, "structural", "Build crashed")
        assert meta.stages[0].status == "failed"
        assert meta.stages[0].worker_result["error"] == "Build crashed"

    def test_finalize_run_metadata(self):
        from prep.services.pipeline_metadata import (
            create_run_metadata, mark_stage_completed,
            finalize_run_metadata,
        )
        meta = create_run_metadata("run-1", "proj-1", "fast_sync", ["structural"])
        mark_stage_completed(meta, "structural")
        finalize_run_metadata(meta, status="completed")
        assert meta.status == "completed"
        assert meta.finished_at is not None
        assert meta.elapsed_seconds is not None

    def test_save_load_roundtrip(self, tmp_path):
        from prep.services.pipeline_metadata import (
            create_run_metadata, save_run_metadata, load_run_metadata,
        )
        meta = create_run_metadata("run-1", "proj-1", "fast_sync", ["structural"])
        save_run_metadata(meta, tmp_path)

        loaded = load_run_metadata(tmp_path)
        assert loaded is not None
        assert loaded.run_id == "run-1"
        assert loaded.group == "fast_sync"
        assert len(loaded.stages) == 1

    def test_to_dict_includes_format_version(self):
        from prep.services.pipeline_metadata import create_run_metadata
        meta = create_run_metadata("run-1", "proj-1", "fast_sync", ["structural"])
        d = meta.to_dict()
        assert d["format_version"] == "1.0"


# ── PipelineRunHistory Tests ─────────────────────────────────────

class TestPipelineRunHistory:
    @pytest.fixture
    def history_db(self, tmp_path):
        from prep.services.pipeline_history import PipelineRunHistory
        h = PipelineRunHistory()
        db_path = tmp_path / "test.db"
        h.init(db_path)
        yield h
        h.close()

    def test_record_and_get(self, history_db):
        from prep.services.pipeline_metadata import create_run_metadata, finalize_run_metadata
        meta = create_run_metadata("run-1", "proj-1", "fast_sync", ["structural", "catalogue"])
        finalize_run_metadata(meta, status="completed")

        history_db.record_run(meta, metadata_file="/path/to/metadata.json")

        entry = history_db.get_run("run-1")
        assert entry is not None
        assert entry.project_id == "proj-1"
        assert entry.group == "fast_sync"
        assert entry.status == "completed"
        assert entry.metadata_file == "/path/to/metadata.json"

    def test_get_project_runs(self, history_db):
        from prep.services.pipeline_metadata import create_run_metadata, finalize_run_metadata

        for i in range(5):
            meta = create_run_metadata(f"run-{i}", "proj-1", "fast_sync", ["structural"])
            finalize_run_metadata(meta, status="completed")
            history_db.record_run(meta)

        runs = history_db.get_project_runs("proj-1", limit=3)
        assert len(runs) == 3

    def test_get_project_runs_filter_group(self, history_db):
        from prep.services.pipeline_metadata import create_run_metadata, finalize_run_metadata

        meta1 = create_run_metadata("run-fast", "proj-1", "fast_sync", ["structural"])
        finalize_run_metadata(meta1, status="completed")
        history_db.record_run(meta1)

        meta2 = create_run_metadata("run-deep", "proj-1", "deep_enrichment", ["enrichment"])
        finalize_run_metadata(meta2, status="completed")
        history_db.record_run(meta2)

        runs = history_db.get_project_runs("proj-1", group="fast_sync")
        assert len(runs) == 1
        assert runs[0].group == "fast_sync"

    def test_get_latest_run(self, history_db):
        from prep.services.pipeline_metadata import create_run_metadata, finalize_run_metadata

        meta = create_run_metadata("run-latest", "proj-1", "fast_sync", ["structural"])
        finalize_run_metadata(meta, status="completed")
        history_db.record_run(meta)

        latest = history_db.get_latest_run("proj-1")
        assert latest is not None
        assert latest.run_id == "run-latest"

    def test_count_runs(self, history_db):
        from prep.services.pipeline_metadata import create_run_metadata, finalize_run_metadata

        for i in range(3):
            meta = create_run_metadata(f"run-{i}", "proj-1", "fast_sync", ["structural"])
            finalize_run_metadata(meta, status="completed")
            history_db.record_run(meta)

        assert history_db.count_runs("proj-1") == 3
        assert history_db.count_runs("proj-2") == 0
        assert history_db.count_runs() == 3

    def test_clear_project(self, history_db):
        from prep.services.pipeline_metadata import create_run_metadata, finalize_run_metadata

        meta = create_run_metadata("run-1", "proj-1", "fast_sync", ["structural"])
        finalize_run_metadata(meta, status="completed")
        history_db.record_run(meta)

        assert history_db.count_runs("proj-1") == 1
        cleared = history_db.clear_project("proj-1")
        assert cleared == 1
        assert history_db.count_runs("proj-1") == 0

    def test_get_run_not_found(self, history_db):
        entry = history_db.get_run("nonexistent")
        assert entry is None

    def test_models_used_stored(self, history_db):
        from prep.services.pipeline_metadata import (
            create_run_metadata, mark_stage_completed, finalize_run_metadata,
        )
        meta = create_run_metadata("run-model", "proj-1", "fast_sync", ["catalogue"])
        mark_stage_completed(meta, "catalogue", worker_result={
            "stage": "catalogue",
            "_model_info": {"provider": "ollama", "model_name": "qwen3:14b"},
            "_stage_timing": {"started_at": time.time(), "elapsed": 5.0},
        })
        finalize_run_metadata(meta, status="completed")
        history_db.record_run(meta)

        entry = history_db.get_run("run-model")
        assert entry.models_used is not None
        assert "catalogue" in entry.models_used
        assert entry.models_used["catalogue"]["model_name"] == "qwen3:14b"


# ── Stages Mapping Tests ─────────────────────────────────────────

class TestStagesMappings:
    def test_all_stages_have_manifest_file(self):
        from prep.services.pipeline.stages import StageId, STAGE_MANIFEST_FILE
        for stage in StageId:
            assert stage in STAGE_MANIFEST_FILE, f"Missing manifest file for {stage.value}"

    def test_all_stages_have_output_file_mapping(self):
        from prep.services.pipeline.stages import StageId, STAGE_OUTPUT_FILE
        for stage in StageId:
            assert stage in STAGE_OUTPUT_FILE, f"Missing output file mapping for {stage.value}"

    def test_all_stages_have_confidence_field_mapping(self):
        from prep.services.pipeline.stages import StageId, STAGE_CONFIDENCE_FIELD
        for stage in StageId:
            assert stage in STAGE_CONFIDENCE_FIELD, f"Missing confidence field for {stage.value}"
