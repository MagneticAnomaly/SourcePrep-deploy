"""
Tests for Phase 120: scope_resolver integration in the /search endpoint.

Contracts verified:
1. applied_scope field appears in response.
2. Mask-filtering removes results outside the named scope.
3. Unknown scope sets scope_warning and falls back to global (no filtering).
4. Role without assigned_to_role link returns global (no auto-mask — Phase 67 removed).
5. Role WITH assigned_to_role on a scope uses that scope's mask.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeResult:
    """Minimal search-result object returned by a fake LayeredIndex."""

    def __init__(self, source_path: str, content: str = "lorem ipsum hero foo") -> None:
        self.score = 0.9
        self.doc = {
            "id": f"chunk:{source_path}",
            "source_path": source_path,
            "content": content,
            "span": {"start_line": 1, "end_line": 1},
        }


class _FakeLayeredIndex:
    """Minimal fake for LayeredIndex — only the search path is exercised."""

    def __init__(self, paths: list[str]) -> None:
        self._paths = paths
        self._results = [_FakeResult(p) for p in paths]
        self._documents = [r.doc for r in self._results]

    def is_loaded(self) -> bool:
        return True

    def search(self, query: str, **kwargs) -> list[_FakeResult]:  # noqa: ARG002
        return list(self._results)

    def get_context(self, *args, **kwargs) -> str:  # noqa: ARG002
        return "ctx"

    def get_context_with_trace_expansion(self, *args, **kwargs) -> dict:  # noqa: ARG002
        return {"context": "ctx", "chunks": [], "trace_expanded": False, "trace_nodes_added": 0}


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def indexed_corpus(monkeypatch):
    """Return a callable setup(project_id, paths=[...]) that injects a fake
    LayeredIndex so /search returns exactly one chunk per registered path.
    """

    fake: _FakeLayeredIndex | None = None

    def setup(project_id: str, paths: list[str]) -> None:  # noqa: ARG001
        nonlocal fake
        fake = _FakeLayeredIndex(paths)

        import prep.server as srv_mod

        monkeypatch.setattr(srv_mod, "_get_project_layered_index", lambda _proj: fake)

    return setup


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_applied_scope_always_present(client: TestClient, project, indexed_corpus) -> None:
    """applied_scope appears in every /search response, even with no scope param."""
    indexed_corpus(project.id, paths=["src/foo.py"])
    r = client.post(
        f"/projects/{project.id}/search",
        json={"query": "foo"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert "applied_scope" in body
    assert body["applied_scope"] == "global"


def test_search_with_scope_filters_results(client: TestClient, project, indexed_corpus) -> None:
    """Results outside the named scope are filtered out; applied_scope matches the scope id."""
    indexed_corpus(project.id, paths=["src/foo.py", "websites/marketing/hero.md"])
    # Create a named scope covering only websites/marketing/
    client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "Marketing", "paths": ["websites/marketing/"]},
    )

    r = client.post(
        f"/projects/{project.id}/search",
        json={"query": "hero", "scope": "marketing"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["applied_scope"] == "marketing"
    paths = [hit["source_path"] for hit in body["results"]]
    assert all(p.startswith("websites/marketing/") for p in paths), (
        f"Expected only websites/marketing/ paths, got: {paths}"
    )
    assert len(paths) == 1


def test_unknown_scope_falls_back_to_global_with_warning(
    client: TestClient, project, indexed_corpus
) -> None:
    """An unknown scope triggers a scope_warning and returns unfiltered results."""
    indexed_corpus(project.id, paths=["src/foo.py"])
    r = client.post(
        f"/projects/{project.id}/search",
        json={"query": "foo", "scope": "marketin"},  # typo — scope doesn't exist
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["applied_scope"] == "global"
    assert "marketin" in body.get("scope_warning", ""), (
        f"Expected scope_warning to mention 'marketin', got: {body.get('scope_warning')}"
    )
    # Results should NOT be filtered — all files visible
    paths = [hit["source_path"] for hit in body["results"]]
    assert "src/foo.py" in paths


def test_role_no_longer_auto_applies_mask(
    client: TestClient, project, indexed_corpus
) -> None:
    """Phase 67 auto-mask is gone: role without assigned_to_role returns global, no filtering."""
    indexed_corpus(project.id, paths=["src/foo.py", "websites/marketing/hero.md"])
    # No scope created, no assigned_to_role
    r = client.post(
        f"/projects/{project.id}/search",
        json={"query": "foo", "role": "copywriter"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["applied_scope"] == "global"
    assert body.get("applied_role") == "copywriter"
    paths = [hit["source_path"] for hit in body["results"]]
    # Both files should be visible — no filtering
    assert len(paths) >= 2


def test_role_with_assigned_scope_uses_it(
    client: TestClient, project, indexed_corpus
) -> None:
    """When a scope has assigned_to_role matching req.role, that scope's mask is applied."""
    indexed_corpus(project.id, paths=["src/foo.py", "websites/marketing/hero.md"])
    client.post(
        f"/projects/{project.id}/scopes",
        json={
            "display_name": "Copy",
            "paths": ["websites/marketing/"],
            "assigned_to_role": "copywriter",
        },
    )

    r = client.post(
        f"/projects/{project.id}/search",
        json={"query": "hero", "role": "copywriter"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["applied_scope"] == "copy"
    paths = [hit["source_path"] for hit in body["results"]]
    assert all(p.startswith("websites/marketing/") for p in paths), (
        f"Expected only websites/marketing/ paths, got: {paths}"
    )
