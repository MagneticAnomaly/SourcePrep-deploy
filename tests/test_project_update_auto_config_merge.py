"""Regression test for the 2026-06-08 cross-cutting review finding.

The dashboard's queue-X-button "Switch to Manual" action sends a
partial auto_config update ({deepEnrichment: "manual"}). The backend
must deep-merge into the existing auto_config rather than replacing
it whole — otherwise the user's fastSync / finalize settings silently
disappear.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    with server._project_build_lock:
        server._project_build_threads.clear()
        server._project_last_build_result.clear()
        server._project_last_build_error.clear()
    with server._project_trace_build_lock:
        server._project_trace_build_threads.clear()
    return TestClient(app)


def test_partial_auto_config_update_preserves_other_keys(
    client: TestClient, tmp_path: Path
):
    """Partial auto_config update must deep-merge, not replace.

    Regression: before the fix, PUT /projects/{id} with
    {config: {auto_config: {deepEnrichment: "manual"}}} would replace
    the entire auto_config dict, silently clobbering fastSync and
    finalize settings the user had previously configured.

    Reproduction path:
      1. POST /projects — creates project with default config (no auto_config).
      2. PUT /projects/{id} — user (or dashboard init) writes the full
         auto_config for the first time.
      3. PUT /projects/{id} — queue X-button fires with only
         {auto_config: {deepEnrichment: "manual"}}. Must preserve the
         keys set in step 2.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    # Step 1: Create a project (AddProjectRequest has no config param).
    create_resp = client.post(
        "/projects",
        json={"path": str(repo), "name": "test-project", "mode": "standalone"},
    )
    assert create_resp.status_code == 200, create_resp.text
    pid = create_resp.json()["data"]["project"]["id"]

    # Step 2: Set the initial full auto_config (simulates dashboard init).
    init_resp = client.put(
        f"/projects/{pid}",
        json={
            "config": {
                "trace": {"enabled": True},
                "auto_config": {
                    "fastSync": True,
                    "deepEnrichment": "auto",
                    "finalize": "auto",
                },
            }
        },
    )
    assert init_resp.status_code == 200, init_resp.text

    # Step 3: Simulate the queue X-button "Switch to Manual" action: only
    # deepEnrichment changes. The dashboard sends just this key.
    update_resp = client.put(
        f"/projects/{pid}",
        json={"config": {"auto_config": {"deepEnrichment": "manual"}}},
    )
    assert update_resp.status_code == 200, update_resp.text

    # Fetch the project to check the persisted state.
    get_resp = client.get(f"/projects/{pid}")
    assert get_resp.status_code == 200, get_resp.text
    result_cfg = get_resp.json()["data"]["project"]["config"]
    auto_cfg = result_cfg.get("auto_config", {})

    assert auto_cfg.get("fastSync") is True, (
        f"fastSync was clobbered by partial auto_config update. auto_config={auto_cfg}"
    )
    assert auto_cfg.get("finalize") == "auto", (
        f"finalize was clobbered by partial auto_config update. auto_config={auto_cfg}"
    )
    assert auto_cfg.get("deepEnrichment") == "manual", (
        f"deepEnrichment did not update. auto_config={auto_cfg}"
    )
    # trace is unchanged
    assert result_cfg.get("trace", {}).get("enabled") is True
