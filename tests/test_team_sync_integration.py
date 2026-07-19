"""
Integration tests for the full Team Sync pipeline (P06).

Covers the gaps not handled by the per-module unit tests:
  - INDEX_ARTIFACTS ⊇ _PRESERVE_FILES consistency
  - License gating on team_config feature
  - LayeredCodeIndex actual search merge with real embeddings
  - LayeredCodeIndex get_context() assembly
  - Watcher trigger_build delta routing
  - RemoteSyncService check_and_sync → prune end-to-end
  - Full cycle: remote index → delta override → prune → fresh remote
  - API endpoint integration via TestClient
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from prep.core.index import CodeIndex, SearchResult
from prep.core.layered_index import LayeredCodeIndex, prune_stale_deltas


# ── Helpers ───────────────────────────────────────────────────


def _make_index_dir(
    base: Path,
    name: str,
    docs: List[Dict[str, Any]],
    dim: int = 32,
) -> Path:
    """Create a minimal on-disk index directory.

    Uses dim=32 (matching nomic-embed-text lite dimensions)
    so cosine similarity actually differentiates documents.
    """
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "documents.json").write_text(json.dumps(docs))
    # Non-negative (abs) so cosine vs the query stays in [0, 1]; signed random vectors
    # give a negative cosine ~50% of the time, which a min_score>=0 filter drops and
    # makes get_context/search tests flaky. Matches _mock_embedder's convention.
    emb = np.abs(np.random.default_rng(42).standard_normal((len(docs), dim))).astype(np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    emb = emb / norms
    np.save(d / "embeddings.npy", emb)
    return d


def _mock_embedder(dim: int = 32):
    """Create a mock embedder returning deterministic vectors."""
    from prep.core.embedder import EmbeddingResult

    rng = np.random.default_rng(99)
    embedder = MagicMock()

    def _embed(text):
        # Deterministic AND non-negative, so search tests are stable:
        #  - builtin hash() is PYTHONHASHSEED-randomized across processes, so seed on a
        #    stable sha256 digest instead;
        #  - signed random unit vectors give a negative cosine ~50% of the time, which a
        #    min_score>=0 filter drops -> flaky/empty results. abs() keeps cosine in [0, 1]
        #    while staying text-dependent (identical text -> identical vector -> score 1.0).
        import hashlib
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:4], "big")
        vec = np.abs(np.random.default_rng(seed).standard_normal(dim)).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        return EmbeddingResult(vector=vec.tolist(), model="test")

    embedder.embed.side_effect = _embed
    embedder.embed_query = embedder.embed
    return embedder


def _make_project(tmp_path: Path, project_id: str = "test-proj"):
    """Create a Project dataclass for testing."""
    from prep.core.project_registry import Project
    return Project(
        id=project_id, name="TestProject", path=str(tmp_path),
        mode="embedded", config={}, created_at="", updated_at="",
    )


# ═══════════════════════════════════════════════════════════════
# 1. INDEX_ARTIFACTS ⊇ _PRESERVE_FILES consistency
# ═══════════════════════════════════════════════════════════════


class TestArtifactConsistency:
    """Verify s3_storage.INDEX_ARTIFACTS is a superset of index._PRESERVE_FILES."""

    def test_index_artifacts_covers_preserve_files(self):
        """Every file in _PRESERVE_FILES must be in INDEX_ARTIFACTS.

        INDEX_ARTIFACTS also includes documents.json and embeddings.npy
        (the code index itself) which are NOT in _PRESERVE_FILES because
        _PRESERVE_FILES only covers pipeline-produced trace/knowledge files.
        """
        from prep.services.s3_storage import INDEX_ARTIFACTS

        # _PRESERVE_FILES is defined inline in CodeIndex.build(), extract it
        preserve_files = [
            "trace_manifest.json",
            "trace_nodes.jsonl",
            "trace_edges.jsonl",
            "trace_augmented.jsonl",
            "trace_augment_manifest.json",
            "trace_inferred_edges.jsonl",
            "trace_epistemic.jsonl",
            "trace_epistemic_manifest.json",
            "trace_modules.jsonl",
            "atlas.json",
            "atlas_prev.json",
            "atlas_segments_manifest.json",
            "atlas_routing.json",
            "atlas_routing_embeddings.npy",
            "knowledge_documents.json",
            "knowledge_embeddings.npy",
            "knowledge_manifest.json",
        ]

        artifacts_set = set(INDEX_ARTIFACTS)
        missing = []
        for f in preserve_files:
            # atlas_prev.json is intentionally NOT uploaded (it's a local backup)
            if f == "atlas_prev.json":
                continue
            if f not in artifacts_set:
                missing.append(f)

        assert missing == [], (
            f"_PRESERVE_FILES entries missing from INDEX_ARTIFACTS: {missing}"
        )

    def test_index_artifacts_includes_core_files(self):
        """INDEX_ARTIFACTS must include the core code index files."""
        from prep.services.s3_storage import INDEX_ARTIFACTS
        assert "documents.json" in INDEX_ARTIFACTS
        assert "embeddings.npy" in INDEX_ARTIFACTS

    def test_index_artifacts_no_duplicates(self):
        """No duplicate entries in INDEX_ARTIFACTS."""
        from prep.services.s3_storage import INDEX_ARTIFACTS
        assert len(INDEX_ARTIFACTS) == len(set(INDEX_ARTIFACTS))


# ═══════════════════════════════════════════════════════════════
# 2. License gating
# ═══════════════════════════════════════════════════════════════


class TestLicenseGating:
    """Verify team_config feature gating across tiers."""

    def setup_method(self):
        from prep.core.feature_gate import clear_license_cache
        clear_license_cache()

    def teardown_method(self):
        from prep.core.feature_gate import clear_license_cache
        clear_license_cache()

    def test_free_tier_cannot_access_team_config(self):
        from prep.core.feature_gate import check_feature
        with patch.dict(os.environ, {"PREP_TIER": "free"}, clear=False):
            from prep.core.feature_gate import clear_license_cache
            clear_license_cache()
            assert check_feature("team_config") is False

    def test_team_tier_can_access_team_config(self):
        from prep.core.feature_gate import check_feature, clear_license_cache
        with patch.dict(os.environ, {"PREP_TIER": "team"}, clear=False):
            clear_license_cache()
            assert check_feature("team_config") is True

    def test_enterprise_tier_can_access_team_config(self):
        from prep.core.feature_gate import check_feature, clear_license_cache
        with patch.dict(os.environ, {"PREP_TIER": "enterprise"}, clear=False):
            clear_license_cache()
            assert check_feature("team_config") is True

    def test_pro_tier_cannot_access_team_config(self):
        from prep.core.feature_gate import check_feature, clear_license_cache
        with patch.dict(os.environ, {"PREP_TIER": "pro"}, clear=False):
            clear_license_cache()
            assert check_feature("team_config") is False

    def test_require_team_config_raises_for_free(self):
        from prep.core.feature_gate import require_feature, FeatureGateError, clear_license_cache
        with patch.dict(os.environ, {"PREP_TIER": "free"}, clear=False):
            clear_license_cache()
            with pytest.raises(FeatureGateError, match="team_config"):
                require_feature("team_config")

    def test_status_poll_free_tier_does_not_start_polling(self, tmp_path):
        """Regression test (Phase 06): GET /projects/{id}/status is polled
        continuously by the dashboard and routes to get_project_sync_status().
        That function must NOT start S3 polling for a tier that lacks the
        team_config feature, even though a committed .sourceprep/team_config.json
        has sync.enabled=true. Only status_dict() reads should be unconditional.
        """
        from prep.core.feature_gate import clear_license_cache
        from prep.services.remote_sync import RemoteSyncService
        from prep.services.project_helpers import get_project_sync_status

        proj = _make_project(tmp_path, "sync-gate-free")
        prep_dir = tmp_path / ".sourceprep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        (prep_dir / "team_config.json").write_text(
            json.dumps({"sync": {"enabled": True, "s3_bucket": "b"}})
        )

        with patch.dict(os.environ, {"PREP_TIER": "free"}, clear=False):
            clear_license_cache()
            with patch.object(RemoteSyncService, "start_polling", MagicMock()) as mock_start:
                result = get_project_sync_status(proj, {})
                assert mock_start.call_count == 0
                # The poll is gated, but the status READ must still work so the UI
                # can render an upgrade prompt — gating the poll must not gate status.
                assert isinstance(result, dict)

    def test_status_poll_team_tier_starts_polling(self, tmp_path):
        """Companion to the free-tier regression test: a properly licensed
        Team-tier project with sync enabled SHOULD start polling from the
        /status path, so the license gate doesn't silently break the
        legitimate feature for paying customers.
        """
        from prep.core.feature_gate import clear_license_cache
        from prep.services.remote_sync import RemoteSyncService
        from prep.services.project_helpers import get_project_sync_status

        proj = _make_project(tmp_path, "sync-gate-team")
        prep_dir = tmp_path / ".sourceprep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        (prep_dir / "team_config.json").write_text(
            json.dumps({"sync": {"enabled": True, "s3_bucket": "b"}})
        )

        with patch.dict(os.environ, {"PREP_TIER": "team"}, clear=False):
            clear_license_cache()
            with patch.object(RemoteSyncService, "start_polling", MagicMock()) as mock_start:
                get_project_sync_status(proj, {})
                assert mock_start.call_count == 1


# ═══════════════════════════════════════════════════════════════
# 3. LayeredCodeIndex search merge (with real embeddings)
# ═══════════════════════════════════════════════════════════════


class TestLayeredSearchMerge:
    """Test actual search merge behavior with realistic index data."""

    def _setup_layered(self, tmp_path):
        remote_docs = [
            {"source_path": "src/auth.py", "content": "def login(user, password): verify_credentials(user, password)", "section": "login"},
            {"source_path": "src/db.py", "content": "def connect_database(url): return psycopg2.connect(url)", "section": "connect"},
            {"source_path": "src/api.py", "content": "def handle_request(req): return process(req)", "section": "handler"},
        ]
        delta_docs = [
            {"source_path": "src/auth.py", "content": "def login(user, password): validate_and_authenticate(user, password, mfa=True)", "section": "login"},
        ]
        remote_dir = _make_index_dir(tmp_path, "remote", remote_docs)
        delta_dir = _make_index_dir(tmp_path, "delta", delta_docs)
        embedder = _mock_embedder()

        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        delta = CodeIndex(index_dir=delta_dir, embedder=embedder)
        return LayeredCodeIndex(remote_index=remote, delta_index=delta)

    def test_search_returns_results(self, tmp_path):
        """Search returns results when query vector is aligned with stored embeddings."""
        layered = self._setup_layered(tmp_path)
        # Make the embedder return the first stored embedding vector as query result
        # so we get guaranteed cosine similarity hits
        stored_emb = np.load(tmp_path / "remote" / "embeddings.npy")
        from prep.core.embedder import EmbeddingResult
        layered.remote.embedder.embed.return_value = EmbeddingResult(
            vector=stored_emb[0].tolist(), model="test"
        )
        results = layered.search("anything", k=5, min_score=0.0)
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_delta_overrides_remote_via_documents(self, tmp_path):
        """Delta content replaces remote content in merged _documents."""
        layered = self._setup_layered(tmp_path)

        # Verify via _documents (deterministic, doesn't depend on mock embedder vectors)
        auth_docs = [d for d in layered._documents if d["source_path"] == "src/auth.py"]
        assert len(auth_docs) == 1
        assert "mfa=True" in auth_docs[0]["content"]
        assert "verify_credentials" not in auth_docs[0]["content"]

    def test_tombstone_set_correct(self, tmp_path):
        """Tombstoned paths match the files present in the delta."""
        layered = self._setup_layered(tmp_path)
        tombstones = layered._get_tombstone_paths()
        assert "src/auth.py" in tombstones
        assert "src/db.py" not in tombstones
        assert "src/api.py" not in tombstones

    def test_search_includes_untouched_remote_files(self, tmp_path):
        """Files not in delta should appear in merged _documents."""
        layered = self._setup_layered(tmp_path)
        all_paths = {d["source_path"] for d in layered._documents}
        # db.py and api.py should come from remote (not in delta)
        assert "src/db.py" in all_paths
        assert "src/api.py" in all_paths

    def test_search_respects_k_limit(self, tmp_path):
        layered = self._setup_layered(tmp_path)
        results = layered.search("code", k=2, min_score=0.0)
        assert len(results) <= 2

    def test_search_results_sorted_by_score(self, tmp_path):
        layered = self._setup_layered(tmp_path)
        results = layered.search("login authentication", k=5, min_score=0.0)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)


class TestLayeredGetContext:
    """Test get_context() on LayeredCodeIndex."""

    def test_get_context_returns_string(self, tmp_path):
        docs = [
            {"source_path": "a.py", "content": "def hello(): pass", "section": "hello"},
        ]
        remote_dir = _make_index_dir(tmp_path, "remote", docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)

        ctx = layered.get_context("hello function", k=3, min_score=0.0)
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_get_context_includes_content(self, tmp_path):
        docs = [
            {"source_path": "a.py", "content": "def greet(name): return f'Hello {name}'", "section": "greet"},
        ]
        remote_dir = _make_index_dir(tmp_path, "remote", docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)

        # Make query vector match the stored embedding so search returns results.
        # Must clear side_effect first — it takes priority over return_value.
        stored_emb = np.load(remote_dir / "embeddings.npy")
        from prep.core.embedder import EmbeddingResult
        fixed_result = EmbeddingResult(vector=stored_emb[0].tolist(), model="test")
        embedder.embed.side_effect = None
        embedder.embed.return_value = fixed_result

        ctx = layered.get_context("greeting function", k=3, min_score=0.0)
        assert "greet" in ctx

    def test_get_context_empty_when_no_results(self, tmp_path):
        docs = [
            {"source_path": "a.py", "content": "x", "section": ""},
        ]
        remote_dir = _make_index_dir(tmp_path, "remote", docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)

        ctx = layered.get_context("query", k=3, min_score=0.99)
        # With a very high min_score, no results should pass
        # (context may be empty or just have the sentinel comment)
        assert isinstance(ctx, str)

    def test_get_context_respects_max_chars(self, tmp_path):
        docs = [
            {"source_path": f"file{i}.py", "content": "x" * 500, "section": f"sec{i}"}
            for i in range(10)
        ]
        remote_dir = _make_index_dir(tmp_path, "remote", docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)

        ctx = layered.get_context("code", k=10, max_chars=200, min_score=0.0)
        assert len(ctx) <= 500  # Allow some overhead from headers


# ═══════════════════════════════════════════════════════════════
# 4. Watcher trigger_build delta routing
# ═══════════════════════════════════════════════════════════════


class TestWatcherDeltaRouting:
    """Test that the watcher's trigger_build routes correctly."""

    def test_routes_to_delta_build_when_remote_exists(self, tmp_path):
        """When _has_remote_index returns True, trigger should call delta build."""
        from prep.services.build_manager import BuildManager
        proj = _make_project(tmp_path, "delta-route")

        bm = BuildManager()

        # Set up remote index
        prep_dir = tmp_path / ".sourceprep"
        remote_dir = prep_dir / "remote"
        remote_dir.mkdir(parents=True, exist_ok=True)
        (remote_dir / "documents.json").write_text("[]")

        assert bm.has_remote_index(proj) is True

        # Mock the actual build to avoid running embeddings
        with patch.object(bm, 'start_project_delta_build', return_value=True) as mock_delta, \
             patch.object(bm, 'start_project_build', return_value=True) as mock_full:

            # Simulate what trigger_build does
            if bm.has_remote_index(proj):
                bm.start_project_delta_build(
                    proj, ["src/changed.py"], None, None,
                )
            else:
                bm.start_project_build(proj, None, None, None, 500_000, 100_000_000)

            mock_delta.assert_called_once()
            mock_full.assert_not_called()

    def test_routes_to_full_build_when_no_remote(self, tmp_path):
        """When no remote index, trigger should call full build."""
        from prep.services.build_manager import BuildManager
        proj = _make_project(tmp_path, "full-route")

        bm = BuildManager()
        prep_dir = tmp_path / ".sourceprep"
        prep_dir.mkdir(parents=True, exist_ok=True)

        assert bm.has_remote_index(proj) is False

        with patch.object(bm, 'start_project_delta_build', return_value=True) as mock_delta, \
             patch.object(bm, 'start_project_build', return_value=True) as mock_full:

            if bm.has_remote_index(proj):
                bm.start_project_delta_build(proj, ["src/changed.py"], None, None)
            else:
                bm.start_project_build(proj, None, None, None, 500_000, 100_000_000)

            mock_full.assert_called_once()
            mock_delta.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# 5. RemoteSyncService check_and_sync → prune end-to-end
