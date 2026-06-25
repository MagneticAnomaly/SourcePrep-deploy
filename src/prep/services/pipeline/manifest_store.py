"""
ManifestStore — Centralized manifest I/O with namespace separation.

Phase 72 Stage 1: Extracted from orchestrator.py to eliminate
cross-concern interference between provenance manifests and
worker hash manifests.

Two file types per stage:
- Provenance manifest: {stage}_manifest.json -> model info, timing, quality
- Worker hash manifest: {stage}_hashes.json -> per-file content hashes

These NEVER share a filename (except STRUCTURAL, where hashes are
embedded inside trace_manifest.json under the ``file_hashes`` key).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC
from pathlib import Path
from typing import Any

from .stages import (
    DEEP_ENRICHMENT_STAGES,
    FAST_SYNC_STAGES,
    STAGE_MANIFEST_FILE,
    StageId,
)

logger = logging.getLogger(__name__)


class ManifestStore:
    """Centralized manifest I/O with namespace separation.

    Stateless — takes an index directory and does file I/O.
    All writes are atomic (tmp + fsync + rename).
    """

    # Stages that have a separate hash file (not embedded in provenance).
    # Other stages either don't have hash caches or embed them in provenance.
    _HASH_FILE_OVERRIDES: dict[StageId, str] = {
        StageId.INFERRED_EDGES: "trace_inferred_hashes.json",
    }

    def __init__(self, idx_dir: Path) -> None:
        self.idx_dir = Path(idx_dir)

    # ── Atomic write helper ────────────────────────────────────

    def _atomic_write_json(self, path: Path, data: dict[str, Any]) -> None:
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
            tmp_path = None
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

    def write_provenance(self, stage: StageId, data: dict[str, Any]) -> None:
        """Write a provenance manifest atomically.

        For STRUCTURAL, the provenance manifest is trace_manifest.json which
        also holds ``file_hashes`` written by TraceBuilder.  We MERGE the
        provenance fields into the existing file so that file_hashes (and
        other builder data like ``config``, ``counts``) are preserved.
        Without this merge, the ~304-byte provenance blob would overwrite
        the ~97 KB manifest, causing coverage gap to report all files as
        untraced and triggering an infinite restart loop.

        For CATALOGUE, the provenance manifest is trace_augment_manifest.json
        which is ALSO written by TraceAugmenter._write_manifest with v1-shape
        fields (``counts``, ``stats``). The same merge-preservation pattern
        applies: without it, the orchestrator's v2 blob clobbers the v1
        counts/stats and the §9.3 #32 fix (PR-P) becomes dead code in
        pipeline mode — augmenter.status() falls back to v2's quality block
        which has different semantics (per-jsonl-line counts that always
        round to ~100%). (Phase 145, 2026-06-25.)
        """
        if stage == StageId.STRUCTURAL:
            preserved_keys = ("file_hashes", "config", "file_errors", "hash_algo", "built_at")
            self._merge_preserve_and_write(stage, data, preserved_keys)
        elif stage == StageId.CATALOGUE:
            # §9.3 #32: preserve TraceAugmenter._write_manifest's v1 fields so
            # PR-P's project_augmentable_count + orphan-filter survive the
            # orchestrator's v2 manifest write. augmenter.status() reads v1
            # first (counts.total_nodes / counts.augmented) before falling
            # back to v2's quality block.
            #
            # PR-P-fixup-r2 (PRP-FIX-001 from scrutiny round 2): also preserve
            # `built_at` and `model` so augmenter.status()'s v1 branch can
            # still populate `last_augment_at` (reads built_at, not v2's
            # finished_at) and the model attribution string. Without these,
            # every pipeline-driven catalogue run silently nulls
            # last_augment_at in the dashboard.
            preserved_keys = ("counts", "stats", "version", "built_at", "model")
            self._merge_preserve_and_write(stage, data, preserved_keys)
        else:
            self._atomic_write_json(self.provenance_path(stage), data)

    def _merge_preserve_and_write(
        self,
        stage: StageId,
        data: dict[str, Any],
        preserved_keys: tuple[str, ...],
    ) -> None:
        """Read the existing provenance manifest at `stage` and preserve
        the named keys before writing `data` atomically. If `data` already
        has a key in `preserved_keys`, the new value wins (caller intent
        respected); otherwise the existing on-disk value is carried over.
        Corrupt or missing existing file → overwrite cleanly with `data`.
        """
        path = self.provenance_path(stage)
        existing: dict[str, Any] = {}
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass  # Corrupt — overwrite is fine
        for key in preserved_keys:
            if key in existing and key not in data:
                data[key] = existing[key]
        self._atomic_write_json(path, data)

    def read_provenance(self, stage: StageId) -> dict[str, Any] | None:
        """Read a provenance manifest. Returns None if missing or corrupt."""
        p = self.provenance_path(stage)
        if not p.exists():
            return None
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.debug("Failed to read provenance for %s", stage.value, exc_info=True)
            return None

    def is_stub_manifest(self, stage: StageId) -> bool:
        """Check if a stage's manifest is a stub created by auto-recovery.

        Stub manifests have ``restored: true`` and were created synthetically
        (Phase 72C) when a manifest was missing but data files existed. They
        should NOT be treated as proof that the stage completed successfully —
        the stage may never have actually run.

        Returns True if the manifest is a stub, False otherwise.
        """
        data = self.read_provenance(stage)
        if data is None:
            return False
        return bool(data.get("restored"))

    # ── Worker hash manifests ──────────────────────────────────

    def hashes_path(self, stage: StageId) -> Path:
        """Path to the worker hash manifest for a stage.

        For INFERRED_EDGES, hashes are in a separate file.
        For STRUCTURAL and others, hashes live inside the provenance manifest.
        """
        override = self._HASH_FILE_OVERRIDES.get(stage)
        if override:
            return self.idx_dir / override
        return self.provenance_path(stage)

    def read_hashes(self, stage: StageId) -> dict[str, str]:
        """Read per-file content hashes for a stage.

        Returns empty dict if missing or corrupt.
        """
        if stage in self._HASH_FILE_OVERRIDES:
            p = self.hashes_path(stage)
            if not p.exists():
                return {}
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                # Phase 60D-4 guard: reject orchestrator metadata that was
                # accidentally written to the hash file.
                if isinstance(data, dict) and "format_version" in data:
                    logger.warning(
                        "Hash file %s contains orchestrator metadata — treating as empty",
                        p.name,
                    )
                    return {}
                return data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, OSError):
                return {}

        # Embedded hashes: read file_hashes key from provenance
        provenance = self.read_provenance(stage)
        if provenance is None:
            return {}
        hashes = provenance.get("file_hashes")
        return hashes if isinstance(hashes, dict) else {}

    def write_hashes(self, stage: StageId, hashes: dict[str, str]) -> None:
        """Write per-file content hashes for a stage."""
        if stage in self._HASH_FILE_OVERRIDES:
            self._atomic_write_json(self.hashes_path(stage), hashes)
        else:
            # Embedded: merge file_hashes into existing provenance manifest
            provenance = self.read_provenance(stage) or {}
            provenance["file_hashes"] = hashes
            self.write_provenance(stage, provenance)

    # ── Quality metrics ────────────────────────────────────────

    def read_quality(self, stage: StageId) -> dict[str, Any] | None:
        """Read quality metrics from a provenance manifest."""
        provenance = self.read_provenance(stage)
        if provenance is None:
            return None
        quality = provenance.get("quality")
        return quality if isinstance(quality, dict) else None

    # ── Graph stats ────────────────────────────────────────────

    def read_graph_stats(self) -> dict[str, Any]:
        """Read node/edge counts from the structural manifest.

        Returns dict with node_count, edge_count. Defaults to zeros.
        """
        stats: dict[str, Any] = {"node_count": 0, "edge_count": 0, "coverage_pct": None}
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

    def sync_downstream_mtimes(self, baseline_stage: StageId, target_stages: list[StageId]) -> list[str]:
        """Touch target stage manifests to match the baseline stage's mtime.

        Returns list of stage names that were synced. Used to prevent
        false STALE_MTIME detection in _detect_resume_point.
        """
        baseline_mtime = self.provenance_mtime(baseline_stage)
        if baseline_mtime == 0.0:
            return []

        synced = []
        for stage in target_stages:
            if stage == baseline_stage:
                continue
            if self.provenance_exists(stage) and self.provenance_mtime(stage) < baseline_mtime:
                self.touch_provenance_mtime(stage, baseline_mtime)
                synced.append(stage.value)
        return synced

    # ── Age summary ────────────────────────────────────────────

    def age_summary(self) -> dict[str, dict[str, Any]]:
        """Get the age of all stage manifests for diagnostics.

        Returns dict keyed by stage name, each with:
        - status: "present" | "missing" | "no_manifest_mapping"
        - age_hours: float (only when present)
        - last_modified: ISO string (only when present)
        """
        import time as _time
        from datetime import datetime

        now = _time.time()
        result: dict[str, dict[str, Any]] = {}

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
                "last_modified": datetime.fromtimestamp(mtime, tz=UTC).isoformat(),
            }

        return result
