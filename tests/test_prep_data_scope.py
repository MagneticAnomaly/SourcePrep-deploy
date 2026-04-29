"""Tests for PrepDataAccess.search_code scope resolution via scope_resolver.

Verifies that search_code uses scope_resolver.resolve_mask (not the legacy
agent_scope_manager) to compute the file mask when a role is provided.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_fake_idx(results):
    """Build a MagicMock that mimics the CodeIndex behaviour used by search_code."""
    fake_idx = MagicMock()
    fake_idx.is_ready.return_value = True
    fake_idx.search.return_value = results
    return fake_idx


def _fake_code_index_cls(results):
    """Return a class-level mock for CodeIndex that yields fake_idx on init."""
    fake_idx = _make_fake_idx(results)
    fake_cls = MagicMock(return_value=fake_idx)
    return fake_cls


def test_search_code_uses_resolver_when_role_has_assigned_scope(
    tmp_settings, dummy_project
):
    """When a scope is assigned to a role, search_code must filter results
    through that scope's paths using scope_resolver.resolve_mask.

    The filter uses exact set membership (source_path in mask), so the scope
    paths must match the source_path values in the search results exactly.
    Here we store the exact file path in the scope to verify the filter works.
    """
    from prep.core.scope_store import scope_store

    # Store the exact file path so the `in mask` filter matches.
    scope_store.create(
        dummy_project.id,
        display_name="Copy",
        paths=["docs/guide.md"],
        assigned_to_role="copywriter",
    )

    from prep.agents.shared.prep_data import PrepDataAccess

    fake_result_in = MagicMock()
    fake_result_in.doc = {"source_path": "docs/guide.md"}
    fake_result_in.score = 0.9

    fake_result_out = MagicMock()
    fake_result_out.doc = {"source_path": "src/main.py"}
    fake_result_out.score = 0.8

    fake_cls = _fake_code_index_cls([fake_result_in, fake_result_out])

    with patch("prep.agents.shared.prep_data.CodeIndex", fake_cls):
        pd = PrepDataAccess(
            index_dir="/tmp/fake-index",
            project_id=dummy_project.id,
        )
        results = pd.search_code("guide", k=5, role="copywriter")

    # Only the result whose source_path is in the scope mask should be returned.
    paths = [r["doc"]["source_path"] for r in results]
    assert "docs/guide.md" in paths
    assert "src/main.py" not in paths


def test_search_code_returns_unfiltered_when_no_assignment(
    tmp_settings, dummy_project
):
    """When a role has no scope assignment, search_code must return an
    unfiltered result set (mask=None → fall through to normal search)."""
    from prep.agents.shared.prep_data import PrepDataAccess

    fake_result = MagicMock()
    fake_result.doc = {"source_path": "src/main.py"}
    fake_result.score = 0.9

    fake_cls = _fake_code_index_cls([fake_result])

    with patch("prep.agents.shared.prep_data.CodeIndex", fake_cls):
        pd = PrepDataAccess(
            index_dir="/tmp/fake-index",
            project_id=dummy_project.id,
        )
        results = pd.search_code("anything", k=5, role="nobody")

    # No mask applied — the result from the unfiltered search passes through.
    paths = [r["doc"]["source_path"] for r in results]
    assert "src/main.py" in paths


def test_search_code_calls_resolve_mask_not_agent_scope_manager(
    tmp_settings, dummy_project
):
    """Verify that scope_resolver.resolve_mask is invoked — not the legacy
    agent_scope_manager.  We capture calls to resolve_mask and confirm the
    right arguments are passed."""
    from prep.agents.shared.prep_data import PrepDataAccess
    from prep.core.scope_resolver import MaskResolution

    fake_result = MagicMock()
    fake_result.doc = {"source_path": "src/a.py"}
    fake_result.score = 0.7

    fake_cls = _fake_code_index_cls([fake_result])

    captured: list = []

    def fake_resolve_mask(project_id, scope, role):
        captured.append({"project_id": project_id, "scope": scope, "role": role})
        return MaskResolution(mask=None, applied_scope="global")

    with (
        patch("prep.agents.shared.prep_data.CodeIndex", fake_cls),
        patch("prep.agents.shared.prep_data.resolve_mask", side_effect=fake_resolve_mask),
    ):
        pd = PrepDataAccess(
            index_dir="/tmp/fake-index",
            project_id=dummy_project.id,
        )
        pd.search_code("query", k=3, role="researcher")

    assert len(captured) == 1
    assert captured[0]["project_id"] == dummy_project.id
    assert captured[0]["scope"] is None
    assert captured[0]["role"] == "researcher"


def test_search_code_filters_by_directory_prefix(tmp_settings, dummy_project):
    """I1 regression: scopes contain directory prefixes (e.g. 'docs/').
    Exact-match 'in mask' returned zero results for any file inside a
    prefixed scope.  The fix uses path_matches_any_scope which handles
    prefix semantics."""
    from prep.core.scope_store import scope_store

    # Store a directory prefix — the typical real-world scope path.
    scope_store.create(
        dummy_project.id,
        display_name="Docs",
        paths=["docs/"],
        assigned_to_role="writer",
    )

    from prep.agents.shared.prep_data import PrepDataAccess

    fake_in = MagicMock()
    fake_in.doc = {"source_path": "docs/guide.md"}
    fake_in.score = 0.9

    fake_out = MagicMock()
    fake_out.doc = {"source_path": "src/foo.py"}
    fake_out.score = 0.8

    fake_cls = _fake_code_index_cls([fake_in, fake_out])

    with patch("prep.agents.shared.prep_data.CodeIndex", fake_cls):
        pd = PrepDataAccess(index_dir="/tmp/fake-index", project_id=dummy_project.id)
        results = pd.search_code("guide", k=5, role="writer")

    paths = [r["doc"]["source_path"] for r in results]
    assert "docs/guide.md" in paths, (
        "File inside scope directory must match via prefix"
    )
    assert "src/foo.py" not in paths, (
        "File outside scope directory must be filtered out"
    )
