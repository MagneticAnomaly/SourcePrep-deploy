# Phase 72 Stage 1: ManifestStore Extraction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract all manifest I/O from the 4,253-line `orchestrator.py` god class into a focused `ManifestStore` class, establishing the first clean module boundary for the Phase 72 decomposition.

**Architecture:** ManifestStore owns ALL manifest file reads/writes (provenance manifests, worker hash caches, manifest mtime queries, graph stats reads). The orchestrator delegates to ManifestStore instead of doing raw file I/O. Atomic writes (tmp + fsync + rename) become the default for all manifest writes.

**Tech Stack:** Python 3.11, pathlib, json, tempfile, os (atomic writes), pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/prep/services/pipeline/manifest_store.py` | **Create** | All manifest I/O: read/write provenance, read/write hashes, mtime queries, graph stats, age summaries, atomic writes |
| `src/prep/services/pipeline/orchestrator.py` | **Modify** | Replace inline manifest I/O with ManifestStore calls |
| `src/prep/services/pipeline/__init__.py` | **Modify** | Re-export ManifestStore |
| `tests/test_manifest_store.py` | **Create** | Unit tests for ManifestStore |

## Key Design Decisions

1. **ManifestStore is stateless** — it takes an `idx_dir: Path` and does file I/O. No caching, no locks. The orchestrator owns the lifecycle.
2. **Atomic writes by default** — all `write_*` methods use tmp + fsync + rename. This fixes the non-atomic write bug in `save_stage_manifest()`.
3. **Two manifest namespaces** preserved: `{stage}_manifest.json` (provenance) and `{stage}_hashes.json` (worker hash cache). These NEVER share a filename.
4. **`trace_manifest.json` dual-purpose** handled explicitly — it contains both provenance AND `file_hashes` inside one file. ManifestStore provides separate `read_structural_hashes()` / `write_structural_hashes()` that surgically update only the `file_hashes` key.

---

### Task 1: Create ManifestStore with provenance read/write and atomic writes

**Files:**
- Create: `src/prep/services/pipeline/manifest_store.py`
- Create: `tests/test_manifest_store.py`

- [ ] **Step 1: Write failing tests for provenance read/write**

```python
"""Tests for ManifestStore — Phase 72 Stage 1."""
import json
import os
import pytest
from pathlib import Path

from prep.services.pipeline.manifest_store import ManifestStore
from prep.services.pipeline.stages import StageId


@pytest.fixture
def idx_dir(tmp_path):
    """Create a temporary index directory."""
    return tmp_path


@pytest.fixture
def store(idx_dir):
    return ManifestStore(idx_dir)


