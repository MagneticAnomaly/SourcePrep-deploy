"""Phase 134 — the Changeset object and its disk persistence.

The Changeset is the SINGLE inter-stage artifact for "what changed in
this pipeline run." Stage 1 (TraceBuilder structural) emits one
Changeset per run by diffing the prior trace_manifest's file_hashes
against the fresh walk's hashes. WorkerFactory loads it once at stage
start and injects it into every downstream worker. Workers use
should_process(path) — no per-stage hash comparison exists post-Phase-134.

The Phase 134 spec at docs/Phase134_ChangesetDrivenPipeline/README.md
explains why this exists. Short version: Phase 133 left six
independent staleness-check sites that all derived "what changed"
from hashes — a hash format change invalidated all six caches
simultaneously and triggered a full LLM re-run on unchanged content.
This object centralizes the truth so the cascade can't recur.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

CHANGESET_FILENAME = "changeset.json"
CHANGESET_VERSION = 1


@dataclass(frozen=True)
class Changeset:
    """The single source of truth for 'what changed in this pipeline run.'

    Emitted by stage 1 (structural). Read by every downstream stage
    via WorkerFactory injection. Persisted to .sourceprep/changeset.json
    so it survives daemon restarts mid-run.
    """
    added:       frozenset[str]   # files new since base_run_id
    modified:    frozenset[str]   # files whose content changed
    deleted:     frozenset[str]   # files in base_run, no longer present
    unchanged:   frozenset[str]   # everything else (carry forward)
    run_id:      str              # this pipeline run's ID (matches journal)
    base_run_id: str | None       # prior run we diffed against; None on first build

    def should_process(self, file_path: str) -> bool:
        """Return True iff a stage worker should run on this file in
        this run. Files in `unchanged` skip processing (carry-forward
        augmentation entries as-is); files in `deleted` are handled
        by the post-stage cleanup pass; everything in `added` or
        `modified` is fair game."""
        return file_path in self.added or file_path in self.modified

    def all_known(self) -> frozenset[str]:
        """Union of added | modified | unchanged — every file the
        pipeline knows about for this run. `deleted` is intentionally
        excluded (no longer present, not 'known' for downstream
        consumers' purposes). Used by the audit orphan check."""
        return self.added | self.modified | self.unchanged


def read_changeset(idx_dir: Path) -> Changeset | None:
    """Load the changeset from idx_dir/changeset.json. Returns None
    if the file is absent or malformed (caller decides fallback)."""
    path = Path(idx_dir) / CHANGESET_FILENAME
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return Changeset(
            added=frozenset(raw.get("added") or []),
            modified=frozenset(raw.get("modified") or []),
            deleted=frozenset(raw.get("deleted") or []),
            unchanged=frozenset(raw.get("unchanged") or []),
            run_id=str(raw.get("run_id") or ""),
            base_run_id=raw.get("base_run_id"),
        )
    except (TypeError, ValueError):
        return None


def write_changeset(idx_dir: Path, cs: Changeset) -> None:
    """Atomic write of the changeset to idx_dir/changeset.json via
    tempfile + rename. A crash mid-write leaves the prior changeset
    on disk (or no file at all if first write)."""
    path = Path(idx_dir) / CHANGESET_FILENAME
    payload = {
        "version": CHANGESET_VERSION,
        "run_id": cs.run_id,
        "base_run_id": cs.base_run_id,
        "added": sorted(cs.added),
        "modified": sorted(cs.modified),
        "deleted": sorted(cs.deleted),
        "unchanged": sorted(cs.unchanged),
    }
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=str(idx_dir),
        delete=False, encoding="utf-8",
    )
    try:
        json.dump(payload, tmp, indent=2, sort_keys=True)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.rename(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise
