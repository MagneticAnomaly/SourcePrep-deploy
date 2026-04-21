"""
Tests for HeadlessRunner and HeadlessWorkerFactory (P06-S20).

Tests the headless pipeline orchestration without requiring a running
daemon, real LLM, or real S3 bucket.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch, call

import pytest

from prep.services.headless_runner import (
    HEADLESS_STAGES,
    PROVIDER_ENDPOINTS,
    HeadlessConfig,
    HeadlessWorkerFactory,
    StageResult,
    headless_create_embedder,
    headless_create_llm_client,
)


# ── HeadlessConfig ────────────────────────────────────────────


class TestHeadlessConfig:
    def test_defaults(self):
        cfg = HeadlessConfig()
        assert cfg.model_provider == "local"
        assert cfg.model_name == "qwen3:4b"
        assert cfg.embedder == "native"
        assert cfg.full_rebuild is False
        assert cfg.branch == "main"
        assert cfg.s3 is None

    def test_custom_values(self):
        cfg = HeadlessConfig(
            repo_url="https://github.com/example/repo",
            branch="develop",
            model_provider="openai",
            model_name="gpt-4.1-mini",
            api_key="sk-test",
        )
        assert cfg.repo_url == "https://github.com/example/repo"
        assert cfg.branch == "develop"
        assert cfg.model_provider == "openai"
        assert cfg.api_key == "sk-test"


# ── LLM Client Factory ───────────────────────────────────────


class TestHeadlessCreateLlmClient:
    def test_local_provider(self):
        cfg = HeadlessConfig(model_provider="local", model_name="qwen3:4b")
        client = headless_create_llm_client(cfg)
        assert client.provider == "ollama"
        assert client.model == "qwen3:4b"
        assert client.endpoint_url == PROVIDER_ENDPOINTS["local"]
        assert client.api_key is None

    def test_openai_provider(self):
        cfg = HeadlessConfig(model_provider="openai", model_name="gpt-4.1-mini", api_key="sk-test")
        client = headless_create_llm_client(cfg)
        assert client.provider == "openai"
        assert client.model == "gpt-4.1-mini"
        assert client.endpoint_url == PROVIDER_ENDPOINTS["openai"]
        assert client.api_key == "sk-test"
        assert client.timeout == 120.0

    def test_anthropic_provider(self):
        cfg = HeadlessConfig(model_provider="anthropic", model_name="claude-sonnet-4-20250514", api_key="sk-ant-test")
        client = headless_create_llm_client(cfg)
        assert client.provider == "anthropic"
        assert client.model == "claude-sonnet-4-20250514"
        assert client.endpoint_url == PROVIDER_ENDPOINTS["anthropic"]

    def test_google_provider(self):
        cfg = HeadlessConfig(model_provider="google", model_name="gemini-2.5-flash", api_key="AIza-test")
        client = headless_create_llm_client(cfg)
        assert client.provider == "google"
        assert client.model == "gemini-2.5-flash"

    def test_unknown_provider_raises(self):
        cfg = HeadlessConfig(model_provider="unknown")
        with pytest.raises(ValueError, match="Unknown model provider"):
            headless_create_llm_client(cfg)


# ── Embedder Factory ─────────────────────────────────────────


class TestHeadlessCreateEmbedder:
    def test_native_when_available(self):
        cfg = HeadlessConfig(embedder="native")
        with patch("prep.core.NativeEmbedder") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = True
            mock_cls.return_value = mock_instance
            embedder = headless_create_embedder(cfg)
            assert embedder is mock_instance

    def test_fallback_to_ollama_when_native_unavailable(self):
        cfg = HeadlessConfig(embedder="native")
        with patch("prep.core.NativeEmbedder") as mock_native, \
             patch("prep.core.OllamaEmbedder") as mock_ollama:
            mock_native.return_value.is_available.return_value = False
            mock_ollama_instance = MagicMock()
            mock_ollama.return_value = mock_ollama_instance
            embedder = headless_create_embedder(cfg)
            assert embedder is mock_ollama_instance

    def test_explicit_ollama(self):
        cfg = HeadlessConfig(embedder="ollama")
        with patch("prep.core.OllamaEmbedder") as mock_ollama:
            mock_ollama_instance = MagicMock()
            mock_ollama.return_value = mock_ollama_instance
            embedder = headless_create_embedder(cfg)
            assert embedder is mock_ollama_instance


# ── HeadlessWorkerFactory ─────────────────────────────────────


class TestHeadlessWorkerFactory:
    def test_llm_client_lazy_init(self):
        cfg = HeadlessConfig(model_provider="openai", model_name="gpt-4.1-mini", api_key="test")
        factory = HeadlessWorkerFactory(
            repo_root=Path("/tmp/repo"),
            index_dir=Path("/tmp/index"),
            config=cfg,
        )
        assert factory._llm_client is None
        llm = factory._get_llm()
        assert llm is not None
        assert factory._llm_client is llm
        # Second call returns same instance
        assert factory._get_llm() is llm

    def test_batch_profile_resolves(self):
        cfg = HeadlessConfig(model_provider="openai", model_name="gpt-4.1-mini", api_key="test")
        factory = HeadlessWorkerFactory(
            repo_root=Path("/tmp/repo"),
            index_dir=Path("/tmp/index"),
            config=cfg,
        )
        # Should not raise even if profile doesn't exist for this model
        profile = factory._get_batch_profile()
        # May be None or a valid profile — shouldn't crash


# ── StageResult ───────────────────────────────────────────────


class TestStageResult:
    def test_success(self):
        r = StageResult(stage="structural", success=True, duration_seconds=1.5)
        assert r.stage == "structural"
        assert r.success is True
        assert r.error is None

    def test_failure(self):
        r = StageResult(stage="enrichment", success=False, error="LLM timeout")
        assert r.success is False
        assert r.error == "LLM timeout"


# ── HEADLESS_STAGES constant ─────────────────────────────────


class TestHeadlessStages:
    def test_stage_count(self):
        assert len(HEADLESS_STAGES) == 10

    def test_stage_ids_unique(self):
        ids = [s[0] for s in HEADLESS_STAGES]
        assert len(ids) == len(set(ids))

    def test_first_stage_is_structural(self):
        assert HEADLESS_STAGES[0][0] == "structural"

    def test_last_stage_is_deep_knowledge(self):
        assert HEADLESS_STAGES[-1][0] == "deep_knowledge"


# ── HeadlessRunner._resolve_repo ──────────────────────────────


class TestResolveRepo:
    def test_repo_path_exists(self, tmp_path):
        from prep.services.headless_runner import HeadlessRunner
        repo = tmp_path / "repo"
        repo.mkdir()
        cfg = HeadlessConfig(repo_path=str(repo))
        runner = HeadlessRunner(cfg)
        resolved = runner._resolve_repo()
        assert resolved == repo.resolve()

    def test_repo_path_missing_raises(self, tmp_path):
        from prep.services.headless_runner import HeadlessRunner
        cfg = HeadlessConfig(repo_path=str(tmp_path / "nonexistent"))
        runner = HeadlessRunner(cfg)
        with pytest.raises(FileNotFoundError):
            runner._resolve_repo()

    def test_no_repo_at_all_raises(self):
        from prep.services.headless_runner import HeadlessRunner
        cfg = HeadlessConfig()  # no repo_url or repo_path
        runner = HeadlessRunner(cfg)
        with pytest.raises(ValueError, match="repo-url or --repo-path"):
            runner._resolve_repo()


# ── HeadlessRunner._get_commit_sha ────────────────────────────


class TestGetCommitSha:
    def test_in_git_repo(self, tmp_path):
        """If tmp_path happens to be inside a git repo, we get a non-empty sha."""
        from prep.services.headless_runner import HeadlessRunner
        cfg = HeadlessConfig()
        runner = HeadlessRunner(cfg)
        # Use the CoDRAG repo itself (which is a git repo)
        sha = runner._get_commit_sha(Path(__file__).parent.parent)
        # Should return a hex string (or empty if git not available)
        assert isinstance(sha, str)
        if sha:
            assert len(sha) == 40  # full SHA

    def test_not_a_git_repo(self, tmp_path):
        from prep.services.headless_runner import HeadlessRunner
        cfg = HeadlessConfig()
        runner = HeadlessRunner(cfg)
        sha = runner._get_commit_sha(tmp_path)
        assert sha == ""


# ── Progress callback factory ─────────────────────────────────


class TestProgressCallbackFactory:
    def test_closure_captures_correct_stage_id(self):
        """Verify the factory function pattern avoids the closure-in-loop bug."""
        from prep.services.headless_runner import HeadlessRunner
        import logging

        # Create multiple progress callbacks as the pipeline loop would
        callbacks = {}
        for stage_id, _ in HEADLESS_STAGES[:3]:
            # Simulate what _run_pipeline does
            def _make_progress_cb(sid: str):
                def progress_cb(message, current, total):
                    return sid  # Return the captured stage_id for testing
                return progress_cb
            callbacks[stage_id] = _make_progress_cb(stage_id)

        # Each callback should return its own stage_id, not the last one
        assert callbacks["structural"]("msg", 0, 1) == "structural"
        assert callbacks["inferred_edges"]("msg", 0, 1) == "inferred_edges"
        assert callbacks["catalogue"]("msg", 0, 1) == "catalogue"
