"""
Tests for S3StorageProvider (P06-S19).

Uses a temp directory to mock S3 operations at the filesystem level.
For real S3 integration testing, use moto or a local MinIO container.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from codrag.services.s3_storage import (
    INDEX_ARTIFACTS,
    S3Config,
    S3StorageProvider,
    SyncManifest,
)


# ── SyncManifest ──────────────────────────────────────────────


class TestSyncManifest:
    def test_roundtrip(self):
        m = SyncManifest(
            version=1,
            timestamp=1700000000.0,
            branch="main",
            commit_sha="abc123",
            content_hash="deadbeef",
            artifact_count=5,
            total_bytes=12345,
        )
        d = m.to_dict()
        m2 = SyncManifest.from_dict(d)
        assert m2.version == 1
        assert m2.branch == "main"
        assert m2.commit_sha == "abc123"
        assert m2.content_hash == "deadbeef"
        assert m2.artifact_count == 5
        assert m2.total_bytes == 12345

    def test_from_dict_defaults(self):
        m = SyncManifest.from_dict({})
        assert m.version == 1
        assert m.branch == "main"
        assert m.commit_sha == ""

    def test_to_dict_json_serializable(self):
        m = SyncManifest(timestamp=time.time())
        s = json.dumps(m.to_dict())
        assert isinstance(s, str)


# ── S3Config ──────────────────────────────────────────────────


class TestS3Config:
    def test_from_env(self):
        env = {
            "CODRAG_S3_ENDPOINT": "https://r2.example.com",
            "CODRAG_S3_BUCKET": "my-bucket",
            "CODRAG_S3_PREFIX": "indexes/repo",
            "CODRAG_S3_ACCESS_KEY": "AKIA...",
            "CODRAG_S3_SECRET_KEY": "secret",
            "CODRAG_S3_REGION": "us-east-1",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = S3Config.from_env()
            assert cfg.endpoint == "https://r2.example.com"
            assert cfg.bucket == "my-bucket"
            assert cfg.prefix == "indexes/repo"
            assert cfg.access_key == "AKIA..."
            assert cfg.secret_key == "secret"
            assert cfg.region == "us-east-1"

    def test_from_env_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = S3Config.from_env()
            assert cfg.bucket == ""
            assert cfg.region == "auto"

    def test_validate_empty(self):
        cfg = S3Config()
        errors = cfg.validate()
        assert len(errors) == 3  # bucket, access_key, secret_key

    def test_validate_complete(self):
        cfg = S3Config(bucket="b", access_key="a", secret_key="s")
        errors = cfg.validate()
        assert errors == []

    def test_s3_key_with_prefix(self):
        cfg = S3Config(bucket="b", prefix="indexes/repo", access_key="a", secret_key="s")
        provider = S3StorageProvider(cfg)
        assert provider._s3_key("index.zip") == "indexes/repo/index.zip"

    def test_s3_key_no_prefix(self):
        cfg = S3Config(bucket="b", prefix="", access_key="a", secret_key="s")
        provider = S3StorageProvider(cfg)
        assert provider._s3_key("manifest.json") == "manifest.json"

    def test_s3_key_trailing_slash(self):
        cfg = S3Config(bucket="b", prefix="indexes/repo/", access_key="a", secret_key="s")
        provider = S3StorageProvider(cfg)
        assert provider._s3_key("index.zip") == "indexes/repo/index.zip"


# ── S3StorageProvider upload/download ─────────────────────────


class TestS3StorageProviderUpload:
    """Test upload_index with a mocked boto3 client."""

    def _make_index_dir(self, tmp_path: Path) -> Path:
        """Create a fake index directory with test artifacts."""
        idx = tmp_path / "index"
        idx.mkdir()
        (idx / "documents.json").write_text('[{"id": "doc1"}]')
        np.save(idx / "embeddings.npy", np.zeros((1, 768), dtype=np.float32))
        (idx / "trace_manifest.json").write_text('{"version": 3}')
        return idx

    def test_upload_creates_manifest(self, tmp_path):
        """Verify upload_index creates a SyncManifest with correct fields."""
        idx = self._make_index_dir(tmp_path)
        uploaded = {}

        mock_client = MagicMock()
        mock_client.upload_file = MagicMock(side_effect=lambda src, bucket, key: uploaded.update({key: src}))
        mock_client.copy_object = MagicMock()
        mock_client.delete_object = MagicMock()
        mock_client.put_object = MagicMock()

        cfg = S3Config(bucket="test-bucket", prefix="test", access_key="a", secret_key="s")
        provider = S3StorageProvider(cfg)
        provider._client = mock_client

        manifest = provider.upload_index(idx, branch="main", commit_sha="abc123def")

        assert manifest.branch == "main"
        assert manifest.commit_sha == "abc123def"
        assert manifest.artifact_count == 3  # documents.json, embeddings.npy, trace_manifest.json
        assert manifest.total_bytes > 0
        assert manifest.content_hash != ""

        # Verify atomic swap: upload to .tmp, copy to final, delete .tmp
        mock_client.upload_file.assert_called_once()
        mock_client.copy_object.assert_called_once()
        mock_client.delete_object.assert_called_once()

        # Verify manifest was uploaded
        mock_client.put_object.assert_called_once()
        put_args = mock_client.put_object.call_args
        assert put_args.kwargs["Key"] == "test/manifest.json"

    def test_upload_empty_dir_raises(self, tmp_path):
        idx = tmp_path / "empty"
        idx.mkdir()

        cfg = S3Config(bucket="b", access_key="a", secret_key="s")
        provider = S3StorageProvider(cfg)
        provider._client = MagicMock()

        with pytest.raises(ValueError, match="No index artifacts"):
            provider.upload_index(idx)


class TestS3StorageProviderDownload:
    """Test download_index and get_remote_manifest with mocked boto3."""

    def test_get_remote_manifest_not_found(self):
        mock_client = MagicMock()
        # Simulate NoSuchKey
        error = type("NoSuchKey", (Exception,), {})
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchKey = error
        mock_client.get_object = MagicMock(side_effect=error("not found"))

        cfg = S3Config(bucket="b", access_key="a", secret_key="s")
        provider = S3StorageProvider(cfg)
        provider._client = mock_client

        result = provider.get_remote_manifest()
        assert result is None

    def test_get_remote_manifest_success(self):
        manifest_data = json.dumps({
            "version": 1,
            "timestamp": 1700000000.0,
            "branch": "main",
            "commit_sha": "abc123",
            "content_hash": "deadbeef",
        }).encode()

        mock_body = MagicMock()
        mock_body.read.return_value = manifest_data

        mock_client = MagicMock()
        mock_client.get_object = MagicMock(return_value={"Body": mock_body})

        cfg = S3Config(bucket="b", prefix="p", access_key="a", secret_key="s")
        provider = S3StorageProvider(cfg)
        provider._client = mock_client

        m = provider.get_remote_manifest()
        assert m is not None
        assert m.branch == "main"
        assert m.commit_sha == "abc123"
        mock_client.get_object.assert_called_once_with(Bucket="b", Key="p/manifest.json")
