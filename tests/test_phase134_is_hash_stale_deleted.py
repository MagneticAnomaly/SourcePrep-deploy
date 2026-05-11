"""Phase 134 — is_hash_stale helper deleted (Phase 133 hot-fix gone)."""
from __future__ import annotations


def test_is_hash_stale_helper_deleted():
    from prep.core import ids
    assert not hasattr(ids, "is_hash_stale"), (
        "Phase 134 deletes is_hash_stale — the per-stage staleness "
        "checks it patched are themselves deleted, so the helper is "
        "now dead code"
    )
