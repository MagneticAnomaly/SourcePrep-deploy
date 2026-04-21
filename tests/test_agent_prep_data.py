"""Tests for PrepDataAccess — the read-only Prep data facade.

All Prep internals are mocked so no index data is required on disk.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.agents.shared.prep_data import PrepDataAccess


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_opp_manager():
    mgr = MagicMock()
    mgr.get_opportunities.return_value = []
    mgr.refresh.return_value = []
    return mgr


@pytest.fixture()
def mock_atlas():
    atlas = MagicMock()
    doc = MagicMock()
    doc.content = "# Atlas content"
    atlas.load.return_value = doc
    return atlas


@pytest.fixture()
def mock_trace_index():
    ti = MagicMock()
    ti.exists.return_value = True
    ti.load.return_value = True
    ti.node_count.return_value = 5
    ti.get_impact_graph.return_value = {
        "target": {"id": "file:src/foo.py"},
        "dependents": [{"name": "bar", "distance": 1}],
        "total_dependents": 1,
    }
    return ti


@pytest.fixture()
def mock_obs_store():
    store = MagicMock()
    store.save.return_value = "obs-uuid-1234"
    store.get_for_query.return_value = []
    return store


def _build_data_access(
    tmp_path: Path,
    mock_opp_manager: MagicMock,
    mock_atlas: MagicMock,
    mock_trace_index: MagicMock,
    mock_obs_store: MagicMock,
    project_id: str = "test-proj",
) -> PrepDataAccess:
    """Helper: patch all internals and return a PrepDataAccess instance.

    Because PrepDataAccess uses lazy imports inside __init__, we patch at
    the source module level so the constructors return our mocks.
    """
    index_dir = tmp_path / "index"
    index_dir.mkdir()

    with (
        patch(
            "prep.core.audit.opportunity_manager.OpportunityManager",
            return_value=mock_opp_manager,
        ),
        patch(
            "prep.core.atlas.generator.CodebaseAtlas",
            return_value=mock_atlas,
        ),
        patch(
            "prep.core.trace.index.TraceIndex",
            return_value=mock_trace_index,
        ),
        patch(
            "prep.services.observation_store.observation_store",
            mock_obs_store,
        ),
    ):
        da = PrepDataAccess(
            index_dir=index_dir,
            project_root=tmp_path,
            project_id=project_id,
        )
    # Explicitly wire mocks so tests don't depend on patch internals
    da._opp_manager = mock_opp_manager
    da._atlas = mock_atlas
    da._trace_index = mock_trace_index
    da._observation_store = mock_obs_store
    return da


@pytest.fixture()
def data_access(tmp_path, mock_opp_manager, mock_atlas, mock_trace_index, mock_obs_store):
    return _build_data_access(
        tmp_path, mock_opp_manager, mock_atlas, mock_trace_index, mock_obs_store
    )


# ── TestGetAuditFindings ──────────────────────────────────────────────────────


class TestGetAuditFindings:
    def test_returns_list(self, data_access, mock_opp_manager):
        result = data_access.get_audit_findings()
        assert isinstance(result, list)
        mock_opp_manager.get_opportunities.assert_called_once_with(include_dismissed=False)

    def test_passes_min_priority(self, data_access, mock_opp_manager):
        data_access.get_audit_findings(min_priority="P1")
        mock_opp_manager.get_opportunities.assert_called_once_with(
            include_dismissed=False, min_priority="P1"
        )

    def test_passes_categories(self, data_access, mock_opp_manager):
        data_access.get_audit_findings(categories=["architecture"])
        mock_opp_manager.get_opportunities.assert_called_once_with(
            include_dismissed=False, categories=["architecture"]
        )

    def test_passes_both_filters(self, data_access, mock_opp_manager):
        data_access.get_audit_findings(min_priority="P0", categories=["quality"])
        mock_opp_manager.get_opportunities.assert_called_once_with(
            include_dismissed=False, min_priority="P0", categories=["quality"]
        )

    def test_returns_items_from_manager(self, data_access, mock_opp_manager):
        fake_item = MagicMock()
        mock_opp_manager.get_opportunities.return_value = [fake_item]
        result = data_access.get_audit_findings()
        assert result == [fake_item]

    def test_refresh_returns_list(self, data_access, mock_opp_manager):
        result = data_access.refresh_audit()
        assert isinstance(result, list)
        mock_opp_manager.refresh.assert_called_once()

    def test_refresh_passes_project_root(self, data_access, mock_opp_manager, tmp_path):
        data_access.refresh_audit()
        call_kwargs = mock_opp_manager.refresh.call_args[1]
        assert "project_root" in call_kwargs

    def test_refresh_passes_categories(self, data_access, mock_opp_manager):
        data_access.refresh_audit(categories=["dependencies"])
        call_kwargs = mock_opp_manager.refresh.call_args[1]
        assert call_kwargs.get("categories") == ["dependencies"]


# ── TestGetAtlas ──────────────────────────────────────────────────────────────


class TestGetAtlas:
    def test_returns_content_string(self, data_access, mock_atlas):
        result = data_access.get_atlas()
        assert result == "# Atlas content"
        mock_atlas.load.assert_called_once()

    def test_returns_empty_when_no_atlas(self, data_access, mock_atlas):
        mock_atlas.load.return_value = None
        result = data_access.get_atlas()
        assert result == ""

    def test_returns_empty_when_content_none(self, data_access, mock_atlas):
        doc = MagicMock()
        doc.content = None
        mock_atlas.load.return_value = doc
        result = data_access.get_atlas()
        assert result == ""

    def test_returns_exact_content(self, data_access, mock_atlas):
        doc = MagicMock()
        doc.content = "## Modules\n- core\n- services\n"
        mock_atlas.load.return_value = doc
        result = data_access.get_atlas()
        assert result == "## Modules\n- core\n- services\n"


# ── TestGetImpactRadius ───────────────────────────────────────────────────────


class TestGetImpactRadius:
    def test_delegates_to_trace_index(self, data_access, mock_trace_index):
        result = data_access.get_impact_radius("src/foo.py")
        mock_trace_index.get_impact_graph.assert_called_once_with(
            "file:src/foo.py", max_hops=2, max_nodes=30
        )
        assert result["dependents"][0]["name"] == "bar"

    def test_passes_custom_hops_and_nodes(self, data_access, mock_trace_index):
        data_access.get_impact_radius("src/foo.py", max_hops=3, max_nodes=10)
        mock_trace_index.get_impact_graph.assert_called_once_with(
            "file:src/foo.py", max_hops=3, max_nodes=10
        )

    def test_returns_empty_when_no_trace(self, tmp_path, mock_opp_manager, mock_atlas, mock_obs_store):
        """When trace index is unavailable, returns minimal safe dict."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        no_trace = MagicMock()
        no_trace.exists.return_value = False
        no_trace.load.return_value = False
        no_trace.node_count.return_value = 0

        with (
            patch(
                "prep.core.audit.opportunity_manager.OpportunityManager",
                return_value=mock_opp_manager,
            ),
            patch(
                "prep.core.atlas.generator.CodebaseAtlas",
                return_value=mock_atlas,
            ),
            patch(
                "prep.core.trace.index.TraceIndex",
                return_value=no_trace,
            ),
            patch(
                "prep.services.observation_store.observation_store",
                mock_obs_store,
            ),
        ):
            da = PrepDataAccess(index_dir=index_dir, project_root=tmp_path)
        da._trace_index = None  # ensure it's really None

        result = da.get_impact_radius("src/something.py")
        assert result == {"target": None, "dependents": []}

    def test_file_path_prefixed(self, data_access, mock_trace_index):
        data_access.get_impact_radius("path/to/module.py")
        args, _ = mock_trace_index.get_impact_graph.call_args
        assert args[0] == "file:path/to/module.py"


