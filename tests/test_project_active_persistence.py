"""Regression test: active flag survives partial config updates.

Bug symptom: user toggles a project inactive in the dashboard, switches
projects, comes back, edits a setting that triggers handleSaveConfig (or
any other full-config snapshot writer), and the project flips back to
active. After a daemon restart the toggle appears ON again and the
project is being processed despite "being inactive".

Two independent fixes prevent this:

1. Frontend (handled in useProjectManager.ts / useTraceSystem.ts /
   useDeepAnalysis.ts): only the dedicated toggle handler writes
   `active`; every other handler now sends a partial config diff.

2. Backend (this file's contract): a PUT /projects/{id} that does not
   include `active` in `req.config` MUST NOT change the persisted
   value. The existing `_merge` already preserves keys absent from the
   incoming config, so this test pins that behavior so future refactors
   cannot regress it (e.g., by switching to a "replace" semantics).
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


def _add_project(client: TestClient, repo_root: Path) -> str:
    res = client.post(
        "/projects",
        json={"path": str(repo_root), "name": "p", "mode": "embedded"},
    )
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def _get_active(client: TestClient, pid: str) -> bool:
    res = client.get(f"/projects/{pid}")
    assert res.status_code == 200
    cfg = res.json()["data"]["project"]["config"] or {}
    return cfg.get("active", True)


def test_partial_config_update_preserves_active_flag(client, tmp_path):
    pid = _add_project(client, tmp_path)

    # Toggle off via the dedicated path (mimics handleToggleActive).
    res = client.put(f"/projects/{pid}", json={"config": {"active": False}})
    assert res.status_code == 200
    assert _get_active(client, pid) is False

    # Now simulate any other handler (e.g. trace.enabled, auto_config,
    # deep_analysis_schedule) sending a partial config that does not
    # include `active`. The persisted active=false MUST survive.
    for partial in (
        {"trace": {"enabled": True}},
        {"auto_config": {"fastSync": True, "deepEnrichment": "auto"}},
        {"deep_analysis_schedule": {"mode": "weekly"}},
        {"include_globs": ["**/*.py"]},
    ):
        res = client.put(f"/projects/{pid}", json={"config": partial})
        assert res.status_code == 200, res.text
        assert _get_active(client, pid) is False, (
            f"active flag was clobbered by partial update {partial!r} — "
            "this is the toggle re-promotion bug"
        )


def test_explicit_active_true_in_request_does_reactivate(client, tmp_path):
    """Sanity check: the dedicated toggle path still works."""
    pid = _add_project(client, tmp_path)

    client.put(f"/projects/{pid}", json={"config": {"active": False}})
    assert _get_active(client, pid) is False

    res = client.put(f"/projects/{pid}", json={"config": {"active": True}})
    assert res.status_code == 200
    assert _get_active(client, pid) is True
