"""Regression: rename-era routing bugs

Two route-ordering regressions were introduced during the
CoDRAG → RunPrep → SourcePrep rebrand:

1. The generic ``GET /settings/{key}`` catch-all was registered BEFORE
   specific routes (``/settings/advanced-config``, ``/settings/admin-policy``,
   ``/settings/pipeline-config``, ``/settings/llm-concurrency-guidelines``,
   ``/settings/batch-estimate``). FastAPI matches in registration order, so
   every specific route was shadowed and returned
   ``404 SETTING_NOT_FOUND`` instead of its real payload.

2. The projects/telemetry router was declared with path
   ``/{project_id}/token-usage`` instead of ``/projects/{project_id}/token-usage``.
   The composite projects_router mounts at root without a prefix, so the UI's
   ``GET /projects/{id}/token-usage`` poll 404'd every few seconds.

This test locks in both fixes so a future refactor can't silently
reintroduce the shadowing.
"""
from __future__ import annotations

import pathlib
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    from prep.services.settings_store import settings
    tmp = pathlib.Path(tempfile.mkdtemp()) / "test_settings.db"
    settings.init(tmp)
    from prep.server import app
    return TestClient(app)


@pytest.mark.parametrize("path", [
    "/settings/admin-policy",
    "/settings/advanced-config",
    "/settings/pipeline-config",
    "/settings/llm-concurrency-guidelines",
    "/settings/batch-estimate",
])
def test_specific_settings_routes_not_shadowed_by_catchall(
    client: TestClient, path: str,
) -> None:
    """Specific /settings/<name> routes must return 200 + their real
    payload, not 404 SETTING_NOT_FOUND from the /settings/{key} catch-all."""
    r = client.get(path)
    body = r.json()
    assert r.status_code == 200, (
        f"{path} returned {r.status_code}, body={body}. "
        "Likely shadowed by GET /settings/{key} catch-all."
    )
    assert isinstance(body, dict) and body.get("success") is True, (
        f"{path} returned non-envelope or failure body: {body}"
    )
    # The catch-all would return error.code='SETTING_NOT_FOUND' on 404.
    # With success=True, that path cannot have been hit.


def test_settings_catchall_still_works_for_unknown_keys(client: TestClient) -> None:
    """GET /settings/<random-key> should still route to the catch-all
    and return a 404 envelope."""
    r = client.get("/settings/random-unknown-key-xyz")
    assert r.status_code == 404
    body = r.json()
    assert body.get("success") is False
    assert body.get("error", {}).get("code") == "SETTING_NOT_FOUND"


def test_token_usage_route_has_projects_prefix(client: TestClient) -> None:
    """GET /projects/{id}/token-usage must be a real route (not 404 via
    FastAPI's default 'Not Found' for unmatched paths). The handler will
    404 with PROJECT_NOT_FOUND for a bogus project id — that's the
    envelope-shaped NotFound, which is what we want to lock in."""
    r = client.get("/projects/does-not-exist/token-usage")
    body = r.json()
    assert body.get("success") is False, (
        f"Route not wired correctly — got body {body}. The envelope-shaped "
        "error means the handler ran and rejected the bogus project. A raw "
        "{'detail':'Not Found'} would indicate the route itself is missing."
    )
    assert body.get("error", {}).get("code") == "PROJECT_NOT_FOUND"
