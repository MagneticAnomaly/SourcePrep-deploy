"""Phase 133 — embedding manifest forward-proofs the hash_algo field
+ CURRENT_HASH_ALGO shared constant lives here. Note: the trace
manifest (the one Phase 133 actually depends on) is built by
TraceBuilder._build_manifest, tested in test_phase133_builder_writes_hash_algo.py.
"""
from __future__ import annotations

from prep.core.manifest import CURRENT_HASH_ALGO, ManifestBuildStats, build_manifest


def test_current_hash_algo_constant_is_blake3_128():
    """The cutover target. Phase 133 establishes BLAKE3-128 as the post-cutover algo."""
    assert CURRENT_HASH_ALGO == "blake3-128"


def _stats() -> ManifestBuildStats:
    """Minimal stats tuple required by the embedding manifest builder."""
    return ManifestBuildStats(
        mode="full",
        files_total=0,
        files_reused=0,
        files_embedded=0,
    )


def test_embedding_manifest_emits_hash_algo_when_provided():
    m = build_manifest(
        model="test-model",
        embedding_dim=64,
        roots=["/tmp/repo"],
        count=0,
        build=_stats(),
        config={},
        file_hashes={"src/foo.py": "deadbeef" * 4},
        hash_algo="blake3-128",
    )
    assert m["hash_algo"] == "blake3-128"
    assert m["file_hashes"] == {"src/foo.py": "deadbeef" * 4}


def test_embedding_manifest_omits_hash_algo_when_not_provided():
    """Back-compat: existing callers that don't pass hash_algo get the
    same manifest shape they get today."""
    m = build_manifest(
        model="test-model",
        embedding_dim=64,
        roots=["/tmp/repo"],
        count=0,
        build=_stats(),
        config={},
    )
    assert "hash_algo" not in m
