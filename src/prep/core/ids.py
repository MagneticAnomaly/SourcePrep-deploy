from __future__ import annotations

import hashlib


def stable_sha256(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[: int(length)]


def stable_file_hash(text: str) -> str:
    return stable_sha256(text, length=16)


def stable_markdown_chunk_id(source_path: str, section: str, idx: int) -> str:
    return stable_sha256(f"{source_path}:{section}:{idx}", length=16)


def stable_code_chunk_id(source_path: str, idx: int) -> str:
    return stable_sha256(f"{source_path}:{idx}", length=16)


def stable_file_node_id(file_path: str) -> str:
    return f"file:{file_path}"


def stable_symbol_node_id(qualname: str, file_path: str, start_line: int) -> str:
    return f"sym:{qualname}@{file_path}:{start_line}"


def stable_external_module_id(module_name: str) -> str:
    return f"ext:{module_name}"


def stable_edge_id(kind: str, source: str, target: str, disambiguator: str = "") -> str:
    if disambiguator:
        return f"edge:{kind}:{source}:{target}:{disambiguator}"
    return f"edge:{kind}:{source}:{target}"


# ── Phase 133 hot-fix: hash format mismatch grace check ──────────────
# Phase 133 cut over the trace manifest from SHA-256-64 (16 hex chars)
# to BLAKE3-128 (32 hex chars). Stages 6-15 (augmenter, enrichment,
# deepening, epistemic_score, audit) each independently compare a
# stored per-entry `file_hash` against the live manifest's `file_hashes`
# to decide if their cached enrichment is stale. After Phase 133 the
# stored hashes are still SHA-256 (from prior runs) while the manifest
# is BLAKE3 — so EVERY comparison fails by length, every entry looks
# stale, and clicking deep_enrichment Auto re-runs the whole LLM chain
# unnecessarily.
#
# This helper short-circuits comparisons where the two strings can't
# possibly represent the same hash (different algorithms / lengths),
# returning False (not-stale) so the cached enrichment is preserved.
# When a file is genuinely modified later, the augmenter writes a new
# BLAKE3 entry; comparisons within the same algorithm work normally.
#
# Phase 134 deletes this helper AND every call site — the changeset-
# driven pipeline removes per-stage staleness checks entirely, so
# `is_stale` becomes a non-question outside stage 1. Grep for
# `is_hash_stale` to find every call site that goes away.
def is_hash_stale(stored_hash: str, current_hash: str) -> bool:
    """Return True only when the two hashes were produced by the same
    algorithm AND differ. A length mismatch (different algorithms) is
    treated as not-stale — Phase 133 migration grace.

    Both inputs may be empty/None; caller is responsible for the
    "have we ever hashed this?" check before delegating to us.
    """
    if not stored_hash or not current_hash:
        return False
    if len(stored_hash) != len(current_hash):
        # Phase 133 grace: SHA-256-64 (16 char) vs BLAKE3-128 (32 char).
        # Cannot meaningfully compare — preserve the cached entry.
        return False
    return stored_hash != current_hash
