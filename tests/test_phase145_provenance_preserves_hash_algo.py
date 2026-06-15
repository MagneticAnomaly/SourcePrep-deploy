"""Phase 145 — STRUCTURAL provenance write must preserve hash_algo + built_at.

Root cause of the daemon-wide "changeset never reports modified" bug
(2026-06-15): TraceBuilder writes trace_manifest.json with `hash_algo`
and `built_at` (builder.py:_build_manifest), but the structural stage's
provenance write (ManifestStore.write_provenance, STRUCTURAL branch) then
MERGES provenance fields back into the same file preserving only
`("file_hashes", "config", "file_errors")` — silently dropping `hash_algo`
and `built_at`.

Consequences (all 13 local projects had `hash_algo: None` on disk and
`changeset.modified == []`):
  * `hash_algo` dropped → `_emit_changeset` always takes Case 3
    ("can't compare → trust prior") → content edits never become
    `modified` → never re-enriched/finalized.
  * `built_at` dropped → `check_index_staleness` (which read `built_at`)
    found nothing → the message-1 staleness bug.

Pre-existing tests cover the builder WRITING hash_algo
(test_phase133_builder_writes_hash_algo.py) but nothing covered the
provenance-merge step that strips it. This pins that step.
"""
from __future__ import annotations

import json
from pathlib import Path

from prep.core.manifest import CURRENT_HASH_ALGO
from prep.services.pipeline.manifest_store import ManifestStore
from prep.services.pipeline.stages import StageId


def test_structural_provenance_preserves_hash_algo_and_built_at(tmp_path: Path):
    idx = tmp_path / "idx"
    idx.mkdir()
    store = ManifestStore(idx)

    # Simulate TraceBuilder's manifest on disk (it writes hash_algo + built_at
    # + file_hashes via _build_manifest).
    builder_manifest = {
        "version": "trace-v1",
        "built_at": "2026-06-15T12:00:00+00:00",
        "hash_algo": CURRENT_HASH_ALGO,
        "file_hashes": {"src/a.swift": "abc123", "src/b.swift": "def456"},
        "config": {"include_globs": ["**/*.swift"]},
        "file_errors": [],
    }
    structural_path = store.provenance_path(StageId.STRUCTURAL)
    structural_path.write_text(json.dumps(builder_manifest), encoding="utf-8")

    # Now the structural stage writes its provenance (no hash_algo/built_at
    # in the provenance blob — those are builder-owned).
    provenance = {
        "stage_id": "structural",
        "run_id": "run-xyz",
        "finished_at": "2026-06-15T12:00:01+00:00",
        "elapsed_seconds": 0.9,
    }
    store.write_provenance(StageId.STRUCTURAL, provenance)

    merged = json.loads(structural_path.read_text(encoding="utf-8"))

    # file_hashes must survive (already covered by the 304-byte-overwrite guard)…
    assert merged.get("file_hashes") == builder_manifest["file_hashes"]
    # …and so must the two builder keys that drive change-detection + staleness.
    assert merged.get("hash_algo") == CURRENT_HASH_ALGO, (
        "hash_algo dropped by provenance merge → _emit_changeset can never "
        "do a real diff (Case 2) → content edits never detected"
    )
    assert merged.get("built_at") == "2026-06-15T12:00:00+00:00", (
        "built_at dropped by provenance merge → check_index_staleness finds "
        "no build time"
    )
    # provenance fields are present too.
    assert merged.get("run_id") == "run-xyz"
    assert merged.get("finished_at") == "2026-06-15T12:00:01+00:00"
