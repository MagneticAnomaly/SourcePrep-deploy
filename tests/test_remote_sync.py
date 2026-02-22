"""
Tests for RemoteSyncService and secrets leakage detection (P06-S22).
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from codrag.services.remote_sync import (
    SECRETS_FILENAME,
    TEAM_CONFIG_FILENAME,
    RemoteSyncService,
    SyncStatus,
    TeamSyncConfig,
    _check_for_leaked_secrets,
    _resolve_s3_credentials,
)


# ── TeamSyncConfig ────────────────────────────────────────────


class TestTeamSyncConfig:
    def test_from_dict_defaults(self):
        cfg = TeamSyncConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.s3_bucket == ""
        assert cfg.poll_interval_minutes == 30

    def test_from_dict_full(self):
        cfg = TeamSyncConfig.from_dict({
            "sync": {
                "enabled": True,
                "s3_endpoint": "https://r2.example.com",
                "s3_bucket": "my-bucket",
                "s3_prefix": "indexes/repo",
                "poll_interval_minutes": 15,
            }
        })
        assert cfg.enabled is True
        assert cfg.s3_endpoint == "https://r2.example.com"
        assert cfg.s3_bucket == "my-bucket"
        assert cfg.s3_prefix == "indexes/repo"
        assert cfg.poll_interval_minutes == 15


# ── SyncStatus ────────────────────────────────────────────────


class TestSyncStatus:
    def test_to_dict(self):
        s = SyncStatus(enabled=True, last_sync_at=1700000000.0, last_sync_commit="abc123")
        d = s.to_dict()
        assert d["enabled"] is True
        assert d["last_sync_commit"] == "abc123"
        assert d["is_syncing"] is False
        assert d["error"] is None

    def test_behind_minutes(self):
        s = SyncStatus(
            last_sync_at=1700000000.0,
            remote_timestamp=1700000600.0,  # 10 minutes later
        )
        behind = s._behind_minutes()
        assert behind is not None
        assert abs(behind - 10.0) < 0.01

    def test_behind_minutes_none_when_up_to_date(self):
        s = SyncStatus(
            last_sync_at=1700000600.0,
            remote_timestamp=1700000000.0,  # remote is older
        )
        assert s._behind_minutes() is None

    def test_behind_minutes_none_when_no_data(self):
        s = SyncStatus()
        assert s._behind_minutes() is None


# ── Credential resolution ─────────────────────────────────────


class TestResolveS3Credentials:
    def test_from_env_vars(self, tmp_path):
        env = {
            "CODRAG_S3_ACCESS_KEY": "AKIA_TEST",
            "CODRAG_S3_SECRET_KEY": "secret_test",
        }
        with patch.dict(os.environ, env, clear=False):
            creds = _resolve_s3_credentials(tmp_path)
            assert creds["access_key"] == "AKIA_TEST"
            assert creds["secret_key"] == "secret_test"

    def test_from_secrets_file(self, tmp_path):
        secrets = {"s3_access_key": "file_key", "s3_secret_key": "file_secret"}
        (tmp_path / SECRETS_FILENAME).write_text(json.dumps(secrets))

        # Clear env vars to force file resolution
        with patch.dict(os.environ, {"CODRAG_S3_ACCESS_KEY": "", "CODRAG_S3_SECRET_KEY": ""}, clear=False):
            creds = _resolve_s3_credentials(tmp_path)
            assert creds["access_key"] == "file_key"
            assert creds["secret_key"] == "file_secret"

    def test_env_takes_priority_over_file(self, tmp_path):
        secrets = {"s3_access_key": "file_key", "s3_secret_key": "file_secret"}
        (tmp_path / SECRETS_FILENAME).write_text(json.dumps(secrets))

        env = {
            "CODRAG_S3_ACCESS_KEY": "env_key",
            "CODRAG_S3_SECRET_KEY": "env_secret",
        }
        with patch.dict(os.environ, env, clear=False):
            creds = _resolve_s3_credentials(tmp_path)
            assert creds["access_key"] == "env_key"  # env wins

    def test_empty_when_nothing_configured(self, tmp_path):
        with patch.dict(os.environ, {"CODRAG_S3_ACCESS_KEY": "", "CODRAG_S3_SECRET_KEY": ""}, clear=False):
            creds = _resolve_s3_credentials(tmp_path)
            assert creds["access_key"] == ""
            assert creds["secret_key"] == ""

    def test_corrupt_secrets_file(self, tmp_path):
        (tmp_path / SECRETS_FILENAME).write_text("not json")
        with patch.dict(os.environ, {"CODRAG_S3_ACCESS_KEY": "", "CODRAG_S3_SECRET_KEY": ""}, clear=False):
            creds = _resolve_s3_credentials(tmp_path)
            assert creds["access_key"] == ""


# ── Secrets leakage detection ─────────────────────────────────


class TestCheckForLeakedSecrets:
    def test_clean_config_no_warning(self, caplog):
        data = {
            "sync": {
                "enabled": True,
                "s3_bucket": "my-bucket",
                "s3_endpoint": "https://r2.example.com",
            }
        }
        _check_for_leaked_secrets(data, "test_config.json")
        assert "SECURITY" not in caplog.text

    def test_detects_access_key(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            data = {
                "sync": {
                    "s3_bucket": "my-bucket",
                    "access_key": "AKIA1234567890ABCDEF",
                }
            }
            _check_for_leaked_secrets(data, "test_config.json")
            assert "SECURITY" in caplog.text
            assert "sync.access_key" in caplog.text

    def test_detects_nested_secret(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            data = {
                "auth": {
                    "api_key": "sk-long-api-key-here",
                }
            }
            _check_for_leaked_secrets(data, "test.json")
            assert "SECURITY" in caplog.text

    def test_ignores_short_values(self, caplog):
        """Short values (≤4 chars) are likely boolean-like or empty, not real secrets."""
        import logging
        with caplog.at_level(logging.WARNING):
            data = {"token": ""}  # empty
            _check_for_leaked_secrets(data, "test.json")
            assert "SECURITY" not in caplog.text

    def test_detects_in_lists(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            data = {
                "endpoints": [
                    {"url": "https://r2.example.com", "secret_key": "super-secret-key-12345"}
                ]
            }
            _check_for_leaked_secrets(data, "test.json")
            assert "SECURITY" in caplog.text


# ── RemoteSyncService ─────────────────────────────────────────


class TestRemoteSyncService:
    def _make_project(self, tmp_path: Path, config: Dict[str, Any] = None) -> Path:
        """Create a fake project root with .codrag/ directory."""
        codrag = tmp_path / ".codrag"
        codrag.mkdir(parents=True)
        if config:
            (codrag / TEAM_CONFIG_FILENAME).write_text(json.dumps(config))
        return tmp_path

    def test_load_config_missing_file(self, tmp_path):
        root = self._make_project(tmp_path)
        svc = RemoteSyncService(root)
        cfg = svc.load_config()
        assert cfg is None
        assert svc.status.enabled is False

    def test_load_config_disabled(self, tmp_path):
        root = self._make_project(tmp_path, {"sync": {"enabled": False}})
        svc = RemoteSyncService(root)
        cfg = svc.load_config()
        assert cfg is not None
        assert cfg.enabled is False

    def test_load_config_enabled(self, tmp_path):
        root = self._make_project(tmp_path, {
            "sync": {
                "enabled": True,
                "s3_bucket": "test-bucket",
                "s3_endpoint": "https://r2.example.com",
                "poll_interval_minutes": 10,
            }
        })
        svc = RemoteSyncService(root)
        cfg = svc.load_config()
        assert cfg.enabled is True
        assert cfg.s3_bucket == "test-bucket"
        assert cfg.poll_interval_minutes == 10

    def test_load_config_with_leaked_secrets_warns(self, tmp_path, caplog):
        import logging
        root = self._make_project(tmp_path, {
            "sync": {
                "enabled": True,
                "s3_bucket": "test-bucket",
                "access_key": "AKIA_LEAKED_IN_CONFIG_FILE",
            }
        })
        with caplog.at_level(logging.WARNING):
            svc = RemoteSyncService(root)
            svc.load_config()
            assert "SECURITY" in caplog.text

    def test_check_and_sync_disabled(self, tmp_path):
        root = self._make_project(tmp_path, {"sync": {"enabled": False}})
        svc = RemoteSyncService(root)
        assert svc.check_and_sync() is False

    def test_check_and_sync_no_credentials(self, tmp_path):
        root = self._make_project(tmp_path, {
            "sync": {"enabled": True, "s3_bucket": "b"}
        })
        with patch.dict(os.environ, {"CODRAG_S3_ACCESS_KEY": "", "CODRAG_S3_SECRET_KEY": ""}, clear=False):
            svc = RemoteSyncService(root)
            assert svc.check_and_sync() is False
            assert "credentials" in svc.status.error.lower()

    def test_status_dict(self, tmp_path):
        root = self._make_project(tmp_path)
        svc = RemoteSyncService(root)
        d = svc.status_dict()
        assert "enabled" in d
        assert "is_syncing" in d
        assert "behind_minutes" in d
        assert "error" in d