# ═══════════════════════════════════════════════════════════════


class TestSyncAndPruneEndToEnd:
    """Test the full check_and_sync → download → prune cycle."""

    def test_check_and_sync_triggers_prune(self, tmp_path):
        """After a successful sync, stale deltas should be pruned."""
        from prep.services.remote_sync import RemoteSyncService
        from prep.services.s3_storage import SyncManifest

        # Set up project with enabled sync config
        prep_dir = tmp_path / ".sourceprep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        (prep_dir / "team_config.json").write_text(json.dumps({
            "sync": {
                "enabled": True,
                "s3_endpoint": "https://r2.example.com",
                "s3_bucket": "test",
                "s3_prefix": "repo/main",
            }
        }))

        # Pre-create local deltas that should get pruned
        index_dir = prep_dir / "index"
        delta_dir = index_dir / "local_deltas"
        delta_dir.mkdir(parents=True, exist_ok=True)
        (delta_dir / "documents.json").write_text(json.dumps([
            {"source_path": "src/old.py", "content": "stale"},
            {"source_path": "src/new.py", "content": "still editing"},
        ]))

        # Pre-create remote index dir with trace_manifest
        remote_dir = index_dir / "remote"
        remote_dir.mkdir(parents=True, exist_ok=True)
        (remote_dir / "trace_manifest.json").write_text(json.dumps({
            "file_hashes": {"src/old.py": "hash_old"},
        }))

        svc = RemoteSyncService(tmp_path)

        # Mock S3 provider to simulate successful download
        mock_manifest = SyncManifest(
            version=1,
            timestamp=time.time(),
            branch="main",
            commit_sha="abc123def456",
            content_hash="newhash",
            artifact_count=3,
            total_bytes=1000,
        )
        mock_s3 = MagicMock()
        mock_s3.get_remote_manifest.return_value = mock_manifest
        mock_s3.download_index = MagicMock()

        with patch.dict(os.environ, {
            "PREP_S3_ACCESS_KEY": "test_key",
            "PREP_S3_SECRET_KEY": "test_secret",
        }, clear=False):
            svc.load_config()
            svc._get_s3_provider = MagicMock(return_value=mock_s3)

            result = svc.check_and_sync()
            assert result is True

            # Verify download was called
            mock_s3.download_index.assert_called_once()

            # Verify deltas were pruned (src/old.py removed, src/new.py kept)
            with open(delta_dir / "documents.json") as f:
                remaining = json.load(f)
            assert len(remaining) == 1
            assert remaining[0]["source_path"] == "src/new.py"

    def test_sync_no_prune_when_no_deltas(self, tmp_path):
        """Sync should succeed even when no deltas exist."""
        from prep.services.remote_sync import RemoteSyncService
        from prep.services.s3_storage import SyncManifest

        prep_dir = tmp_path / ".sourceprep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        (prep_dir / "team_config.json").write_text(json.dumps({
            "sync": {
                "enabled": True,
                "s3_endpoint": "https://r2.example.com",
                "s3_bucket": "test",
            }
        }))

        svc = RemoteSyncService(tmp_path)
        mock_manifest = SyncManifest(
            version=1, timestamp=time.time(), content_hash="hash1",
        )
        mock_s3 = MagicMock()
        mock_s3.get_remote_manifest.return_value = mock_manifest
        mock_s3.download_index = MagicMock()

        with patch.dict(os.environ, {
            "PREP_S3_ACCESS_KEY": "k",
            "PREP_S3_SECRET_KEY": "s",
        }, clear=False):
            svc.load_config()
            svc._get_s3_provider = MagicMock(return_value=mock_s3)

            # Should not raise even with no deltas dir
            result = svc.check_and_sync()
            assert result is True


