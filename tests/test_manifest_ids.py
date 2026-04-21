from __future__ import annotations

import hashlib

from prep.core.ids import (
    stable_code_chunk_id,
    stable_file_hash,
    stable_markdown_chunk_id,
    stable_sha256,
)
from prep.core.manifest import ManifestBuildStats, build_manifest, read_manifest, write_manifest


def test_stable_sha256_default_length() -> None:
    a = stable_sha256("hello")
    b = stable_sha256("hello")
    c = stable_sha256("hello", length=32)
    assert a == b
    assert len(a) == 16
    assert len(c) == 32


def test_stable_chunk_ids_match_previous_hashing() -> None:
    md = stable_markdown_chunk_id("README.md", "Intro", 0)
    md_expected = hashlib.sha256("README.md:Intro:0".encode("utf-8")).hexdigest()[:16]
    assert md == md_expected

    code = stable_code_chunk_id("src/main.py", 3)
    code_expected = hashlib.sha256("src/main.py:3".encode("utf-8")).hexdigest()[:16]
    assert code == code_expected


def test_stable_file_hash_matches_previous_hashing() -> None:
    raw = "print('hello')\n"
    h = stable_file_hash(raw)
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    assert h == expected


def test_manifest_roundtrip(tmp_path) -> None:
    m = build_manifest(
        model="nomic-embed-text",
        embedding_dim=768,
        roots=["src"],
        count=12,
        build=ManifestBuildStats(
            mode="full",
            files_total=3,
            files_reused=0,
            files_embedded=3,
            chunks_total=12,
            chunks_reused=0,
            chunks_embedded=12,
        ),
        config={"include_globs": ["**/*.py"], "exclude_globs": [], "max_file_bytes": 500_000, "role_weights": {}},
        built_at="2026-02-01T00:00:00Z",
    )

    p = tmp_path / "manifest.json"
    write_manifest(p, m)
    loaded = read_manifest(p)
    assert loaded == m
