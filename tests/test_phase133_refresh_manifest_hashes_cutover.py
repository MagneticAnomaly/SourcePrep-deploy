"""Phase 133 follow-up — refresh_manifest_hashes must not split-brain
the manifest into ``hash_algo: blake3-128`` + SHA-256 hashes.

Pre-fix: orchestrator hot paths (force_from_start gap-check, Phase 72
pre-gap refresh, post-fast_sync refresh) called refresh_manifest_hashes
which used Python ``stable_file_hash`` (SHA-256-64) and rewrote
``file_hashes`` without touching ``hash_algo``. Post-cutover this
produced a manifest with ``hash_algo: blake3-128`` (from the prior
structural rebuild) but SHA-256 hashes — every coverage call after
the first post-cutover fast_sync flagged 100% stale, triggering a
loop. Fix: refresh_manifest_hashes now uses prep_engine.walk_repo +
prep_engine.hash_content and tags hash_algo=CURRENT_HASH_ALGO on
write."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from prep.core.manifest import CURRENT_HASH_ALGO


def _has_prep_engine() -> bool:
    try:
        import prep_engine  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _has_prep_engine(),
    reason="prep_engine PyO3 binding not built; refresh_manifest_hashes returns 0 without it",
)


def _seed_pre_cutover_manifest(repo: Path, idx: Path, content: str) -> str:
    """Write a pre-cutover-shaped manifest (SHA-256 hashes, no hash_algo)
    matching Path A's 'pre-cutover' state. Returns the SHA-256-64 hex."""
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        # no hash_algo field — this is the state pre-Phase-133 manifests have
        "file_hashes": {"main.py": sha},
        "built_at": "2026-05-01T00:00:00Z",
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )
    return sha


def test_refresh_rewrites_hashes_with_blake3_and_tags_algo(tmp_path: Path):
    """The headline regression: after refresh_manifest_hashes runs, the
    manifest must carry hash_algo=blake3-128 AND the file_hashes must
    be 32-hex-char BLAKE3 (not 16-hex-char SHA-256)."""
    from prep.services.pipeline.resume import ResumeStrategy

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    idx = tmp_path / "index"
    idx.mkdir()

    sha_before = _seed_pre_cutover_manifest(repo, idx, "def main(): pass\n")
    assert len(sha_before) == 16, "fixture sanity: pre-cutover hash is 16-hex SHA-256"

    # Mock the project lookup so refresh_manifest_hashes can resolve the
    # idx_dir without a real registry.
    from unittest.mock import MagicMock, patch
    fake_proj = MagicMock()
    fake_proj.id = "test-proj"
    fake_proj.path = str(repo)
    fake_proj.config = {"include_globs": ["**/*.py"], "exclude_globs": []}

    with patch("prep.services.project_helpers.require_project", return_value=fake_proj), \
         patch("prep.core.project_registry.project_index_dir", return_value=idx):
        ResumeStrategy.refresh_manifest_hashes("test-proj")

    after = json.loads((idx / "trace_manifest.json").read_text())

    assert after.get("hash_algo") == CURRENT_HASH_ALGO, (
        f"refresh_manifest_hashes must tag hash_algo on write; got {after.get('hash_algo')!r}"
    )
    file_hashes = after.get("file_hashes") or {}
    assert "main.py" in file_hashes
    new_hash = file_hashes["main.py"]
    assert len(new_hash) == 32, (
        f"refresh_manifest_hashes must write 32-hex BLAKE3 hashes, "
        f"not 16-hex SHA-256; got {len(new_hash)}-char {new_hash!r}"
    )
    assert new_hash != sha_before, "BLAKE3 of same content must differ from SHA-256"


def test_refresh_does_not_split_brain_when_hashes_unchanged(tmp_path: Path):
    """Even when no individual hash changed, refresh must rewrite
    hash_algo if it was stale or absent. Otherwise a manifest stuck on
    'sha256-64' would survive every refresh call."""
    from prep.services.pipeline.resume import ResumeStrategy

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    idx = tmp_path / "index"
    idx.mkdir()

    # Seed manifest with the CORRECT BLAKE3 hash but stale algo tag.
    import prep_engine
    blake = prep_engine.hash_content("def main(): pass\n")
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        "hash_algo": "sha256-64",  # stale tag
        "file_hashes": {"main.py": blake},
        "built_at": "2026-05-01T00:00:00Z",
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )

    from unittest.mock import MagicMock, patch
    fake_proj = MagicMock()
    fake_proj.id = "test-proj"
    fake_proj.path = str(repo)
    fake_proj.config = {"include_globs": ["**/*.py"], "exclude_globs": []}

    with patch("prep.services.project_helpers.require_project", return_value=fake_proj), \
         patch("prep.core.project_registry.project_index_dir", return_value=idx):
        ResumeStrategy.refresh_manifest_hashes("test-proj")

    after = json.loads((idx / "trace_manifest.json").read_text())
    assert after.get("hash_algo") == CURRENT_HASH_ALGO, (
        "refresh must rewrite hash_algo even when no hashes changed"
    )