# ── TestSaveObservation ───────────────────────────────────────────────────────


class TestSaveObservation:
    def test_delegates_to_observation_store(self, data_access, mock_obs_store):
        obs_id = data_access.save_observation("Found a bug in auth")
        mock_obs_store.save.assert_called_once_with(
            "test-proj",
            "Found a bug in auth",
            file_path=None,
            category="note",
        )
        assert obs_id == "obs-uuid-1234"

    def test_passes_file_path(self, data_access, mock_obs_store):
        data_access.save_observation("JWT tokens", file_path="src/auth.py")
        call_kwargs = mock_obs_store.save.call_args[1]
        assert call_kwargs["file_path"] == "src/auth.py"

    def test_passes_category(self, data_access, mock_obs_store):
        data_access.save_observation("Design choice", category="decision")
        call_kwargs = mock_obs_store.save.call_args[1]
        assert call_kwargs["category"] == "decision"

    def test_returns_obs_id(self, data_access, mock_obs_store):
        mock_obs_store.save.return_value = "my-custom-id"
        result = data_access.save_observation("whatever")
        assert result == "my-custom-id"

    def test_get_observations_delegates(self, data_access, mock_obs_store):
        fake_obs = MagicMock()
        mock_obs_store.get_for_query.return_value = [fake_obs]
        result = data_access.get_observations("authentication", limit=3)
        mock_obs_store.get_for_query.assert_called_once_with(
            "test-proj", "authentication", limit=3
        )
        assert result == [fake_obs]

    def test_get_observations_default_limit(self, data_access, mock_obs_store):
        data_access.get_observations("query")
        _, call_kwargs = mock_obs_store.get_for_query.call_args
        assert call_kwargs.get("limit") == 5


