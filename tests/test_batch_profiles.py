"""Tests for BYOK batch profiles and strategy."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

# Load batch modules directly from file to avoid codrag.core.__init__'s
# heavy dependency chain (fastapi, etc.)
_CORE = Path(__file__).resolve().parent.parent / "src" / "codrag" / "core"

def _load_module(name: str, filepath: Path):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_bp = _load_module("codrag.core.batch_profiles", _CORE / "batch_profiles.py")
_bs = _load_module("codrag.core.batch_strategy", _CORE / "batch_strategy.py")

BatchProfile = _bp.BatchProfile
BatchProfileName = _bp.BatchProfileName
BatchStage = _bp.BatchStage
PROFILE_LARGE = _bp.PROFILE_LARGE
PROFILE_STANDARD = _bp.PROFILE_STANDARD
PROFILE_COMPACT = _bp.PROFILE_COMPACT
PROFILE_OFF = _bp.PROFILE_OFF
PROFILES = _bp.PROFILES
detect_profile = _bp.detect_profile
resolve_profile = _bp.resolve_profile

BatchStrategy = _bs.BatchStrategy
BatchedResponseParser = _bs.BatchedResponseParser
create_batch_strategy = _bs.create_batch_strategy


# ── Profile detection ─────────────────────────────────────────────

class TestDetectProfile:
    """Test auto-detection of batch profiles from provider + model."""

    def test_ollama_always_off(self):
        assert detect_profile("ollama", "ministral-3:3b") == PROFILE_OFF
        assert detect_profile("ollama", "llama3.1:70b") == PROFILE_OFF
        assert detect_profile("ollama", "qwen2.5-coder:3b") == PROFILE_OFF

    def test_anthropic_claude_4_large(self):
        profile = detect_profile("anthropic", "claude-sonnet-4-5-20250514")
        assert profile.name == BatchProfileName.LARGE

    def test_anthropic_claude_4_opus_large(self):
        profile = detect_profile("anthropic", "claude-opus-4-5-20250514")
        assert profile.name == BatchProfileName.LARGE

    def test_anthropic_claude_3_standard(self):
        profile = detect_profile("anthropic", "claude-3-opus-20240229")
        assert profile.name == BatchProfileName.STANDARD

    def test_anthropic_claude_3_sonnet_standard(self):
        profile = detect_profile("anthropic", "claude-3-5-sonnet-20241022")
        assert profile.name == BatchProfileName.STANDARD

    def test_openai_gpt41_standard(self):
        profile = detect_profile("openai", "gpt-4.1")
        assert profile.name == BatchProfileName.STANDARD

    def test_openai_gpt41_mini_standard(self):
        profile = detect_profile("openai", "gpt-4.1-mini")
        assert profile.name == BatchProfileName.STANDARD

    def test_openai_gpt4o_compact(self):
        profile = detect_profile("openai", "gpt-4o")
        assert profile.name == BatchProfileName.COMPACT

    def test_openai_gpt4o_mini_compact(self):
        profile = detect_profile("openai", "gpt-4o-mini")
        assert profile.name == BatchProfileName.COMPACT

    def test_compatible_gemini_25_pro_large(self):
        profile = detect_profile("openai-compatible", "gemini-2.5-pro")
        assert profile.name == BatchProfileName.LARGE

    def test_compatible_gemini_25_flash_compact(self):
        profile = detect_profile("openai-compatible", "gemini-2.5-flash")
        assert profile.name == BatchProfileName.COMPACT

    def test_compatible_deepseek_compact(self):
        profile = detect_profile("openai-compatible", "deepseek-chat")
        assert profile.name == BatchProfileName.COMPACT

    def test_compatible_claude_via_openrouter(self):
        profile = detect_profile("openai-compatible", "anthropic/claude-4-sonnet")
        assert profile.name == BatchProfileName.LARGE

    def test_compatible_unknown_model_compact(self):
        profile = detect_profile("openai-compatible", "some-unknown-model")
        assert profile.name == BatchProfileName.COMPACT

    def test_unknown_provider_off(self):
        profile = detect_profile("unknown-provider", "some-model")
        assert profile == PROFILE_OFF

    def test_case_insensitive(self):
        profile = detect_profile("OPENAI", "GPT-4.1-MINI")
        assert profile.name == BatchProfileName.STANDARD


# ── Profile resolution with overrides ─────────────────────────────

class TestResolveProfile:
    def test_auto_delegates_to_detect(self):
        profile = resolve_profile("openai", "gpt-4.1", override="auto")
        assert profile.name == BatchProfileName.STANDARD

    def test_none_override_auto(self):
        profile = resolve_profile("openai", "gpt-4.1", override=None)
        assert profile.name == BatchProfileName.STANDARD

    def test_explicit_large_override(self):
        profile = resolve_profile("ollama", "ministral-3:3b", override="large")
        assert profile.name == BatchProfileName.LARGE

    def test_explicit_off_override(self):
        profile = resolve_profile("anthropic", "claude-sonnet-4-5", override="off")
        assert profile.name == BatchProfileName.OFF

    def test_invalid_override_falls_back(self):
        profile = resolve_profile("openai", "gpt-4.1", override="nonexistent")
        assert profile.name == BatchProfileName.STANDARD  # auto-detected


# ── Batch sizes ───────────────────────────────────────────────────

class TestBatchSizes:
    def test_large_profile_sizes(self):
        assert PROFILE_LARGE.batch_size(BatchStage.CATALOGUE_FILE) == 100
        assert PROFILE_LARGE.batch_size(BatchStage.EPISTEMIC_CODE) == 50
        assert PROFILE_LARGE.batch_size(BatchStage.EPISTEMIC_DOC) == 15

    def test_standard_profile_sizes(self):
        assert PROFILE_STANDARD.batch_size(BatchStage.CATALOGUE_FILE) == 50
        assert PROFILE_STANDARD.batch_size(BatchStage.EPISTEMIC_CODE) == 25

    def test_compact_profile_sizes(self):
        assert PROFILE_COMPACT.batch_size(BatchStage.CATALOGUE_FILE) == 20
        assert PROFILE_COMPACT.batch_size(BatchStage.EPISTEMIC_CODE) == 10

    def test_off_profile_all_ones(self):
        for stage in BatchStage:
            assert PROFILE_OFF.batch_size(stage) == 1

    def test_unknown_stage_returns_1(self):
        # BatchStage enum is exhaustive, but test the dict fallback
        profile = BatchProfile(
            name=BatchProfileName.LARGE,
            output_class="test",
            sizes={},
        )
        assert profile.batch_size(BatchStage.CATALOGUE_FILE) == 1


# ── BatchStrategy ─────────────────────────────────────────────────

class TestBatchStrategy:
    def test_is_batched_large(self):
        strategy = create_batch_strategy("anthropic", "claude-sonnet-4-5", BatchStage.CATALOGUE_FILE)
        assert strategy.is_batched is True
        assert strategy.batch_size == 100

    def test_is_batched_off(self):
        strategy = create_batch_strategy("ollama", "ministral-3:3b", BatchStage.CATALOGUE_FILE)
        assert strategy.is_batched is False
        assert strategy.batch_size == 1

    def test_chunk_items(self):
        strategy = BatchStrategy(profile=PROFILE_STANDARD, stage=BatchStage.CATALOGUE_FILE)
        items = list(range(120))
        batches = strategy.chunk_items(items)
        assert len(batches) == 3  # 50, 50, 20
        assert len(batches[0]) == 50
        assert len(batches[1]) == 50
        assert len(batches[2]) == 20

    def test_chunk_items_single(self):
        strategy = BatchStrategy(profile=PROFILE_OFF, stage=BatchStage.CATALOGUE_FILE)
        items = list(range(5))
        batches = strategy.chunk_items(items)
        assert len(batches) == 5
        assert all(len(b) == 1 for b in batches)

    def test_chunk_items_empty(self):
        strategy = BatchStrategy(profile=PROFILE_STANDARD, stage=BatchStage.CATALOGUE_FILE)
        assert strategy.chunk_items([]) == []

    def test_chunk_items_fewer_than_batch(self):
        strategy = BatchStrategy(profile=PROFILE_STANDARD, stage=BatchStage.CATALOGUE_FILE)
        items = list(range(10))
        batches = strategy.chunk_items(items)
        assert len(batches) == 1
        assert len(batches[0]) == 10


# ── BatchedResponseParser ─────────────────────────────────────────

class TestBatchedResponseParser:
    def test_parse_results_object(self):
        response = json.dumps({
            "results": [
                {"file": "a.py", "summary": "File A"},
                {"file": "b.py", "summary": "File B"},
            ]
        })
        results = BatchedResponseParser.parse(response)
        assert len(results) == 2
        assert results[0]["file"] == "a.py"
        assert results[1]["file"] == "b.py"

    def test_parse_json_array(self):
        response = json.dumps([
            {"file": "a.py", "summary": "File A"},
            {"file": "b.py", "summary": "File B"},
        ])
        results = BatchedResponseParser.parse(response)
        assert len(results) == 2

    def test_parse_jsonl(self):
        response = '{"file": "a.py", "summary": "A"}\n{"file": "b.py", "summary": "B"}\n{"file": "c.py", "summary": "C"}'
        results = BatchedResponseParser.parse(response)
        assert len(results) == 3

    def test_parse_regex_extraction(self):
        response = 'Here are the results:\n### File 1\n{"file": "a.py", "summary": "A"}\n### File 2\n{"file": "b.py", "summary": "B"}'
        results = BatchedResponseParser.parse(response)
        assert len(results) == 2

    def test_parse_empty(self):
        assert BatchedResponseParser.parse("") == []
        assert BatchedResponseParser.parse("   ") == []

    def test_parse_invalid_json(self):
        assert BatchedResponseParser.parse("not json at all") == []

    def test_parse_mixed_valid_invalid_jsonl(self):
        response = '{"file": "a.py"}\nnot json\n{"file": "b.py"}\nalso not json'
        results = BatchedResponseParser.parse(response)
        assert len(results) == 2

    def test_parse_nested_json_objects(self):
        response = json.dumps({
            "results": [
                {"file": "a.py", "nested": {"key": "val"}},
            ]
        })
        results = BatchedResponseParser.parse(response)
        assert len(results) == 1
        assert results[0]["nested"]["key"] == "val"

    def test_parse_filters_non_dict_items(self):
        response = json.dumps(["string_item", {"file": "a.py"}, 42, {"file": "b.py"}])
        results = BatchedResponseParser.parse(response)
        assert len(results) == 2


# ── Plan-tier concurrency ──────────────────────────────────────────


def test_cloud_concurrency_uses_plan_tier_max():
    """F-59 is resolved — cloud models must no longer be hardcapped at 1."""
    from codrag.core.batch_profiles import get_batch_concurrency
    with patch("codrag.core.batch_profiles._get_plan_tier", return_value="max"):
        result = get_batch_concurrency("ollama", model="kimi-k2.5:cloud")
        assert result == 10


def test_cloud_concurrency_uses_plan_tier_pro():
    from codrag.core.batch_profiles import get_batch_concurrency
    with patch("codrag.core.batch_profiles._get_plan_tier", return_value="pro"):
        result = get_batch_concurrency("ollama", model="kimi-k2.5:cloud")
        assert result == 3


def test_cloud_concurrency_defaults_to_free_when_unset():
    from codrag.core.batch_profiles import get_batch_concurrency
    with patch("codrag.core.batch_profiles._get_plan_tier", return_value="free"):
        result = get_batch_concurrency("ollama", model="kimi-k2.5:cloud")
        assert result == 1


def test_local_model_still_returns_one():
    from codrag.core.batch_profiles import get_batch_concurrency
    result = get_batch_concurrency("ollama", model="gemma3:12b")
    assert result == 1


# ── Cloud Token Safety toggle (Phase 112 T16) ─────────────────────


def test_cloud_safety_off_promotes_gemini_to_large(monkeypatch):
    from codrag.core.batch_profiles import resolve_profile, PROFILE_LARGE
    monkeypatch.setattr(
        "codrag.server.get_advanced_llm_settings",
        lambda: {"enforce_cloud_token_safety": False},
    )
    profile = resolve_profile("ollama", "gemini-3-flash-preview:cloud")
    assert profile is PROFILE_LARGE


def test_cloud_safety_off_keeps_kimi_on_cloud_small(monkeypatch):
    """Kimi's thinking preamble eats output budget regardless of the 16K cap."""
    from codrag.core.batch_profiles import resolve_profile, PROFILE_CLOUD_SMALL
    monkeypatch.setattr(
        "codrag.server.get_advanced_llm_settings",
        lambda: {"enforce_cloud_token_safety": False},
    )
    profile = resolve_profile("ollama", "kimi-k2.5:cloud")
    assert profile is PROFILE_CLOUD_SMALL


def test_cloud_safety_on_keeps_default_cloud_small(monkeypatch):
    """Default behavior preserved when safety toggle is ON."""
    from codrag.core.batch_profiles import resolve_profile, PROFILE_CLOUD_SMALL
    monkeypatch.setattr(
        "codrag.server.get_advanced_llm_settings",
        lambda: {"enforce_cloud_token_safety": True},
    )
    profile = resolve_profile("ollama", "gemini-3-flash-preview:cloud")
    assert profile is PROFILE_CLOUD_SMALL
