"""Phase 96F: Tests for concept_seeder swarm path.

These tests cover the routing logic and the swarm fallback behavior.
The actual swarm orchestration (LLM calls, fan-out) is mocked — the
goal here is to verify the routing decisions and the fallback graph.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codrag.core.concept_seeder import (
    MIN_MODULES_FOR_SWARM,
    _build_module_context,
    _build_module_summary,
    _SwarmFallback,
    seed_concepts,
    seed_concepts_swarm,
)


# ── Helpers ──────────────────────────────────────────────────────


def _module(name: str, file_count: int) -> dict:
    return {
        "module_id": name.lower().replace(" ", "_"),
        "name": name,
        "file_count": file_count,
        "member_files": [f"src/{name.lower()}/{i}.py" for i in range(file_count)],
        "summary": f"The {name} subsystem",
        "domain_tags": ["test"],
        "internal_dependencies": [],
        "external_dependencies": ["logging"],
    }


# ── Routing tests ────────────────────────────────────────────────


class TestSeedConceptsRouting:
    """seed_concepts() should prefer swarm by default and fall back."""

    def test_prefer_swarm_false_skips_swarm(self):
        """prefer_swarm=False should call sequential directly without
        attempting swarm at all."""
        with patch(
            "codrag.core.concept_seeder._seed_concepts_sequential",
            return_value={"status": "success", "mode": "sequential"},
        ) as seq_mock, patch(
            "codrag.core.concept_seeder.seed_concepts_swarm",
        ) as swarm_mock:
            result = seed_concepts("proj-1", prefer_swarm=False)

        assert result["mode"] == "sequential"
        seq_mock.assert_called_once_with("proj-1")
        swarm_mock.assert_not_called()

    def test_swarm_fallback_routes_to_sequential(self):
        """When swarm raises _SwarmFallback, sequential should be called."""
        with patch(
            "codrag.core.concept_seeder.seed_concepts_swarm",
            side_effect=_SwarmFallback("test: no model"),
        ), patch(
            "codrag.core.concept_seeder._seed_concepts_sequential",
            return_value={"status": "success", "mode": "sequential"},
        ) as seq_mock:
            result = seed_concepts("proj-1")

        assert result["mode"] == "sequential"
        seq_mock.assert_called_once_with("proj-1")

    def test_swarm_unexpected_exception_falls_back(self):
        """An unexpected exception in swarm should still trigger fallback,
        not propagate to the caller."""
        with patch(
            "codrag.core.concept_seeder.seed_concepts_swarm",
            side_effect=RuntimeError("unexpected"),
        ), patch(
            "codrag.core.concept_seeder._seed_concepts_sequential",
            return_value={"status": "success", "mode": "sequential"},
        ) as seq_mock:
            result = seed_concepts("proj-1")

        assert result["mode"] == "sequential"
        seq_mock.assert_called_once()

    def test_swarm_success_skips_sequential(self):
        """When swarm succeeds, sequential should not be called."""
        with patch(
            "codrag.core.concept_seeder.seed_concepts_swarm",
            return_value={"status": "success", "mode": "swarm", "concepts_created": 12},
        ), patch(
            "codrag.core.concept_seeder._seed_concepts_sequential",
        ) as seq_mock:
            result = seed_concepts("proj-1")

        assert result["mode"] == "swarm"
        assert result["concepts_created"] == 12
        seq_mock.assert_not_called()


# ── Fallback condition tests ─────────────────────────────────────


class TestSeedConceptsSwarmFallback:
    """Verify each fallback condition raises _SwarmFallback with a clear reason."""

    def _setup_swarm_path(self, modules=None, llm_provider="ollama", llm_model="kimi-k2.5:cloud"):
        """Create patches for the swarm path entry points."""
        llm = MagicMock()
        llm.provider = llm_provider
        llm.model = llm_model

        project = MagicMock()
        project.name = "TestProj"
        project.path = "/tmp/testproj"

        return llm, project, modules or []

    def test_no_llm_raises_fallback(self):
        with patch(
            "codrag.services.project_helpers.require_project",
            return_value=MagicMock(name="TestProj", path="/tmp"),
        ), patch(
            "codrag.core.project_registry.project_index_dir",
            return_value=Path("/tmp"),
        ), patch(
            "codrag.core.concept_seeder._get_seeder_llm",
            return_value=None,
        ):
            with pytest.raises(_SwarmFallback, match="no LLM"):
                seed_concepts_swarm("proj-1")

    def test_model_not_swarm_capable_raises_fallback(self):
        llm, project, _ = self._setup_swarm_path()
        with patch(
            "codrag.services.project_helpers.require_project",
            return_value=project,
        ), patch(
            "codrag.core.project_registry.project_index_dir",
            return_value=Path("/tmp"),
        ), patch(
            "codrag.core.concept_seeder._get_seeder_llm",
            return_value=llm,
        ), patch(
            "codrag.services.pipeline.scheduler.is_swarm_active_for_stage",
            return_value=False,
        ):
            with pytest.raises(_SwarmFallback, match="not swarm-capable"):
                seed_concepts_swarm("proj-1")

    def test_scheduler_returns_no_budget_raises_fallback(self):
        llm, project, _ = self._setup_swarm_path()
        with patch(
            "codrag.services.project_helpers.require_project",
            return_value=project,
        ), patch(
            "codrag.core.project_registry.project_index_dir",
            return_value=Path("/tmp"),
        ), patch(
            "codrag.core.concept_seeder._get_seeder_llm",
            return_value=llm,
        ), patch(
            "codrag.services.pipeline.scheduler.is_swarm_active_for_stage",
            return_value=True,
        ), patch(
            "codrag.services.pipeline.scheduler.pipeline_scheduler.full_budget_for_swarm",
            return_value=None,
        ):
            with pytest.raises(_SwarmFallback, match="below min_workers"):
                seed_concepts_swarm("proj-1")

    def test_too_few_modules_raises_fallback(self, tmp_path):
        """Only 2 modules → below MIN_MODULES_FOR_SWARM (3) → fallback."""
        # Write a trace_modules.jsonl with 2 modules
        modules_file = tmp_path / "trace_modules.jsonl"
        import json
        with open(modules_file, "w") as f:
            f.write(json.dumps(_module("Module1", 6)) + "\n")
            f.write(json.dumps(_module("Module2", 7)) + "\n")

        llm, project, _ = self._setup_swarm_path()
        with patch(
            "codrag.services.project_helpers.require_project",
            return_value=project,
        ), patch(
            "codrag.core.project_registry.project_index_dir",
            return_value=tmp_path,
        ), patch(
            "codrag.core.concept_seeder._get_seeder_llm",
            return_value=llm,
        ), patch(
            "codrag.services.pipeline.scheduler.is_swarm_active_for_stage",
            return_value=True,
        ), patch(
            "codrag.services.pipeline.scheduler.pipeline_scheduler.full_budget_for_swarm",
            return_value=10,
        ):
            with pytest.raises(_SwarmFallback, match="only 2 modules"):
                seed_concepts_swarm("proj-1")


# ── Helper function tests ────────────────────────────────────────


class TestModuleHelpers:
    def test_build_module_summary_includes_name_and_file_count(self):
        mod = _module("Pipeline Orchestrator", 12)
        summary = _build_module_summary(mod)
        assert "Pipeline Orchestrator" in summary
        assert "12 files" in summary
        assert "subsystem" in summary  # part of summary text

    def test_build_module_context_caps_member_files(self):
        mod = _module("LargeModule", 50)
        ctx = _build_module_context(mod)
        assert ctx["file_count"] == 50
        assert len(ctx["member_files"]) == 25  # capped at 25

    def test_build_module_context_handles_missing_fields(self):
        mod = {"name": "Sparse"}
        ctx = _build_module_context(mod)
        assert ctx["name"] == "Sparse"
        assert ctx["file_count"] == 0
        assert ctx["member_files"] == []
        assert ctx["component_status"] == "unknown"


# ── Constants ────────────────────────────────────────────────────


def test_min_modules_for_swarm_matches_scheduler_floor():
    """MIN_MODULES_FOR_SWARM should match the scheduler's min_workers
    floor (3) so the two checks agree."""
    assert MIN_MODULES_FOR_SWARM == 3