class TestProvenanceManifest:
    def test_write_and_read_provenance(self, store, idx_dir):
        data = {"format_version": "2.0", "stage_id": "enrichment", "quality": {"total_items": 100}}
        store.write_provenance(StageId.ENRICHMENT, data)
        
        result = store.read_provenance(StageId.ENRICHMENT)
        assert result is not None
        assert result["stage_id"] == "enrichment"
        assert result["quality"]["total_items"] == 100

    def test_provenance_path_uses_stage_manifest_file(self, store):
        path = store.provenance_path(StageId.ENRICHMENT)
        assert path.name == "trace_epistemic_manifest.json"

    def test_provenance_exists_false_when_missing(self, store):
        assert store.provenance_exists(StageId.ENRICHMENT) is False

    def test_provenance_exists_true_after_write(self, store):
        store.write_provenance(StageId.ENRICHMENT, {"stage_id": "enrichment"})
        assert store.provenance_exists(StageId.ENRICHMENT) is True

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
        """Verify no partial writes — file appears atomically."""
        store.write_provenance(StageId.ENRICHMENT, {"stage_id": "enrichment"})
        # No .tmp files should remain
        tmp_files = list(idx_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_read_provenance_handles_corrupt_json(self, store, idx_dir):
        path = store.provenance_path(StageId.ENRICHMENT)
        path.write_text("not valid json {{{")
        assert store.read_provenance(StageId.ENRICHMENT) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_manifest_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prep.services.pipeline.manifest_store'`

- [ ] **Step 3: Write ManifestStore class with provenance methods**

```python
"""
ManifestStore — Centralized manifest I/O with namespace separation.

Phase 72 Stage 1: Extracted from orchestrator.py to eliminate
cross-concern interference between provenance manifests and
worker hash manifests.

Two file types per stage:
- Provenance manifest: {stage}_manifest.json -> model info, timing, quality
- Worker hash manifest: {stage}_hashes.json -> per-file content hashes

These NEVER share a filename.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from .stages import (
    StageId,
    STAGE_MANIFEST_FILE,
    STAGE_OUTPUT_FILE,
    FAST_SYNC_STAGES,
    DEEP_ENRICHMENT_STAGES,
)

logger = logging.getLogger(__name__)


class ManifestStore:
    """Centralized manifest I/O with namespace separation.

    Stateless — takes an index directory and does file I/O.
    All writes are atomic (tmp + fsync + rename).
    """

    def __init__(self, idx_dir: Path) -> None:
        self.idx_dir = Path(idx_dir)

    # ── Atomic write helper ────────────────────────────────────

    def _atomic_write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON atomically: tmp file -> fsync -> rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = None
        tmp_path = None
        try:
            fd = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".tmp",
                dir=str(path.parent),
                delete=False,
                encoding="utf-8",
            )
            tmp_path = fd.name
            json.dump(data, fd, indent=2, ensure_ascii=False)
            fd.flush()
            os.fsync(fd.fileno())
            fd.close()
            fd = None
            os.rename(tmp_path, path)
            tmp_path = None  # rename succeeded, don't unlink
        finally:
            if fd is not None:
                fd.close()
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ── Provenance manifests ───────────────────────────────────

    def provenance_path(self, stage: StageId) -> Path:
        """Path to the provenance manifest for a stage."""
        filename = STAGE_MANIFEST_FILE.get(stage, f"{stage.value}_manifest.json")
        return self.idx_dir / filename

    def provenance_exists(self, stage: StageId) -> bool:
        """Check if a provenance manifest exists and is non-empty."""
        p = self.provenance_path(stage)
        return p.exists() and p.stat().st_size > 0

    def provenance_mtime(self, stage: StageId) -> float:
        """Get the mtime of a provenance manifest. Returns 0.0 if missing."""
        p = self.provenance_path(stage)
        if p.exists():
            return p.stat().st_mtime
        return 0.0

    def write_provenance(self, stage: StageId, data: Dict[str, Any]) -> None:
        """Write a provenance manifest atomically."""
        self._atomic_write_json(self.provenance_path(stage), data)

    def read_provenance(self, stage: StageId) -> Optional[Dict[str, Any]]:
        """Read a provenance manifest. Returns None if missing or corrupt."""
        p = self.provenance_path(stage)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.debug("Failed to read provenance for %s", stage.value, exc_info=True)
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_manifest_store.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/manifest_store.py tests/test_manifest_store.py
git commit -m "feat(pipeline): add ManifestStore with provenance read/write and atomic writes"
```

---

### Task 2: Add worker hash manifest methods to ManifestStore

**Files:**
- Modify: `src/prep/services/pipeline/manifest_store.py`
- Modify: `tests/test_manifest_store.py`

- [ ] **Step 1: Write failing tests for hash manifest methods**

Add to `tests/test_manifest_store.py`:

```python
class TestWorkerHashManifest:
    def test_write_and_read_hashes(self, store):
        hashes = {"src/foo.py": "sha256:abc123", "src/bar.py": "sha256:def456"}
        store.write_hashes(StageId.INFERRED_EDGES, hashes)
        
        result = store.read_hashes(StageId.INFERRED_EDGES)
        assert result == hashes

    def test_hashes_path_uses_stage_hashes_json(self, store):
        path = store.hashes_path(StageId.INFERRED_EDGES)
        assert path.name == "trace_inferred_hashes.json"

    def test_hashes_path_for_structural(self, store):
        """Structural hashes live INSIDE trace_manifest.json, not a separate file."""
        path = store.hashes_path(StageId.STRUCTURAL)
        assert path.name == "trace_manifest.json"

    def test_read_hashes_returns_empty_when_missing(self, store):
        assert store.read_hashes(StageId.INFERRED_EDGES) == {}

    def test_read_hashes_handles_corrupt_json(self, store, idx_dir):
        path = store.hashes_path(StageId.INFERRED_EDGES)
        path.write_text("corrupt!")
        assert store.read_hashes(StageId.INFERRED_EDGES) == {}

    def test_structural_hashes_read_from_file_hashes_key(self, store, idx_dir):
        """Structural hash manifest is embedded inside trace_manifest.json."""
        manifest = {
            "built_at": "2026-04-04",
            "file_hashes": {"src/main.py": "sha256:aaa", "src/lib.py": "sha256:bbb"},
            "counts": {"nodes_total": 100},
        }
        store._atomic_write_json(store.provenance_path(StageId.STRUCTURAL), manifest)
        
        result = store.read_hashes(StageId.STRUCTURAL)
        assert result == {"src/main.py": "sha256:aaa", "src/lib.py": "sha256:bbb"}

    def test_structural_hashes_empty_when_no_file_hashes_key(self, store, idx_dir):
        manifest = {"built_at": "2026-04-04", "counts": {"nodes_total": 100}}
        store._atomic_write_json(store.provenance_path(StageId.STRUCTURAL), manifest)
        
        assert store.read_hashes(StageId.STRUCTURAL) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_manifest_store.py::TestWorkerHashManifest -v`
Expected: FAIL with `AttributeError: 'ManifestStore' object has no attribute 'write_hashes'`

- [ ] **Step 3: Add hash manifest methods to ManifestStore**

Add to `manifest_store.py` after the provenance methods:

```python
    # ── Known hash file overrides ──────────────────────────────
    # Most stages don't have a separate hash file. Only these do:
    _HASH_FILE_OVERRIDES: Dict[StageId, str] = {
        StageId.INFERRED_EDGES: "trace_inferred_hashes.json",
        # Future: add hash files for other workers here as they adopt
        # the IncrementalWorkerMixin (Phase 72 Stage 5).
    }

    # ── Worker hash manifests ──────────────────────────────────

    def hashes_path(self, stage: StageId) -> Path:
        """Path to the worker hash manifest for a stage.

        For STRUCTURAL, hashes are embedded inside trace_manifest.json
        (the ``file_hashes`` key). For INFERRED_EDGES, they're in a
        separate file. Other stages don't have hash files yet.
        """
        override = self._HASH_FILE_OVERRIDES.get(stage)
        if override:
            return self.idx_dir / override
        # Structural and others: hashes live inside the provenance manifest
        return self.provenance_path(stage)

    def read_hashes(self, stage: StageId) -> Dict[str, str]:
        """Read per-file content hashes for a stage.

        Returns empty dict if missing or corrupt.
        """
        if stage in self._HASH_FILE_OVERRIDES:
            # Separate hash file (e.g., trace_inferred_hashes.json)
            p = self.hashes_path(stage)
            if not p.exists():
                return {}
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Guard: reject orchestrator metadata that was accidentally
                # written here (Phase 60D-4 collision guard)
                if isinstance(data, dict) and "format_version" in data:
                    logger.warning(
                        "Hash file %s contains orchestrator metadata — treating as empty",
                        p.name,
                    )
                    return {}
                return data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, OSError):
                return {}

        # Embedded hashes (structural): read file_hashes key from provenance
        provenance = self.read_provenance(stage)
        if provenance is None:
            return {}
        hashes = provenance.get("file_hashes")
        return hashes if isinstance(hashes, dict) else {}

    def write_hashes(self, stage: StageId, hashes: Dict[str, str]) -> None:
        """Write per-file content hashes for a stage."""
        if stage in self._HASH_FILE_OVERRIDES:
            self._atomic_write_json(self.hashes_path(stage), hashes)
        else:
            # Embedded: merge file_hashes into the existing provenance manifest
            provenance = self.read_provenance(stage) or {}
            provenance["file_hashes"] = hashes
            self.write_provenance(stage, provenance)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_manifest_store.py -v`
Expected: All 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/manifest_store.py tests/test_manifest_store.py
git commit -m "feat(pipeline): add worker hash manifest methods to ManifestStore"
```

---

### Task 3: Add quality metrics, graph stats, and age summary methods

**Files:**
- Modify: `src/prep/services/pipeline/manifest_store.py`
- Modify: `tests/test_manifest_store.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_manifest_store.py`:

```python
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
        manifest = {
            "counts": {"nodes_total": 51072, "edges_total": 78589},
        }
        store.write_provenance(StageId.STRUCTURAL, manifest)
        
        stats = store.read_graph_stats()
        assert stats["node_count"] == 51072
        assert stats["edge_count"] == 78589

    def test_read_graph_stats_defaults_to_zeros(self, store):
        stats = store.read_graph_stats()
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0

    def test_age_summary_all_stages(self, store):
        """age_summary returns status for all 11 stages."""
        summary = store.age_summary()
        # Should have entries for all fast_sync + deep_enrichment stages
        assert len(summary) == 11

    def test_age_summary_shows_present_and_missing(self, store):
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        summary = store.age_summary()
        assert summary["structural"]["status"] == "present"
        assert summary["enrichment"]["status"] == "missing"

    def test_touch_manifests_syncs_mtime(self, store, idx_dir):
        """touch_downstream_mtimes brings stale manifests up to baseline."""
        import time
        store.write_provenance(StageId.STRUCTURAL, {"stage_id": "structural"})
        time.sleep(0.05)
        store.write_provenance(StageId.INFERRED_EDGES, {"stage_id": "inferred_edges"})
        
        # Touch inferred_edges to match structural
        baseline = store.provenance_mtime(StageId.STRUCTURAL)
        store.touch_provenance_mtime(StageId.INFERRED_EDGES, baseline)
        
        ie_mtime = store.provenance_mtime(StageId.INFERRED_EDGES)
        assert ie_mtime == pytest.approx(baseline, abs=1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_manifest_store.py::TestQualityAndStats -v`
Expected: FAIL with `AttributeError: 'ManifestStore' object has no attribute 'read_quality'`

- [ ] **Step 3: Add quality, graph stats, age summary, and mtime touch methods**

Add to `manifest_store.py`:

```python
    # ── Quality metrics ────────────────────────────────────────

    def read_quality(self, stage: StageId) -> Optional[Dict[str, Any]]:
        """Read quality metrics from a provenance manifest."""
        provenance = self.read_provenance(stage)
        if provenance is None:
            return None
        quality = provenance.get("quality")
        return quality if isinstance(quality, dict) else None

    # ── Graph stats ────────────────────────────────────────────

    def read_graph_stats(self) -> Dict[str, Any]:
        """Read node/edge counts from the structural manifest.

        Returns dict with node_count, edge_count. Defaults to zeros.
        """
        stats: Dict[str, Any] = {"node_count": 0, "edge_count": 0, "coverage_pct": None}
        provenance = self.read_provenance(StageId.STRUCTURAL)
        if provenance is None:
            return stats
        counts = provenance.get("counts", {})
        stats["node_count"] = counts.get("nodes_total", 0) or counts.get("files_parsed", 0)
        stats["edge_count"] = counts.get("edges_total", 0)
        return stats

    # ── Mtime operations ───────────────────────────────────────

    def touch_provenance_mtime(self, stage: StageId, mtime: float) -> None:
        """Set a provenance manifest's mtime to a specific value."""
        p = self.provenance_path(stage)
        if p.exists():
            os.utime(str(p), (mtime, mtime))

    # ── Age summary ────────────────────────────────────────────

    def age_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get the age of all stage manifests for diagnostics.

        Returns dict keyed by stage name, each with:
        - status: "present" | "missing" | "no_manifest_mapping"
        - age_hours: float (only when present)
        - last_modified: ISO string (only when present)
        """
        import time as _time
        from datetime import datetime, timezone

        now = _time.time()
        result: Dict[str, Dict[str, Any]] = {}

        for stage in list(FAST_SYNC_STAGES) + list(DEEP_ENRICHMENT_STAGES):
            mf = STAGE_MANIFEST_FILE.get(stage)
            if not mf:
                result[stage.value] = {"status": "no_manifest_mapping"}
                continue
            mp = self.idx_dir / mf
            if not mp.exists():
                result[stage.value] = {"status": "missing"}
                continue
            mtime = mp.stat().st_mtime
            age_hours = round((now - mtime) / 3600, 1)
            result[stage.value] = {
                "status": "present",
                "age_hours": age_hours,
                "last_modified": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
            }

        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_manifest_store.py -v`
Expected: All 24 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/manifest_store.py tests/test_manifest_store.py
git commit -m "feat(pipeline): add quality metrics, graph stats, age summary to ManifestStore"
```

---

### Task 4: Wire ManifestStore into orchestrator — replace manifest read methods

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py`
- Modify: `src/prep/services/pipeline/__init__.py`

This task replaces the orchestrator's internal manifest READ methods with ManifestStore delegation. Writes come in Task 5.

- [ ] **Step 1: Add ManifestStore import and helper to orchestrator**

At the top of `orchestrator.py`, after the existing imports from `.state_machine`, add:

```python
from .manifest_store import ManifestStore
```

Add a helper method to `PipelineOrchestrator.__init__`:
After `self._changed_paths: Dict[str, set[str]] = {}` (line 86), add:
```python
        # Phase 72: Manifest store instances per project
        self._manifest_stores: Dict[str, ManifestStore] = {}
```

Add a helper method after `_get_file_logger`:
```python
    def _get_manifest_store(self, project_id: str) -> Optional[ManifestStore]:
        """Get or create a ManifestStore for a project."""
        if project_id not in self._manifest_stores:
            try:
                from prep.services.project_helpers import require_project
                from prep.core.project_registry import project_index_dir
                project = require_project(project_id)
                idx_dir = Path(project_index_dir(project))
                self._manifest_stores[project_id] = ManifestStore(idx_dir)
            except Exception:
                logger.debug("Could not create ManifestStore for %s", project_id, exc_info=True)
                return None
        return self._manifest_stores.get(project_id)
```

- [ ] **Step 2: Replace `_read_graph_stats_from_manifest` (line 2740)**

Replace the static method `_read_graph_stats_from_manifest` with a delegation:

```python
    @staticmethod
    def _read_graph_stats_from_manifest(idx_dir) -> Dict[str, Any]:
        """Read node/edge counts from trace_manifest.json for rules file stats.

        Delegates to ManifestStore. Non-fatal — returns zeros on any error.
        """
        try:
            store = ManifestStore(Path(idx_dir))
            return store.read_graph_stats()
        except Exception:
            return {"node_count": 0, "edge_count": 0, "coverage_pct": None}
```

- [ ] **Step 3: Replace `_log_manifest_age_summary` (line 3882)**

Replace the method body with ManifestStore delegation:

```python
    def _log_manifest_age_summary(self, project_id: str, idx_dir: Path, pfl: Any = None) -> None:
        """Log the age of all stage manifests for diagnostic purposes."""
        store = ManifestStore(idx_dir)
        manifest_ages = store.age_summary()

        if pfl:
            pfl.selfheal("manifest_age", f"Pipeline checkpoint age summary for {project_id}", {
                "project_id": project_id,
                "manifests": manifest_ages,
            })

        ages_str = ", ".join(
            f"{k}={v.get('age_hours', '?')}h" if v.get("status") == "present" else f"{k}=MISSING"
            for k, v in manifest_ages.items()
        )
        logger.info("Phase 61B manifest ages for %s: %s", project_id, ages_str)
```

- [ ] **Step 4: Update `__init__.py` to export ManifestStore**

Add `ManifestStore` to the imports and `__all__` in `src/prep/services/pipeline/__init__.py`.

- [ ] **Step 5: Run existing tests to verify nothing broke**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py tests/test_manifest_store.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/orchestrator.py src/prep/services/pipeline/manifest_store.py src/prep/services/pipeline/__init__.py
git commit -m "refactor(pipeline): wire ManifestStore into orchestrator for manifest reads"
```

---

### Task 5: Wire ManifestStore into orchestrator — replace manifest write methods

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py`

This replaces the orchestrator's manifest WRITE operations. The key method is `_write_stage_manifest_and_update_run` and the mtime-sync helpers.

- [ ] **Step 1: Replace `_sync_downstream_manifest_mtimes` (line 148)**

Replace the static method body with ManifestStore delegation:

```python
    @staticmethod
    def _sync_downstream_manifest_mtimes(project_id: str, pfl: Any = None) -> None:
        """Touch all downstream manifest files to match structural mtime."""
        try:
            from prep.services.project_helpers import require_project
            from prep.core.project_registry import project_index_dir

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            store = ManifestStore(idx_dir)

            baseline_mtime = store.provenance_mtime(StageId.STRUCTURAL)
            if baseline_mtime == 0.0:
                return

            synced = []
            for stage in list(StageId):
                if stage == StageId.STRUCTURAL:
                    continue
                if store.provenance_exists(stage):
                    stage_mtime = store.provenance_mtime(stage)
                    if stage_mtime < baseline_mtime:
                        store.touch_provenance_mtime(stage, baseline_mtime)
                        synced.append(stage.value)

            if synced:
                logger.info(
                    "Phase 60D: Synced %d downstream manifest mtimes to structural "
                    "mtime (%.0f) for %s: %s",
                    len(synced), baseline_mtime, project_id, ", ".join(synced),
                )
                if pfl:
                    pfl.log("structural", f"Synced {len(synced)} downstream manifest mtimes")

        except Exception:
            logger.debug(
                "Failed to sync downstream manifest mtimes for %s (non-fatal)",
                project_id, exc_info=True,
            )
```

- [ ] **Step 2: Replace `_touch_stale_deep_manifests` (line 280)**

```python
    @staticmethod
    def _touch_stale_deep_manifests(project_id: str) -> None:
        """Touch deep enrichment manifests so they match the catalogue mtime."""
        try:
            from prep.services.project_helpers import require_project
            from prep.core.project_registry import project_index_dir

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            store = ManifestStore(idx_dir)

            cat_mtime = store.provenance_mtime(StageId.CATALOGUE)
            if cat_mtime == 0.0:
                return

            for stage in DEEP_ENRICHMENT_STAGES:
                if store.provenance_exists(stage):
                    stage_mtime = store.provenance_mtime(stage)
                    if stage_mtime < cat_mtime:
                        store.touch_provenance_mtime(stage, cat_mtime)
                        logger.debug(
                            "Touched deep manifest %s to match catalogue mtime (%.0f)",
                            STAGE_MANIFEST_FILE.get(stage), cat_mtime,
                        )
        except Exception:
            logger.debug(
                "Failed to touch stale deep manifests for %s (non-fatal)",
                project_id, exc_info=True,
            )
```

- [ ] **Step 3: Update `_write_stage_manifest_and_update_run` to use ManifestStore for the final save**

In `_write_stage_manifest_and_update_run` (line 3985), replace the `save_stage_manifest` call (around line 4112-4113):

Replace:
```python
            manifest_filename = STAGE_MANIFEST_FILE.get(stage, f"{stage.value}_manifest.json")
            save_stage_manifest(manifest, idx_dir / manifest_filename)
```

With:
```python
            manifest_filename = STAGE_MANIFEST_FILE.get(stage, f"{stage.value}_manifest.json")
            # Phase 72: Use ManifestStore for atomic writes
            store = ManifestStore(Path(idx_dir))
            store.write_provenance(stage, manifest.to_dict())
```

- [ ] **Step 4: Run existing tests**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py tests/test_manifest_store.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/orchestrator.py
git commit -m "refactor(pipeline): replace manifest writes with ManifestStore atomic writes"
```

---

### Task 6: Replace manifest reads in `_detect_resume_point` and `_auto_recover_stale_pipelines`

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py`

These are the most critical manifest-reading methods — they determine whether stages need to re-run.

- [ ] **Step 1: Update `_detect_resume_point` to use ManifestStore for mtime queries**

In `_detect_resume_point` (line 1441), after the `idx_dir` resolution (line 1474), add:

```python
        store = ManifestStore(idx_dir)
```

Then replace the manifest existence/mtime checks in the loop. At line 1493-1496, replace:

```python
            if manifest_file:
                mpath = idx_dir / manifest_file
                if mpath.exists() and mpath.stat().st_size > 0:
```

With:

```python
            if manifest_file:
                if store.provenance_exists(stage):
```

And replace mtime reads (line 1536):

```python
                        manifest_mtime = mpath.stat().st_mtime
```

With:

```python
                        manifest_mtime = store.provenance_mtime(stage)
```

And the mtime touch (line 1583):

```python
                                _os.utime(str(mpath), (baseline_mtime, baseline_mtime))
```

With:

```python
                                store.touch_provenance_mtime(stage, baseline_mtime)
```

Note: Keep the structural mtime baseline read as-is for now since it reads `trace_manifest.json` directly — the ManifestStore equivalent is `store.provenance_mtime(StageId.STRUCTURAL)`. Replace:

```python
        structural_manifest = idx_dir / "trace_manifest.json"
        baseline_mtime = 0.0
        if not skip_mtime_cascade and structural_manifest.exists():
            baseline_mtime = structural_manifest.stat().st_mtime
```

With:

```python
        baseline_mtime = 0.0
        if not skip_mtime_cascade:
            baseline_mtime = store.provenance_mtime(StageId.STRUCTURAL)
```

- [ ] **Step 2: Update `_auto_recover_stale_pipelines` manifest reads**

In `_auto_recover_stale_pipelines` (line 3667), replace the raw manifest reads in the staleness loop. After the `idx_dir` resolution (line 3689), add:

```python
            store = ManifestStore(idx_dir)
```

Replace the structural manifest read (line 3740-3741):
```python
                structural_manifest = idx_dir / "trace_manifest.json"
                if not structural_manifest.exists():
```
With:
```python
                if not store.provenance_exists(StageId.STRUCTURAL):
```

Replace the structural mtime read (line 3744):
```python
                structural_mtime = structural_manifest.stat().st_mtime
```
With:
```python
                structural_mtime = store.provenance_mtime(StageId.STRUCTURAL)
```

Replace the deep stage manifest checks (lines 3748-3757 and 3768-3777):
```python
                    mf = STAGE_MANIFEST_FILE.get(stage)
                    if mf:
                        mp = idx_dir / mf
                        if not mp.exists():
                            deep_stale = True
                            break
                        if mp.stat().st_mtime < structural_mtime:
```
With:
```python
                    if not store.provenance_exists(stage):
                        deep_stale = True
                        break
                    if store.provenance_mtime(stage) < structural_mtime:
```

(Apply the same replacement for the second loop — the "re-verify after touching" loop.)

- [ ] **Step 3: Run existing tests**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator.py tests/test_manifest_store.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/prep/services/pipeline/orchestrator.py
git commit -m "refactor(pipeline): replace raw manifest reads in resume/recovery with ManifestStore"
```

---

### Task 7: Final cleanup — remove dead imports, verify line count reduction, push

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py`

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/pytest tests/ -x -q --timeout=30`
Expected: All tests pass (some may skip if they need a running daemon)

- [ ] **Step 2: Verify orchestrator line count decreased**

Run: `wc -l src/prep/services/pipeline/orchestrator.py`
Expected: ~4,100 lines (down from 4,253 — modest reduction for Stage 1 since we're delegating but haven't deleted the old method bodies yet. Bigger reductions come in Stages 2-3.)

- [ ] **Step 3: Verify ManifestStore line count**

Run: `wc -l src/prep/services/pipeline/manifest_store.py`
Expected: ~200-250 lines

- [ ] **Step 4: Run linting**

Run: `ruff check src/prep/services/pipeline/manifest_store.py src/prep/services/pipeline/orchestrator.py`
Fix any issues.

- [ ] **Step 5: Push to remote**

```bash
git push origin feat/phase72-pipeline-refactor
```

- [ ] **Step 6: Tag the milestone**

```bash
git tag phase72-stage1-manifest-store
```