# ── TestGetModuleStructure ───────────────────────────────────────────────────


class TestGetModuleStructure:
    def test_returns_empty_when_no_file(self, data_access):
        result = data_access.get_module_structure()
        assert result == []

    def test_reads_jsonl_file(self, data_access):
        import json

        modules_path = data_access._index_dir / "trace_modules.jsonl"
        modules_path.write_text(
            json.dumps({"name": "Core", "file_count": 10, "domain_tags": ["api"]})
            + "\n"
            + json.dumps({"name": "UI", "file_count": 5, "domain_tags": ["frontend"]})
            + "\n"
        )
        result = data_access.get_module_structure()
        assert len(result) == 2
        assert result[0]["name"] == "Core"
        assert result[1]["domain_tags"] == ["frontend"]


# ── TestSearchCode ───────────────────────────────────────────────────────────


class TestSearchCode:
    def test_returns_empty_when_no_index(self, data_access):
        result = data_access.search_code("authentication")
        assert result == []


# ── TestGetRoleVector ────────────────────────────────────────────────────────


class TestGetRoleVector:
    def test_returns_role_vector_for_known_role(self, data_access):
        result = data_access.get_role_vector("ceo")
        # resolve_role("ceo") should return a built-in RoleVector
        assert result is not None
        assert result.role_id == "ceo"

    def test_returns_none_for_invalid(self, data_access):
        # Even garbage strings should resolve (fallback to engineering)
        # so this should still return something
        result = data_access.get_role_vector("xyzzy_nonexistent")
        assert result is not None  # resolve_role has a fallback


# ── TestGetAtlasWithRole ─────────────────────────────────────────────────────


class TestGetAtlasWithRole:
    def test_returns_full_atlas_without_role(self, data_access):
        mock_doc = MagicMock()
        mock_doc.content = "# Full Atlas Content"
        data_access._atlas = MagicMock()
        data_access._atlas.load.return_value = mock_doc
        result = data_access.get_atlas()
        assert result == "# Full Atlas Content"

    def test_returns_full_atlas_when_projection_fails(self, data_access):
        mock_doc = MagicMock()
        mock_doc.content = "# Full Atlas"
        data_access._atlas = MagicMock()
        data_access._atlas.load.return_value = mock_doc
        # Role projection may fail if no enrichment data exists
        result = data_access.get_atlas(role="ceo")
        # Should return something (either projected or full fallback)
        assert isinstance(result, str)
        assert len(result) > 0
