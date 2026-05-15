"""
Phase 139 — embedder memory hardening tests
==========================================

Covers:
- Process-wide singleton in embedder_factory (T1.1)
- Direct-construction warning on NativeEmbedder (Q11)
- Conservative batch and max_length defaults (T1.3)
- Env-var overrides: PREP_EMBED_MAX_BATCH, PREP_EMBED_MAX_LEN,
  PREP_EMBED_LEGACY, PREP_DAEMON_MAX_RSS_GB, PREP_COREML_USE_ANE
- RSS watchdog formula and behavior (T1.4)
- Bucket helpers (_seq_buckets, _pick_bucket, _pad_2d) (T1.2)
- close_shared_embedders() clears the cache
"""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

import numpy as np
import pytest

from prep.core import embedder as emod
from prep.core import memory_guard
from prep.services import embedder_factory as factory


# Default server config for the factory's step 3 fallback.
_DEFAULT_CONFIG = {
    "ollama_url": "http://localhost:11434",
    "model": "nomic-embed-text",
    "embedding_source": "native",
}


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Reset all process-wide state between tests."""
    factory.close_shared_embedders()
    memory_guard.reset_for_tests()
    # Remove Phase-139 env vars unless a test sets them.
    for key in (
        "PREP_EMBED_LEGACY", "PREP_EMBED_MAX_BATCH", "PREP_EMBED_MAX_LEN",
        "PREP_DAEMON_MAX_RSS_GB", "PREP_COREML_USE_ANE",
        "PREP_RSS_TELEMETRY", "PREP_RSS_TELEMETRY_LOG",
    ):
        monkeypatch.delenv(key, raising=False)

    # Stub prep.server config so factory's resolution doesn't crash.
    import prep.server
    monkeypatch.setattr(prep.server, "_config", dict(_DEFAULT_CONFIG), raising=False)
    monkeypatch.setattr(prep.server, "_load_ui_config", lambda: {}, raising=False)

    yield

    factory.close_shared_embedders()
    memory_guard.reset_for_tests()


# ── T1.1 singleton ────────────────────────────────────────────────

class TestSingleton:
    def test_repeat_create_native_returns_same_instance(self):
        """create_embedder('native') twice returns the same cached object."""
        a = factory.create_embedder("native")
        b = factory.create_embedder("native")
        assert a is b

    def test_repeat_create_ollama_returns_same_instance(self):
        a = factory.create_embedder("ollama")
        b = factory.create_embedder("ollama")
        assert a is b

    def test_native_and_ollama_are_separate(self):
        a = factory.create_embedder("native")
        b = factory.create_embedder("ollama")
        assert a is not b

    def test_close_shared_embedders_clears_cache(self):
        a = factory.create_embedder("native")
        n = factory.close_shared_embedders()
        assert n >= 1
        b = factory.create_embedder("native")
        assert a is not b  # new instance after close

    def test_native_close_drops_session_ref(self):
        emb = emod.NativeEmbedder(_from_factory=True)
        emb._session = object()
        emb._tokenizer = object()
        emb.close()
        assert emb._session is None
        assert emb._tokenizer is None


# ── Q11 direct-construction warning ──────────────────────────────

class TestDirectConstructionWarning:
    def test_direct_init_warns(self, caplog):
        with caplog.at_level(logging.WARNING):
            emod.NativeEmbedder()
        assert any(
            "NativeEmbedder() constructed directly" in rec.message
            for rec in caplog.records
        ), "expected direct-construction warning"

    def test_factory_init_does_not_warn(self, caplog):
        with caplog.at_level(logging.WARNING):
            emod.NativeEmbedder(_from_factory=True)
        # No "constructed directly" line allowed.
        assert not any(
            "constructed directly" in rec.message
            for rec in caplog.records
        )


# ── T1.3 conservative defaults ────────────────────────────────────

class TestDefaults:
    def test_max_length_default_is_1024(self):
        emb = emod.NativeEmbedder(_from_factory=True)
        assert emb.max_length == 1024

    def test_max_length_legacy_mode_restores_8192(self, monkeypatch):
        monkeypatch.setenv("PREP_EMBED_LEGACY", "1")
        emb = emod.NativeEmbedder(_from_factory=True)
        assert emb.max_length == 8192

    def test_max_length_env_override(self, monkeypatch):
        monkeypatch.setenv("PREP_EMBED_MAX_LEN", "512")
        emb = emod.NativeEmbedder(_from_factory=True)
        assert emb.max_length == 512

    def test_max_length_explicit_arg_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("PREP_EMBED_MAX_LEN", "512")
        emb = emod.NativeEmbedder(max_length=300, _from_factory=True)
        assert emb.max_length == 300

    def test_default_batch_size_coreml_is_16(self):
        assert emod._default_batch_size("CoreMLExecutionProvider") == 16

    def test_default_batch_size_cpu_is_8(self):
        assert emod._default_batch_size("CPUExecutionProvider") == 8

    def test_default_batch_size_cuda_is_16(self):
        assert emod._default_batch_size("CUDAExecutionProvider") == 16

    def test_default_batch_size_directml_is_16(self):
        assert emod._default_batch_size("DmlExecutionProvider") == 16

    def test_env_batch_override_applies_to_all_providers(self, monkeypatch):
        monkeypatch.setenv("PREP_EMBED_MAX_BATCH", "4")
        assert emod._default_batch_size("CoreMLExecutionProvider") == 4
        assert emod._default_batch_size("CPUExecutionProvider") == 4
        assert emod._default_batch_size("CUDAExecutionProvider") == 4

    def test_env_batch_override_minimum_is_1(self, monkeypatch):
        monkeypatch.setenv("PREP_EMBED_MAX_BATCH", "0")
        # 0 is below minimum so falls back to provider default
        assert emod._default_batch_size("CoreMLExecutionProvider") == 16

    def test_legacy_mode_restores_old_batch_table(self, monkeypatch):
        monkeypatch.setenv("PREP_EMBED_LEGACY", "1")
        # Pre-Phase-139 GPU default was 128 (possibly scaled by RAM).
        # On most CI/dev machines (any RAM) it's at least 64.
        legacy = emod._default_batch_size("CoreMLExecutionProvider")
        assert legacy >= 64, f"legacy batch should be ≥64, got {legacy}"


# ── T1.2 bucket helpers ───────────────────────────────────────────

class TestBuckets:
    def test_seq_buckets_default(self):
        assert emod._seq_buckets(1024) == (128, 256, 512, 1024)

    def test_seq_buckets_filtered_by_max_length(self):
        assert emod._seq_buckets(512) == (128, 256, 512)
        assert emod._seq_buckets(256) == (128, 256)
        assert emod._seq_buckets(128) == (128,)

    def test_seq_buckets_below_smallest(self):
        # max_length smaller than the smallest bucket — degenerate but
        # should still return a single-bucket tuple
        assert emod._seq_buckets(64) == (64,)

    def test_pick_bucket_smallest_match(self):
        buckets = (128, 256, 512, 1024)
        assert emod._pick_bucket([60], buckets, 1024) == 128
        assert emod._pick_bucket([200], buckets, 1024) == 256
        assert emod._pick_bucket([300, 100, 250], buckets, 1024) == 512
        assert emod._pick_bucket([1000], buckets, 1024) == 1024

    def test_pick_bucket_over_all_returns_max_length(self):
        buckets = (128, 256, 512)
        assert emod._pick_bucket([700], buckets, 512) == 512

    def test_pad_2d_correct_shape_and_padding(self):
        rows = [[1, 2, 3], [4, 5], [6]]
        out = emod._pad_2d(rows, target_len=5, pad_value=0)
        assert out.shape == (3, 5)
        assert out.dtype == np.int64
        assert out[0].tolist() == [1, 2, 3, 0, 0]
        assert out[1].tolist() == [4, 5, 0, 0, 0]
        assert out[2].tolist() == [6, 0, 0, 0, 0]

    def test_pad_2d_truncates_long_rows(self):
        rows = [[1, 2, 3, 4, 5, 6], [7, 8]]
        out = emod._pad_2d(rows, target_len=3)
        assert out.shape == (2, 3)
        assert out[0].tolist() == [1, 2, 3]
        assert out[1].tolist() == [7, 8, 0]


# ── T1.4 memory guard ─────────────────────────────────────────────

class TestMemoryGuard:
    def test_ceiling_formula_below_floor_returns_floor(self):
        """Mock total RAM at 8 GB → 25% = 2 GB → floor (4 GB) wins."""
        with patch.object(memory_guard, "_detect_total_ram_bytes", return_value=8 * 1024**3):
            memory_guard.reset_for_tests()
            assert memory_guard.compute_ceiling_bytes() == 4 * 1024**3

    def test_ceiling_formula_in_range(self):
        """Mock 64 GB total → 25% = 16 GB → use fraction directly."""
        with patch.object(memory_guard, "_detect_total_ram_bytes", return_value=64 * 1024**3):
            memory_guard.reset_for_tests()
            assert memory_guard.compute_ceiling_bytes() == 16 * 1024**3

    def test_ceiling_formula_above_cap_returns_cap(self):
        """Mock 256 GB total → 25% = 64 GB → cap (32 GB) wins."""
        with patch.object(memory_guard, "_detect_total_ram_bytes", return_value=256 * 1024**3):
            memory_guard.reset_for_tests()
            assert memory_guard.compute_ceiling_bytes() == 32 * 1024**3

    def test_env_override_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("PREP_DAEMON_MAX_RSS_GB", "12")
        # Even with a huge mocked machine, env wins
        with patch.object(memory_guard, "_detect_total_ram_bytes", return_value=256 * 1024**3):
            memory_guard.reset_for_tests()
            assert memory_guard.compute_ceiling_bytes() == 12 * 1024**3

    def test_env_override_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("PREP_DAEMON_MAX_RSS_GB", "not-a-number")
        with patch.object(memory_guard, "_detect_total_ram_bytes", return_value=64 * 1024**3):
            memory_guard.reset_for_tests()
            assert memory_guard.compute_ceiling_bytes() == 16 * 1024**3

    def test_env_override_zero_falls_back(self, monkeypatch):
        monkeypatch.setenv("PREP_DAEMON_MAX_RSS_GB", "0")
        with patch.object(memory_guard, "_detect_total_ram_bytes", return_value=64 * 1024**3):
            memory_guard.reset_for_tests()
            assert memory_guard.compute_ceiling_bytes() == 16 * 1024**3

    def test_ram_detection_fails_returns_floor(self):
        with patch.object(memory_guard, "_detect_total_ram_bytes", return_value=0):
            memory_guard.reset_for_tests()
            assert memory_guard.compute_ceiling_bytes() == 4 * 1024**3

    def test_sample_returns_real_rss(self):
        snap = memory_guard.sample()
        assert snap.rss_bytes > 0  # this test process has nonzero RSS
        assert snap.ceiling_bytes > 0
        assert snap.over_ceiling == (snap.rss_bytes > snap.ceiling_bytes)

    def test_check_raises_when_over_and_cannot_shrink(self):
        """When the ceiling is tiny enough that we exceed it AND can_shrink=False,
        ``check`` raises ``MemoryCeilingExceeded``."""
        # Force a ceiling below the test process's own RSS.
        with patch.object(memory_guard, "compute_ceiling_bytes", return_value=1024):
            with pytest.raises(memory_guard.MemoryCeilingExceeded):
                memory_guard.check(can_shrink=False)

    def test_check_does_not_raise_when_can_shrink(self):
        with patch.object(memory_guard, "compute_ceiling_bytes", return_value=1024):
            snap = memory_guard.check(can_shrink=True)
            assert snap.over_ceiling


# ── Provider opts (T1.2) — exercised on non-mac, validated locally ─

class TestProviderOpts:
    def test_apply_phase139_provider_opts_noop_on_non_mac(self):
        """On Linux/Windows the provider list is unchanged."""
        import platform
        if platform.system() == "Darwin":
            pytest.skip("non-mac branch")
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        out = emod._apply_phase139_provider_opts(providers, "/tmp/fake.onnx")
        assert out == providers

    def test_apply_phase139_provider_opts_macos_injects_coreml_opts(self):
        """On macOS the CoreML entry becomes a (name, opts) tuple."""
        import platform
        if platform.system() != "Darwin":
            pytest.skip("mac-only branch")
        providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        out = emod._apply_phase139_provider_opts(providers, "/tmp/fake.onnx")
        # CoreML entry is now a tuple
        assert isinstance(out[0], tuple) and out[0][0] == "CoreMLExecutionProvider"
        opts = out[0][1]
        assert opts["MLComputeUnits"] == "CPUAndGPU"  # ANE off by default
        assert opts["RequireStaticInputShapes"] == "1"
        assert opts["ModelFormat"] == "MLProgram"
        assert "ModelCacheDirectory" in opts

    def test_apply_phase139_provider_opts_macos_ane_opt_in(self, monkeypatch):
        """PREP_COREML_USE_ANE=1 routes back to CPUAndNeuralEngine."""
        import platform
        if platform.system() != "Darwin":
            pytest.skip("mac-only branch")
        monkeypatch.setenv("PREP_COREML_USE_ANE", "1")
        providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        out = emod._apply_phase139_provider_opts(providers, "/tmp/fake.onnx")
        opts = out[0][1]
        assert opts["MLComputeUnits"] == "CPUAndNeuralEngine"


# ── Env helpers ────────────────────────────────────────────────────

class TestEnvHelpers:
    def test_env_int_default_on_missing(self, monkeypatch):
        monkeypatch.delenv("FOO_BAR", raising=False)
        assert emod._env_int("FOO_BAR", 42) == 42

    def test_env_int_default_on_invalid(self, monkeypatch):
        monkeypatch.setenv("FOO_BAR", "not-a-number")
        assert emod._env_int("FOO_BAR", 42) == 42

    def test_env_int_default_on_below_min(self, monkeypatch):
        monkeypatch.setenv("FOO_BAR", "0")
        assert emod._env_int("FOO_BAR", 42, minimum=1) == 42

    def test_env_int_reads_value(self, monkeypatch):
        monkeypatch.setenv("FOO_BAR", "99")
        assert emod._env_int("FOO_BAR", 42) == 99

    def test_env_flag_truthy(self, monkeypatch):
        for truthy in ("1", "true", "TRUE", "yes", "on"):
            monkeypatch.setenv("FOO_FLAG", truthy)
            assert emod._env_flag("FOO_FLAG") is True

    def test_env_flag_falsy(self, monkeypatch):
        for falsy in ("0", "false", "no", "off", ""):
            monkeypatch.setenv("FOO_FLAG", falsy)
            assert emod._env_flag("FOO_FLAG") is False

    def test_legacy_mode_off_by_default(self, monkeypatch):
        monkeypatch.delenv("PREP_EMBED_LEGACY", raising=False)
        assert emod._legacy_mode() is False
