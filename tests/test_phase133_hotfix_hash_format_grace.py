"""Phase 133 hot-fix: is_hash_stale graces hash-format mismatches so the
SHA-256 → BLAKE3 manifest cutover does NOT trigger a full LLM re-run of
the augmenter / enrichment / deepening / scoring / audit-staleness
chain.

Pre-fix symptom: clicking deep_enrichment Auto after Phase 133 landed
re-ran every stage from scratch because each downstream stage's stored
file_hash (SHA-256-64, 16 hex chars) mismatched the manifest's
file_hashes (BLAKE3-128, 32 hex chars). Every comparison failed by
length → every node looked stale → re-LLM cascade.

Phase 134 deletes the per-stage staleness checks entirely (changeset-
driven pipeline). This test pins the hot-fix until 134 lands.
"""
from __future__ import annotations

from prep.core.ids import is_hash_stale


def test_same_format_differ_is_stale():
    """Within the same hash algorithm, a real difference is real stale."""
    blake_a = "a" * 32
    blake_b = "b" * 32
    assert is_hash_stale(blake_a, blake_b) is True


def test_same_format_match_is_not_stale():
    blake = "deadbeef" * 4
    assert is_hash_stale(blake, blake) is False


def test_length_mismatch_is_grace_not_stale():
    """The headline regression: SHA-256-64 stored vs BLAKE3-128 manifest.
    Pre-fix this would have been treated as stale (length diff → string
    diff). Post-fix: graced, treated as not-stale, cached enrichment
    preserved."""
    sha256_64 = "a120afed0f1d286a"  # 16 hex chars (the actual format on disk)
    blake3_128 = "a120afed0f1d286a" + "b" * 16  # 32 hex chars
    assert is_hash_stale(sha256_64, blake3_128) is False
    # Order doesn't matter
    assert is_hash_stale(blake3_128, sha256_64) is False


def test_empty_inputs_are_not_stale():
    """Caller is responsible for the 'have we ever hashed this?' check;
    if either input is empty the comparison returns not-stale."""
    assert is_hash_stale("", "abc") is False
    assert is_hash_stale("abc", "") is False
    assert is_hash_stale("", "") is False


def test_none_inputs_are_not_stale():
    """Defensive against None leaks at call sites that haven't yet
    normalized to empty string."""
    assert is_hash_stale(None, "abc") is False  # type: ignore[arg-type]
    assert is_hash_stale("abc", None) is False  # type: ignore[arg-type]