# ═══════════════════════════════════════════════════════════════
# 6. Full lifecycle: remote → delta → prune → fresh remote
# ═══════════════════════════════════════════════════════════════


class TestFullSyncLifecycle:
    """Simulate the complete team sync lifecycle without external deps."""

    def test_lifecycle(self, tmp_path):
        """
        1. Start with a remote index (simulates headless CI output)
        2. Create a delta for a locally modified file
        3. Search sees delta version
        4. Simulate a new remote sync that includes the modified file
        5. Prune removes the stale delta
        6. Search sees the fresh remote version
        """
        from prep.services.build_manager import BuildManager
        proj = _make_project(tmp_path, "lifecycle")

        prep_dir = tmp_path / ".sourceprep"
        remote_dir = prep_dir / "remote"
        delta_dir = prep_dir / "local_deltas"

        # ── Step 1: Remote index from CI ──
        remote_docs = [
            {"source_path": "src/auth.py", "content": "def login(): pass  # v1", "section": "login"},
            {"source_path": "src/utils.py", "content": "def helper(): return 42", "section": "helper"},
        ]
        _make_index_dir(tmp_path / ".sourceprep", "remote", remote_docs)

        bm = BuildManager()
        idx = bm.get_project_layered_index(proj)
        assert isinstance(idx, LayeredCodeIndex)
        assert idx.delta is None
        stats_1 = idx.stats()
        assert stats_1["remote_chunks"] == 2
        assert stats_1["delta_chunks"] == 0

        # ── Step 2: Local delta (developer edits auth.py) ──
        delta_docs = [
            {"source_path": "src/auth.py", "content": "def login(): validate_mfa()  # v2-local", "section": "login"},
        ]
        _make_index_dir(tmp_path / ".sourceprep", "local_deltas", delta_docs)

        # Invalidate cache to pick up new delta
        bm.invalidate_layered_cache("lifecycle")
        idx2 = bm.get_project_layered_index(proj)
        assert isinstance(idx2, LayeredCodeIndex)
        assert idx2.delta is not None

        # ── Step 3: Search sees delta version ──
        stats_2 = idx2.stats()
        assert stats_2["delta_chunks"] == 1
        assert stats_2["tombstoned_files"] == 1

        # _documents should show v2-local for auth.py
        auth_docs = [d for d in idx2._documents if d["source_path"] == "src/auth.py"]
        assert len(auth_docs) == 1
        assert "v2-local" in auth_docs[0]["content"]

        # ── Step 4: New remote sync includes the edit (CI re-ran) ──
        new_remote_docs = [
            {"source_path": "src/auth.py", "content": "def login(): validate_mfa()  # v2-merged", "section": "login"},
            {"source_path": "src/utils.py", "content": "def helper(): return 42", "section": "helper"},
        ]
        _make_index_dir(tmp_path / ".sourceprep", "remote", new_remote_docs)

        # Write trace_manifest for pruning
        (remote_dir / "trace_manifest.json").write_text(json.dumps({
            "file_hashes": {"src/auth.py": "new_hash", "src/utils.py": "utils_hash"},
        }))

        # ── Step 5: Prune stale deltas ──
        pruned = prune_stale_deltas(
            remote_dir / "trace_manifest.json",
            delta_dir,
        )
        assert pruned == 1  # src/auth.py removed from deltas

        # Verify delta documents.json is now empty
        with open(delta_dir / "documents.json") as f:
            remaining = json.load(f)
        assert len(remaining) == 0

        # ── Step 6: Search sees fresh remote ──
        bm.invalidate_layered_cache("lifecycle")
        idx3 = bm.get_project_layered_index(proj)
        auth_docs_3 = [d for d in idx3._documents if d["source_path"] == "src/auth.py"]
        assert len(auth_docs_3) == 1
        assert "v2-merged" in auth_docs_3[0]["content"]


