"""Tests for Phase 44: Unified Task-Based LLM Resolver.

Verifies that ``_get_llm_client_for_task()`` correctly routes in both
structured and mapped assignment modes, including fallbacks and edge cases.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ui_config(
    *,
    mode: str = "structured",
    small_enabled: bool = False,
    large_enabled: bool = False,
    code_enabled: bool = False,
    blocks: list | None = None,
) -> dict:
    """Build a minimal ui_config dict for testing."""
    return {
        "llm_config": {
            "assignment_mode": mode,
            "saved_endpoints": [
                {"id": "ep-ollama", "name": "Ollama", "provider": "ollama", "url": "http://localhost:11434"},
                {"id": "ep-cloud", "name": "Cloud", "provider": "openai", "url": "https://api.openai.com"},
            ],
            "small_model": {
                "enabled": small_enabled,
                "endpoint_id": "ep-ollama",
                "model": "qwen3:4b",
            },
            "large_model": {
                "enabled": large_enabled,
                "endpoint_id": "ep-ollama",
                "model": "qwen3:32b",
            },
            "code_model": {
                "enabled": code_enabled,
                "endpoint_id": "ep-ollama",
                "model": "deepseek-coder:6.7b",
            },
            "assignment_blocks": blocks or [],
        }
    }


def _patch_load(config: dict):
    """Return a patch context for ``_load_ui_config`` returning *config*."""
    return patch("codrag.server._load_ui_config", return_value=config)


# ---------------------------------------------------------------------------
# Structured Mode Tests
# ---------------------------------------------------------------------------

class TestStructuredMode:
    """_get_llm_client_for_task in structured mode."""

    def test_catalogue_uses_small(self):
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(small_enabled=True)
        with _patch_load(cfg):
            client = _get_llm_client_for_task("catalogue")
        assert client is not None
        assert client.model == "qwen3:4b"

    def test_enrichment_uses_large(self):
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(large_enabled=True)
        with _patch_load(cfg):
            client = _get_llm_client_for_task("enrichment")
        assert client is not None
        assert client.model == "qwen3:32b"

    def test_inferred_edges_uses_code(self):
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(code_enabled=True)
        with _patch_load(cfg):
            client = _get_llm_client_for_task("inferred_edges")
        assert client is not None
        assert client.model == "deepseek-coder:6.7b"

    def test_inferred_edges_falls_back_to_small(self):
        """Code slot disabled → falls back to small."""
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(code_enabled=False, small_enabled=True)
        with _patch_load(cfg):
            client = _get_llm_client_for_task("inferred_edges")
        assert client is not None
        assert client.model == "qwen3:4b"

    def test_enrichment_falls_back_to_small(self):
        """Large slot disabled → falls back to small."""
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(large_enabled=False, small_enabled=True)
        with _patch_load(cfg):
            client = _get_llm_client_for_task("enrichment")
        assert client is not None
        assert client.model == "qwen3:4b"

    def test_returns_none_when_nothing_configured(self):
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config()
        with _patch_load(cfg):
            client = _get_llm_client_for_task("catalogue")
        assert client is None

    def test_search_intent_uses_small(self):
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(small_enabled=True)
        with _patch_load(cfg):
            client = _get_llm_client_for_task("search_intent")
        assert client is not None
        assert client.model == "qwen3:4b"

    def test_audit_uses_large(self):
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(large_enabled=True)
        with _patch_load(cfg):
            client = _get_llm_client_for_task("audit")
        assert client is not None
        assert client.model == "qwen3:32b"

    def test_default_mode_is_structured(self):
        """Missing assignment_mode defaults to structured."""
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(small_enabled=True)
        del cfg["llm_config"]["assignment_mode"]
        with _patch_load(cfg):
            client = _get_llm_client_for_task("catalogue")
        assert client is not None
        assert client.model == "qwen3:4b"


# ---------------------------------------------------------------------------
# Mapped Mode Tests
# ---------------------------------------------------------------------------

class TestMappedMode:
    """_get_llm_client_for_task in mapped mode."""

    def test_basic_mapped_resolution(self):
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-ollama", "model": "qwen3:4b", "tasks": ["catalogue", "augmentation"]},
        ])
        with _patch_load(cfg):
            client = _get_llm_client_for_task("catalogue")
        assert client is not None
        assert client.model == "qwen3:4b"

    def test_mapped_different_models(self):
        """Different tasks → different models."""
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-ollama", "model": "qwen3:4b", "tasks": ["catalogue"]},
            {"id": "b2", "endpoint_id": "ep-cloud", "model": "gpt-4.1-mini", "tasks": ["enrichment"]},
        ])
        with _patch_load(cfg):
            cat = _get_llm_client_for_task("catalogue")
            enr = _get_llm_client_for_task("enrichment")
        assert cat.model == "qwen3:4b"
        assert enr.model == "gpt-4.1-mini"

    def test_mapped_unassigned_returns_none(self):
        """Task not in any block → None."""
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-ollama", "model": "qwen3:4b", "tasks": ["catalogue"]},
        ])
        with _patch_load(cfg):
            client = _get_llm_client_for_task("enrichment")
        assert client is None

    def test_mapped_missing_endpoint_returns_none(self):
        """Block references non-existent endpoint → None."""
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-nonexistent", "model": "qwen3:4b", "tasks": ["catalogue"]},
        ])
        with _patch_load(cfg):
            client = _get_llm_client_for_task("catalogue")
        assert client is None

    def test_mapped_empty_model_returns_none(self):
        """Block with empty model string → None."""
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-ollama", "model": "", "tasks": ["catalogue"]},
        ])
        with _patch_load(cfg):
            client = _get_llm_client_for_task("catalogue")
        assert client is None

    def test_mapped_cloud_provider(self):
        """Cloud endpoint resolves correctly."""
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-cloud", "model": "gpt-4.1-mini", "tasks": ["enrichment", "clustering", "atlas"]},
        ])
        with _patch_load(cfg):
            client = _get_llm_client_for_task("atlas")
        assert client is not None
        assert client.model == "gpt-4.1-mini"
        assert client.provider == "openai"

    def test_mapped_timeout_for_heavy_tasks(self):
        """Heavy tasks (enrichment, atlas, etc.) get 600s timeout."""
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-ollama", "model": "qwen3:32b", "tasks": ["enrichment", "catalogue"]},
        ])
        with _patch_load(cfg):
            heavy = _get_llm_client_for_task("enrichment")
            light = _get_llm_client_for_task("catalogue")
        assert heavy.timeout == 600.0
        assert light.timeout == 120.0


# ---------------------------------------------------------------------------
# Model Identity Tests (VRAM lifecycle)
# ---------------------------------------------------------------------------

class TestModelIdentity:
    """_get_model_identity_for_task for VRAM lifecycle tracking."""

    def test_structured_identity(self):
        from codrag.server import _get_model_identity_for_task
        cfg = _make_ui_config(small_enabled=True)
        with _patch_load(cfg):
            identity = _get_model_identity_for_task("catalogue")
        assert identity == ("ep-ollama", "qwen3:4b")

    def test_mapped_identity(self):
        from codrag.server import _get_model_identity_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-cloud", "model": "gpt-4.1-mini", "tasks": ["enrichment"]},
        ])
        with _patch_load(cfg):
            identity = _get_model_identity_for_task("enrichment")
        assert identity == ("ep-cloud", "gpt-4.1-mini")

    def test_same_model_same_identity(self):
        """Two tasks on the same block should have the same identity."""
        from codrag.server import _get_model_identity_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-ollama", "model": "qwen3:32b", "tasks": ["enrichment", "clustering"]},
        ])
        with _patch_load(cfg):
            id1 = _get_model_identity_for_task("enrichment")
            id2 = _get_model_identity_for_task("clustering")
        assert id1 == id2

    def test_different_blocks_different_identity(self):
        from codrag.server import _get_model_identity_for_task
        cfg = _make_ui_config(mode="mapped", blocks=[
            {"id": "b1", "endpoint_id": "ep-ollama", "model": "qwen3:4b", "tasks": ["catalogue"]},
            {"id": "b2", "endpoint_id": "ep-ollama", "model": "qwen3:32b", "tasks": ["enrichment"]},
        ])
        with _patch_load(cfg):
            id1 = _get_model_identity_for_task("catalogue")
            id2 = _get_model_identity_for_task("enrichment")
        assert id1 != id2

    def test_unconfigured_returns_none(self):
        from codrag.server import _get_model_identity_for_task
        cfg = _make_ui_config()
        with _patch_load(cfg):
            identity = _get_model_identity_for_task("catalogue")
        assert identity is None

    def test_structured_fallback_identity(self):
        """Large disabled, small enabled → enrichment falls back to small identity."""
        from codrag.server import _get_model_identity_for_task
        cfg = _make_ui_config(large_enabled=False, small_enabled=True)
        with _patch_load(cfg):
            identity = _get_model_identity_for_task("enrichment")
        assert identity == ("ep-ollama", "qwen3:4b")


# ---------------------------------------------------------------------------
# TASK_TO_SLOT + STAGE_TASK_ID Consistency
# ---------------------------------------------------------------------------

class TestMappingConsistency:
    """Ensure the various mapping dicts are internally consistent."""

    def test_all_task_ids_in_task_to_slot(self):
        from codrag.server import TASK_TO_SLOT
        expected = {
            "catalogue", "inferred_edges", "enrichment", "group_reasoning", "clustering",
            "atlas", "deepening", "search_intent", "audit", "augmentation",
        }
        assert set(TASK_TO_SLOT.keys()) == expected

    def test_stage_task_id_covers_all_stages(self):
        from codrag.services.pipeline_orchestrator import STAGE_TASK_ID, StageId
        assert set(STAGE_TASK_ID.keys()) == set(StageId)

    def test_stage_task_id_values_are_valid(self):
        """All non-None values in STAGE_TASK_ID should be valid CodragTaskIds."""
        from codrag.services.pipeline_orchestrator import STAGE_TASK_ID
        from codrag.server import TASK_TO_SLOT
        valid_tasks = set(TASK_TO_SLOT.keys())
        for stage, task_id in STAGE_TASK_ID.items():
            if task_id is not None:
                assert task_id in valid_tasks, f"STAGE_TASK_ID[{stage}] = {task_id!r} not in TASK_TO_SLOT"


# ---------------------------------------------------------------------------
# Backward Compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    """Ensure existing configs without new fields still work."""

    def test_missing_assignment_mode_defaults_structured(self):
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(small_enabled=True)
        del cfg["llm_config"]["assignment_mode"]
        with _patch_load(cfg):
            client = _get_llm_client_for_task("catalogue")
        assert client is not None

    def test_missing_assignment_blocks_defaults_empty(self):
        from codrag.server import _get_llm_client_for_task
        cfg = _make_ui_config(mode="mapped")
        del cfg["llm_config"]["assignment_blocks"]
        with _patch_load(cfg):
            client = _get_llm_client_for_task("catalogue")
        assert client is None

    def test_missing_llm_config_entirely(self):
        from codrag.server import _get_llm_client_for_task
        with _patch_load({}):
            client = _get_llm_client_for_task("catalogue")
        assert client is None

    def test_slot_resolver_still_works(self):
        """_get_llm_client_for_slot is still available for legacy callers."""
        from codrag.server import _get_llm_client_for_slot
        cfg = _make_ui_config(small_enabled=True)
        with _patch_load(cfg):
            client = _get_llm_client_for_slot("small")
        assert client is not None
        assert client.model == "qwen3:4b"


# ---------------------------------------------------------------------------
# Phase 112: Coordinator Slot Resolution
# ---------------------------------------------------------------------------

class TestCoordinatorSlot:
    """Phase 112: _get_llm_client_for_slot("coordinator") resolution."""

    def test_coordinator_inherits_from_large_when_inherit_flag_true(self):
        """Default behavior: coordinator inherits the large-slot client."""
        fake_ui_cfg = {
            "llm_config": {
                "saved_endpoints": [
                    {"id": "ep1", "url": "http://localhost:11434", "provider": "ollama"},
                ],
                "large_model": {"enabled": True, "endpoint_id": "ep1", "model": "kimi-k2.5:cloud"},
                "coordinator_model": {"enabled": False, "inherit_from_large": True},
            }
        }
        with patch("codrag.server._load_ui_config", return_value=fake_ui_cfg):
            from codrag.server import _get_llm_client_for_slot
            client = _get_llm_client_for_slot("coordinator")
        assert client is not None
        assert client.model == "kimi-k2.5:cloud"

    def test_coordinator_uses_own_model_when_inherit_flag_false(self):
        """When inherit_from_large is False and coordinator is configured, use it."""
        fake_ui_cfg = {
            "llm_config": {
                "saved_endpoints": [
                    {"id": "ep1", "url": "http://localhost:11434", "provider": "ollama"},
                ],
                "large_model": {"enabled": True, "endpoint_id": "ep1", "model": "kimi-k2.5:cloud"},
                "coordinator_model": {
                    "enabled": True,
                    "inherit_from_large": False,
                    "endpoint_id": "ep1",
                    "model": "gemini-3-flash-preview:cloud",
                },
            }
        }
        with patch("codrag.server._load_ui_config", return_value=fake_ui_cfg):
            from codrag.server import _get_llm_client_for_slot
            client = _get_llm_client_for_slot("coordinator")
        assert client is not None
        assert client.model == "gemini-3-flash-preview:cloud"

    def test_coordinator_falls_back_to_large_when_unconfigured(self):
        """No coordinator_model block at all → fall back to large."""
        fake_ui_cfg = {
            "llm_config": {
                "saved_endpoints": [
                    {"id": "ep1", "url": "http://localhost:11434", "provider": "ollama"},
                ],
                "large_model": {"enabled": True, "endpoint_id": "ep1", "model": "kimi-k2.5:cloud"},
            }
        }
        with patch("codrag.server._load_ui_config", return_value=fake_ui_cfg):
            from codrag.server import _get_llm_client_for_slot
            client = _get_llm_client_for_slot("coordinator")
        assert client is not None
        assert client.model == "kimi-k2.5:cloud"

    def test_coordinator_returns_none_when_neither_configured(self):
        """No coordinator, no large → None."""
        fake_ui_cfg = {"llm_config": {"saved_endpoints": []}}
        with patch("codrag.server._load_ui_config", return_value=fake_ui_cfg):
            from codrag.server import _get_llm_client_for_slot
            client = _get_llm_client_for_slot("coordinator")
        assert client is None

    def test_coordinator_timeout_matches_large(self):
        """Coordinator slot uses 600s timeout (same as large — handles big synthesis payloads)."""
        fake_ui_cfg = {
            "llm_config": {
                "saved_endpoints": [
                    {"id": "ep1", "url": "http://localhost:11434", "provider": "ollama"},
                ],
                "coordinator_model": {
                    "enabled": True,
                    "inherit_from_large": False,
                    "endpoint_id": "ep1",
                    "model": "gemini-3-flash-preview:cloud",
                },
            }
        }
        with patch("codrag.server._load_ui_config", return_value=fake_ui_cfg):
            from codrag.server import _get_llm_client_for_slot
            client = _get_llm_client_for_slot("coordinator")
        assert client is not None
        assert client.timeout == 600.0

    def test_get_coordinator_llm_client_helper_delegates(self):
        """WorkerFactory._get_coordinator_llm_client() delegates to _get_llm_client_for_slot."""
        fake_ui_cfg = {
            "llm_config": {
                "saved_endpoints": [
                    {"id": "ep1", "url": "http://localhost:11434", "provider": "ollama"},
                ],
                "large_model": {"enabled": True, "endpoint_id": "ep1", "model": "kimi-k2.5:cloud"},
                "coordinator_model": {"enabled": False, "inherit_from_large": True},
            }
        }
        with patch("codrag.server._load_ui_config", return_value=fake_ui_cfg):
            from codrag.services.pipeline.workers import WorkerFactory
            client = WorkerFactory._get_coordinator_llm_client()
        assert client is not None
        assert client.model == "kimi-k2.5:cloud"
