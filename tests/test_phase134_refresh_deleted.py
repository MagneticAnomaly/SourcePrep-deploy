"""Phase 134 — ResumeStrategy.refresh_manifest_hashes is deleted.

Pre-Phase-134 this 220-line method walked the disk, hashed every
file, and rewrote trace_manifest.json::file_hashes. The orchestrator
called it on three hot paths (force_from_start gap-check, Phase 72
pre-gap refresh, post-fast_sync refresh). With Phase 134's changeset
as the single staleness signal, this function has no purpose."""
from __future__ import annotations


def test_refresh_manifest_hashes_method_deleted():
    from prep.services.pipeline.resume import ResumeStrategy
    assert not hasattr(ResumeStrategy, "refresh_manifest_hashes"), (
        "Phase 134 deletes ResumeStrategy.refresh_manifest_hashes — "
        "the changeset is the staleness signal, refreshing manifest "
        "hashes between runs is unnecessary"
    )


def test_orchestrator_no_refresh_call_sites():
    """Verify by source inspection that orchestrator.py doesn't call
    the deleted method."""
    import inspect
    from prep.services.pipeline import orchestrator
    src = inspect.getsource(orchestrator)
    assert "refresh_manifest_hashes" not in src, (
        "orchestrator.py must not call the deleted refresh_manifest_hashes"
    )
    assert "_refresh_manifest_hashes" not in src
