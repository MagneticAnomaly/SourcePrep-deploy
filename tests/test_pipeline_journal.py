"""
Tests for Phase 25: Pipeline Journal + Checkpoint + Recovery
"""

import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── Journal Tests ────────────────────────────────────────────────

class TestPipelineJournal:
    """Test the PipelineJournal CRUD and recovery logic."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a fresh journal for each test."""
        from prep.services.pipeline_journal import PipelineJournal
        self.db_path = tmp_path / "test_settings.db"
        self.journal = PipelineJournal()
        self.journal.init(self.db_path)
        yield
        self.journal.close()

    def test_start_run_creates_entry(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural", "catalogue"])
        assert run_id.startswith("run-")
        entry = self.journal.get_run(run_id)
        assert entry is not None
        assert entry.project_id == "proj-1"
        assert entry.group == "fast_sync"
        assert entry.status == "running"
        assert entry.stages == ["structural", "catalogue"]
        assert entry.current_stage == "structural"
        assert entry.current_stage_index == 0
        assert entry.started_at is not None

    def test_stage_lifecycle(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural", "catalogue"])
        self.journal.stage_started(run_id, "structural", 0)
        self.journal.stage_completed(run_id, "structural")

        entry = self.journal.get_run(run_id)
        assert entry.stage_results["structural"] == "completed"

    def test_run_completed(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        self.journal.stage_completed(run_id, "structural")
        self.journal.run_completed(run_id)

        entry = self.journal.get_run(run_id)
        assert entry.status == "completed"
        assert entry.finished_at is not None

    def test_run_cancelled(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        self.journal.run_cancelled(run_id)

        entry = self.journal.get_run(run_id)
        assert entry.status == "cancelled"
        assert entry.error == "Cancelled by user"

    def test_stage_failed(self):
        run_id = self.journal.start_run("proj-1", "deep_enrichment", ["enrichment"])
        self.journal.stage_failed(run_id, "enrichment", "OOM killed")

        entry = self.journal.get_run(run_id)
        assert entry.status == "failed"
        assert entry.error == "OOM killed"
        assert entry.stage_results["enrichment"] == "failed"

    def test_heartbeat_updates_timestamp(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        entry_before = self.journal.get_run(run_id)
        time.sleep(0.05)
        self.journal.heartbeat(run_id)
        entry_after = self.journal.get_run(run_id)
        assert entry_after.last_heartbeat > entry_before.last_heartbeat

    def test_recover_crashed_runs(self):
        # Create a "running" entry with a stale heartbeat
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        # Manually set heartbeat to the past
        conn = self.journal._require_conn()
        conn.execute(
            "UPDATE pipeline_runs SET last_heartbeat = ? WHERE run_id = ?",
            (time.time() - 120, run_id),
        )
        conn.commit()
        # Stop heartbeat thread so it doesn't update
        self.journal._stop_heartbeat(run_id)

        crashed = self.journal.recover_crashed_runs(timeout_s=60)
        assert len(crashed) == 1
        assert crashed[0].run_id == run_id
        assert crashed[0].status == "crashed"

    def test_recover_ignores_recent_heartbeat(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        # Heartbeat is fresh — should NOT be detected as crashed
        crashed = self.journal.recover_crashed_runs(timeout_s=60)
        assert len(crashed) == 0

    def test_resolve_crashed_run(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        conn = self.journal._require_conn()
        conn.execute(
            "UPDATE pipeline_runs SET status = 'crashed' WHERE run_id = ?",
            (run_id,),
        )
        conn.commit()
        self.journal._stop_heartbeat(run_id)

        resolved = self.journal.resolve_crashed_run(run_id, "resumed")
        assert resolved is True
        entry = self.journal.get_run(run_id)
        assert entry.status == "resumed"

    def test_get_crashed_runs_filtered(self):
        r1 = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        r2 = self.journal.start_run("proj-2", "fast_sync", ["structural"])
        conn = self.journal._require_conn()
        for rid in (r1, r2):
            conn.execute("UPDATE pipeline_runs SET status = 'crashed' WHERE run_id = ?", (rid,))
            self.journal._stop_heartbeat(rid)
        conn.commit()

        all_crashed = self.journal.get_crashed_runs()
        assert len(all_crashed) == 2

        p1_crashed = self.journal.get_crashed_runs("proj-1")
        assert len(p1_crashed) == 1
        assert p1_crashed[0].project_id == "proj-1"

    def test_get_active_run(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        active = self.journal.get_active_run("proj-1", "fast_sync")
        assert active is not None
        assert active.run_id == run_id

        none_active = self.journal.get_active_run("proj-1", "deep_enrichment")
        assert none_active is None

    def test_clear_project(self):
        r1 = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        r2 = self.journal.start_run("proj-2", "fast_sync", ["structural"])
        self.journal._stop_heartbeat(r1)
        self.journal._stop_heartbeat(r2)

        deleted = self.journal.clear_project("proj-1")
        assert deleted == 1
        assert self.journal.get_run(r1) is None
        assert self.journal.get_run(r2) is not None

    def test_set_checkpoint(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        self.journal.set_checkpoint(run_id, "/tmp/checkpoint_abc")
        entry = self.journal.get_run(run_id)
        assert entry.checkpoint_path == "/tmp/checkpoint_abc"

    def test_chain_deep_persisted(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"], chain_deep=True)
        entry = self.journal.get_run(run_id)
        assert entry.chain_deep is True

    def test_to_dict(self):
        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural", "catalogue"])
        entry = self.journal.get_run(run_id)
        d = entry.to_dict()
        assert d["run_id"] == run_id
        assert d["project_id"] == "proj-1"
        assert d["group"] == "fast_sync"
        assert d["status"] == "running"
        assert d["stages"] == ["structural", "catalogue"]

    def test_get_project_runs(self):
        r1 = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        self.journal.run_completed(r1)
        r2 = self.journal.start_run("proj-1", "deep_enrichment", ["enrichment"])
        self.journal._stop_heartbeat(r2)

        runs = self.journal.get_project_runs("proj-1")
        assert len(runs) == 2
        # Most recent first
        assert runs[0].run_id == r2


# ── Checkpoint Tests ─────────────────────────────────────────────

class TestPipelineCheckpoint:
    """Test checkpoint creation, verification, and restoration."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.index_dir = tmp_path / "index"
        self.index_dir.mkdir()
        # Create some trace files
        (self.index_dir / "trace_nodes.jsonl").write_text(
            '{"id": "node-1", "kind": "function"}\n'
            '{"id": "node-2", "kind": "class"}\n'
        )
        (self.index_dir / "trace_edges.jsonl").write_text(
            '{"source": "node-1", "target": "node-2"}\n'
        )
        (self.index_dir / "trace_manifest.json").write_text(
            '{"version": 1, "counts": {"nodes": 2, "edges": 1}}'
        )
        (self.index_dir / "trace_epistemic.jsonl").write_text(
            '{"node_id": "node-1", "confidence": 0.8}\n'
        )

    def test_create_checkpoint_for_destructive_stage(self):
        from prep.services.pipeline_checkpoint import create_checkpoint

        cp_path = create_checkpoint(self.index_dir, "run-abc", "deepening")
        assert cp_path is not None
        cp = Path(cp_path)
        assert (cp / "trace_nodes.jsonl").exists()
        assert (cp / "trace_edges.jsonl").exists()
        assert (cp / "trace_epistemic.jsonl").exists()
        assert (cp / "trace_manifest.json").exists()

    def test_no_checkpoint_for_safe_stage(self):
        from prep.services.pipeline_checkpoint import create_checkpoint

        cp_path = create_checkpoint(self.index_dir, "run-abc", "structural")
        assert cp_path is None

    def test_verify_valid_files(self):
        from prep.services.pipeline_checkpoint import verify_trace_files

        valid, corrupt = verify_trace_files(self.index_dir)
        assert valid is True
        assert corrupt == []

    def test_verify_corrupt_jsonl(self):
        from prep.services.pipeline_checkpoint import verify_trace_files

        # Write corrupt JSONL
        (self.index_dir / "trace_nodes.jsonl").write_text(
            '{"id": "node-1"}\n'
            'THIS IS NOT JSON\n'
        )
        valid, corrupt = verify_trace_files(self.index_dir)
        assert valid is False
        assert "trace_nodes.jsonl" in corrupt

    def test_verify_corrupt_json(self):
        from prep.services.pipeline_checkpoint import verify_trace_files

        (self.index_dir / "trace_manifest.json").write_text("NOT JSON {{{")
        valid, corrupt = verify_trace_files(self.index_dir)
        assert valid is False
        assert "trace_manifest.json" in corrupt

    def test_restore_checkpoint(self):
        from prep.services.pipeline_checkpoint import create_checkpoint, restore_checkpoint

        cp_path = create_checkpoint(self.index_dir, "run-abc", "deepening")
        # Corrupt the live file
        (self.index_dir / "trace_epistemic.jsonl").write_text("CORRUPT DATA")
        # Restore
        restored = restore_checkpoint(cp_path, self.index_dir)
        assert restored >= 1
        # Verify restored content
        content = (self.index_dir / "trace_epistemic.jsonl").read_text()
        assert '"confidence": 0.8' in content

    def test_auto_heal(self):
        from prep.services.pipeline_checkpoint import create_checkpoint, auto_heal

        cp_path = create_checkpoint(self.index_dir, "run-abc", "enrichment")
        # Corrupt a file
        (self.index_dir / "trace_epistemic.jsonl").write_text("CORRUPT!")
        results = auto_heal(self.index_dir, cp_path)
        assert results.get("trace_epistemic.jsonl") == "healed"

    def test_auto_heal_no_backup(self):
        from prep.services.pipeline_checkpoint import auto_heal

        (self.index_dir / "trace_epistemic.jsonl").write_text("CORRUPT!")
        results = auto_heal(self.index_dir, None)
        assert results.get("trace_epistemic.jsonl") == "no_backup"

    def test_cleanup_checkpoint(self):
        from prep.services.pipeline_checkpoint import create_checkpoint, cleanup_checkpoint

        cp_path = create_checkpoint(self.index_dir, "run-abc", "deepening")
        assert Path(cp_path).is_dir()
        cleanup_checkpoint(cp_path)
        assert not Path(cp_path).exists()

    def test_cleanup_all_checkpoints(self):
        from prep.services.pipeline_checkpoint import create_checkpoint, cleanup_all_checkpoints

        create_checkpoint(self.index_dir, "run-1", "deepening")
        create_checkpoint(self.index_dir, "run-2", "enrichment")
        assert (self.index_dir / ".checkpoints").is_dir()
        cleanup_all_checkpoints(self.index_dir)
        assert not (self.index_dir / ".checkpoints").exists()


# ── Integration: Orchestrator + Journal ──────────────────────────

class TestOrchestratorJournalIntegration:
    """Test that PipelineOrchestrator writes to the journal on transitions."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from prep.services.pipeline_journal import PipelineJournal
        self.db_path = tmp_path / "test_settings.db"
        self.journal = PipelineJournal()
        self.journal.init(self.db_path)

        # Patch the module-level journal singleton
        self._journal_patch = patch(
            "prep.services.pipeline_journal.journal", self.journal
        )
        self._journal_patch.start()
        yield
        self._journal_patch.stop()
        self.journal.close()

    def test_start_group_writes_journal(self):
        from prep.services.build_orchestrator import BuildOrchestrator
        from prep.services.pipeline_orchestrator import (
            PipelineOrchestrator, FAST_SYNC_STAGES,
        )

        orch = BuildOrchestrator()
        pipeline = PipelineOrchestrator(orchestrator=orch)

        # Mock the worker to not actually run
        with patch("prep.services.pipeline_orchestrator.WorkerFactory.create_worker") as mock_worker:
            mock_fn = MagicMock(return_value={"stage": "structural"})
            mock_worker.return_value = mock_fn
            pipeline.run_fast_sync("proj-1")

        # Check journal has an entry
        runs = self.journal.get_project_runs("proj-1")
        assert len(runs) == 1
        assert runs[0].group == "fast_sync"
        assert runs[0].status == "running"

    def test_cancel_writes_journal(self):
        from prep.services.build_orchestrator import BuildOrchestrator
        from prep.services.pipeline_orchestrator import PipelineOrchestrator

        orch = BuildOrchestrator()
        pipeline = PipelineOrchestrator(orchestrator=orch)

        with patch("prep.services.pipeline_orchestrator.WorkerFactory.create_worker") as mock_worker:
            mock_fn = MagicMock(return_value={"stage": "structural"})
            mock_worker.return_value = mock_fn
            pipeline.run_fast_sync("proj-1")

        pipeline.cancel_fast_sync("proj-1")

        runs = self.journal.get_project_runs("proj-1")
        assert len(runs) == 1
        assert runs[0].status == "cancelled"

    def test_resume_crashed_run(self):
        """Simulate a crash and verify resume creates a new run."""
        from prep.services.build_orchestrator import BuildOrchestrator
        from prep.services.pipeline_orchestrator import PipelineOrchestrator

        orch = BuildOrchestrator()
        pipeline = PipelineOrchestrator(orchestrator=orch)

        # Create a crashed entry manually
        run_id = self.journal.start_run(
            "proj-1", "fast_sync",
            ["structural", "catalogue", "validation", "knowledge"],
        )
        self.journal.stage_completed(run_id, "structural")
        self.journal.stage_started(run_id, "catalogue", 1)
        # Simulate crash: mark as crashed
        conn = self.journal._require_conn()
        conn.execute(
            "UPDATE pipeline_runs SET status = 'crashed' WHERE run_id = ?",
            (run_id,),
        )
        conn.commit()
        self.journal._stop_heartbeat(run_id)

        # Resume
        with patch("prep.services.pipeline_orchestrator.WorkerFactory.create_worker") as mock_worker:
            mock_fn = MagicMock(return_value={"stage": "catalogue"})
            mock_worker.return_value = mock_fn
            result = pipeline.resume_crashed_run(run_id)

        assert result is True

        # Original run should be marked as "resumed"
        original = self.journal.get_run(run_id)
        assert original.status == "resumed"

        # A new run should exist
        runs = self.journal.get_project_runs("proj-1")
        assert len(runs) == 2
        new_run = [r for r in runs if r.run_id != run_id][0]
        assert new_run.status == "running"
        assert new_run.current_stage_index == 1  # resumed from catalogue

    def test_discard_crashed_run(self):
        from prep.services.build_orchestrator import BuildOrchestrator
        from prep.services.pipeline_orchestrator import PipelineOrchestrator

        orch = BuildOrchestrator()
        pipeline = PipelineOrchestrator(orchestrator=orch)

        run_id = self.journal.start_run("proj-1", "fast_sync", ["structural"])
        conn = self.journal._require_conn()
        conn.execute(
            "UPDATE pipeline_runs SET status = 'crashed' WHERE run_id = ?",
            (run_id,),
        )
        conn.commit()
        self.journal._stop_heartbeat(run_id)

        result = pipeline.discard_crashed_run(run_id)
        assert result is True
        entry = self.journal.get_run(run_id)
        assert entry.status == "discarded"

    def test_startup_recovery(self):
        from prep.services.build_orchestrator import BuildOrchestrator
        from prep.services.pipeline_orchestrator import PipelineOrchestrator

        orch = BuildOrchestrator()
        pipeline = PipelineOrchestrator(orchestrator=orch)

        # Create a stale "running" entry
        run_id = self.journal.start_run("proj-1", "deep_enrichment", ["enrichment"])
        conn = self.journal._require_conn()
        conn.execute(
            "UPDATE pipeline_runs SET last_heartbeat = ? WHERE run_id = ?",
            (time.time() - 120, run_id),
        )
        conn.commit()
        self.journal._stop_heartbeat(run_id)

        # Patch out the auto-heal calls that need project registry
        with patch("prep.services.pipeline_orchestrator.PipelineOrchestrator._create_checkpoint_if_needed"):
            with patch("prep.services.pipeline_checkpoint.verify_trace_files", return_value=(True, [])):
                with patch("prep.services.project_helpers.require_project"):
                    with patch("prep.core.project_registry.project_index_dir", return_value=Path("/tmp")):
                        crashed = pipeline.startup_recovery()

        assert len(crashed) == 1
        assert crashed[0]["run_id"] == run_id
        assert crashed[0]["status"] == "crashed"