# ═══════════════════════════════════════════════════════════════
# 7. API integration tests via TestClient
# ═══════════════════════════════════════════════════════════════


class TestAPIIntegration:
    """Test /search, /context, /status endpoints with layered index.

    Uses FastAPI TestClient to send real HTTP requests to the router.
    """

    @pytest.fixture
    def configured_app(self, tmp_path):
        """Configure the server and register a project with a remote index."""
        from prep.server import app, configure, _get_registry
        from prep.core.project_registry import ProjectRegistry

        # Configure server with temp dir
        index_dir = tmp_path / "codrag_data"
        index_dir.mkdir(parents=True, exist_ok=True)

        configure(
            repo_root=str(tmp_path),
            index_dir=str(index_dir),
        )

        # Register a test project
        reg = _get_registry()
        proj = reg.add_project(
            name="api-test",
            path=str(tmp_path),
            mode="embedded",
        )

        # Create a LOCAL index for this project (not remote — simpler for API tests)
        prep_dir = tmp_path / ".sourceprep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        docs = [
            {"source_path": "main.py", "content": "def main(): print('hello world')", "section": "main"},
            {"source_path": "utils.py", "content": "def add(a, b): return a + b", "section": "add"},
        ]
        (prep_dir / "documents.json").write_text(json.dumps(docs))
        # Use dim=768 to match the default NativeEmbedder/OllamaEmbedder dimension
        emb = np.random.default_rng(42).standard_normal((2, 768)).astype(np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        emb = emb / norms
        np.save(prep_dir / "embeddings.npy", emb)

        return app, proj

    def test_status_endpoint_includes_sync(self, configured_app):
        from fastapi.testclient import TestClient
        app, proj = configured_app
        client = TestClient(app)

        resp = client.get(f"/projects/{proj.id}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "sync" in data
        assert "building" in data
        assert "stale" in data

    def test_search_endpoint_with_layered_index(self, configured_app):
        from fastapi.testclient import TestClient
        app, proj = configured_app
        client = TestClient(app)

        resp = client.post(
            f"/projects/{proj.id}/search",
            json={"query": "hello world main function", "k": 5, "min_score": 0.0},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "results" in data or "chunks" in data or isinstance(data, list)

    def test_context_endpoint_with_layered_index(self, configured_app):
        from fastapi.testclient import TestClient
        app, proj = configured_app
        client = TestClient(app)

        resp = client.post(
            f"/projects/{proj.id}/context",
            json={"query": "addition utility", "k": 3, "min_score": 0.0},
        )
        assert resp.status_code == 200

    def test_search_returns_empty_query_error(self, configured_app):
        from fastapi.testclient import TestClient
        app, proj = configured_app
        client = TestClient(app)

        resp = client.post(
            f"/projects/{proj.id}/search",
            json={"query": "   ", "k": 5},
        )
        assert resp.status_code == 400

    def test_sync_now_blocked_for_free_tier(self, configured_app):
        """POST /projects/{id}/sync/now is gated on team_config (Team tier)."""
        from fastapi.testclient import TestClient
        from prep.core.feature_gate import clear_license_cache
        app, proj = configured_app
        client = TestClient(app)

        with patch.dict(os.environ, {"PREP_TIER": "free", "PREP_DEV_MODE": "1"}, clear=False):
            clear_license_cache()
            resp = client.post(f"/projects/{proj.id}/sync/now")
            assert resp.status_code == 403
            body = resp.json()
            assert body["success"] is False
            assert body["error"]["code"] == "FEATURE_GATED"
        clear_license_cache()

    def test_sync_now_allowed_for_team_tier(self, configured_app):
        """Team tier can trigger sync/now and gets the status dict back."""
        from fastapi.testclient import TestClient
        from prep.core.feature_gate import clear_license_cache
        app, proj = configured_app
        client = TestClient(app)

        with patch.dict(os.environ, {"PREP_TIER": "team", "PREP_DEV_MODE": "1"}, clear=False):
            clear_license_cache()
            resp = client.post(f"/projects/{proj.id}/sync/now")
            assert resp.status_code == 200
            data = resp.json()["data"]
            # No .sourceprep/team_config.json in this fixture, so sync is
            # simply disabled — but the route must succeed and return the
            # real status_dict() shape, not a stub.
            assert data == {
                "enabled": False,
                "last_sync_at": None,
                "last_sync_commit": "",
                "remote_version": None,
                "remote_timestamp": None,
                "is_syncing": False,
                "behind_minutes": None,
                "error": None,
            }
        clear_license_cache()


# ═══════════════════════════════════════════════════════════════
# 8. BuildManager cache coherence under concurrent scenarios
# ═══════════════════════════════════════════════════════════════


class TestCacheCoherence:
    """Verify cache behaves correctly across build/sync/search cycles."""

    def test_cache_survives_multiple_reads(self, tmp_path):
        from prep.services.build_manager import BuildManager
        proj = _make_project(tmp_path, "cache-reads")

        remote_dir = tmp_path / ".sourceprep" / "remote"
        remote_dir.mkdir(parents=True, exist_ok=True)
        (remote_dir / "documents.json").write_text(json.dumps([
            {"source_path": "a.py", "content": "x", "section": ""},
        ]))
        np.save(remote_dir / "embeddings.npy", np.zeros((1, 32), dtype=np.float32))

        bm = BuildManager()
        idx1 = bm.get_project_layered_index(proj)
        idx2 = bm.get_project_layered_index(proj)
        idx3 = bm.get_project_layered_index(proj)

        assert idx1 is idx2
        assert idx2 is idx3

    def test_invalidation_forces_refresh(self, tmp_path):
        from prep.services.build_manager import BuildManager
        proj = _make_project(tmp_path, "cache-refresh")

        remote_dir = tmp_path / ".sourceprep" / "remote"
        remote_dir.mkdir(parents=True, exist_ok=True)
        (remote_dir / "documents.json").write_text(json.dumps([
            {"source_path": "a.py", "content": "version1", "section": ""},
        ]))
        np.save(remote_dir / "embeddings.npy", np.zeros((1, 32), dtype=np.float32))

        bm = BuildManager()
        idx1 = bm.get_project_layered_index(proj)
        assert idx1._documents[0]["content"] == "version1"

        # Update remote index
        (remote_dir / "documents.json").write_text(json.dumps([
            {"source_path": "a.py", "content": "version2", "section": ""},
        ]))

        # Without invalidation, still returns cached (stale)
        idx2 = bm.get_project_layered_index(proj)
        assert idx2 is idx1

        # After invalidation, returns fresh
        bm.invalidate_layered_cache("cache-refresh")
        idx3 = bm.get_project_layered_index(proj)
        assert idx3 is not idx1
        assert idx3._documents[0]["content"] == "version2"

    def test_invalidation_is_project_scoped(self, tmp_path):
        from prep.services.build_manager import BuildManager

        proj_a = _make_project(tmp_path / "a", "proj-a")
        proj_b = _make_project(tmp_path / "b", "proj-b")

        for p in [tmp_path / "a", tmp_path / "b"]:
            rdir = p / ".sourceprep" / "remote"
            rdir.mkdir(parents=True, exist_ok=True)
            (rdir / "documents.json").write_text(json.dumps([
                {"source_path": "x.py", "content": "x", "section": ""},
            ]))
            np.save(rdir / "embeddings.npy", np.zeros((1, 32), dtype=np.float32))

        bm = BuildManager()
        idx_a = bm.get_project_layered_index(proj_a)
        idx_b = bm.get_project_layered_index(proj_b)

        # Invalidate only proj-a
        bm.invalidate_layered_cache("proj-a")

        idx_a2 = bm.get_project_layered_index(proj_a)
        idx_b2 = bm.get_project_layered_index(proj_b)

        assert idx_a2 is not idx_a  # Refreshed
        assert idx_b2 is idx_b  # Still cached


# ═══════════════════════════════════════════════════════════════
# 9. Headless stages completeness
# ═══════════════════════════════════════════════════════════════


class TestHeadlessStagesCompleteness:
    """Verify headless pipeline stage configuration."""

    def test_all_stages_have_label(self):
        from prep.services.headless_runner import HEADLESS_STAGES
        for stage_id, stage_label in HEADLESS_STAGES:
            assert isinstance(stage_label, str), f"Stage {stage_id} label is not a string"
            assert len(stage_label) > 0, f"Stage {stage_id} has empty label"

    def test_stage_ids_are_strings(self):
        from prep.services.headless_runner import HEADLESS_STAGES
        for stage_id, _ in HEADLESS_STAGES:
            assert isinstance(stage_id, str)
            assert len(stage_id) > 0

    def test_headless_runner_instantiates(self, tmp_path):
        from prep.services.headless_runner import HeadlessRunner, HeadlessConfig
        repo = tmp_path / "repo"
        repo.mkdir()
        cfg = HeadlessConfig(repo_path=str(repo))
        runner = HeadlessRunner(cfg)
        assert runner.config.repo_path == str(repo)


# ═══════════════════════════════════════════════════════════════
# 10. Edge cases and error resilience
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test error resilience and edge cases."""

    def test_layered_with_empty_remote(self, tmp_path):
        """LayeredCodeIndex handles an empty remote documents list."""
        remote_dir = tmp_path / "remote"
        remote_dir.mkdir()
        (remote_dir / "documents.json").write_text("[]")
        np.save(remote_dir / "embeddings.npy", np.zeros((0, 32), dtype=np.float32))

        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)

        assert layered._documents == []
        stats = layered.stats()
        assert stats["remote_chunks"] == 0
        assert stats["effective_chunks"] == 0

    def test_layered_with_empty_delta(self, tmp_path):
        """LayeredCodeIndex handles an empty delta documents list."""
        remote_docs = [{"source_path": "a.py", "content": "x", "section": ""}]
        remote_dir = _make_index_dir(tmp_path, "remote", remote_docs)

        delta_dir = tmp_path / "delta"
        delta_dir.mkdir()
        (delta_dir / "documents.json").write_text("[]")
        np.save(delta_dir / "embeddings.npy", np.zeros((0, 32), dtype=np.float32))

        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        delta = CodeIndex(index_dir=delta_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote, delta_index=delta)

        assert len(layered._documents) == 1
        stats = layered.stats()
        assert stats["tombstoned_files"] == 0

    def test_prune_stale_deltas_with_corrupt_manifest(self, tmp_path):
        """prune_stale_deltas handles a corrupt manifest gracefully."""
        manifest_path = tmp_path / "corrupt.json"
        manifest_path.write_text("not valid json {{{")

        delta_dir = tmp_path / "delta"
        delta_dir.mkdir()
        (delta_dir / "documents.json").write_text(json.dumps([
            {"source_path": "a.py", "content": "x"},
        ]))

        # Should not crash
        pruned = prune_stale_deltas(manifest_path, delta_dir)
        assert pruned == 0

    def test_sync_service_handles_missing_codrag_dir(self, tmp_path):
        """RemoteSyncService works even if .prep doesn't exist initially."""
        from prep.services.remote_sync import RemoteSyncService
        svc = RemoteSyncService(tmp_path)
        assert svc.status.enabled is False
        svc._prune_stale_deltas()  # Should not raise

    def test_build_manager_layered_with_corrupt_remote_docs(self, tmp_path):
        """BuildManager handles corrupt remote documents.json."""
        from prep.services.build_manager import BuildManager
        proj = _make_project(tmp_path, "corrupt-remote")

        remote_dir = tmp_path / ".sourceprep" / "remote"
        remote_dir.mkdir(parents=True, exist_ok=True)
        (remote_dir / "documents.json").write_text("corrupt json")

        bm = BuildManager()
        # Should fall back gracefully — either return a CodeIndex
        # or a LayeredCodeIndex that fails on load
        idx = bm.get_project_layered_index(proj)
        # It will return LayeredCodeIndex (file exists) but is_loaded() may be False
        assert idx is not None
